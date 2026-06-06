# backend/app/graph.py
from typing import Literal, Dict, Any, List
from langgraph.graph import StateGraph, END
from app.retriever import get_retriever
from app.reranker import get_reranker
from app.critic import get_critic
from app.rewriter import get_rewriter
from app.generator import get_generator
from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)

# State is a dictionary (LangGraph native)
# We'll use a TypedDict for clarity, but simple dict works.
# For simplicity, we define the structure via functions.

def _get_empty_state(original_query: str) -> Dict[str, Any]:
    return {
        "original_query": original_query,
        "current_query": original_query,
        "retrieved_chunks": [],
        "critique_score": None,
        "critique_reason": None,
        "loop_count": 0,
        "final_answer": None,
    }

async def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        retriever = get_retriever()
        reranker = get_reranker()
        retrieved = await retriever.retrieve(state["current_query"], top_k=settings.reranker_cutoff)
        reranked = await reranker.rerank(state["current_query"], retrieved, top_k=5)
        state["retrieved_chunks"] = reranked
        logger.info(f"Retrieved {len(reranked)} chunks for query: {state['current_query'][:50]}")
    except Exception as e:
        logger.error(f"Retrieve node failed: {e}")
        state["retrieved_chunks"] = []
    return state

async def critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        critic = get_critic()
        score, reason = await critic.grade_relevance(state["current_query"], state["retrieved_chunks"])
        state["critique_score"] = score
        state["critique_reason"] = reason
        logger.info(f"Critic score: {score}, reason: {reason[:100]}")
    except Exception as e:
        logger.error(f"Critic node failed: {e}")
        state["critique_score"] = 0.5
        state["critique_reason"] = f"Critic error: {str(e)}"
    return state

async def rewrite_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        rewriter = get_rewriter()
        new_query = await rewriter.rewrite(state["original_query"], state["critique_reason"])
        state["current_query"] = new_query
        state["loop_count"] = state.get("loop_count", 0) + 1
        logger.info(f"Rewritten query (loop {state['loop_count']}): {new_query[:100]}")
    except Exception as e:
        logger.error(f"Rewrite node failed: {e}")
        # Keep current query
        state["loop_count"] = state.get("loop_count", 0) + 1
    return state

async def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        generator = get_generator()
        answer = await generator.generate(state["original_query"], state["retrieved_chunks"])
        state["final_answer"] = answer
        logger.info(f"Generated answer (length {len(answer)})")
    except Exception as e:
        logger.error(f"Generate node failed: {e}")
        state["final_answer"] = "Failed to generate answer due to an error."
    return state

async def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state["final_answer"] = (
        "I've tried multiple attempts but couldn't find a reliable answer. "
        "Please rephrase your question or provide more context."
    )
    logger.warning(f"Fallback triggered after {state.get('loop_count', 0)} loops")
    return state

def should_continue(state: Dict[str, Any]) -> Literal["rewrite", "generate", "fallback"]:
    loop_count = state.get("loop_count", 0)
    if loop_count >= settings.max_loops:
        return "fallback"
    score = state.get("critique_score")
    if score is None:
        return "generate"
    if score < settings.critic_threshold:
        return "rewrite"
    return "generate"

def build_reflexion_graph():
    builder = StateGraph(dict)   # state is a dictionary

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("critic", critic_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("generate", generate_node)
    builder.add_node("fallback", fallback_node)

    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "critic")
    builder.add_conditional_edges("critic", should_continue, {
        "rewrite": "rewrite",
        "generate": "generate",
        "fallback": "fallback"
    })
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("generate", END)
    builder.add_edge("fallback", END)

    return builder.compile()

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_reflexion_graph()
    return _graph