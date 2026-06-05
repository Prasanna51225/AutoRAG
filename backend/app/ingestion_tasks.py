# backend/app/ingestion_tasks.py
import time
from celery import shared_task
from app.celery_app import celery_app

@shared_task(bind=True, name="ingest_document")
def ingest_document(self, file_path: str, metadata: dict = None):
    """
    Phase 1 dummy task – will be replaced with real ingestion in Phase 2.
    Simulates processing and stores a fake result.
    """
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100})
    
    # Simulate chunking + embedding (Phase 2 replaces this)
    for i in range(1, 101):
        time.sleep(0.02)  # simulate work
        self.update_state(state="PROGRESS", meta={"current": i, "total": 100})
    
    result = {
        "status": "success",
        "file_path": file_path,
        "metadata": metadata or {},
        "chunks_processed": 42,  # placeholder
        "message": f"Dummy ingestion completed for {file_path} (Phase 1)"
    }
    return result

@shared_task(name="check_health")
def health_check():
    """Simple task to verify Celery is working."""
    return {"status": "ok", "timestamp": time.time()}