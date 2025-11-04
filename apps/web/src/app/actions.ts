
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { ASSISTANT_ID, BASE } from "@/utils/langgraph";
import { createServerSupabase } from "@/utils/supabase/server";

async function ensureSession(redirectTo: string): Promise<string> {
  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? null;
  if (!token) {
    const params = new URLSearchParams();
    if (redirectTo && redirectTo !== '/') {
      params.set('redirect', redirectTo);
    }
    const query = params.toString();
    redirect(query ? `/login?${query}` : '/login');
  }
  return token;
}

async function authFetch(input: string, init: RequestInit = {}, redirectTo = "/chat") {
  const token = await ensureSession(redirectTo);
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}

async function getThreadCookie(): Promise<string | null> {
  const store = await cookies();
  return store.get("thread_id")?.value ?? null;
}

export async function setThreadCookie(id: string): Promise<void> {
  const store = await cookies();
  store.set("thread_id", id, { path: "/", httpOnly: true });
}

export async function forceCreateThread(): Promise<string> {
  const res = await authFetch(`${BASE}/threads`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ metadata: {} }),
  });
  if (!res.ok) throw new Error(`Failed to create thread: ${res.status}`);
  const data = await res.json();
  const id: string = data.thread_id || data.id;
  await setThreadCookie(id);
  return id;
}

type CreateThreadOptions = {
  force?: boolean;
};

export async function createThread(options: CreateThreadOptions = {}): Promise<string> {
  if (!options.force) {
    const existing = await getThreadCookie();
    if (existing) return existing;
  }
  const id = await forceCreateThread();
  revalidatePath("/clarifier");
  revalidatePath("/result");
  revalidatePath("/chat");
  return id;
}

function buildEnsureThreadUrl(redirectTo: string, force = false) {
  const params = new URLSearchParams({ redirect: redirectTo });
  if (force) params.set("force", "1");
  return `/api/thread/ensure?${params.toString()}`;
}

type GetStateOptions = {
  redirectTo?: string;
};

export async function getState(threadId?: string, options: GetStateOptions = {}) {
  const redirectTo = options.redirectTo ?? "/";
  const tid = threadId ?? (await getThreadCookie());
  if (!tid) {
    redirect(buildEnsureThreadUrl(redirectTo));
  }
  const res = await authFetch(`${BASE}/threads/${tid}/state`, { cache: "no-store" }, redirectTo);
  if (res.status === 404) {
    redirect(buildEnsureThreadUrl(redirectTo, true));
  }
  if (!res.ok) throw new Error(`Failed to fetch state: ${res.status}`);
  const state = await res.json();
  const runId = state?.values?.run_id ?? null;
  return { threadId: tid, state, runId };
}

export async function fetchTrace(runId: string) {
  const res = await authFetch(`${BASE}/runs/${runId}/trace`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to fetch trace: ${res.status} ${text}`);
  }
  return res.json();
}

export async function fetchStatus(runId: string) {
  const res = await authFetch(`${BASE}/runs/${runId}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to fetch status: ${res.status} ${text}`);
  }
  return res.json();
}

// Start a run without waiting for completion (for streaming)
type RunSuccess = {
  ok: true;
  runId: string | null;
  state?: unknown | null;
};

type RunFailure = {
  ok: false;
  error: string;
  status?: number;
  detail?: string;
};

type RunResult = RunSuccess | RunFailure;

function buildRunFailure(status: number | undefined, text: string | undefined, fallback: string): RunFailure {
  const detail = text?.trim() || undefined;
  const message = status ? `${fallback} (${status})` : fallback;
  return {
    ok: false,
    error: detail ? `${message}: ${detail}` : message,
    status,
    detail,
  };
}

export async function startRun(input: string): Promise<RunResult> {
  try {
    const tid = await createThread();
    const payload = {
      input: {
        messages: [{ role: "user", content: input }],
      },
    };
    const res = await authFetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return buildRunFailure(res.status, text, "Failed to start run");
    }
    const json = await res.json();
    const runId: string = json?.id || json?.run_id || null;
    return { ok: true, runId };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return { ok: false, error: message };
  }
}

// Start a run and wait for completion (simple, reliable path)
export async function startRunWait(input: string): Promise<RunResult> {
  try {
    const tid = await createThread();
    const payload = {
      input: {
        messages: [{ role: "user", content: input }],
      },
    };
    const res = await authFetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}/wait`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return buildRunFailure(res.status, text, "Failed to start run");
    }
    const json = await res.json();
    const runId: string = json?.id || json?.run_id || null;
    const state = json?.state ?? null;
    return { ok: true, runId, state };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return { ok: false, error: message };
  }
}

// Submit clarifier answers to resume the graph
export async function submitClarifier(formData: FormData) {
  const tid = await createThread();
  const answers = Object.fromEntries(formData.entries());

  // Send answers as a user message; backend nodes normalize dicts/strings
  const body = {
    input: {
      messages: [{ role: "user", content: JSON.stringify(answers) }],
    },
  };

  const res = await authFetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}/wait`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  }); // POST runs.wait
  if (!res.ok) throw new Error(`Failed to resume run: ${res.status}`);
}

// Backtrack one checkpoint and resume
export async function backtrackLast() {
  const tid = await createThread();

  // 1) History (newest first)
  const histRes = await authFetch(`${BASE}/threads/${tid}/history`, { cache: "no-store" }); // GET history
  if (!histRes.ok) throw new Error(`Failed to fetch history: ${histRes.status}`);
  const states = await histRes.json();
  if (!Array.isArray(states) || states.length < 2) return; // nothing to backtrack

  const latest = states[0];
  const prev = states[1]; // previous checkpoint

  const latestValues = latest?.state?.values;
  const missing = Array.isArray(latestValues?.missing_fields) ? latestValues.missing_fields : [];
  const hasClarifierQuestion = typeof latestValues?.clarifier_question === "string" && latestValues.clarifier_question.trim().length > 0;
  const canBacktrack = missing.length > 0 && hasClarifierQuestion;

  if (!canBacktrack) {
    throw new Error("Backtracking is only available immediately after a clarifier turn.");
  }

  // 2) Optionally edit state at that checkpoint (no edits here, just fork)
  const updRes = await authFetch(`${BASE}/threads/${tid}/state`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      checkpoint_id: prev.checkpoint_id,
      values: {},
    }),
  }); // POST update_state
  if (!updRes.ok) throw new Error(`Failed to update state: ${updRes.status}`);
  const newCfg = await updRes.json();

  // 3) Resume from the new checkpoint id
  const runRes = await authFetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}/wait`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ input: null, checkpoint_id: newCfg.checkpoint_id }),
  }); // POST runs.wait from checkpoint
  if (!runRes.ok) throw new Error(`Failed to resume from checkpoint: ${runRes.status}`);

  revalidatePath("/clarifier");
  revalidatePath("/result");
}
