# backend/app/embeddings.py
import asyncio
import hashlib
import json
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import redis
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class EmbeddingCache:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def _key(self, text: str) -> str:
        return f"embed:{hashlib.md5(text.encode()).hexdigest()}"

    def get(self, text: str) -> Optional[List[float]]:
        key = self._key(text)
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    def set(self, text: str, embedding: List[float]):
        key = self._key(text)
        self.redis.setex(key, self.ttl, json.dumps(embedding))

class DenseEmbedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        logger.info(f"Loading dense embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device="cpu")
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.cache = None
        logger.info(f"Dense embedder ready, dimension={self.dimension}")

    def set_redis(self, redis_client: redis.Redis, ttl: int = 3600):
        self.cache = EmbeddingCache(redis_client, ttl)

    async def embed(self, text: str) -> List[float]:
        if self.cache:
            cached = self.cache.get(text)
            if cached:
                return cached
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(None, self.model.encode, text)
        embedding_list = embedding.tolist()
        if self.cache:
            self.cache.set(text, embedding_list)
        return embedding_list

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        uncached_indices = []
        uncached_texts = []
        results = [None] * len(texts)
        if self.cache:
            for i, t in enumerate(texts):
                cached = self.cache.get(t)
                if cached:
                    results[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(t)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts
        if uncached_texts:
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(None, self.model.encode, uncached_texts)
            for idx, emb in zip(uncached_indices, embeddings):
                emb_list = emb.tolist()
                results[idx] = emb_list
                if self.cache:
                    self.cache.set(uncached_texts[uncached_indices.index(idx)], emb_list)
        return results

_embedder = None

def get_embedder() -> DenseEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = DenseEmbedder()
    return _embedder