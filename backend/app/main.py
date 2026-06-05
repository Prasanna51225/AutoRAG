# backend/app/main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import os
import tempfile
from contextlib import asynccontextmanager

from app.config import settings
from app.celery_app import celery_app
from app.ingestion_tasks import ingest_document

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

from app.qdrant_client import get_qdrant_manager
from app.embeddings import get_embedder
from app.utils import get_redis_client

# ========== Metrics ==========
REQUESTS = Counter("autoreq_requests_total", "Total HTTP requests", ["method", "endpoint"])
REQUEST_DURATION = Histogram("autoreq_request_duration_seconds", "Request latency", ["endpoint"])

# ========== Lifespan ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify connections
    print("🚀 AutoRAG backend starting...")
    # Check Redis connection (will do properly in Phase 2)
    print("✅ Services ready ")
    yield
    # Shutdown
    print("🛑 AutoRAG shutting down...")
    try:
        embedder = get_embedder()
        # Redis client will be set later, but we can test
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, settings.embedding_cache_ttl)
        manager = get_qdrant_manager()
        await manager.ensure_collection(embedder.dimension)
        print("✅ Embedder and Qdrant collection ready")
    except Exception as e:
        print(f"⚠️ Error during startup: {e}")

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
    
    # Check API
    status["services"]["api"] = "running"
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        status["services"]["redis"] = "connected"
    except Exception as e:
        status["services"]["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Check Qdrant
    try:
        manager = get_qdrant_manager()
        manager.client.get_collections()
        status["services"]["qdrant"] = "connected"
    except Exception as e:
        status["services"]["qdrant"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # Check Ollama (optional, just ping)
    try:
        import httpx
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        if resp.status_code == 200:
            status["services"]["ollama"] = "connected"
        else:
            status["services"]["ollama"] = f"unexpected status {resp.status_code}"
    except Exception as e:
        status["services"]["ollama"] = f"error: {str(e)}"
    
    return status

# ========== Ingestion Endpoints ==========
class IngestResponse(BaseModel):
    task_id: str
    status: str
    message: str

@app.post("/ingest", response_model=IngestResponse)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    REQUESTS.labels(method="POST", endpoint="/ingest").inc()
    
    # Generate unique filename to avoid collisions
    original_filename = file.filename
    safe_name = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = f"/uploads/{safe_name}"
    
    # Save file to shared volume
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Parse metadata if provided
    meta_dict = {"original_filename": original_filename}
    if metadata:
        import json
        try:
            meta_dict.update(json.loads(metadata))
        except:
            meta_dict["raw_metadata"] = metadata
    
    # Queue Celery task
    task = ingest_document.delay(file_path, meta_dict)
    
    return IngestResponse(
        task_id=task.id,
        status="queued",
        message=f"Document {original_filename} queued for ingestion."
    )

@app.get("/ingest/{task_id}")
async def get_ingestion_status(task_id: str):
    """Check the status of an ingestion task."""
    task = celery_app.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {"status": "pending", "progress": 0}
    elif task.state == "PROGRESS":
        response = {"status": "processing", "progress": task.info.get("current", 0)}
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

# ========== Query Stub (Phase 1) ==========
class QueryRequest(BaseModel):
    query: str
    stream: bool = False

class QueryResponse(BaseModel):
    answer: str
    metadata: Dict[str, Any]

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Phase 1 stub – will be replaced with full reflexion loop in Phase 4.
    """
    REQUESTS.labels(method="POST", endpoint="/query").inc()
    # Dummy response
    return QueryResponse(
        answer="This is a Phase 1 stub. The reflexion loop is not yet implemented.",
        metadata={"phase": 1, "query": request.query}
    )

# ========== Metrics Endpoint ==========
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ========== Root Info ==========
@app.get("/")
async def root():
    return {
        "service": "AutoRAG",
        "phase": 1,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }