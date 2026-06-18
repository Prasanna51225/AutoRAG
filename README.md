# AutoRAG

A production-ready RAG system that actually knows when its retrieval is bad — and fixes it.

Most RAG setups are one-shot: you ask, it searches, it answers. If the search comes back with garbage, the answer is garbage too. AutoRAG adds a reflexion loop on top, where a critic LLM grades the retrieved chunks and, if they're not good enough, a rewriter LLM rephrases the query and tries again. Up to two rounds. No manual intervention needed.

---

## How it works

1. You ask a question
2. The system does a hybrid search (dense embeddings + BM25) and grabs the top 20 chunks
3. A cross-encoder reranker re-orders them and keeps the top 5
4. A critic LLM scores how relevant those chunks are (0–1)
5. If the score is ≥ 0.7 → generate the answer
6. If not, a rewriter LLM produces a better query and we go back to step 2
7. After at most 2 loops, either generate the best answer we have or return a polite fallback

The whole thing is async, so multiple users can hit it at the same time without things piling up.

---

## Stack

| Layer | What's used |
|---|---|
| Frontend | React + Tailwind |
| Backend API | FastAPI |
| Orchestration | LangGraph (state machine with conditional edges) |
| Vector DB | Qdrant (hybrid dense + sparse search) |
| LLM | Ollama running Llama 3.2 3B locally |
| Embeddings | MiniLM (384-dim dense) + BM25 (sparse) |
| Reranker | BGE cross-encoder |
| Async ingestion | Celery + Redis |
| Caching | Redis |
| Observability | Prometheus + Grafana |

---

## Project structure

```
AutoRAG/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI entry point
│       ├── graph.py             # LangGraph reflexion loop
│       ├── retriever.py         # Hybrid search
│       ├── reranker.py          # BGE cross-encoder
│       ├── critic.py            # Relevance scoring
│       ├── rewriter.py          # Query rewriting
│       ├── generator.py         # Final answer generation
│       ├── embeddings.py        # Dense embeddings (MiniLM)
│       ├── sparse.py            # Sparse vectors (BM25)
│       ├── qdrant_client.py     # Qdrant helpers
│       ├── ingestion_tasks.py   # Celery tasks
│       ├── chunking.py          # Text splitting
│       ├── celery_app.py        # Celery setup
│       ├── config.py            # Settings
│       └── state.py             # LangGraph state definition
├── frontend/
│   └── src/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       └── App.jsx
├── grafana/
├── prometheus/
├── docker-compose.yml
└── requirements.txt
```

---
Architecture :
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Browser                               │
│                         (React + Tailwind Frontend)                        │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    │ HTTP (REST API)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Gateway (Backend)                        │
│                                                                             │
│  • Receives user queries and file uploads                                  │
│  • Validates requests (Pydantic)                                           │
│  • Spawns the LangGraph reflexion loop                                     │
│  • Exposes Prometheus metrics and OpenAPI docs                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph Reflexion Loop                           │
│                                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌───────────────┐      │
│   │ Retrieve │───▶│  Rerank  │───▶│  Critic  │───▶│  Generate or  │      │
│   │ (hybrid) │    │ (BGE)    │    │ (LLM)    │    │   Rewrite     │      │
│   └──────────┘    └──────────┘    └────┬─────┘    └───────────────┘      │
│                                         │                                   │
│                           if score < 0.7 ──────────────────────────┐      │
│                                         │                          │      │
│                                         ▼                          │      │
│                              ┌───────────────────┐                 │      │
│                              │ Query Rewriter    │                 │      │
│                              │ (LLM – rewrites   │                 │      │
│                              │  query to improve │                 │      │
│                              │  retrieval)       │                 │      │
│                              └─────────┬─────────┘                 │      │
│                                        │                           │      │
│                                        └───────────────────────────┘      │
│                                             (loop back to Retrieve)       │
│                                                                             │
│   Max loops: 2                                                            │
│   Fallback: polite "can't answer" message                                  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────┐
│      Qdrant         │ │      Ollama         │ │        Redis            │
│   (Vector DB)       │ │   (LLM Server)      │ │   (Cache + Broker)      │
│                     │ │                     │ │                         │
│  • Stores dense +   │ │  • llama3.2:3b      │ │  • Embedding cache      │
│    sparse vectors   │ │  • Used for:        │ │  • Query result cache   │
│  • Hybrid search    │ │    - Critic         │ │  • Celery message broker│
│  • Payload storage  │ │    - Rewriter       │ │  • Session storage      │
│                     │ │    - Generator      │ │                         │
└─────────────────────┘ └─────────────────────┘ └─────────────────────────┘
                                    │
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Celery Worker                                 │
│                                                                             │
│  • Listens to Redis queue                                                  │
│  • Processes ingestion tasks:                                              │
│    1. Chunk documents (RecursiveCharacterTextSplitter)                     │
│    2. Generate dense embeddings (MiniLM)                                  │
│    3. Generate sparse vectors (BM25)                                      │
│    4. Upsert to Qdrant                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

## Getting started

Requirements: Docker and Docker Compose. That's it.

```bash
git clone <your-repo-url>
cd AutoRAG
docker-compose up --build
```

Wait for Ollama to finish pulling the model (first run only, takes a minute or two).

Then open `http://localhost:5173` in your browser.

**To use it:**
- Click the paperclip icon to upload a PDF or text file
- Wait a moment for ingestion to finish in the background
- Ask a question — the reflexion loop kicks in automatically if needed

No environment variables need to be changed for basic local usage.

---


## Observability

Prometheus scrapes metrics automatically. Grafana dashboards are pre-configured and available at `http://localhost:3000`.

Tracked metrics include request count, latency, reflexion loop count, critic scores, and cache hit rate.

---

## Why LangGraph instead of a simple loop?

LangGraph gives you an explicit state machine with conditional edges, which makes the reflexion loop easy to inspect and debug. You can see exactly which node the system is in at any point, and adding new steps (like a second critic or a fallback retriever) is straightforward without untangling spaghetti chains.

---

