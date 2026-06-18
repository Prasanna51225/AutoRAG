# backend/app/retriever.py
import asyncio
import hashlib
import json
from typing import List, Dict, Any, Optional
from app.config import settings
from app.qdrant_client import get_qdrant_manager
from app.embeddings import get_embedder
from app.sparse import get_sparse_vectorizer
from app.utils import get_logger, get_redis_client
import redis

logger = get_logger(__name__)

class QueryCache:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def _key(self, query: str) -> str:
        return f"query_cache:{hashlib.md5(query.encode()).hexdigest()}"

    def get(self, query: str) -> Optional[List[Dict[str, Any]]]:
        key = self._key(query)
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    def set(self, query: str, chunks: List[Dict[str, Any]]):
        key = self._key(query)
        self.redis.setex(key, self.ttl, json.dumps(chunks))

class HybridRetriever:
    def __init__(self):
        self.qdrant = get_qdrant_manager()
        self.embedder = get_embedder()
        self.sparse_vectorizer = get_sparse_vectorizer()
        self.cache = None
        logger.info("HybridRetriever initialised")

    def set_redis(self, redis_client: redis.Redis, ttl: int = 3600):
        self.embedder.set_redis(redis_client, ttl)
        self.cache = QueryCache(redis_client, ttl)

    async def retrieve(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        if self.cache:
            cached = self.cache.get(query)
            if cached:
                logger.debug(f"Cache hit for query: {query[:50]}")
                return cached

        dense_vec = await self.embedder.embed(query)
        sparse_vec = self.sparse_vectorizer.vectorize(query)

        try:
            results = await asyncio.to_thread(
                self.qdrant.search_hybrid,
                dense_vec,
                sparse_vec,
                top_k,
            )
        except Exception as e:
            logger.warning(f"Hybrid search failed ({e}), falling back to dense-only")
            results = await asyncio.to_thread(
                self.qdrant.search_dense,
                dense_vec,
                top_k,
            )

        chunks = []
        for hit in results:
            chunks.append({
                "text": hit.payload["text"],
                "score": hit.score,
                "metadata": hit.payload.get("metadata", {}),
                "id": hit.id,
                "rerank_score": None,
            })

        if self.cache:
            self.cache.set(query, chunks)

        logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:50]}")
        return chunks

_retriever = None

def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever