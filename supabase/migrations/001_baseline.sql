-- users_profile
CREATE TABLE IF NOT EXISTS public.users_profile (
    user_id uuid PRIMARY KEY,
    email text,
    plan text DEFAULT 'free'::text,
    plan_since timestamptz DEFAULT now(),
    trial_ends_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- usage_counters
CREATE TABLE IF NOT EXISTS public.usage_counters (
    user_id uuid NOT NULL,
    period_month text NOT NULL,
    runs_day text DEFAULT to_char(timezone('utc', now()), 'YYYY-MM-DD'),
    runs_used_day integer DEFAULT 0,
    prompt_tokens bigint DEFAULT 0,
    completion_tokens bigint DEFAULT 0,
    updated_at timestamptz DEFAULT now(),
    PRIMARY KEY (user_id, period_month)
);

-- stripe_customers
CREATE TABLE IF NOT EXISTS public.stripe_customers (
    user_id uuid PRIMARY KEY,
    customer_id text UNIQUE,
    subscription_id text UNIQUE,
    status text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- trace_logs
CREATE TABLE IF NOT EXISTS public.trace_logs (
    id bigint PRIMARY KEY DEFAULT nextval('trace_logs_id_seq'::regclass),
    thread_id text,
    run_id text,
    user_id uuid,
    level text,
    message text,
    data jsonb,
    created_at timestamptz DEFAULT now()
);

-- qna
CREATE TABLE IF NOT EXISTS public.qna (
    thread_id text NOT NULL,
    turn_index integer NOT NULL,
    user_id uuid,
    role text,
    content text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (thread_id, turn_index)
);

-- checkpoint_migrations
CREATE TABLE IF NOT EXISTS public.checkpoint_migrations (
    v integer PRIMARY KEY
);

-- checkpoints
CREATE TABLE IF NOT EXISTS public.checkpoints (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT ''::text,
    checkpoint_id text NOT NULL,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb,
    metadata jsonb DEFAULT '{}'::jsonb,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- checkpoint_blobs
CREATE TABLE IF NOT EXISTS public.checkpoint_blobs (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT ''::text,
    channel text NOT NULL,
    version text NOT NULL,
    type text,
    blob bytea,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- checkpoint_writes
CREATE TABLE IF NOT EXISTS public.checkpoint_writes (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT ''::text,
    checkpoint_id text NOT NULL,
    task_id text NOT NULL,
    idx integer NOT NULL,
    channel text NOT NULL,
    type text,
    blob bytea NOT NULL,
    task_path text DEFAULT ''::text,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- knowledge_base
CREATE TABLE IF NOT EXISTS public.knowledge_base (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text,
    summary text,
    note text,
    url text,
    risks jsonb DEFAULT '[]'::jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    created_by uuid
);

-- Foreign keys (duplicate-safe)
DO $$
BEGIN
    ALTER TABLE public.users_profile
        ADD CONSTRAINT users_profile_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.usage_counters
        ADD CONSTRAINT usage_counters_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.stripe_customers
        ADD CONSTRAINT stripe_customers_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES auth.users (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.knowledge_base
        ADD CONSTRAINT fk_kb_created_by_auth_users
        FOREIGN KEY (created_by) REFERENCES auth.users (id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;