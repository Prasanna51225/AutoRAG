import json
import re
from typing import Literal, List, Dict, Any

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

# ── Indicators ────────────────────────────────────────────────────────────────

_SYNTHESIS_RE = re.compile(
    r'\b(summarize|overview|all\s+the|every|list\s+all|collect|timeline|history'
    r'|evolution|how\s+did|what\s+happened|entire|complete|comprehensive'
    r'|all\s+(?:people|entities|locations|investments|plans|challenges))\b',
    re.IGNORECASE,
)

_MULTI_HOP_RE = re.compile(
    r'\b(compare|contrast|then|after|before|since|how\s+did|why\s+did'
    r'|what\s+caused|relationship|connection|led\s+to|result(?:ed)?\s+in'
    r'|because|therefore|consequently)\b',
    re.IGNORECASE,
)

_TIMELINE_RE = re.compile(
    r'\b(timeline|chronolog|history|year|when|evolution|progress|developed?'
    r'|grew|expanded?|changed?|transformed?)\b',
    re.IGNORECASE,
)


# ── Node functions ────────────────────────────────────────────────────────────

async def retrieve_node(state: ReflexionState) -> dict:
    retriever = get_retriever()
    reranker = get_reranker()
    retrieved = await retriever.retrieve(state.current_query, top_k=settings.reranker_cutoff)
    reranked = await reranker.rerank(state.current_query, retrieved, top_k=20)
    return {"retrieved_chunks": reranked}


async def full_doc_retrieval_node(state: ReflexionState) -> dict:
    retriever = get_retriever()
    reranker = get_reranker()
    retrieved = await retriever.retrieve(state.current_query, top_k=100)
    reranked = await reranker.rerank(state.current_query, retrieved, top_k=30)
    return {"retrieved_chunks": reranked}


async def critic_node(state: ReflexionState) -> dict:
    critic = get_critic()
    score, reason = await critic.grade_relevance(state.current_query, state.retrieved_chunks)
    return {"critique_score": score, "critique_reason": reason}


async def rewrite_node(state: ReflexionState) -> dict:
    rewriter = get_rewriter()
    new_query = await rewriter.rewrite(state.original_query, state.critique_reason)
    return {"current_query": new_query, "loop_count": state.loop_count + 1}


async def generate_node(state: ReflexionState) -> dict:
    generator = get_generator()
    answer = await generator.generate(
        state.original_query,
        state.retrieved_chunks,
        entity_map=state.entity_map,
        timeline_events=state.timeline_events,
    )
    return {"final_answer": answer}


async def fallback_node(state: ReflexionState) -> dict:
    return {
        "final_answer": (
            "I've tried multiple attempts but couldn't find a reliable answer. "
            "Please rephrase your question or provide more context."
        )
    }


async def decompose_node(state: ReflexionState) -> dict:
    timeline_hint = ""
    if _TIMELINE_RE.search(state.original_query):
        timeline_hint = (
            "Include at least one sub‑question about chronological order or "
            "specific years/dates mentioned in the document."
        )
    prompt = (
        f"Break the following question into 3-5 simpler sub‑questions whose combined "
        f"answers would fully answer the original. {timeline_hint}\n"
        f"Output JSON only: {{\"subqueries\": [\"q1\", \"q2\", ...]}}\n"
        f"Question: {state.original_query}"
    )
    response = await call_ollama(prompt)
    try:
        start, end = response.find('{'), response.rfind('}') + 1
        data = json.loads(response[start:end])
        subqueries = data.get("subqueries", [])
    except Exception:
        subqueries = [state.original_query]
    return {"subqueries": subqueries}


async def multi_hop_retrieve(state: ReflexionState) -> dict:
    if not state.subqueries:
        return {}
    retriever = get_retriever()
    reranker = get_reranker()
    all_chunks = []
    for subq in state.subqueries:
        chunks = await retriever.retrieve(subq, top_k=25)
        all_chunks.extend(chunks)
    # Deduplicate
    seen = set()
    unique = []
    for ch in all_chunks:
        key = ch["text"][:100].strip()
        if key not in seen:
            seen.add(key)
            unique.append(ch)
    reranked = await reranker.rerank(state.original_query, unique, top_k=25)
    return {"retrieved_chunks": reranked}


async def aggregation_node(state: ReflexionState) -> dict:
    entity_map = {}
    investment_list = []
    future_plan_list = []
    challenge_list = []
    timeline_events = []

    for chunk in state.retrieved_chunks:
        meta = chunk.get("metadata", {})

        # Entities
        for etype, enames in meta.get("entities", {}).items():
            entity_map.setdefault(etype, [])
            for name in enames:
                if name not in entity_map[etype]:
                    entity_map[etype].append(name)

        # Investments
        for inv in meta.get("investments", []):
            if inv not in investment_list:
                investment_list.append(inv)

        # Future plans
        for fp in meta.get("future_plans", []):
            if fp not in future_plan_list:
                future_plan_list.append(fp)

        # Challenges
        for ch in meta.get("challenges", []):
            if ch not in challenge_list:
                challenge_list.append(ch)

        # Timeline
        for ev in meta.get("timeline", []):
            key = (ev.get("year"), ev.get("event", "")[:60])
            if not any((e.get("year"), e.get("event", "")[:60]) == key for e in timeline_events):
                timeline_events.append(ev)

    timeline_events.sort(key=lambda e: e.get("year", 0))

    # Structured summary
    structured_summary = {
        "people": list(set(entity_map.get("PER", []))),
        "organizations": list(set(entity_map.get("ORG", []))),
        "locations": list(set(entity_map.get("LOC", []))),
        "timeline": timeline_events,
        "investments": investment_list,
        "future_plans": future_plan_list,
        "challenges": challenge_list,
    }

    return {
        "entity_map": entity_map,
        "investment_list": investment_list,
        "future_plan_list": future_plan_list,
        "challenge_list": challenge_list,
        "timeline_events": timeline_events,
        "structured_summary": structured_summary,
    }


