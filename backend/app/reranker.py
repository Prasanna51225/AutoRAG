# backend/app/reranker.py
import asyncio
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class Reranker:
    """Cross-encoder reranker with lazy loading (avoids startup timeout)."""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        self._model = None
        self.cutoff = settings.reranker_cutoff
        logger.info(f"Reranker placeholder created (model will load on first use)")
    
    @property
    def model(self):
        if self._model is None:
            logger.info(f"Loading reranker model: {self.model_name}")
            # CPU is fine; use device="cuda" if GPU available
            self._model = CrossEncoder(self.model_name, device="cpu")
            logger.info("Reranker model loaded successfully")
        return self._model
    
    async def rerank(self, query: str, chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Rerank retrieved chunks using cross-encoder.
        Input chunks are truncated to self.cutoff for performance.
        Returns top_k chunks with rerank_score added.
        """
        if not chunks:
            return []
        
        # Truncate to cutoff
        chunks_to_rerank = chunks[:self.cutoff]
        
        # Prepare pairs
        pairs = [(query, chunk["text"]) for chunk in chunks_to_rerank]
        
        # Run inference (blocking, run in thread)
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, self.model.predict, pairs)
        
        # Attach scores
        for chunk, score in zip(chunks_to_rerank, scores):
            chunk["rerank_score"] = float(score)
        
        # Sort by rerank score descending
        chunks_to_rerank.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        return chunks_to_rerank[:top_k]

# Singleton
_reranker = None

def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker