# Intelligent Robot Vacuum Customer Service Agent

> Enterprise-grade intelligent customer service system powered by LangGraph ReAct Agent. Hybrid retrieval, tool orchestration, evaluation framework, multi-user isolation, Docker deployment.

[中文文档](README.md)

---

## Architecture

```
├── agent/                      # Agent core
│   ├── react_agent.py          # ReAct Agent (LangGraph create_agent)
│   └── tools/
│       ├── agent_tools.py      # 7 tools (real user data integration)
│       └── middleware.py        # Middleware: monitoring/logging/dynamic prompt/retry
├── rag/                        # RAG retrieval engine
│   ├── hybrid_retriever.py     # BM25 + Vector hybrid search + RRF fusion + Cross-encoder rerank
│   ├── rag_service.py          # Retrieval service (retrieval decoupled from LLM summarization)
│   └── vector_store.py         # ChromaDB vector store + document management
├── model/
│   └── factory.py              # DeepSeek + BGE Embedding factory (lazy loading)
├── storage/
│   └── conversation_store.py   # SQLite user management + conversation persistence (multi-user)
├── evaluate/                   # Evaluation framework
│   ├── cases.py                # 30 test cases across 7 categories
│   ├── golden_rag.py           # RAG retrieval ground truth (20 queries)
│   ├── runner.py               # Batch execution + trace collection
│   ├── judge.py                # LLM-as-judge with 4 scoring dimensions
│   ├── metrics.py              # Summary stats + baseline diff
│   └── run.py                  # One-click entry point
├── utils/                      # Config, logging, file handling, prompt loading
├── config/                     # YAML configuration files
├── prompts/                    # Prompt templates
├── data/                       # Knowledge base files + external data CSV
├── Dockerfile                  # Docker image build
├── docker-compose.yml          # Docker Compose orchestration
└── app.py                      # Streamlit frontend (with login/register)
```

## Key Features

### RAG Retrieval Pipeline

| Stage | Technology |
|-------|-----------|
| Document loading | PyPDFLoader / TextLoader |
| Text splitting | RecursiveCharacterTextSplitter (200/20) |
| Embedding | BAAI/bge-small-zh-v1.5 |
| Vector store | ChromaDB with MD5 dedup and auto-load on startup |
| Keyword search | BM25 (rank-bm25), character-level tokenization for Chinese |
| Hybrid fusion | Reciprocal Rank Fusion (RRF), k=60 |
| Reranking | BAAI/bge-reranker-v2-m3 Cross-encoder (graceful fallback when offline) |
| Output | Raw reference documents returned directly; Agent synthesizes |

### Agent Engine

- **ReAct loop**: LangGraph `create_agent` drives Think → Act → Observe → Re-think
- **7 tools**: `rag_search` / `get_weather` / `get_user_location` / `get_user_id` / `get_current_month` / `fetch_external_data` / `fill_context_for_report`
- **Dynamic prompt switching**: Report scenarios auto-switch to specialized prompt
- **Enterprise retry**: Exponential backoff + jitter; `TransientAPIError` distinguishes transient vs permanent failures
- **Context compaction**: LLM-based summary compression when messages exceed 20

### Multi-User System

- **Registration & login**: Independent account system with PBKDF2 password hashing
- **Conversation isolation**: Each user sees only their own conversations via `WHERE user_id = ?`
- **Real user data**: `get_user_id` returns actual logged-in user ID; `get_current_month` returns real current month
- **City geolocation**: Client IP auto-detection + sidebar manual picker fallback. Priority: manual > IP > default

### Evaluation Framework

```
By scenario:
  Edge cases     
  Maintenance    
  Troubleshooting 
  Multi-tool       
  Report gen      
  Weather+care     
  Purchase advice 
```

```bash
python -m evaluate.run              # Full agent eval
python -m evaluate.run --baseline    # Save as baseline
python -m evaluate.run --rag-only    # RAG-only retrieval eval
```

### Engineering

- **Docker deployment**: One-command `docker build`, volume-mounted persistence
- **Conversation persistence**: SQLite, multi-session with auto-titling, per-user scoping
- **KB management**: Auto-load on startup, in-page upload, MD5 dedup
- **Log rotation**: RotatingFileHandler, 10MB per file
- **Lazy initialization**: RAG service, Embedding, Reranker, ChatModel all deferred

## Quick Start

### Local Development

**Prerequisites**

- Python 3.12+
- Windows / macOS / Linux

**Installation**

```bash
git clone <repo-url> && cd intelligent-customer-agent
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Configuration**

`config/rag.yml`

```yaml
chat_model_name: deepseek-v4-flash
embedding_model_name: BAAI/bge-small-zh-v1.5
base_url: https://api.deepseek.com
```

`config/agent.yml`

```yaml
gaodekey: <your Amap API Key>    # https://lbs.amap.com/
default_city: Guangzhou
```

**Environment variables**

```bash
export DEEPSEEK_API_KEY=<your-key>   # Windows: set DEEPSEEK_API_KEY=xxx
```

**Initialize Knowledge Base**

Files in `data/` are auto-loaded on first startup. Manual alternative:

```bash
python rag/vector_store.py
```

**Launch**

```bash
streamlit run app.py
```

### Docker Deployment

```bash
# Build image
docker build -t customer-agent .

# Run container
docker run -d --name customer-agent --restart unless-stopped \
  -p 8501:8501 \
  -e DEEPSEEK_API_KEY=<your-key> \
  -e GAODE_KEY=<your-gaode-key> \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/storage:/app/storage \
  -v $(pwd)/data:/app/data \
  customer-agent

# Or via Docker Compose
# 1. Create .env file with DEEPSEEK_API_KEY and GAODE_KEY
# 2. docker compose up -d
```

Visit `http://<server-ip>:8501`. Register an account on first visit.

### Run Evaluation

```bash
python -m evaluate.run              # Full 30-case evaluation
python -m evaluate.run --baseline    # Set current results as baseline
python -m evaluate.run --rag-only    # RAG retrieval eval only
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph (create_agent) |
| LLM | DeepSeek V4 (OpenAI-compatible API) |
| Embedding | BAAI/bge-small-zh-v1.5 |
| Vector DB | ChromaDB |
| Keyword Search | BM25 (rank-bm25) |
| Reranking | BAAI/bge-reranker-v2-m3 |
| Frontend | Streamlit |
| Persistence | SQLite (users + conversations) |
| External API | Amap (weather + IP geolocation) |
| Deployment | Docker + Docker Compose |
| Logging | RotatingFileHandler |

## Interview Talking Points

Topics you can discuss in depth around this project:

- **Why RRF over score-weighted fusion?** — BM25 and vector scores are not on the same scale. RRF relies solely on rank position, naturally solving normalization.
- **Is ReAct built into the LLM or the framework?** — Three-layer collaboration: LLM function calling × System Prompt × LangGraph StateGraph execution loop.
- **Why decouple retrieval from generation?** — Tools should not invoke LLM summarization internally. Return raw documents and let the Agent synthesize, saving tokens with no information loss.
- **How are tool failures handled?** — `TransientAPIError` marks retryable errors → middleware exponential backoff → permanent failures returned to Agent for ReAct re-planning.
- **How is the evaluation system designed?** — 30 cases × LLM-as-judge × 8 failure categories × baseline comparison, not just pass rate.
- **How is context managed?** — LLM summarization compresses overflow messages, preserving key info (identity, preferences, intent) while discarding redundant steps.
- **How is multi-user isolation implemented?** — `users` table + `conversations.user_id` foreign key, all queries scoped by user ID.
- **How are tool data sources made real?** — `get_user_id` reads actual logged-in user; `get_current_month` returns real date; `fetch_external_data` integrates with CSV external data source with demo fallback.

## License

MIT
