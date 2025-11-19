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

When this graph runs inside LangGraph Server/LangSmith, a managed Postgres
checkpointer is injected automatically. No extra environment variables are
required—the `graph = builder.compile()` call is enough to enable durable
clarifier resumes and backtracking.

For local development you can still point LangGraph at your own Postgres by
setting `LANGGRAPH_PG_URL` before launching `langgraph dev`, but production
deployments are expected to rely on the built-in storage.

After each deploy, open `/chat`, trigger a clarifier question, submit the
answers, and verify the `POST /threads/{id}/runs/{run_id}/resume` call succeeds.
