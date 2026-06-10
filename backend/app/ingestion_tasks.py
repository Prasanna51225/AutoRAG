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
from app.entity_extractor import extract_entities
from app.temporal_extractor import extract_dates
from app.utils import get_logger, get_redis_client
import httpx

logger = get_logger(__name__)

async def call_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "http://ollama:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        return resp.json()["response"]

def generate_summary(text: str) -> str:
    """Generate document summary using Ollama."""
    prompt = f"Summarize the following document in 500 words or less:\n\n{text[:8000]}"
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    summary = loop.run_until_complete(call_ollama(prompt))
    loop.close()
    return summary

def extract_relationships(text: str) -> list:
    """Extract (subject, relation, object) triples."""
    prompt = f"""Extract all (subject, relation, object) triples from the following text. Output as JSON list.
    Example: [["Elon Musk", "is CEO of", "SpaceX"], ["Tesla", "produces", "electric cars"]]
    Text: {text[:1500]}
    Triples:"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(call_ollama(prompt))
    loop.close()
    try:
        return json.loads(response)
    except:
        return []

@shared_task(bind=True, name="ingest_document")
def ingest_document(self, file_content: str, metadata: Dict[str, Any] = None):
    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100, "step": "starting"})
    
    try:
        # Step 1: chunk
        chunker = get_chunker()
        chunks = chunker.chunk_text(file_content, metadata or {})
        total_chunks = len(chunks)
        self.update_state(state="PROGRESS", meta={"current": 10, "total": 100, "step": "chunking"})
        
        # Step 2: generate document summary and add as first chunk
        try:
            summary = generate_summary(file_content)
            summary_chunk = {
                "text": f"DOCUMENT SUMMARY:\n{summary}",
                "metadata": {**(metadata or {}), "is_summary": True, "chunk_index": -1},
                "chunk_index": -1
            }
            chunks.insert(0, summary_chunk)
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
        
        # Step 3: extract entities and dates for each chunk
        for idx, chunk in enumerate(chunks):
            entities = extract_entities(chunk["text"])
            dates = extract_dates(chunk["text"])
            chunk["metadata"]["entities"] = entities
            chunk["metadata"]["dates"] = dates
            # relationships extraction (optional, can be heavy)
            if total_chunks <= 50:  # only for small docs
                relations = extract_relationships(chunk["text"])
                chunk["metadata"]["relations"] = relations
        
        self.update_state(state="PROGRESS", meta={"current": 30, "total": 100, "step": "extracted metadata"})
        
        # Step 4: embeddings (dense)
        embedder = get_embedder()
        redis_client = get_redis_client()
        embedder.set_redis(redis_client, 3600)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        chunk_texts = [c["text"] for c in chunks]
        dense_embeddings = loop.run_until_complete(embedder.embed_batch(chunk_texts))
        self.update_state(state="PROGRESS", meta={"current": 50, "total": 100, "step": "dense_embedding"})
        
        # Step 5: sparse vectors
        sparse_vectorizer = get_sparse_vectorizer()
        sparse_vectorizer.update_idf(chunk_texts)
        sparse_vectors = [sparse_vectorizer.vectorize(text) for text in chunk_texts]
        self.update_state(state="PROGRESS", meta={"current": 70, "total": 100, "step": "sparse_embedding"})
        
        # Step 6: store in Qdrant
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
        raise self.retry(exc=e, countdown=60, max_retries=3)