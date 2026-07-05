# ViZ Triage Agent

**Clinical symptom triage co-pilot** — an 11-node LangGraph pipeline with Claude, PostgreSQL history, optional Clerk auth, and MCP-backed medical search.

**Repository:** [github.com/vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent)

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [LangGraph pipeline](#langgraph-pipeline)
- [Request flow](#request-flow)
- [Production deployment](#production-deployment)
- [Local development](#local-development)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Tests](#tests)

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

Design highlights:

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

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: ViZ Triage Agent"
git branch -M main
git remote add origin https://github.com/vijayshreepathak/triage-agent.git
git push -u origin main
```

### Step 2 — Deploy backend (Render recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Or manually:

1. Create a **Web Service** on [Render](https://render.com) from this repo (root directory = repo root).
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `uvicorn app.api.main:app --host 0.0.0.0 --port $PORT`
4. **Health check path:** `/health`
5. Set environment variables (see [backend env](#backend-env)):

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

**Alternatives:** `Procfile` + Railway (`railway.toml`) or Fly.io with the same start command.

> For **MCP search** in production, deploy `python -m mcp_server.server` as a second service and set `SEARCH_PROVIDER=mcp` + `MCP_SERVER_URL`. For simplicity, use `SEARCH_PROVIDER=duckduckgo` on Render free tier.

### Step 3 — Deploy frontend (Vercel)

1. Import [github.com/vijayshreepathak/triage-agent](https://github.com/vijayshreepathak/triage-agent) on [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Next.js** (auto-detected).
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `API_BACKEND_URL` | `https://triage-api.onrender.com` (your backend URL) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Optional — `pk_live_...` |
| `CLERK_SECRET_KEY` | Optional — `sk_live_...` |

5. Deploy.

**CLI alternative:**

```bash
cd frontend
npx vercel
# set API_BACKEND_URL when prompted
npx vercel --prod
```

### Step 4 — Verify

| Check | URL |
|-------|-----|
| UI loads | `https://your-app.vercel.app` |
| Health (via proxy) | `https://your-app.vercel.app/api/health` |
| Cases | `https://your-app.vercel.app/api/cases` |
| Backend direct | `https://triage-api.onrender.com/health` |

Update backend `CORS_ORIGINS` with your final Vercel domain (including preview URLs if needed).

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

Three terminals for the full stack:

```powershell
# Terminal 1 — API
python -m venv .venv
.venv\Scripts\activate
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

**Local PostgreSQL (optional):**

```bash
docker compose up -d
# DATABASE_URL=postgresql+asyncpg://triage:triage_secret@localhost:5432/triage
```

---

## Environment variables

### Backend (`.env`)

Copy from `.env.example`. Key settings:

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `DATABASE_URL` | Async SQLAlchemy URL | `postgresql+asyncpg://...@neon.tech/neondb?ssl=require` |
| `SEARCH_PROVIDER` | `duckduckgo` \| `tavily` \| `mcp` \| `none` | `duckduckgo` |
| `MCP_SERVER_URL` | When `SEARCH_PROVIDER=mcp` | `http://127.0.0.1:8765/mcp` |
| `AUTH_MODE` | `none` \| `api_key` \| `clerk` | `none` |
| `CLERK_PUBLISHABLE_KEY` | Clerk public key | `pk_test_...` |
| `CLERK_ISSUER` | Clerk JWT issuer | `https://xxx.clerk.accounts.dev` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000,https://app.vercel.app` |
| `DEBUG_ENDPOINT_ENABLED` | Enable `POST /debug` | `true` (dev), `false` (prod) |
| `RATE_LIMIT_PER_MINUTE` | Per-IP rate limit (0 = off) | `30` |

Pull Clerk keys automatically:

```bash
npx clerk env pull --file .env
```

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `API_BACKEND_URL` | Backend URL for Next.js rewrites (required for prod on Vercel) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk widget (optional) |
| `CLERK_SECRET_KEY` | Clerk server-side (optional) |

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
│   └── vercel.json           # Vercel project settings
├── mcp_server/               # Standalone MCP medical search server
├── tests/                    # pytest suite (55+ tests)
├── scripts/                  # Evaluation utilities
├── render.yaml               # Render Blueprint (backend)
├── railway.toml              # Railway config (backend)
├── Procfile                  # Generic PaaS start command
├── docker-compose.yml        # Local PostgreSQL
├── requirements.txt
└── .env.example
```

### Frontend features

- **Virtualized case sidebar** — all 100 cases via `@tanstack/react-virtual`
- **Visual guide modal** — animated LangGraph pipeline tour
- **Mobile layout** — bottom nav, responsive grid
- **Dark theme** — ViZ Triage branding
- **Clerk auth** — optional; passthrough when keys unset
- **Connection banner** — surfaces API connectivity issues

---

## Tests

```powershell
# From repo root with venv active
pytest
```

Tests force `AUTH_MODE=none` and in-memory SQLite — no API keys or Postgres required.

---

## License

Built for the Stance Health technical interview. See repository for usage terms.
 
 