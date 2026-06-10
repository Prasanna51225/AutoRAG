# backend/app/reranker.py
import asyncio
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        logger.info(f"Loading reranker model: {model_name}")
        self.model = CrossEncoder(model_name, device="cpu")
        self.cutoff = settings.reranker_cutoff

    async def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        chunks_to_rerank = chunks[:self.cutoff]
        pairs = [(query, chunk["text"]) for chunk in chunks_to_rerank]
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, self.model.predict, pairs)
        for chunk, score in zip(chunks_to_rerank, scores):
            chunk["rerank_score"] = float(score)
        chunks_to_rerank.sort(key=lambda x: x["rerank_score"], reverse=True)
        return chunks_to_rerank[:top_k]

_reranker = None

def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker