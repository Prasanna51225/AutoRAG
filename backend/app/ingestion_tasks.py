# backend/app/ingestion_tasks.py
import os
from typing import Dict, Any
from celery import shared_task
import asyncio
from app.celery_app import celery_app
from app.chunking import get_chunker
from app.embeddings import get_embedder
from app.sparse import get_sparse_vectorizer
from app.qdrant_client import get_qdrant_manager
from app.utils import get_logger, parse_document, get_redis_client

logger = get_logger(__name__)

@shared_task(bind=True, name="ingest_document")
def ingest_document(self, file_path: str, metadata: Dict[str, Any] = None):
    """
    Asynchronously ingest a document: parse, chunk, embed, store in Qdrant.
    """
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100})
    
    try:
        # Step 1: Parse document (PDF or text)
        logger.info(f"Parsing document: {file_path}")
        doc_text = parse_document(file_path)
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "step": "parsing"})
        
        # Step 2: Chunk text
        chunker = get_chunker()
        chunks = chunker.chunk_text(doc_text, metadata or {})
        total_chunks = len(chunks)
        logger.info(f"Created {total_chunks} chunks")
        self.update_state(state="PROGRESS", meta={"current": 20, "total": 100, "step": "chunking", "chunks": total_chunks})
        
        # Step 3: Generate dense embeddings
        embedder = get_embedder()
        # Set Redis client
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, ttl=3600)
        
        # Run async embedding in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        chunk_texts = [c["text"] for c in chunks]
        dense_embeddings = loop.run_until_complete(embedder.embed_batch(chunk_texts))
        self.update_state(state="PROGRESS", meta={"current": 50, "total": 100, "step": "dense_embedding"})
        
        # Step 4: Generate sparse vectors (BM25)
        sparse_vectorizer = get_sparse_vectorizer()
        # Update IDF with the new document chunks (for better future retrieval)
        sparse_vectorizer.update_idf(chunk_texts)
        sparse_vectors = [sparse_vectorizer.vectorize(text) for text in chunk_texts]
        self.update_state(state="PROGRESS", meta={"current": 70, "total": 100, "step": "sparse_embedding"})
        
        # Step 5: Store in Qdrant
        qdrant_manager = get_qdrant_manager()
        # Ensure collection exists (with correct dense dimension)
        dense_dim = embedder.dimension
        loop.run_until_complete(qdrant_manager.ensure_collection(dense_dim))
        loop.run_until_complete(qdrant_manager.upsert_chunks(chunks, dense_embeddings, sparse_vectors))
        self.update_state(state="PROGRESS", meta={"current": 90, "total": 100, "step": "storing"})
        
        loop.close()
        
        # Cleanup temporary file – only after success
        if os.path.exists(file_path):
            os.unlink(file_path)
        
        result = {
            "status": "success",
            "file_path": file_path,
            "metadata": metadata or {},
            "chunks_processed": total_chunks,
            "message": f"Successfully ingested document with {total_chunks} chunks."
        }
        return result
    
    except Exception as e:
        logger.exception(f"Ingestion failed for {file_path}")
        # DO NOT delete the file here – it may be needed for retry
        # The file will be cleaned up by the retry mechanism or eventually by the system
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(name="check_health")
def health_check():
    """Celery health check."""
    return {"status": "ok", "message": "Celery worker is alive"}