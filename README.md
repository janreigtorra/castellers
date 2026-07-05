# Xiquet.cat — AI Assistant for Casteller Knowledge

**Xiquet.cat** is a Catalan-language AI assistant that makes the world of castells accessible through natural conversation. It answers questions about colles, diades, castells, actuacions, puntuacions, concursos, and casteller history — combining structured database queries with semantic search over curated documents.

## What Problem Does It Solve?

Casteller knowledge is rich but scattered:

- **Structured data** lives in the [CCCC](https://www.cccc.cat) database (thousands of diades, castells, and puntuacions across decades).
- **Conceptual knowledge** (history, terminology, culture) is spread across articles, wikis, and the *Revista Castells*.

Finding answers today means knowing where to look, how to filter, and how to interpret raw tables. Xiquet bridges that gap: users ask questions in Catalan ("Quants 3d10fm han descarregat els Minyons de Terrassa?") and get conversational answers backed by real data and sources.

The project is non-profit, self-funded, and still evolving. It may occasionally miss or misinterpret a question — feedback is welcome via the contact page.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         User (Catalan questions)                         │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
┌─────────────────────────────────▼────────────────────────────────────────┐
│  Frontend — React (Vercel)                                               │
│  Chat UI · Session management · Entity chips · Tables · Joc del Mocador  │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │ REST API (JWT)
┌─────────────────────────────────▼────────────────────────────────────────┐
│  Backend — FastAPI (Fly.io)                                              │
│  main.py · auth · chat orchestration · Stripe subscriptions              │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Xiquet Agent (xiquet/agent.py)                                     │ │
│  │  Router → Entity extraction → direct | RAG | SQL | hybrid handlers  │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└───────────────┬──────────────────────────────┬─────────────────────────────┘
                │                              │
┌───────────────▼──────────────┐  ┌──────────▼────────────────────────────┐
│  Supabase PostgreSQL         │  │  External LLM APIs                      │
│  · Auth + user profiles      │  │  SambaNova (primary), OpenAI, Groq,     │
│  · Chat sessions/messages    │  │  Anthropic, Gemini, DeepSeek, etc.      │
│  · CCCC events & castells    │  │  OpenAI embeddings (text-embedding-3)   │
│  · pgvector RAG chunks       │  └─────────────────────────────────────────┘
└──────────────────────────────┘
```

### Data Sources

| Source | Used for | Storage |
|--------|----------|---------|
| CCCC database | Diades, castells, puntuacions, colles | Supabase PostgreSQL (`events`, `castells`, etc.) |
| Curated text chunks | Conceptual / historical knowledge | `castellers_info_chunks` table with pgvector embeddings |
| Revista Castells scraper | Magazine articles | Indexed into the same RAG table |
| Colles metadata | Colla profiles, colors, founding years | PostgreSQL + static JSON |

---

## AI Architecture (`xiquet/agent.py`)

The core intelligence lives in the `Xiquet` class. Every question goes through a multi-stage pipeline:

```
Question
   │
   ├─ Guardrails (off-topic, meta-LLM, non-casteller domains)
   ├─ Language check (Catalan only)
   ├─ Length limit (basic: 35 tokens, premium: 200 tokens)
   │
   ▼
Entity extraction (heuristics + fuzzy matching)
   · colles, castells, anys, llocs, diades, gamma, concurs fields
   · Pre-selected entities from the UI override extraction
   · Previous-message context for follow-ups ("I els de Valls?")
   │
   ▼
LLM Router (structured output via FirstCallResponseFormat)
   · Chooses route: direct | rag | sql
   · Pattern overrides (IS_SQL_QUERY_PATTERNS) can upgrade rag → sql
   · Fuzzy matching assigns sql_query_type (millor_diada, castell_historia, …)
   │
   ▼
Route handler
   ├─ direct  → canned response (general / off-topic questions)
   ├─ rag     → semantic search + LLM narrative answer
   ├─ sql     → parameterized query + table + LLM summary
   └─ hybrid  → RAG + SQL when ≥3 entity dimensions are detected
   │
   ▼
Fallbacks
   · SQL with no results → retry as RAG
   · "No tinc informació" on follow-up → merge entities, retry SQL custom
```

### Routing Modes

| Route | When | Handler |
|-------|------|---------|
| **direct** | Very general or non-casteller questions | Returns `direct_response` from the router LLM |
| **rag** | Descriptive / historical / conceptual questions | `handle_rag()` — retrieval + generation |
| **sql** | Quantitative questions with grounding entities | `handle_sql()` — query DB, format table, summarize |
| **hybrid** | RAG route but rich entity context (≥3 dimensions) | `handle_hybrid_rag_sql()` — combines both sources |

### SQL Path (`xiquet/llm_sql_v2.py`)

Instead of generating raw SQL with an LLM, `LLMSQLGeneratorV2` builds **parameterized queries** from extracted entities and a classified `sql_query_type`:

- `millor_diada`, `millor_castell`, `castell_historia`, `castells_list`
- `first_castell`, `year_summary`, `concurs_ranking`, `concurs_history`
- `colles`, `location_actuations`, `custom` (open-ended)

Results are organized per query type, capped for the frontend table (`SQL_RESULT_LIMIT = 40`), and a subset is fed to the LLM for a natural-language summary. Structured `table_data` is returned alongside the narrative.

### RAG Path (`xiquet/rag.py`)

Query-time retrieval uses a **hybrid search** over `castellers_info_chunks`:

1. **Vector search** — OpenAI `text-embedding-3-small` embeddings stored in Supabase pgvector (IVFFlat index)
2. **BM25 / full-text** — PostgreSQL GIN index for keyword matching
3. **Metadata filtering** — chunks filtered by extracted colles and years
4. **Reranking** — `rerank_rag_results()` scores and reorders candidates
5. **Generation** — top chunks passed to the response LLM with strict Catalan instructions

Indexing (offline) is handled by `database_pipeline/load_castellers_info_chunks.py`, which embeds chunks from `data_basic/data_to_embed/`.

### Entity Extraction (`xiquet/utility_functions.py`)

Before the LLM router runs, heuristic extractors scan the question for:

- Colla names (fuzzy match against the full colles catalog)
- Castell codes and statuses (Descarregat, Carregat, Intent…)
- Years, year ranges, and Catalan number words ("noranta", "vuitanta")
- Locations, diada names, gamma keywords (7, 8, 9, extra…)
- Concurs editions, jornades, and positions

The router LLM refines and validates these entities using structured output (`FirstCallResponseFormat`).

### Models in Use

Configured in `agent.py` (swap via `provider:model` strings):

| Role | Default model |
|------|---------------|
| Router + entity extraction | `sambanova:gpt-oss-120b` |
| SQL / direct responses | `sambanova:Meta-Llama-3.3-70B-Instruct` |
| RAG responses | `sambanova:Meta-Llama-3.3-70B-Instruct` |

---

## AI Integration

### LLM Provider Layer (`xiquet/llm_function.py` + `llm_providers/`)

All LLM calls go through a single `llm_call()` function with a `provider:model` format:

```python
llm_call(prompt, model="sambanova:Meta-Llama-3.3-70B-Instruct", response_format=FirstCallResponseFormat)
```

Supported providers (each in its own module under `llm_providers/`):

- **SambaNova** (production default)
- OpenAI, Anthropic, Groq, Gemini, DeepSeek, Cerebras, Ollama (local)

The `LLMManager` dispatches to the right provider. API keys are read from environment variables (`SAMBANOVA_API_KEY`, `OPENAI_API_KEY`, etc.).

**Guardrails** (`is_guardrail_violation`) block meta-LLM questions, programming requests, and clearly off-topic domains before any routing happens.

### Chat API Flow (two-phase, async)

The frontend uses a two-phase pattern for responsive UX:

1. **`POST /api/chat/start`** — creates a pending message, runs routing in a background task
2. **`GET /api/chat/status/{message_id}`** — polls until `entities_ready` (shows entity chips) then `complete` (full answer + table)

A synchronous shortcut also exists:

- **`POST /api/chat`** — full pipeline in one request
- **`POST /api/chat/route`** — routing + entities only (no answer generation)

Responses include `route_used`, `identified_entities`, `table_data`, and `response_time_ms`. Messages and sessions persist in Supabase with Row Level Security.

### Embeddings Pipeline

| Step | Module | Details |
|------|--------|---------|
| Chunk creation | `database_pipeline/revista_castells_to_chunks.py`, scrapers | JSON chunks with metadata (colles, years, categories) |
| Indexing | `database_pipeline/load_castellers_info_chunks.py` | OpenAI embeddings → `castellers_info_chunks` in Supabase |
| Query-time search | `xiquet/rag.py` | Hybrid vector + BM25, reranking, metadata filter |
| Warmup | `main.py` startup | Preloads entity cache, embedding model, and RAG indexes |

### Rate Limiting & Subscriptions

- **Basic plan**: 10 questions/hour, 35-token question limit
- **Premium plan** (Stripe, 1.99€/month): unlimited questions, 200-token limit

---

## Project Structure

```
castellers/
├── backend/
│   ├── main.py                          # FastAPI server, chat endpoints, admin APIs
│   ├── auth_service.py                  # Supabase JWT authentication
│   ├── database_service.py              # Chat sessions, messages, profiles
│   ├── xiquet/                          # AI agent package
│   │   ├── agent.py                     # Xiquet class — routing & handlers
│   │   ├── llm_function.py              # Multi-provider LLM interface
│   │   ├── llm_sql_v2.py                # Parameterized SQL generation
│   │   ├── rag.py                         # Hybrid retrieval + reranking
│   │   ├── utility_functions.py         # Entity extraction & cache
│   │   └── util_dics.py                   # SQL patterns, mappings, guardrails
│   ├── llm_providers/                   # Provider implementations
│   ├── joc_del_mocador/                 # Casteller trivia game backend
│   ├── database_pipeline/                 # Data loading, scraping, RAG indexing
│   ├── data_basic/                        # Static JSON data & chunks to embed
│   ├── migrations/                        # SQL migrations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js                       # Routing (chat, game, colles, admin…)
│   │   ├── components/
│   │   │   ├── ChatInterface.js         # Main chat UI
│   │   │   ├── SessionManager.js        # Conversation history
│   │   │   ├── JocDelMocador/           # Trivia game
│   │   │   ├── CollesCastelleres.js     # Colla directory
│   │   │   └── CompararDiades.js        # Diada comparison tool
│   │   ├── apiService.js                # Backend API client
│   │   └── supabaseClient.js            # Auth client
│   └── package.json
├── database_pipeline/                     # Shared SQL schemas
├── docker/                                # Dockerfiles
├── scrapers/                              # Wiki / events scrapers
├── docker-compose.yml                     # Local dev (backend + frontend)
└── Makefile
```

---

## Technology Stack

### Backend
- **FastAPI** + **Uvicorn** — async REST API
- **Supabase** — authentication, PostgreSQL, pgvector
- **psycopg2** — connection pooling for SQL queries
- **Stripe** — premium subscriptions
- **rapidfuzz** — fuzzy entity matching

### Frontend
- **React** (Create React App) — SPA with client-side routing
- **Axios** — API communication
- **Supabase JS** — client-side auth

### AI / ML
- **SambaNova** — primary LLM provider (routing + generation)
- **OpenAI** — embeddings (`text-embedding-3-small`) for RAG
- **pgvector** — vector similarity search in PostgreSQL
- **Pydantic** — structured LLM output (`FirstCallResponseFormat`)

### Infrastructure
- **Fly.io** — backend hosting (Paris region)
- **Vercel** — frontend hosting
- **Docker Compose** — local development

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- `.env` file at project root with Supabase and LLM API keys (see [Environment Configuration](#environment-configuration))

### Development
```bash
make dev

# Access:
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

### Other Commands
```bash
make down      # Stop services
make logs      # Tail all logs
make migrate   # Run database migrations
make clean     # Remove containers and volumes
```

---

## API Endpoints

### Chat
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat/start` | Start async processing (returns `message_id`) |
| `GET` | `/api/chat/status/{id}` | Poll for entities and final response |
| `POST` | `/api/chat` | Synchronous full chat |
| `POST` | `/api/chat/route` | Route + entities only |
| `GET` | `/api/chat/history` | Message history for a session |

### Sessions & Auth
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/sessions` | Create session |
| `GET` | `/api/sessions` | List user sessions |
| `PUT` | `/api/sessions/{id}` | Update session |
| `DELETE` | `/api/sessions/{id}` | Delete session |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/register` | Register |

### Data & Features
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/colles` | List colles |
| `GET` | `/api/colles/{id}` | Colla detail |
| `GET` | `/api/diades` | Diades listing |
| `GET` | `/api/joc-del-mocador/questions` | Trivia questions |
| `GET` | `/api/entities/options` | Entity autocomplete options |

### Subscriptions
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/subscription/create-checkout` | Stripe checkout |
| `GET` | `/api/subscription/status` | Current plan |

---

## Environment Configuration

### Backend (`.env`)
```bash
# Supabase
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_JWT_SECRET=...

# LLM providers (at minimum SAMBANOVA + OPENAI for embeddings)
SAMBANOVA_API_KEY=...
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...

# Stripe (optional, for premium)
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PREMIUM_PRICE_ID=price_...

# App
FRONTEND_URL=https://xiquet.cat
CORS_ORIGINS=https://xiquet.cat,https://www.xiquet.cat
```

### Frontend (`.env` or docker-compose environment)
```bash
REACT_APP_SUPABASE_URL=https://...
REACT_APP_SUPABASE_ANON_KEY=eyJ...
REACT_APP_API_URL=http://localhost:8000
```

---

## Database Schema

### Chat (Supabase)
- **`profiles`** — user metadata, subscription tier
- **`chat_sessions`** — conversation sessions per user
- **`chat_messages`** — messages with `route_used`, `identified_entities`, response metadata
- **`pending_messages`** — async chat processing state

### Casteller Data (PostgreSQL)
- Events, castells, puntuacions, colles — loaded from CCCC via `database_pipeline/`
- **`castellers_info_chunks`** — RAG document chunks with `combined_embedding` (pgvector)

### Security
- Row Level Security on all user-facing tables
- JWT validation on every authenticated endpoint
- CORS restricted to known frontend origins

---

## Deployment

| Component | Platform | Config |
|-----------|----------|--------|
| Backend | Fly.io | `backend/fly.toml` — runs migrations on deploy |
| Frontend | Vercel | `frontend/vercel.json` — CRA build |
| Database | Supabase | Managed PostgreSQL with pgvector |

```bash
# Local
make dev

# Backend (Fly.io)
cd backend && fly deploy

# Frontend deploys automatically via Vercel on push
```

---

## Key Features

- Conversational casteller Q&A in Catalan
- Multi-route AI (SQL for stats, RAG for knowledge, hybrid for complex queries)
- Interactive entity chips (colles, castells, years) before the answer arrives
- Structured data tables alongside narrative answers
- Persistent chat sessions with follow-up context
- Colla directory, diada comparison, and trivia game (*Joc del Mocador*)
- Premium subscription for unlimited usage
- Admin tools for data sync, scraping, and RAG re-indexing

---

**Xiquet.cat** — casteller knowledge, one question at a time.
