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
        if not chunks:
            return "The context does not contain that information."

        # Detect if query asks to collect/list
        is_collection = any(phrase in query.lower() for phrase in ["list all", "collect", "all the", "every", "each"])

        # Use top 8 chunks
        context = "\n---\n".join([chunk["text"] for chunk in chunks[:8]])

        if is_collection:
            prompt = f"""You are an expert assistant. The user asks to list or collect multiple items.
            Context:
            {context}
            Query: {query}
            Extract every distinct item from the context and present them as a bullet list.
            If the context does not contain the information, say exactly: "The context does not contain that information."
            """
        else:
            prompt = f"""You are an expert assistant. Use the provided context to answer the query.
            If the context does not contain the information, you may use your general knowledge but clearly mark such statements with "[General knowledge]".
            Context:
            {context}
            Query: {query}
            Answer (prioritise context; if uncertain, say "Based on my general knowledge, ..."):
            """

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False}
                )
                response.raise_for_status()
                answer = response.json()["response"].strip()
                return answer
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return "I encountered an error while generating the answer."

_generator = None

def get_generator() -> AnswerGenerator:
    global _generator
    if _generator is None:
        _generator = AnswerGenerator()
    return _generator