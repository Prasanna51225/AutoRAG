# backend/app/ingestion_tasks.py
import asyncio
from typing import Dict, Any
from celery import shared_task
from app.celery_app import celery_app
from app.chunking import get_chunker
from app.embeddings import get_embedder
from app.sparse import get_sparse_vectorizer
from app.qdrant_client import get_qdrant_manager
from app.utils import get_logger, get_redis_client

logger = get_logger(__name__)

@shared_task(bind=True, name="ingest_document")
def ingest_document(self, file_content: str, metadata: Dict[str, Any] = None):
    """
    Asynchronously ingest a document from its content string.
    """
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100, "step": "starting"})
    
    try:
        # Step 1: Use content directly (already text)
        doc_text = file_content
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "step": "parsed"})
        
        # Step 2: Chunk text
        chunker = get_chunker()
        chunks = chunker.chunk_text(doc_text, metadata or {})
        total_chunks = len(chunks)
        self.update_state(state="PROGRESS", meta={"current": 20, "total": 100, "step": "chunking", "chunks": total_chunks})
        
        # Step 3: Generate dense embeddings
        embedder = get_embedder()
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, 3600)
        
        # Run async embedding in a new event loop (because Celery is synchronous)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        chunk_texts = [c["text"] for c in chunks]
        dense_embeddings = loop.run_until_complete(embedder.embed_batch(chunk_texts))
        self.update_state(state="PROGRESS", meta={"current": 50, "total": 100, "step": "dense_embedding"})
        
        # Step 4: Generate sparse vectors (BM25)
        sparse_vectorizer = get_sparse_vectorizer()
        # Update IDF with the new document chunks
        sparse_vectorizer.update_idf(chunk_texts)
        sparse_vectors = [sparse_vectorizer.vectorize(text) for text in chunk_texts]
        self.update_state(state="PROGRESS", meta={"current": 70, "total": 100, "step": "sparse_embedding"})
        
        # Step 5: Store in Qdrant
        qdrant_manager = get_qdrant_manager()
        dense_dim = embedder.dimension
        loop.run_until_complete(qdrant_manager.ensure_collection(dense_dim))
        loop.run_until_complete(qdrant_manager.upsert_chunks(chunks, dense_embeddings, sparse_vectors))
        loop.close()
        
        result = {
            "status": "success",
            "metadata": metadata or {},
            "chunks_processed": total_chunks,
            "message": f"Successfully ingested document with {total_chunks} chunks."
        }
        return result
    
    except Exception as e:
        logger.exception(f"Ingestion failed: {str(e)}")
        # Retry after 60 seconds, up to 3 times
        raise self.retry(exc=e, countdown=60, max_retries=3)

@shared_task(name="check_health")
def health_check():
    return {"status": "ok", "message": "Celery worker is alive"}