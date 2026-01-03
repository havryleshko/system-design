# Backend (FastAPI + LangGraph)

LangGraph-powered API that orchestrates the system-design agent, handles Supabase-authenticated requests, and persists state/memory in Postgres.

## Requirements
- Python 3.12+
- Postgres database URL for LangGraph store/checkpointer (Supabase Postgres works)

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
- **LangGraph Studio / langgraph dev**:
  ```bash
  langgraph dev
  # uses langgraph.json (graph: system_design_agent, env: .env, auth: app.auth:auth)
  ```

## Environment variables
See `env.example` for the canonical list. Key values:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | LLM calls |
| `LANGGRAPH_PG_URL` | Required Postgres URL for LangGraph store/checkpointer |
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
- `LANGGRAPH_PG_URL` is mandatory. The backend calls `langgraph-checkpoint-postgres`’s `setup()` on startup to validate connectivity.
- Memory/checkpointer partitioning depends on run metadata: always pass `user_id`, `thread_id`, and `run_id` when triggering runs in Studio or via the API.

## Deploying
- **VM (recommended for MVP)**: run FastAPI behind HTTPS (Caddy recommended) and set env vars from `env.example`.
- **LangGraph Cloud / Studio** (optional): point to `langgraph.json`; ensure env vars are configured per workspace.

After deploying, hit `/health/checkpointer` to verify database access, then run through `/threads/:id/runs/:run_id/resume` to ensure persistence works end-to-end.

