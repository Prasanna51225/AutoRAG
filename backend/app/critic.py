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

    async def grade_relevance(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> Tuple[float, str]:
        if not chunks:
            return 0.0, "No chunks retrieved."

        # Use up to 20 chunks to assess broad coverage
        top_chunks = chunks[:20]
        context = "\n---\n".join([c["text"][:500] for c in top_chunks])

        prompt = f"""Rate how well the retrieved documents answer the query. Use these guidelines:

- 1.0 = The query is fully answered across the documents (all key facts, entities, timeline are present).
- 0.7 = Most aspects are covered, but a few minor details are missing.
- 0.5 = Some relevant info, but many important details are missing.
- 0.3 = Only vague or partial coverage.
- 0.0 = Irrelevant.

IMPORTANT: For broad, synthesis-style queries (like "explain how X transformed..."), the answer may require information from many chunks. A score of 0.7 or higher is appropriate if all key aspects (people, technologies, timeline, challenges, plans, investments) are covered across the chunks, even if no single chunk contains everything.

Query: {query}

Documents (first {len(top_chunks)} chunks):
{context}

Output ONLY JSON: {{"score": float (0-1), "reason": "short explanation"}}"""

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                result_text = response.json()["response"]
                start = result_text.find('{')
                end = result_text.rfind('}') + 1
                if start != -1 and end > 0:
                    data = json.loads(result_text[start:end])
                    score = max(0.0, min(1.0, float(data.get("score", 0.5))))
                    reason = data.get("reason", "No reason provided")
                else:
                    score, reason = 0.5, "JSON parsing failed"
                return score, reason
        except Exception as e:
            logger.error(f"Critic failed: {e}")
            return 0.5, f"Critic error: {str(e)}"


# ── Singleton ─────────────────────────────────────────────────────────────────
_critic = None


def get_critic() -> Critic:
    global _critic
    if _critic is None:
        _critic = Critic()
    return _critic