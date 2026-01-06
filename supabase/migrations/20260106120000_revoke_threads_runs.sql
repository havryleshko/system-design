BEGIN;

-- Defense-in-depth: prevent browser-side Supabase roles from accessing internal tables.
-- These tables are meant to be accessed via the backend service, not directly from clients.
REVOKE ALL PRIVILEGES ON TABLE public.threads FROM anon, authenticated;
REVOKE ALL PRIVILEGES ON TABLE public.runs FROM anon, authenticated;

COMMIT;


