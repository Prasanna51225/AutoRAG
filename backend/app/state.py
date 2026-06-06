# backend/app/state.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ReflexionState(BaseModel):
    """State passed through the LangGraph reflexion loop."""
    original_query: str
    current_query: str          # may be rewritten
    retrieved_chunks: List[Dict[str, Any]] = []   # each: {"text":..., "score":..., "rerank_score":..., "metadata":...}
    critique_score: Optional[float] = None
    critique_reason: Optional[str] = None
    loop_count: int = 0
    final_answer: Optional[str] = None
    trace_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True