BEGIN;

-- public.checkpoint_blobs
DROP POLICY IF EXISTS checkpoint_blobs_delete_on_thread_owner ON public.checkpoint_blobs;
DROP POLICY IF EXISTS checkpoint_blobs_insert_on_thread_owner ON public.checkpoint_blobs;
DROP POLICY IF EXISTS checkpoint_blobs_select_on_thread_owner ON public.checkpoint_blobs;
DROP POLICY IF EXISTS checkpoint_blobs_update_on_thread_owner ON public.checkpoint_blobs;

CREATE POLICY checkpoint_blobs_delete_on_thread_owner
  ON public.checkpoint_blobs
  FOR DELETE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_blobs.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_blobs_insert_on_thread_owner
  ON public.checkpoint_blobs
  FOR INSERT
  TO authenticated
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_blobs.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_blobs_select_on_thread_owner
  ON public.checkpoint_blobs
  FOR SELECT
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_blobs.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_blobs_update_on_thread_owner
  ON public.checkpoint_blobs
  FOR UPDATE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_blobs.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid)))) ))
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_blobs.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

-- public.checkpoint_writes
DROP POLICY IF EXISTS checkpoint_writes_delete_on_thread_owner ON public.checkpoint_writes;
DROP POLICY IF EXISTS checkpoint_writes_insert_on_thread_owner ON public.checkpoint_writes;
DROP POLICY IF EXISTS checkpoint_writes_select_on_thread_owner ON public.checkpoint_writes;
DROP POLICY IF EXISTS checkpoint_writes_update_on_thread_owner ON public.checkpoint_writes;

CREATE POLICY checkpoint_writes_delete_on_thread_owner
  ON public.checkpoint_writes
  FOR DELETE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_writes.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_writes_insert_on_thread_owner
  ON public.checkpoint_writes
  FOR INSERT
  TO authenticated
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_writes.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_writes_select_on_thread_owner
  ON public.checkpoint_writes
  FOR SELECT
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_writes.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoint_writes_update_on_thread_owner
  ON public.checkpoint_writes
  FOR UPDATE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_writes.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid)))) ))
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoint_writes.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

-- public.checkpoints
DROP POLICY IF EXISTS checkpoints_delete_on_thread_owner ON public.checkpoints;
DROP POLICY IF EXISTS checkpoints_insert_on_thread_owner ON public.checkpoints;
DROP POLICY IF EXISTS checkpoints_select_on_thread_owner ON public.checkpoints;
DROP POLICY IF EXISTS checkpoints_update_on_thread_owner ON public.checkpoints;

CREATE POLICY checkpoints_delete_on_thread_owner
  ON public.checkpoints
  FOR DELETE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoints.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoints_insert_on_thread_owner
  ON public.checkpoints
  FOR INSERT
  TO authenticated
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoints.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoints_select_on_thread_owner
  ON public.checkpoints
  FOR SELECT
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoints.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

CREATE POLICY checkpoints_update_on_thread_owner
  ON public.checkpoints
  FOR UPDATE
  TO authenticated
  USING ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoints.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid)))) ))
  WITH CHECK ((EXISTS ( SELECT 1
   FROM qna
  WHERE ((qna.thread_id = checkpoints.thread_id) AND (qna.user_id = ( SELECT auth.uid() AS uid))))));

-- public.knowledge_base
DROP POLICY IF EXISTS kb_delete_owner ON public.knowledge_base;
DROP POLICY IF EXISTS kb_insert_authenticated ON public.knowledge_base;
DROP POLICY IF EXISTS kb_select_authenticated ON public.knowledge_base;
DROP POLICY IF EXISTS kb_update_owner ON public.knowledge_base;

CREATE POLICY kb_delete_owner
  ON public.knowledge_base
  FOR DELETE
  TO authenticated
  USING ((created_by = ( SELECT auth.uid() AS uid)));

CREATE POLICY kb_insert_authenticated
  ON public.knowledge_base
  FOR INSERT
  TO authenticated
  WITH CHECK ((created_by = ( SELECT auth.uid() AS uid)));

CREATE POLICY kb_select_authenticated
  ON public.knowledge_base
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY kb_update_owner
  ON public.knowledge_base
  FOR UPDATE
  TO authenticated
  USING ((created_by = ( SELECT auth.uid() AS uid)))
  WITH CHECK ((created_by = ( SELECT auth.uid() AS uid)));

-- public.qna
DROP POLICY IF EXISTS qna_no_write ON public.qna;
DROP POLICY IF EXISTS qna_select_own ON public.qna;

CREATE POLICY qna_no_write
  ON public.qna
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY qna_select_own
  ON public.qna
  FOR SELECT
  TO authenticated
  USING ((auth.uid() = user_id));

-- public.stripe_customers
DROP POLICY IF EXISTS stripe_no_write ON public.stripe_customers;
DROP POLICY IF EXISTS stripe_select_own ON public.stripe_customers;

CREATE POLICY stripe_no_write
  ON public.stripe_customers
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY stripe_select_own
  ON public.stripe_customers
  FOR SELECT
  TO authenticated
  USING ((auth.uid() = user_id));

-- public.trace_logs
DROP POLICY IF EXISTS trace_no_write ON public.trace_logs;
DROP POLICY IF EXISTS trace_select_own ON public.trace_logs;

CREATE POLICY trace_no_write
  ON public.trace_logs
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY trace_select_own
  ON public.trace_logs
  FOR SELECT
  TO authenticated
  USING ((auth.uid() = user_id));

-- public.usage_counters
DROP POLICY IF EXISTS usage_no_write ON public.usage_counters;
DROP POLICY IF EXISTS usage_select_own ON public.usage_counters;

CREATE POLICY usage_no_write
  ON public.usage_counters
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY usage_select_own
  ON public.usage_counters
  FOR SELECT
  TO authenticated
  USING ((auth.uid() = user_id));

-- public.users_profile
DROP POLICY IF EXISTS users_profile_no_write ON public.users_profile;
DROP POLICY IF EXISTS users_profile_select_own ON public.users_profile;

CREATE POLICY users_profile_no_write
  ON public.users_profile
  FOR ALL
  TO authenticated
  USING (false)
  WITH CHECK (false);

CREATE POLICY users_profile_select_own
  ON public.users_profile
  FOR SELECT
  TO authenticated
  USING ((auth.uid() = user_id));

COMMIT;