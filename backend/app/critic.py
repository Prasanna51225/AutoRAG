# backend/app/critic.py
import asyncio
import json
from typing import List, Dict, Any, Tuple
import httpx
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class Critic:
    def __init__(self, ollama_base_url: str = None, model: str = None):
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

    async def grade_relevance(self, query: str, chunks: List[Dict[str, Any]]) -> Tuple[float, str]:
        if not chunks:
            return 0.0, "No chunks retrieved."

        top_chunks = chunks[:3]
        context = "\n---\n".join([c["text"] for c in top_chunks])

        prompt = f"""Rate how well these documents answer the query on a scale from 0 to 1, where:
        - 1.0 = Perfect, fully answers the query
        - 0.6 = Partial, some relevant information but missing key parts
        - 0.3 = Vague connection, not directly helpful
        - 0.0 = Completely irrelevant
        Query: {query}
        Documents:
        {context}
        Output ONLY JSON: {{"score": float, "reason": "short explanation"}}
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False}
                )
                result_text = response.json()["response"]
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start != -1 and end != 0:
                    data = json.loads(result_text[start:end])
                    score = float(data.get("score", 0.3))
                    reason = data.get("reason", "No reason")
                else:
                    score = 0.3
                    reason = "Parsing failed"
                return score, reason
        except Exception as e:
            logger.error(f"Critic failed: {e}")
            return 0.3, f"Critic error: {str(e)}"

_critic = None

def get_critic() -> Critic:
    global _critic
    if _critic is None:
        _critic = Critic()
    return _critic