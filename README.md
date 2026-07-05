# ViZ Triage Agent

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](frontend/)
[![LangGraph](https://img.shields.io/badge/LangGraph-pipeline-purple.svg)](app/graph/builder.py)
[![Tests](https://img.shields.io/badge/tests-55%20passing-brightgreen.svg)](tests/)

**Clinical symptom triage co-pilot** built for the Stance Health technical interview — an 11-node LangGraph pipeline with Claude, PostgreSQL history, optional Clerk auth, and MCP-backed medical search.

| | |
|---|---|
| **Repository** | [github.com/vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent) |
| **Frontend** | Next.js 16 · React 19 · Tailwind 4 · Framer Motion |
| **Backend** | FastAPI · LangGraph · Pydantic v2 · SQLAlchemy async |
| **Deploy** | Vercel (UI) + Render / Railway (API) + Neon (DB) |

---

## Table of contents

- [What it does](#what-it-does)
- [Architecture overview](#architecture-overview)
- [LangGraph pipeline](#langgraph-pipeline)
- [Request flow](#request-flow)
- [Production deployment](#production-deployment)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)

---

## What it does

ViZ Triage Agent helps clinicians and patients evaluate symptom narratives through a structured AI pipeline:

1. **Parse** free-text patient messages into clinical signals
2. **Detect red flags** using rules + LLM reasoning
3. **Classify urgency** (emergency, urgent, routine, etc.)
4. **Ground answers** with optional medical search (DuckDuckGo, Tavily, or MCP)
5. **Explain** results in plain language with confidence scores
6. **Persist history** to PostgreSQL when auth is enabled

The **Next.js UI** ships with a virtualized 100-case sidebar, animated LangGraph visual guide, mobile layout, and live execution trace mode.

---

## Architecture overview

The system is a **monorepo** with three runtime processes locally, and **two hosted services** in production (Vercel + Render/Railway).

```mermaid
flowchart TB
    subgraph Client["Browser"]
        UI["ViZ Triage UI<br/>(Next.js 16)"]
    end

    subgraph Vercel["Vercel — frontend"]
        Next["Next.js App Router"]
        Proxy["/api/* rewrite proxy"]
    end

    subgraph Backend["Render / Railway — backend"]
        API["FastAPI + Uvicorn"]
        Graph["LangGraph runner"]
        Auth["Auth layer<br/>none | api_key | clerk"]
    end

    subgraph Data["Data & external services"]
        Neon["Neon PostgreSQL"]
        Claude["Anthropic Claude"]
        Search["Search provider<br/>DuckDuckGo | Tavily | MCP"]
        MCP["MCP server<br/>(optional, separate process)"]
        Clerk["Clerk JWT / JWKS"]
    end

    UI --> Next
    Next --> Proxy
    Proxy -->|"API_BACKEND_URL"| API
    API --> Auth
    Auth --> Graph
    Graph --> Claude
    Graph --> Search
    Search -.->|"SEARCH_PROVIDER=mcp"| MCP
    API --> Neon
    Auth -.->|"AUTH_MODE=clerk"| Clerk
    UI -.->|"optional sign-in"| Clerk
```

| Layer | Technology | Host |
|-------|------------|------|
| **UI** | Next.js 16, React 19, Tailwind 4, Framer Motion | **Vercel** |
| **API** | FastAPI, LangGraph, Pydantic v2 | **Render / Railway / Fly.io** |
| **Database** | PostgreSQL via SQLAlchemy async (`asyncpg`) | **Neon** (recommended) |
| **LLM** | Claude Sonnet (default) | Anthropic API |
| **Search** | DuckDuckGo, Tavily, or MCP | In-process or separate MCP server |
| **Auth** | Clerk JWT (optional) | Clerk + FastAPI JWKS verification |

> **Why two hosts?** Vercel runs the Next.js frontend and rewrites `/api/*` to your backend URL. The FastAPI + LangGraph engine is a long-running Python process and must run on a container/PaaS host — it cannot run as a Vercel serverless function in this architecture.

### Monorepo layout

```mermaid
flowchart LR
    subgraph Repo["triage-agent/"]
        FE["frontend/<br/>Next.js → Vercel"]
        BE["app/<br/>FastAPI → Render"]
        MCP["mcp_server/<br/>optional sidecar"]
        DB["tests/ scripts/<br/>dev tooling"]
    end

    FE -->|"API_BACKEND_URL"| BE
    BE --> MCP
```

---

## LangGraph pipeline

Every triage request flows through an **11-node StateGraph** with one conditional branch after search decision.

```mermaid
flowchart LR
    START((START)) --> parse["1 parse_input"]
    parse --> extract["2 extract_clinical_signals"]
    extract --> norm["3 normalize_symptoms"]
    norm --> red["4 red_flag_detection"]
    red --> urg["5 urgency_classification"]
    urg --> decide["6 search_decision"]

    decide -->|"needs search"| search["7 search_medical_sources"]
    decide -->|"skip search"| merge["8 merge_evidence"]
    search --> merge

    merge --> explain["9 generate_clinical_explanation"]
    explain --> conf["10 confidence_scoring"]
    conf --> build["11 build_structured_response"]
    build --> END((END))
```

| Node | Responsibility |
|------|----------------|
| `parse_input` | Validate and normalize raw patient message |
| `extract_clinical_signals` | LLM structured extraction (symptoms, duration, severity) |
| `normalize_symptoms` | Synonym mapping + canonical symptom names |
| `red_flag_detection` | Rule engine + LLM for emergency indicators |
| `urgency_classification` | Triage level (e.g. emergency, urgent, routine) |
| `search_decision` | Conditional: ground answer with external sources? |
| `search_medical_sources` | DuckDuckGo / Tavily / MCP search |
| `merge_evidence` | Join point — works with or without search results |
| `generate_clinical_explanation` | Patient-facing explanation with citations |
| `confidence_scoring` | Calibrated confidence + disclaimers |
| `build_structured_response` | Final JSON contract for the UI |

**Design highlights**

- **Dependency injection** — nodes are bundled via `NodeBundle`; the graph has no direct LLM/search imports (testable with stubs).
- **Safe degradation** — every path returns a valid triage response; infrastructure errors become structured 500s with request IDs.
- **Trace mode** — `POST /debug` returns full node-by-node execution trace (disabled in production via `DEBUG_ENDPOINT_ENABLED=false`).

---

## Request flow

```mermaid
sequenceDiagram
    participant U as User
    participant N as Next.js (Vercel)
    participant F as FastAPI
    participant G as LangGraph
    participant L as Claude
    participant D as Neon DB

    U->>N: Select case / type message
    N->>F: POST /api/triage (rewrite proxy)
    F->>F: Auth (optional Clerk JWT)
    F->>G: runner.run(patient_id, message)
    loop 11 nodes
        G->>L: Structured LLM calls
        G->>G: Rules + search (if needed)
    end
    G-->>F: GraphState
    F->>D: Persist run (history)
    F-->>N: TriageResponse JSON
    N-->>U: Animated result card
```

The frontend never calls the backend directly from the browser — it uses **same-origin** `/api` paths. Next.js rewrites those to `API_BACKEND_URL`, avoiding CORS issues in dev and production.

---

## Production deployment

### Prerequisites

- GitHub repo: [vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent)
- [Anthropic API key](https://console.anthropic.com)
- [Neon PostgreSQL](https://neon.tech) database URL
- [Vercel](https://vercel.com) account (frontend)
- [Render](https://render.com) or [Railway](https://railway.app) account (backend)

### Step 1 — Deploy backend (Render recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or manually:

1. Create a **Web Service** on [Render](https://render.com) from this repo (**root directory** = repo root, not `frontend/`).
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
4. **Health check path:** `/health`
5. Set environment variables (see [Backend environment variables](#backend-environment-variables)):

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST/neondb?ssl=require
SEARCH_PROVIDER=duckduckgo
AUTH_MODE=none
APP_ENV=production
DEBUG_ENDPOINT_ENABLED=false
RATE_LIMIT_PER_MINUTE=30
CORS_ORIGINS=https://your-app.vercel.app
```

6. Copy the public URL, e.g. `https://triage-api.onrender.com`.

**Alternatives:** use the included `Procfile` (Railway via `railway.toml`) or Fly.io with the same start command.

> For **MCP search** in production, deploy `python -m mcp_server.server` as a second service and set `SEARCH_PROVIDER=mcp` + `MCP_SERVER_URL`. For simplicity, use `SEARCH_PROVIDER=duckduckgo` on Render free tier.

### Step 2 — Deploy frontend (Vercel)

1. Import [github.com/vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent) on [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js** (auto-detected from `frontend/vercel.json`).
4. Add environment variables:

| Variable | Required | Value |
|----------|----------|-------|
| `API_BACKEND_URL` | **Yes** | `https://triage-api.onrender.com` (your backend URL) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | No | `pk_live_...` |
| `CLERK_SECRET_KEY` | No | `sk_live_...` |

5. Deploy.

**CLI alternative:**

```bash
cd frontend
npx vercel
# set API_BACKEND_URL when prompted
npx vercel --prod
```

### Step 3 — Verify

| Check | URL |
|-------|-----|
| UI loads | `https://your-app.vercel.app` |
| Health (via proxy) | `https://your-app.vercel.app/api/health` |
| Cases | `https://your-app.vercel.app/api/cases` |
| Backend direct | `https://triage-api.onrender.com/health` |

After Vercel assigns your domain, update backend `CORS_ORIGINS` to include it (and preview URLs if needed).

### Deployment diagram

```mermaid
flowchart LR
    subgraph GitHub
        Repo["vijayshreepathak/triage-agent"]
    end

    subgraph Vercel
        FE["frontend/<br/>Next.js"]
    end

    subgraph Render
        BE["FastAPI API<br/>uvicorn :PORT"]
    end

    subgraph Cloud
        NeonDB["Neon PostgreSQL"]
        Anthropic["Anthropic API"]
    end

    Repo -->|auto deploy| FE
    Repo -->|auto deploy| BE
    FE -->|"rewrite /api/*"| BE
    BE --> NeonDB
    BE --> Anthropic
```

---

## Local development

### Clone the repository

```bash
git clone https://github.com/vijayshreepathak/triage-agent.git
cd triage-agent
```

### Run the full stack (3 terminals)

```powershell
# Terminal 1 — API
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # add ANTHROPIC_API_KEY, DATABASE_URL
uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — MCP search (optional)
python -m mcp_server.server
# set SEARCH_PROVIDER=mcp in .env

# Terminal 3 — Next.js UI
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

| Service | URL |
|---------|-----|
| **Next.js UI** (primary) | http://localhost:3000 |
| **FastAPI** (API + legacy static UI) | http://127.0.0.1:8000 |
| **MCP server** | http://127.0.0.1:8765/mcp |
| **OpenAPI docs** | http://127.0.0.1:8000/docs |

**Local PostgreSQL (optional):**

```bash
docker compose up -d
# DATABASE_URL=postgresql+asyncpg://triage:triage_secret@localhost:5432/triage
```

---

## Environment variables

### Backend environment variables

Copy `.env.example` → `.env` at the repo root.

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `DATABASE_URL` | Async SQLAlchemy URL | `postgresql+asyncpg://...@neon.tech/neondb?ssl=require` |
| `SEARCH_PROVIDER` | `duckduckgo` \| `tavily` \| `mcp` \| `none` | `duckduckgo` |
| `MCP_SERVER_URL` | When `SEARCH_PROVIDER=mcp` | `http://127.0.0.1:8765/mcp` |
| `AUTH_MODE` | `none` \| `api_key` \| `clerk` | `none` (dev), `clerk` (prod) |
| `CLERK_PUBLISHABLE_KEY` | Clerk public key (backend + UI bootstrap) | `pk_test_...` |
| `CLERK_ISSUER` | Clerk JWT issuer | `https://xxx.clerk.accounts.dev` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,https://app.vercel.app` |
| `DEBUG_ENDPOINT_ENABLED` | Enable `POST /debug` | `true` (dev), `false` (prod) |
| `RATE_LIMIT_PER_MINUTE` | Per-IP rate limit (`0` = off) | `30` |
| `APP_ENV` | Environment label | `dev` / `production` |

Pull Clerk keys automatically:

```bash
npx clerk env pull --file .env
```

### Frontend environment variables

Copy `frontend/.env.example` → `frontend/.env.local`.

| Variable | Description |
|----------|-------------|
| `API_BACKEND_URL` | Backend URL for Next.js rewrites (**required on Vercel**) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk widget (optional) |
| `CLERK_SECRET_KEY` | Clerk server-side middleware (optional) |

### Clerk setup (Next.js + FastAPI)

1. Create an application at [clerk.com](https://clerk.com).
2. Add keys to **both** `.env` (backend) and `frontend/.env.local`.
3. Set `AUTH_MODE=clerk` in backend `.env`.
4. Add your Vercel domain under **Allowed origins** in the Clerk dashboard.
5. Protected routes (`/triage`, `/debug`, `/history`, `/stats`, `/metrics`) require a valid Bearer JWT.

---

## API reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | Open | Liveness, DB + MCP status |
| `GET` | `/config` | Open | Frontend bootstrap (no secrets) |
| `GET` | `/cases` | Open | 100-case interview dataset |
| `POST` | `/triage` | When enabled | Run triage graph |
| `POST` | `/debug` | When enabled | Triage + execution trace |
| `GET` | `/history` | When enabled | Persisted runs |
| `GET` | `/stats` | When enabled | Dashboard aggregates |
| `GET` | `/metrics` | When enabled | JSON metrics snapshot |
| `GET` | `/` | Open | Legacy static test console |

Via Vercel, prefix with `/api` — e.g. `/api/health`, `/api/triage`.

Interactive docs (local backend): http://127.0.0.1:8000/docs

---

## Project structure

```
triage-agent/
├── app/                      # FastAPI + LangGraph backend
│   ├── api/                  # Routes, auth, middleware, CORS
│   ├── graph/                # StateGraph builder + runner
│   ├── nodes/                # 11 pipeline node implementations
│   ├── services/             # Red flags, confidence, metrics, MCP health
│   ├── tools/                # LLM + search provider adapters
│   ├── db/                   # SQLAlchemy models + repository
│   ├── prompts/              # Structured LLM prompt templates
│   └── static/               # Legacy HTML UI + cases.json fallback
├── frontend/                 # Next.js 16 App Router (deploy to Vercel)
│   ├── src/components/       # TriageApp, CaseSidebar, VisualGuideModal, …
│   ├── src/lib/api.ts        # Same-origin /api client
│   ├── next.config.ts        # API rewrite proxy
│   └── vercel.json           # Vercel project settings (region: bom1)
├── mcp_server/               # Standalone MCP medical search server
├── tests/                    # pytest suite (55 tests)
├── scripts/                  # Evaluation utilities
├── render.yaml               # Render Blueprint (backend)
├── railway.toml              # Railway config (backend)
├── Procfile                  # Generic PaaS start command
├── runtime.txt               # Python 3.12.8
├── docker-compose.yml        # Local PostgreSQL
├── requirements.txt
└── .env.example
```

### Frontend features

| Feature | Implementation |
|---------|----------------|
| Virtualized case sidebar | `@tanstack/react-virtual` — all 100 cases scroll smoothly |
| Visual guide modal | Animated LangGraph pipeline tour (Pipeline / Features / Safety tabs) |
| Execution trace | Live node-by-node debug output in sidebar |
| Mobile layout | Bottom nav, responsive grid, touch-friendly controls |
| Dark theme | ViZ Triage branding with Framer Motion transitions |
| Clerk auth | Optional; middleware passthrough when keys unset |
| Connection banner | Surfaces API connectivity issues on load |

---

## Tests

```powershell
# From repo root with venv active
pytest
```

55 tests — forces `AUTH_MODE=none` and in-memory SQLite; no API keys or Postgres required.

**Run evaluation over the full dataset:**

```bash
python scripts/evaluate_dataset.py
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| **"Cannot reach the triage engine"** in UI | Backend not running or wrong `API_BACKEND_URL` | Start uvicorn locally; on Vercel, set `API_BACKEND_URL` to your Render/Railway URL |
| **`/api/health` returns 404 on Vercel** | Root Directory not set to `frontend` | Vercel project settings → Root Directory → `frontend` |
| **CORS errors** (direct API calls) | Missing origin in backend | Add Vercel URL to `CORS_ORIGINS` in backend env |
| **Render cold start timeout** | Free tier spins down | First request may take ~30s; health check wakes the service |
| **`/cases` 503** | External dataset unreachable | Backend falls back to `app/static/data/cases.json` automatically |
| **Auth misconfigured** | `AUTH_MODE=clerk` without keys | Set Clerk keys or use `AUTH_MODE=none` for demo |
| **MCP disconnected** in `/health` | MCP server not running | Start `python -m mcp_server.server` or switch to `SEARCH_PROVIDER=duckduckgo` |

---

## Security notes

- Never commit `.env` or `.env.local` — they are gitignored.
- Set `DEBUG_ENDPOINT_ENABLED=false` in production.
- Rotate any API keys that were exposed during development.
- Use `AUTH_MODE=clerk` or `api_key` before exposing the API publicly.

---

## License
**Author:** [Vijayshree Pathak](https://github.com/vijayshreepathak)
