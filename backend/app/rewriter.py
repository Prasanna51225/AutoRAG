import httpx
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

class QueryRewriter:
    def __init__(self, ollama_base_url: str = None, model: str = None):
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

    async def rewrite(self, original_query: str, critique_reason: str, previous_rewrites: list = None) -> str:
        history = ""
        if previous_rewrites:
            history = "Previously rewritten queries:\n" + "\n".join(previous_rewrites)
        prompt = f"""Original query: {original_query}
{history}
Critique reason: {critique_reason}
Rewrite the query to make it more specific or rephrase ambiguous terms for better retrieval.
Output ONLY the rewritten query, no explanation.
"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False}
                )
                response.raise_for_status()
                return response.json()["response"].strip()
        except Exception as e:
            logger.error(f"Query rewrite failed: {e}")
            return original_query

_rewriter = None

def get_rewriter() -> QueryRewriter:
    global _rewriter
    if _rewriter is None:
        _rewriter = QueryRewriter()
    return _rewriter
