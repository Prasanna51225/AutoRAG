# backend/app/main.py
import time
import json
import tempfile
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import httpx

from app.config import settings
from app.celery_app import celery_app
from app.ingestion_tasks import ingest_document
from app.qdrant_client import get_qdrant_manager
from app.embeddings import get_embedder
from app.retriever import get_retriever
from app.reranker import get_reranker
from app.utils import get_redis_client, get_logger

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logger = get_logger(__name__)

# ========== Metrics ==========
REQUESTS = Counter("autoreq_requests_total", "Total HTTP requests", ["method", "endpoint"])
REQUEST_DURATION = Histogram("autoreq_request_duration_seconds", "Request latency", ["endpoint"])

# ========== Request/Response Models ==========
class QueryRequest(BaseModel):
    query: str
    stream: bool = False

class QueryResponse(BaseModel):
    answer: str
    metadata: Dict[str, Any]

class IngestResponse(BaseModel):
    task_id: str
    status: str
    message: str

class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5

class RetrieveResponse(BaseModel):
    query: str
    chunks: List[Dict[str, Any]]
    retrieval_time_ms: float

# ========== Lifespan ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 AutoRAG backend starting...")
    try:
        # Preload embedder and ensure Qdrant collection
        embedder = get_embedder()
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, settings.embedding_cache_ttl)
        
        qdrant_manager = get_qdrant_manager()
        await qdrant_manager.ensure_collection(embedder.dimension)
        print("✅ Embedder and Qdrant collection ready")
        
        # Preload retriever and reranker
        retriever = get_retriever()
        retriever.set_redis(redis_client, settings.embedding_cache_ttl)
        reranker = get_reranker()
        print("✅ Retriever and reranker ready")
        
    except Exception as e:
        print(f"⚠️ Startup error: {e}")
    
    yield
    # Shutdown
    print("🛑 AutoRAG shutting down...")

app = FastAPI(
    title="AutoRAG API",
    description="Self‑improving RAG with reflexion loop and async ingestion",
    version="1.0.0",
    lifespan=lifespan,
)

# ========== Health Check ==========
@app.get("/health")
async def health_check():
    """Full health check with all dependencies."""
    status = {"status": "healthy", "services": {}}
    
    # API
    status["services"]["api"] = "running"
    
    # Redis
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        status["services"]["redis"] = "connected"
    except Exception as e:
        status["services"]["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Qdrant
    try:
        qdrant_manager = get_qdrant_manager()
        qdrant_manager.client.get_collections()
        status["services"]["qdrant"] = "connected"
    except Exception as e:
        status["services"]["qdrant"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Ollama
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                status["services"]["ollama"] = "connected"
            else:
                status["services"]["ollama"] = f"unexpected status {resp.status_code}"
                status["status"] = "degraded"
    except Exception as e:
        status["services"]["ollama"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Retriever / Reranker status
    try:
        retriever = get_retriever()
        reranker = get_reranker()
        status["services"]["retriever"] = "initialised"
        status["services"]["reranker"] = "initialised"
    except Exception as e:
        status["services"]["retriever_reranker"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    return status

# ========== Ingestion Endpoints ==========
@app.post("/ingest", response_model=IngestResponse)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    """
    Upload a document (TXT or PDF) for asynchronous ingestion.
    Returns a task_id to poll for completion.
    """
    REQUESTS.labels(method="POST", endpoint="/ingest").inc()
    
    # Read file content
    content = await file.read()
    
    # Try to decode as text (for TXT files)
    try:
        file_content = content.decode("utf-8", errors="replace")
    except Exception:
        # For PDF or binary, we would use a PDF parser, but for simplicity we assume TXT
        raise HTTPException(status_code=400, detail="Only text files are supported in this demo")
    
    # Parse metadata if provided
    meta_dict = {}
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except:
            meta_dict = {"raw_metadata": metadata}
    meta_dict["filename"] = file.filename
    meta_dict["content_type"] = file.content_type
    
    # Queue Celery task with content string instead of file path
    task = ingest_document.delay(file_content, meta_dict)
    
    return IngestResponse(
        task_id=task.id,
        status="queued",
        message=f"Document {file.filename} queued for ingestion."
    )

@app.get("/ingest/{task_id}")
async def get_ingestion_status(task_id: str):
    """Check the status of an ingestion task."""
    task = celery_app.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"status": "pending", "progress": 0}
    elif task.state == "PROGRESS":
        response = {"status": "processing", "progress": task.info.get("current", 0), "step": task.info.get("step", "working")}
    elif task.state == "SUCCESS":
        response = {"status": "completed", "result": task.result}
    elif task.state == "FAILURE":
        response = {"status": "failed", "error": str(task.info)}
    else:
        response = {"status": task.state}
    return JSONResponse(response)

@app.get("/collections")
async def list_collections():
    """List Qdrant collections (for debugging)."""
    manager = get_qdrant_manager()
    collections = manager.client.get_collections().collections
    return {"collections": [c.name for c in collections]}

# ========== Retrieval & Reranking Endpoint ==========
@app.post("/retrieve", response_model=RetrieveResponse)
async def test_retrieve(request: RetrieveRequest):
    """
    Test endpoint that performs hybrid search + reranking and returns chunks.
    """
    REQUESTS.labels(method="POST", endpoint="/retrieve").inc()
    start_time = time.time()
    
    retriever = get_retriever()
    reranker = get_reranker()
    
    # Retrieve top-k from retriever (using configured cutoff)
    retrieved = await retriever.retrieve(request.query, top_k=settings.reranker_cutoff)
    # Rerank and get final top_k
    final_chunks = await reranker.rerank(request.query, retrieved, top_k=request.top_k)
    
    elapsed_ms = (time.time() - start_time) * 1000
    return RetrieveResponse(
        query=request.query,
        chunks=final_chunks,
        retrieval_time_ms=round(elapsed_ms, 2)
    )

# ========== Query Stub (Phase 3) ==========
@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Phase 3 stub – will be replaced with full reflexion loop in Phase 4.
    """
    REQUESTS.labels(method="POST", endpoint="/query").inc()
    retriever = get_retriever()
    reranker = get_reranker()
    retrieved = await retriever.retrieve(request.query, top_k=settings.reranker_cutoff)
    final_chunks = await reranker.rerank(request.query, retrieved, top_k=3)
    
    answer = f"This is a Phase 3 stub. Retrieved {len(final_chunks)} relevant chunks."
    if final_chunks:
        answer += f" First chunk: {final_chunks[0]['text'][:100]}..."
    
    return QueryResponse(
        answer=answer,
        metadata={
            "phase": 3,
            "query": request.query,
            "chunks_retrieved": len(final_chunks),
        }
    )

# ========== Debug/Utility Endpoints ==========
@app.get("/test_embedding")
async def test_embedding(text: str):
    embedder = get_embedder()
    emb = await embedder.embed(text)
    return {"text": text[:50], "embedding_length": len(emb)}

# ========== Metrics ==========
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ========== Root Info ==========
@app.get("/")
async def root():
    return {
        "service": "AutoRAG",
        "phase": 3,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "retrieve": "/retrieve (POST)",
        "ingest": "/ingest (POST)"
    }