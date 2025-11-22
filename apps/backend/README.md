# Backend Auth Configuration

This service validates Supabase-issued JWTs before forwarding LangGraph
requests. Two environment variables must be present in every deployment:

- `SUPABASE_JWKS_URL` &mdash; set to the Supabase project's JWKS endpoint,
  e.g. `https://<project-ref>.supabase.co/auth/v1/certs`.
- `SUPABASE_ANON_KEY` &mdash; the project's anonymous API key.
- `SUPABASE_JWT_SECRET` &mdash; fallback HMAC secret used if JWKS fetching is
  unavailable (copy it from Supabase Settings → API → JWT secret).

The backend sends the anon key as the `apikey` header when fetching the JWKS
document. If either variable is missing or incorrect, authentication fails
with `401 Authentication not configured`. Make sure to update these values in
LangSmith (and any other runtime) whenever you rotate Supabase credentials.

## LangGraph Checkpointer (Clarifier Resume)

Persistent checkpoints are required and **`LANGGRAPH_PG_URL` is mandatory**.
The app now raises at import time if this variable is missing, so production
deployments must supply a working Postgres URL.

1. Provision a Postgres instance (Supabase works fine) and copy the full
   connection string, e.g. `postgresql://user:pass@host:5432/db`.
2. Set `LANGGRAPH_PG_URL` in every runtime (Render, LangSmith, `langgraph dev`,
   etc.). The backend invokes `langgraph-checkpoint-postgres`'s `.setup()`
   automatically on startup, so there is no manual migration step.
3. (Optional) If several environments share the same database, use separate
   schemas or distinct DBs. A missing/invalid `LANGGRAPH_PG_URL` will now stop
   the process immediately, preventing the clarifier from ever running without
   persistence.
4. After deploying, open `/chat`, trigger a clarifier question, submit the form,
   and ensure `POST /threads/{id}/runs/{run_id}/resume` returns `200`.

