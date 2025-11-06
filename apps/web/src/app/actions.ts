
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

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

type ThreadState = { metadata?: Record<string, unknown> | null; values?: Record<string, unknown> | null } | null;

function isTerminal(state: ThreadState, expectedRunId: string | null): boolean {
  const sRunId: string | null = state?.metadata?.run_id || state?.values?.run_id || null;
  if (expectedRunId && sRunId && expectedRunId !== sRunId) return false;
  const values = (state?.values || {}) as Record<string, unknown>;
  return Boolean(
    (typeof values.output === "string" && values.output) ||
      values.architecture_json ||
      values.design_json ||
      (typeof values.clarifier_question === "string" && values.clarifier_question)
  );
}

async function waitForState(threadId: string, runId: string, timeoutMs = 120_000, pollIntervalMs = 1_000): Promise<RunResult> {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() <= deadline) {
    const res = await authFetch(`${BASE}/threads/${threadId}/state`, { cache: "no-store" });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return buildRunFailure(res.status, text, "Failed to fetch thread state");
    }
    const state = await res.json();
    if (isTerminal(state, runId)) return { ok: true, runId, state };

    await delay(pollIntervalMs);
  }

  return {
    ok: false,
    error: "Timed out waiting for run to complete",
    status: 504,
  };
}

async function invokeRun(threadId: string, body: Record<string, unknown>, wait: boolean): Promise<RunResult> {
  const payload = {
    assistant_id: ASSISTANT_ID,
    ...body,
  };

  const res = await authFetch(`${BASE}/threads/${threadId}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    return buildRunFailure(res.status, text, "Failed to start run");
  }

  const data = await res.json().catch(() => ({}));
  const runId: string | null = data?.run_id || data?.id || null;
  if (!runId) {
    return {
      ok: false,
      error: "Run created but no run ID was returned",
    };
  }

  if (!wait) {
    return { ok: true, runId };
  }

  return await waitForState(threadId, runId);
}

async function executeRun({ input, wait }: { input: string; wait: boolean }): Promise<RunResult> {
  const body = {
    input: {
      messages: [{ role: "user", content: input }],
    },
  };

  let forced = false;

  while (true) {
    const tid = forced ? await forceCreateThread() : await createThread({ force: false });
    const result = await invokeRun(tid, body, wait);

    if (result.ok || forced) {
      return result;
    }

    if (result.status === 404 && !forced) {
      forced = true;
      continue;
    }

    return result;
  }
}

export async function startRun(input: string): Promise<RunResult> {
  try {
    const result = await executeRun({ input, wait: false });
    if (!result.ok) return result;
    return { ok: true, runId: result.runId };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return { ok: false, error: message };
  }
}

// Start a run and wait for completion (simple, reliable path)
export async function startRunWait(input: string): Promise<RunResult> {
  try {
    return await executeRun({ input, wait: true });
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
  const payload = {
    input: {
      messages: [{ role: "user", content: JSON.stringify(answers) }],
    },
  };

  const result = await invokeRun(tid, payload, true);
  if (!result.ok) {
    throw new Error(result.error);
  }
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
  const resumePayload = { input: null, checkpoint_id: newCfg.checkpoint_id } as Record<string, unknown>;
  const resumeResult = await invokeRun(tid, resumePayload, true);
  if (!resumeResult.ok) {
    throw new Error(resumeResult.error);
  }

  revalidatePath("/clarifier");
  revalidatePath("/result");
}
