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

# ========== Metrics ==========
REQUESTS = Counter("autoreq_requests_total", "Total HTTP requests", ["method", "endpoint"])
REQUEST_DURATION = Histogram("autoreq_request_duration_seconds", "Request latency", ["endpoint"])

# ========== Lifespan ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify connections
    print("🚀 AutoRAG backend starting...")
    # Check Redis connection (will do properly in Phase 2)
    print("✅ Services ready (Phase 1 dummy)")
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
    """Return health status of all critical dependencies."""
    # Phase 1: just return basic info (will add Qdrant/Redis checks later)
    return {
        "status": "healthy",
        "services": {
            "api": "running",
            "celery": "configured",
            "qdrant": "not_checked_phase1",
            "redis": "not_checked_phase1",
            "ollama": "not_checked_phase1",
        }
    }

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
    """
    Upload a document (PDF, TXT, etc.) for asynchronous ingestion.
    Returns a task_id to poll for completion.
    """
    REQUESTS.labels(method="POST", endpoint="/ingest").inc()
    
    # Save uploaded file to a temporary location
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    # Parse metadata if provided
    meta_dict = {}
    if metadata:
        import json
        try:
            meta_dict = json.loads(metadata)
        except:
            meta_dict = {"raw_metadata": metadata}
    
    # Queue Celery task
    task = ingest_document.delay(tmp_path, meta_dict)
    
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
        response = {"status": "processing", "progress": task.info.get("current", 0)}
    elif task.state == "SUCCESS":
        response = {"status": "completed", "result": task.result}
    elif task.state == "FAILURE":
        response = {"status": "failed", "error": str(task.info)}
    else:
        response = {"status": task.state}
    return JSONResponse(response)

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