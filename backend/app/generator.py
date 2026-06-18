import re
from typing import List, Dict, Any, Optional

import httpx

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# ── Query-type detectors (simplified, using separate patterns) ─────────────

_COLLECTION_PATTERNS = [
    re.compile(r'\blist\s+all\b', re.IGNORECASE),
    re.compile(r'\bcollect\b', re.IGNORECASE),
    re.compile(r'\bevery\b', re.IGNORECASE),
    re.compile(r'\ball\s+the\b', re.IGNORECASE),
    re.compile(r'\beach\b', re.IGNORECASE),
    re.compile(r'\benumerate\b', re.IGNORECASE),
    re.compile(r'\bwhat\s+are\s+all\b', re.IGNORECASE),
]

_TIMELINE_PATTERNS = [
    re.compile(r'\btimeline\b', re.IGNORECASE),
    re.compile(r'\bchronolog', re.IGNORECASE),
    re.compile(r'\bhistory\b', re.IGNORECASE),
    re.compile(r'\byear\b', re.IGNORECASE),
    re.compile(r'\bwhen\b', re.IGNORECASE),
    re.compile(r'\bevolution\b', re.IGNORECASE),
    re.compile(r'\bdevelop', re.IGNORECASE),
    re.compile(r'\bprogress\b', re.IGNORECASE),
    re.compile(r'\bgrew\b', re.IGNORECASE),
    re.compile(r'\bexpanded?', re.IGNORECASE),
    re.compile(r'\bchanged?', re.IGNORECASE),
    re.compile(r'\btransformed?', re.IGNORECASE),
    re.compile(r'\bhow\s+did\b', re.IGNORECASE),
]

_CAUSE_EFFECT_PATTERNS = [
    re.compile(r'\bwhy\b', re.IGNORECASE),
    re.compile(r'\bbecause\b', re.IGNORECASE),
    re.compile(r'\bcause\b', re.IGNORECASE),
    re.compile(r'\breason\b', re.IGNORECASE),
    re.compile(r'\bled\s+to\b', re.IGNORECASE),
    re.compile(r'\bresult(?:ed)?\s+in\b', re.IGNORECASE),
    re.compile(r'\bimpact\b', re.IGNORECASE),
    re.compile(r'\beffect\b', re.IGNORECASE),
    re.compile(r'\bconsequence\b', re.IGNORECASE),
    re.compile(r'\btherefore\b', re.IGNORECASE),
    re.compile(r'\bthus\b', re.IGNORECASE),
    re.compile(r'\bhence\b', re.IGNORECASE),
]

_SYNTHESIS_PATTERNS = [
    re.compile(r'\bsummarize\b', re.IGNORECASE),
    re.compile(r'\boverview\b', re.IGNORECASE),
    re.compile(r'\bcomprehensive\b', re.IGNORECASE),
    re.compile(r'\bcomplete\b', re.IGNORECASE),
    re.compile(r'\ball\s+the\b', re.IGNORECASE),
    re.compile(r'\bevery\b', re.IGNORECASE),
    re.compile(r'\blist\s+all\b', re.IGNORECASE),
    re.compile(r'\bcollect\b', re.IGNORECASE),
    re.compile(r'\btimeline\b', re.IGNORECASE),
    re.compile(r'\bhistory\b', re.IGNORECASE),
    re.compile(r'\bevolution\b', re.IGNORECASE),
    re.compile(r'\bexplain\s+how\b', re.IGNORECASE),
    re.compile(r'\btransformation\b', re.IGNORECASE),
    re.compile(r'all\s+(?:people|investments|locations|plans|challenges|technologies)', re.IGNORECASE),
]

def _match_any(query: str, patterns: list) -> bool:
    return any(p.search(query) for p in patterns)

