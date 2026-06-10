# backend/app/graph.py
import json
from typing import Literal
from langgraph.graph import StateGraph, END
from app.state import ReflexionState
from app.retriever import get_retriever
from app.reranker import get_reranker
from app.critic import get_critic
from app.rewriter import get_rewriter
from app.generator import get_generator
from app.config import settings
from app.utils import get_logger, call_ollama

logger = get_logger(__name__)

async def retrieve_node(state: ReflexionState) -> ReflexionState:
    retriever = get_retriever()
    reranker = get_reranker()
    retrieved = await retriever.retrieve(state.current_query, top_k=settings.reranker_cutoff)
    reranked = await reranker.rerank(state.current_query, retrieved, top_k=8)
    state.retrieved_chunks = reranked
    return state

async def critic_node(state: ReflexionState) -> ReflexionState:
    critic = get_critic()
    score, reason = await critic.grade_relevance(state.current_query, state.retrieved_chunks)
    state.critique_score = score
    state.critique_reason = reason
    return state

async def rewrite_node(state: ReflexionState) -> ReflexionState:
    rewriter = get_rewriter()
    new_query = await rewriter.rewrite(state.original_query, state.critique_reason)
    state.current_query = new_query
    state.loop_count += 1
    return state

async def generate_node(state: ReflexionState) -> ReflexionState:
    generator = get_generator()
    answer = await generator.generate(state.original_query, state.retrieved_chunks)
    state.final_answer = answer
    return state

async def fallback_node(state: ReflexionState) -> ReflexionState:
    state.final_answer = (
        "I've tried multiple attempts but couldn't find a reliable answer. "
        "Please rephrase your question or provide more context."
    )
    return state

async def decompose_node(state: ReflexionState) -> ReflexionState:
    """Break complex query into subqueries."""
    prompt = f"""Break the following question into 2-3 simpler sub-questions that, when answered together, would answer the original.
    Output as JSON: {{"subqueries": ["q1", "q2", ...]}}
    Question: {state.original_query}"""
    response = await call_ollama(prompt)
    try:
        data = json.loads(response)
        state.subqueries = data.get("subqueries", [])
    except:
        state.subqueries = [state.original_query]
    return state

async def multi_hop_retrieve(state: ReflexionState) -> ReflexionState:
    if not state.subqueries:
        return state
    retriever = get_retriever()
    reranker = get_reranker()
    all_chunks = []
    for subq in state.subqueries:
        chunks = await retriever.retrieve(subq, top_k=15)
        all_chunks.extend(chunks)
    # Deduplicate by text
    seen = set()
    unique = []
    for ch in all_chunks:
        if ch["text"] not in seen:
            seen.add(ch["text"])
            unique.append(ch)
    reranked = await reranker.rerank(state.original_query, unique, top_k=12)
    state.retrieved_chunks = reranked
    return state

async def fusion_node(state: ReflexionState) -> ReflexionState:
    if len(state.retrieved_chunks) <= 1:
        return state
    chunks_text = "\n".join([c["text"] for c in state.retrieved_chunks[:10]])
    prompt = f"""Combine the following text segments into a single, coherent, well-structured passage. Remove duplicates and resolve contradictions. Preserve all facts.
    Segments:
    {chunks_text}
    Combined passage:"""
    fused = await call_ollama(prompt)
    state.retrieved_chunks = [{"text": fused, "score": 1.0, "rerank_score": 1.0, "metadata": {"fused": True}}]
    return state

async def verify_node(state: ReflexionState) -> ReflexionState:
    if not state.final_answer:
        return state
    context = "\n".join([c["text"] for c in state.retrieved_chunks[:5]])
    prompt = f"""Given the answer and the context, verify each claim. List any claim not supported by context.
    Context: {context}
    Answer: {state.final_answer}
    Unsupported claims (if any, otherwise "None"):"""
    unsupported = await call_ollama(prompt)
    if unsupported.strip() != "None":
        # Retry generation with stricter instruction
        generator = get_generator()
        new_answer = await generator.generate(state.original_query, state.retrieved_chunks)
        state.final_answer = new_answer
    return state

def should_continue(state: ReflexionState) -> Literal["rewrite", "generate", "fallback"]:
    if state.loop_count >= settings.max_loops:
        return "fallback"
    if state.critique_score is None:
        return "generate"
    if state.critique_score < settings.critic_threshold:
        return "rewrite"
    return "generate"

def should_decompose(state: ReflexionState) -> bool:
    # Simple heuristic: if query contains multi-hop indicators
    indicators = ["compare", "contrast", "then", "after", "before", "list all", "collect"]
    return any(word in state.original_query.lower() for word in indicators)

def build_reflexion_graph():
    builder = StateGraph(ReflexionState)
    builder.add_node("decompose", decompose_node)
    builder.add_node("multi_hop_retrieve", multi_hop_retrieve)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("fusion", fusion_node)
    builder.add_node("critic", critic_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("generate", generate_node)
    builder.add_node("verify", verify_node)
    builder.add_node("fallback", fallback_node)

    # Entry: decide whether to decompose
    builder.add_node("entry", lambda s: s)
    builder.set_entry_point("entry")
    builder.add_conditional_edges("entry", should_decompose, {True: "decompose", False: "retrieve"})
    builder.add_edge("decompose", "multi_hop_retrieve")
    builder.add_edge("multi_hop_retrieve", "fusion")
    builder.add_edge("retrieve", "fusion")
    builder.add_edge("fusion", "critic")
    builder.add_conditional_edges("critic", should_continue, {
        "rewrite": "rewrite",
        "generate": "generate",
        "fallback": "fallback"
    })
    builder.add_edge("rewrite", "retrieve")
    builder.add_edge("generate", "verify")
    builder.add_edge("verify", END)
    builder.add_edge("fallback", END)

    return builder.compile()

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_reflexion_graph()
    return _graph