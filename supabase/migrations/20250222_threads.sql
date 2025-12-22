-- Threads and runs persistence for system-design agent

CREATE TABLE IF NOT EXISTS threads (
    thread_id UUID PRIMARY KEY,
    user_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_run_id UUID NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    user_id TEXT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    user_input TEXT NULL,
    final_state JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_runs_thread_created_at ON runs(thread_id, created_at DESC);


