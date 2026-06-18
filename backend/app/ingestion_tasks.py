# backend/app/ingestion_tasks.py
import asyncio
import json
from typing import Dict, Any
from celery import shared_task
from app.celery_app import celery_app
from app.chunking import get_chunker
from app.embeddings import get_embedder
from app.sparse import get_sparse_vectorizer
from app.qdrant_client import get_qdrant_manager
# FIX: Removed import of entity_extractor (BERT NER – too slow, caused timeouts).
# Use only lightweight temporal extractor.
from app.temporal_extractor import extract_dates
from app.utils import get_logger, get_redis_client
from app.entity_extractor import extract_entities


logger = get_logger(__name__)

@shared_task(bind=True, name="ingest_document")
def ingest_document(self, file_content: str, metadata: Dict[str, Any] = None):
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100, "step": "starting"})

    # FIX: Each Celery task must create its own event loop. Never reuse one from the
    # parent process – it will be closed or in a bad state.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Step 1: chunk
        chunker = get_chunker()
        chunks = chunker.chunk_text(file_content, metadata or {})
        total_chunks = len(chunks)
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "step": "chunking"})

# Step 2: lightweight metadata extraction per chunk (dates + entities + numbers)
        for chunk in chunks:
            dates = extract_dates(chunk["text"])
            chunk["metadata"]["dates"] = dates

            extracted = extract_entities(chunk["text"])
            chunk["metadata"]["entities"] = extracted.get("entities", {})
            chunk["metadata"]["numerical"] = extracted.get("numerical", {})

        self.update_state(state="PROGRESS", meta={"current": 30, "total": 100, "step": "metadata_extracted"})

        # Step 3: dense embeddings
        embedder = get_embedder()
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, 3600)
        chunk_texts = [c["text"] for c in chunks]
        dense_embeddings = loop.run_until_complete(embedder.embed_batch(chunk_texts))
        self.update_state(state="PROGRESS", meta={"current": 60, "total": 100, "step": "dense_embedding"})

        # Step 4: sparse vectors
        sparse_vectorizer = get_sparse_vectorizer()
        sparse_vectorizer.update_idf(chunk_texts)
        sparse_vectors = [sparse_vectorizer.vectorize(text) for text in chunk_texts]
        self.update_state(state="PROGRESS", meta={"current": 80, "total": 100, "step": "sparse_embedding"})

        # Step 5: store in Qdrant
        qdrant_manager = get_qdrant_manager()
        dense_dim = embedder.dimension
        loop.run_until_complete(qdrant_manager.ensure_collection(dense_dim))
        loop.run_until_complete(qdrant_manager.upsert_chunks(chunks, dense_embeddings, sparse_vectors))

        result = {
            "status": "success",
            "metadata": metadata or {},
            "chunks_processed": total_chunks,
            "message": f"Successfully ingested document with {total_chunks} chunks."
        }
        return result

    except Exception as e:
        logger.exception(f"Ingestion failed: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

    finally:
        loop.close()
