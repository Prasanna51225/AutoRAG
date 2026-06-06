# backend/app/generator.py
import httpx
from typing import List, Dict, Any
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class AnswerGenerator:
    def __init__(self, ollama_base_url: str = None, model: str = None):
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
    
    async def generate(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Generate final answer using top chunks as context.
        """
        if not chunks:
            return "I couldn't find any relevant information to answer your query."
        
        context = "\n---\n".join([chunk["text"] for chunk in chunks[:5]])
        prompt = f"""You are a helpful assistant. Use only the provided context to answer the query.
If the context doesn't contain enough information, say "I don't have enough information to answer that."

Context:
{context}

Query: {query}

Answer (be concise, cite sources as [doc] if multiple chunks):
"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                answer = response.json()["response"].strip()
                return answer
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"Failed to generate answer: {str(e)}"

# Singleton
_generator = None

def get_generator() -> AnswerGenerator:
    global _generator
    if _generator is None:
        _generator = AnswerGenerator()
    return _generator