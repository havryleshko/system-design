BEGIN;

ALTER TABLE public.clarifier_sessions
  ADD COLUMN IF NOT EXISTS final_status text NULL; -- ready|draft

COMMIT;


