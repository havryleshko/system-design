BEGIN;

-- -----------------------------------------------------------------------------
-- Clarifier chat persistence (DB-backed)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.clarifier_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  thread_id uuid NOT NULL REFERENCES public.threads(thread_id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'active', -- active|finalized|abandoned
  original_input text NOT NULL,
  final_summary text NULL,
  enriched_prompt text NULL,
  missing_fields jsonb NULL,
  assumptions jsonb NULL,
  turn_count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clarifier_sessions_user_updated
  ON public.clarifier_sessions(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_clarifier_sessions_thread_updated
  ON public.clarifier_sessions(thread_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS public.clarifier_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.clarifier_sessions(id) ON DELETE CASCADE,
  role text NOT NULL, -- system|assistant|user
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_clarifier_messages_session_created
  ON public.clarifier_messages(session_id, created_at ASC);

-- -----------------------------------------------------------------------------
-- RLS (mandatory)
-- Note: user_id is stored as text; compare to auth.uid()::text.
-- -----------------------------------------------------------------------------

ALTER TABLE public.clarifier_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clarifier_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS clarifier_sessions_select_own ON public.clarifier_sessions;
DROP POLICY IF EXISTS clarifier_sessions_insert_own ON public.clarifier_sessions;
DROP POLICY IF EXISTS clarifier_sessions_update_own ON public.clarifier_sessions;
DROP POLICY IF EXISTS clarifier_sessions_delete_own ON public.clarifier_sessions;

CREATE POLICY clarifier_sessions_select_own
  ON public.clarifier_sessions
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid()::text);

CREATE POLICY clarifier_sessions_insert_own
  ON public.clarifier_sessions
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY clarifier_sessions_update_own
  ON public.clarifier_sessions
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY clarifier_sessions_delete_own
  ON public.clarifier_sessions
  FOR DELETE
  TO authenticated
  USING (user_id = auth.uid()::text);

DROP POLICY IF EXISTS clarifier_messages_select_own ON public.clarifier_messages;
DROP POLICY IF EXISTS clarifier_messages_insert_own ON public.clarifier_messages;
DROP POLICY IF EXISTS clarifier_messages_delete_own ON public.clarifier_messages;
DROP POLICY IF EXISTS clarifier_messages_update_own ON public.clarifier_messages;

CREATE POLICY clarifier_messages_select_own
  ON public.clarifier_messages
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.clarifier_sessions s
      WHERE s.id = clarifier_messages.session_id
        AND s.user_id = auth.uid()::text
    )
  );

CREATE POLICY clarifier_messages_insert_own
  ON public.clarifier_messages
  FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.clarifier_sessions s
      WHERE s.id = clarifier_messages.session_id
        AND s.user_id = auth.uid()::text
    )
  );

CREATE POLICY clarifier_messages_update_own
  ON public.clarifier_messages
  FOR UPDATE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.clarifier_sessions s
      WHERE s.id = clarifier_messages.session_id
        AND s.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM public.clarifier_sessions s
      WHERE s.id = clarifier_messages.session_id
        AND s.user_id = auth.uid()::text
    )
  );

CREATE POLICY clarifier_messages_delete_own
  ON public.clarifier_messages
  FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM public.clarifier_sessions s
      WHERE s.id = clarifier_messages.session_id
        AND s.user_id = auth.uid()::text
    )
  );

COMMIT;