async def fusion_node(state: ReflexionState) -> dict:
    chunks = state.retrieved_chunks
    if len(chunks) <= 1:
        return {}
    MAX_CHUNKS = 10
    MAX_CHARS = 300
    preamble_parts = []
    if state.entity_map:
        emap = state.entity_map
        if emap.get("PER"):
            preamble_parts.append(f"Key people: {', '.join(emap['PER'][:15])}")
        if emap.get("ORG"):
            preamble_parts.append(f"Key organizations: {', '.join(emap['ORG'][:10])}")
        if emap.get("LOC"):
            preamble_parts.append(f"Key locations: {', '.join(emap['LOC'][:10])}")
    if state.timeline_events:
        years = sorted({e["year"] for e in state.timeline_events})
        preamble_parts.append(f"Years covered: {years}")

    preamble = "\n".join(preamble_parts)
    chunks_text = "\n\n---CHUNK---\n\n".join(
        [c["text"][:MAX_CHARS] for c in chunks[:MAX_CHUNKS]]
    )
    prompt = (
        "You are a document synthesis assistant.\n"
        + (f"Context preamble:\n{preamble}\n\n" if preamble else "")
        + "Combine the following text segments into one coherent passage.\n"
        "Preserve all facts, names, numbers, and dates. Remove exact duplicates.\n\n"
        f"Segments:\n{chunks_text}\n\n"
        "Combined passage:"
    )
    try:
        fused = await call_ollama(prompt)
    except Exception:
        fused = "\n\n".join([c["text"] for c in chunks[:MAX_CHUNKS]])
    return {"fused_context": fused, "retrieved_chunks": [{"text": fused, "score": 1.0, "rerank_score": 1.0, "metadata": {"fused": True}}] + chunks[:5]}


async def verify_node(state: ReflexionState) -> dict:
    if not state.final_answer:
        return {}
    context = "\n".join([c["text"] for c in state.retrieved_chunks[:10]])
    prompt = (
        f"Given the answer and the context, identify any claim in the answer that is NOT "
        f"supported by the context. List each unsupported claim on its own line.\n"
        f"If all claims are supported, output exactly: None\n\n"
        f"Context:\n{context}\n\n"
        f"Answer:\n{state.final_answer}\n\n"
        f"Unsupported claims:"
    )
    unsupported = await call_ollama(prompt)
    if unsupported.strip().lower() not in ("none", "none."):
        generator = get_generator()
        new_answer = await generator.generate(state.original_query, state.retrieved_chunks)
        return {"final_answer": new_answer}
    return {}


# ── Routing functions ─────────────────────────────────────────────────────────

def should_continue(state: ReflexionState) -> Literal["rewrite", "generate", "fallback"]:
    if state.loop_count >= settings.max_loops:
        return "fallback"
    if state.critique_score is None:
        return "generate"
    if state.critique_score < settings.critic_threshold:
        return "rewrite"
    return "generate"


def route_entry(state: ReflexionState) -> str:
    q = state.original_query
    if _SYNTHESIS_RE.search(q):
        return "full_doc_retrieval"
    if _MULTI_HOP_RE.search(q):
        return "decompose"
    return "retrieve"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_reflexion_graph():
    builder = StateGraph(ReflexionState)

    # Nodes
    builder.add_node("entry",              lambda s: {})           # FIXED: returns empty dict
    builder.add_node("retrieve",           retrieve_node)
    builder.add_node("full_doc_retrieval", full_doc_retrieval_node)
    builder.add_node("decompose",          decompose_node)
    builder.add_node("multi_hop_retrieve", multi_hop_retrieve)
    builder.add_node("aggregation",        aggregation_node)
    builder.add_node("fusion",             fusion_node)
    builder.add_node("critic",             critic_node)
    builder.add_node("rewrite",            rewrite_node)
    builder.add_node("generate",           generate_node)
    builder.add_node("verify",             verify_node)
    builder.add_node("fallback",           fallback_node)

    # Entry routing
    builder.set_entry_point("entry")
    builder.add_conditional_edges(
        "entry",
        route_entry,
        {
            "retrieve":           "retrieve",
            "full_doc_retrieval": "full_doc_retrieval",
            "decompose":          "decompose",
        },
    )

    # Retrieval paths converge at aggregation → fusion → critic
    builder.add_edge("retrieve",           "aggregation")
    builder.add_edge("full_doc_retrieval", "aggregation")
    builder.add_edge("decompose",          "multi_hop_retrieve")
    builder.add_edge("multi_hop_retrieve", "aggregation")
    builder.add_edge("aggregation",        "fusion")
    builder.add_edge("fusion",             "critic")

    # Critic routing
    builder.add_conditional_edges(
        "critic",
        should_continue,
        {
            "rewrite":  "rewrite",
            "generate": "generate",
            "fallback": "fallback",
        },
    )

    # Rewrite loops back to retrieve
    builder.add_edge("rewrite", "retrieve")

    # Generate → verify → end
    builder.add_edge("generate", "verify")
    builder.add_edge("verify",   END)
    builder.add_edge("fallback", END)

    return builder.compile()


# ── Singleton ─────────────────────────────────────────────────────────────────

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_reflexion_graph()
    return _graph