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

        # Separate summary chunks (always kept) from normal chunks
        summary_chunks = [c for c in chunks if c.get("metadata", {}).get("is_summary")]
        normal_chunks = [c for c in chunks if not c.get("metadata", {}).get("is_summary")]

        # Score normal chunks (up to cutoff)
        to_score = normal_chunks[:self.cutoff]   # <-- define to_score even if empty
        if to_score:
            pairs = [(query, c["text"]) for c in to_score]
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(None, self.model.predict, pairs)
            for chunk, score in zip(to_score, scores):
                chunk["rerank_score"] = float(score)
            to_score.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Summaries get a high score
        for sc in summary_chunks:
            sc["rerank_score"] = 1.0

        # Merge: summaries first, then top normal chunks
        merged = summary_chunks + to_score
        return merged[:top_k]

_reranker = None

def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker