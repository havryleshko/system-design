# Backend (FastAPI + LangGraph)

LangGraph-powered FastAPI API that:
- accepts Supabase-authenticated requests
- runs a multi-stage LangGraph pipeline (planner/research/design/critic/evals)
- persists state with a Postgres checkpointer/store
- returns a minimal UI contract: `values = { goal, blueprint, output }`

## Requirements
- Python 3.12+
- Postgres database URL (Supabase Postgres works)

## Setup
1. Copy env template: `cp env.example .env`
2. Create a virtualenv and install deps:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. optional: run migrations located in `supabase/migrations`.

## Running locally
- **FastAPI dev server** (recommended for frontend integration):
  ```bash
  make run
  # uvicorn app.main:app --reload
  ```
  - health endpoints: `GET /`, `GET /health/checkpointer`

- **LangGraph Studio / langgraph dev** (optional):
  ```bash
  langgraph dev
  # uses langgraph.json (graph: system_design_agent, env: .env, auth: app.auth:auth)
  ```

## Environment variables
See `env.example` for the canonical list. Key values:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | LLM calls |
| `LANGGRAPH_PG_URL` | Required Postgres URL for LangGraph checkpointer/store and threads/runs persistence |
| `SUPABASE_ANON_KEY` | Sent as `apikey` header when fetching JWKS |
| `SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL` | Used to derive JWKS URL if not explicitly provided |
| `SUPABASE_JWKS_URL` | Explicit JWKS endpoint (`https://<project>.supabase.co/auth/v1/.well-known/jwks.json`) |
| `SUPABASE_JWT_SECRET` | Optional HS256 fallback when JWKS unavailable |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional for Supabase admin ops |
| `TAVILY_API_KEY`, `GITHUB_TOKEN` | Optional enrichment providers |

### Supabase auth flow
- Incoming requests must send a Supabase JWT in the `Authorization: Bearer <token>` header.
- Tokens are verified using `SUPABASE_JWT_SECRET` (HS256) or JWKS (ES256). Missing configuration results in `401 Authentication not configured`.

### LangGraph persistence
- `LANGGRAPH_PG_URL` is mandatory. `/health/checkpointer` verifies DB connectivity.
- Persistence depends on `thread_id` (checkpointer key). The backend resets run-scoped fields at run start to avoid stale state reuse.

## Deploying
- **VM (recommended for MVP)**: run FastAPI behind HTTPS (Caddy recommended) and set env vars from `env.example`.
 

