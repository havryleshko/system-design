BEGIN;

ALTER TABLE public.runs
  ADD COLUMN IF NOT EXISTS clarifier_session_id uuid NULL,
  ADD COLUMN IF NOT EXISTS clarifier_summary text NULL;

CREATE INDEX IF NOT EXISTS idx_runs_clarifier_session_id
  ON public.runs(clarifier_session_id);

COMMIT;