class AnswerGenerator:
    def __init__(self, ollama_base_url: str = None, model: str = None):
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

    async def generate(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        entity_map: Optional[Dict[str, List[str]]] = None,
        timeline_events: Optional[List[Dict]] = None,
    ) -> str:
        if not chunks:
            return "The context does not contain that information."

        # Determine query type using pattern matching
        is_synthesis = _match_any(query, _SYNTHESIS_PATTERNS)
        is_timeline = _match_any(query, _TIMELINE_PATTERNS)
        is_collection = _match_any(query, _COLLECTION_PATTERNS)

        # For synthesis queries, use fewer chunks to avoid overwhelming the model
        max_chunks = 20  # default
        if is_synthesis:
            max_chunks = 8
        elif is_timeline:
            max_chunks = 12
        elif is_collection:
            max_chunks = 15

        # Build context (full text of each chunk, trimmed)
        context_parts = []
        for i, chunk in enumerate(chunks[:max_chunks]):
            text = chunk.get("text", "")
            if not text:
                continue
            # Trim each chunk to 1500 chars max (to stay within model limits)
            if len(text) > 1500:
                text = text[:1500] + "..."
            context_parts.append(f"[Chunk {i+1}] {text}")
        context = "\n\n".join(context_parts)

        # Select prompt based on query type
        if is_synthesis:
            prompt = self._synthesis_prompt(query, context)
        elif is_timeline:
            prompt = self._timeline_prompt(query, context)
        elif is_collection:
            prompt = self._collection_prompt(query, context)
        else:
            prompt = self._default_prompt(query, context)

        # Make the API call
        answer = await self._call_ollama(prompt)

        # If answer is too short or says "I don't have enough information", retry with a simpler prompt
        if len(answer.split()) < 30 or "don't have enough information" in answer.lower():
            logger.info("Answer too short or missing info, retrying with simpler prompt")
            retry_prompt = self._retry_prompt(query, context)
            answer = await self._call_ollama(retry_prompt)

        return answer

    async def _call_ollama(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                return response.json()["response"].strip()
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return "I encountered an error while generating the answer."

    # ── Prompt templates ──────────────────────────────────────────────────────

    @staticmethod
    def _default_prompt(query: str, context: str) -> str:
        return f"""Answer the query using ONLY the provided context.
If the context does not contain the answer, say "I don't have enough information."

Context:
{context}

Query: {query}

Answer:"""

    @staticmethod
    def _collection_prompt(query: str, context: str) -> str:
        return f"""You are an expert assistant. The user asks for a complete list.
Scan ALL chunks and extract every distinct item. Do NOT omit any.
Present as a numbered list. State the total count after the list.

Context:
{context}

Query: {query}

Complete list:"""

    @staticmethod
    def _timeline_prompt(query: str, context: str) -> str:
        return f"""You are an expert historian. Build a chronological answer.
Extract every year and the associated event. Arrange from earliest to latest.
Highlight cause-and-effect where visible.

Context:
{context}

Query: {query}

Chronological timeline:"""

    @staticmethod
    def _synthesis_prompt(query: str, context: str) -> str:
        return f"""You are a comprehensive document analyst. Provide an EXHAUSTIVE answer covering ALL of the following categories (skip any not present in the context):

- People & Roles
- Organizations & Partners
- Locations & Geographies
- Technologies & Products
- Financial Investments & Funding
- Key Events & Timeline
- Operational Challenges
- Future Plans & Roadmap

RULES:
- Your answer MUST be at least 500 words long.
- Do NOT over‑summarise. Include specific names, figures, and dates.
- If a category has many items, list them ALL.
- Distinguish between project‑specific and company‑wide plans.
- Use the context to support every claim.

Context:
{context}

Query: {query}

Comprehensive answer (all categories, detailed):"""

    @staticmethod
    def _retry_prompt(query: str, context: str) -> str:
        """Simpler prompt to use if the first attempt fails."""
        return f"""You are a document analyst. Provide a detailed answer to the query using the context.
Include as much specific information as possible: names, dates, numbers, technologies, locations.
If the context lacks information, say "Not mentioned".

Context:
{context}

Query: {query}

Detailed answer:"""


# ── Singleton ─────────────────────────────────────────────────────────────────
_generator = None


def get_generator() -> AnswerGenerator:
    global _generator
    if _generator is None:
        _generator = AnswerGenerator()
    return _generator