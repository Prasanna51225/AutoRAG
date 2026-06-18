from typing import Annotated, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import operator

# ----- Reducer functions -----

def keep_original(a: str, b: str) -> str:
    """Always keep the first (original) value."""
    return a if a is not None else b

def latest_value(a: str, b: str) -> str:
    """Always take the newer value."""
    return b

# ----- State definition -----

class ReflexionState(BaseModel):
    # Core query fields – only entry node should set original_query
    original_query: Annotated[str, keep_original] = Field(default="")
    
    # current_query may be rewritten; use latest_value reducer
    current_query: Annotated[str, latest_value] = Field(default="")

    # Retrieval fields – accumulate lists (using operator.add) if needed
    retrieved_chunks: Annotated[List[Dict[str, Any]], operator.add] = Field(default_factory=list)
    subqueries: List[str] = Field(default_factory=list)
    fused_context: Optional[str] = None

    # Aggregated cross‑chunk knowledge
    entity_map: Dict[str, List[str]] = Field(default_factory=dict)
    investment_list: List[str] = Field(default_factory=list)
    future_plan_list: List[str] = Field(default_factory=list)
    challenge_list: List[str] = Field(default_factory=list)
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list)
    structured_summary: Optional[Dict[str, Any]] = None

    # Critic / loop control
    critique_score: Optional[float] = None
    critique_reason: Optional[str] = None
    loop_count: int = 0

    # Output
    final_answer: Optional[str] = None

    # Observability
    trace_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True