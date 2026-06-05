# backend/app/celery_app.py
from celery import Celery
from app.config import settings

celery_app = Celery(
    "autoreag",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Auto-discover tasks from the 'ingestion_tasks' module
celery_app.autodiscover_tasks(["app.ingestion_tasks"], force=True)