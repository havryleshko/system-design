
"use server";

import { randomUUID } from "crypto";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { ASSISTANT_ID, BASE } from "@/utils/langgraph";
import { createServerSupabase } from "@/utils/supabase/server";

type LogContext = {
  requestId?: string;
  scope?: string;
  target?: string;
};

function makeRequestId(prefix: string): string {
  if (typeof randomUUID === "function") return randomUUID();
  const rand = Math.random().toString(16).slice(2);
  return `${prefix}-${Date.now()}-${rand}`;
}

function logWarn(scope: string, message: string, extra?: Record<string, unknown>) {
  console.warn(`[${scope}] ${message}`, extra);
}

function logError(scope: string, message: string, extra?: Record<string, unknown>) {
  console.error(`[${scope}] ${message}`, extra);
}

async function ensureSession(redirectTo: string, context?: LogContext): Promise<string> {
  const requestId = context?.requestId ?? makeRequestId("ensureSession");
  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? null;
  if (!token) {
    logWarn("auth.ensureSession", "Missing Supabase session", {
      requestId,
      redirectTo,
    });
    const params = new URLSearchParams();
    if (redirectTo && redirectTo !== '/') {
      params.set('redirect', redirectTo);
    }
    const query = params.toString();
    redirect(query ? `/login?${query}` : '/login');
  }
  return token;
}

async function authFetch(input: string, init: RequestInit = {}, redirectTo = "/chat", context?: LogContext) {
  const requestId = context?.requestId ?? makeRequestId("authFetch");
  const scope = context?.scope ?? "auth.fetch";
  const target = context?.target ?? input;
  const token = await ensureSession(redirectTo, { requestId, scope });
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  try {
    const res = await fetch(input, { ...init, headers });
    if (!res.ok) {
      let body = "";
      try {
        body = await res.clone().text();
      } catch {
        body = "[unreadable body]";
      }
      logWarn(scope, "authFetch received non-OK response", {
        requestId,
        target,
        status: res.status,
        body: body?.slice(0, 1024) || null,
      });
    }
    return res;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError(scope, "authFetch threw", { requestId, target, error: message });
    throw err;
  }
}

async function getThreadCookie(): Promise<string | null> {
  const store = await cookies();
  return store.get("thread_id")?.value ?? null;
}

export async function setThreadCookie(id: string): Promise<void> {
  const store = await cookies();
  store.set("thread_id", id, { path: "/", httpOnly: true });
}

export async function forceCreateThread(context?: LogContext): Promise<string> {
  const requestId = context?.requestId ?? makeRequestId("thread-force");
  const scope = "thread.forceCreate";
  const url = `${BASE}/threads`;
  try {
    const res = await authFetch(
      url,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ metadata: {} }),
      },
      "/chat",
      { requestId, scope, target: url }
    );
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const message = text?.slice(0, 1024) || "";
      logError(scope, "Failed to create thread", {
        requestId,
        status: res.status,
        body: message,
      });
      throw new Error(`Failed to create thread: ${res.status}`);
    }
    const data = await res.json();
    const id: string = data.thread_id || data.id;
    await setThreadCookie(id);
    return id;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError(scope, "forceCreateThread threw", { requestId, error: message });
    throw err;
  }
}

type CreateThreadOptions = {
  force?: boolean;
  requestId?: string;
};

export async function createThread(options: CreateThreadOptions = {}): Promise<string> {
  const requestId = options.requestId ?? makeRequestId("thread");
  const scope = "thread.create";
  try {
    if (!options.force) {
      const existing = await getThreadCookie();
      if (existing) return existing;
    }
    const id = await forceCreateThread({ requestId, scope });
    revalidatePath("/result");
    revalidatePath("/chat");
    return id;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError(scope, "createThread failed", { requestId, error: message, force: Boolean(options.force) });
    throw err;
  }
}

type GetStateOptions = {
  redirectTo?: string;
};

export async function getState(threadId?: string, options: GetStateOptions = {}) {
  const redirectTo = options.redirectTo ?? "/";
  let tid = threadId ?? (await getThreadCookie());
  if (!tid) {
    // No thread yet — create one and continue
    tid = await forceCreateThread();
  }

  // Try once
  let res = await authFetch(`${BASE}/threads/${tid}/state`, { cache: "no-store" }, redirectTo);

  // If the thread was evicted/unknown (404) or backend errored (500), force-create and retry once
  if (res.status === 404 || res.status === 500) {
    tid = await forceCreateThread();
    res = await authFetch(`${BASE}/threads/${tid}/state`, { cache: "no-store" }, redirectTo);
  }

  // If we lost auth, bounce to login
  if (res.status === 401) {
    redirect("/login");
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Failed to fetch state: ${res.status} ${text}`);
  }

  const state = await res.json();
  const runId =
    (state?.values?.run_id as string | null | undefined) ??
    (state?.metadata?.run_id as string | null | undefined) ??
    null;
  return { threadId: tid, state, runId };
}

export async function fetchTrace(runId: string) {
  const res = await authFetch(`${BASE}/runs/${runId}/trace`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    // Handle 404 gracefully - trace might not exist yet
    if (res.status === 404) {
      return { id: runId, events: [], timeline: [], branch_path: [] };
    }
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

function buildRunFailure(status: number | undefined, text: string | undefined, fallback: string, extra?: Record<string, unknown>): RunFailure {
  const detail = text?.trim() || undefined;
  const message = status ? `${fallback} (${status})` : fallback;
  if (extra) {
    const scope = typeof extra.scope === "string" ? extra.scope : "run.failure";
    logError(scope, fallback, {
      ...extra,
      status,
      detail,
    });
  }
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
  const rawRunId = state?.metadata?.run_id ?? state?.values?.run_id ?? null;
  const sRunId: string | null = typeof rawRunId === "string" ? rawRunId : null;
  if (expectedRunId && sRunId && expectedRunId !== sRunId) return false;
  const values = (state?.values || {}) as Record<string, unknown>;
  return Boolean(
    (typeof values.output === "string" && values.output) ||
      values.architecture_json ||
      values.design_json
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

async function invokeRun(threadId: string, body: Record<string, unknown>, wait: boolean, context?: LogContext): Promise<RunResult> {
  const requestId = context?.requestId ?? makeRequestId("invokeRun");
  const scope = context?.scope ?? "run.invoke";
  const target = `${BASE}/threads/${threadId}/runs`;
  const payload = {
    assistant_id: ASSISTANT_ID,
    ...body,
  };

  try {
    const res = await authFetch(
      target,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      },
      "/chat",
      { requestId, scope, target }
    );

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      return buildRunFailure(res.status, text, "Failed to start run", { requestId, scope, target, threadId });
    }

    const data = await res.json().catch(() => ({}));
    const runId: string | null = data?.run_id || data?.id || null;
    if (!runId) {
      logError(scope, "Run response missing run_id", { requestId, threadId });
      return {
        ok: false,
        error: "Run created but no run ID was returned",
      };
    }

    if (!wait) {
      return { ok: true, runId };
    }

    return await waitForState(threadId, runId);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logError(scope, "invokeRun threw", { requestId, threadId, error: message });
    throw err;
  }
}

async function executeRun({ input, wait }: { input: string; wait: boolean }): Promise<RunResult> {
  const requestId = makeRequestId(wait ? "run-wait" : "run-stream");
  const body = {
    input: {
      messages: [{ role: "user", content: input }],
    },
  };

  let forced = false;

  while (true) {
    let tid: string;
    try {
      tid = await createThread({ force: forced, requestId });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      logError("run.execute", "Failed to create thread", { requestId, forced, error: message });
      return {
        ok: false,
        error: `Unable to create thread: ${message}`,
      };
    }
    let result: RunResult;
    try {
      result = await invokeRun(tid, body, wait, { requestId, scope: "run.invoke", target: `${BASE}/threads/${tid}/runs` });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      logError("run.execute", "invokeRun threw", { requestId, threadId: tid, error: message });
      return {
        ok: false,
        error: `Unable to start run: ${message}`,
      };
    }

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

// Start a run for streaming and return both thread and run IDs
export type StartStreamSuccess = {
  ok: true;
  threadId: string;
  runId: string;
};

export type StartStreamResult = StartStreamSuccess | RunFailure;

export async function startRunStream(input: string): Promise<StartStreamResult> {
  const requestId = makeRequestId("run-stream");
  const scope = "run.stream";
  try {
    const body = {
      input: {
        messages: [{ role: "user", content: input }],
      },
    };

    let threadId: string;
    try {
      threadId = await createThread({ requestId });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      logError(scope, "createThread failed", { requestId, error: message });
      return { ok: false, error: `Unable to prepare thread: ${message}` };
    }

    let result: RunResult;
    try {
      result = await invokeRun(threadId, body, false, { requestId, scope, target: `${BASE}/threads/${threadId}/runs` });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      logError(scope, "invokeRun threw", { requestId, threadId, error: message });
      return { ok: false, error: `Unable to start run: ${message}` };
    }

    if (!result.ok || !result.runId) {
      if (result.ok) {
        logError(scope, "invokeRun reported success without runId", { requestId, threadId });
        return { ok: false, error: "Run created but no run ID was returned" };
      }
      logWarn(scope, "invokeRun returned failure", { requestId, threadId, status: result.status, detail: result.detail });
      return result;
    }
    return { ok: true, threadId, runId: result.runId };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    logError(scope, "startRunStream threw", { requestId, error: message });
    return { ok: false, error: message };
  }
}

// Submit clarifier answers to resume the graph
export async function submitClarifier(formData: FormData) {
  const scope = "clarifier.submit";
  const requestId = makeRequestId("clarifier-resume");
  const threadIdRaw = formData.get("thread_id");
  const tid =
    typeof threadIdRaw === "string" && threadIdRaw.trim()
      ? threadIdRaw.trim()
      : await createThread();
  const runIdRaw = formData.get("run_id");
  const interruptIdRaw = formData.get("interrupt_id");
  if (typeof runIdRaw !== "string" || !runIdRaw) {
    throw new Error("Run ID missing while resuming clarifier");
  }

  const answerRaw = formData.get("answer");
  const answer = typeof answerRaw === "string" ? answerRaw.trim() : "";
  if (!answer) {
    throw new Error("Please provide an answer.");
  }

  const resumeValue: Record<string, unknown> = { answer };
  const resumeBody =
    typeof interruptIdRaw === "string" && interruptIdRaw
      ? { resume: { [interruptIdRaw]: resumeValue } }
      : { resume: resumeValue };
  const resumeTarget = `${BASE}/threads/${tid}/runs/${runIdRaw}/resume`;
  console.info(`[${scope}] resuming clarifier`, {
    requestId,
    threadId: tid,
    runId: runIdRaw,
    interruptId: typeof interruptIdRaw === "string" ? interruptIdRaw : null,
    resume: resumeBody,
  });
  const res = await authFetch(
    resumeTarget,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(resumeBody),
    },
    "/chat",
    { requestId, scope, target: resumeTarget }
  );
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    logError(scope, "Resume failed", {
      requestId,
      threadId: tid,
      runId: runIdRaw,
      status: res.status,
      body: detail?.slice(0, 1024) || null,
    });
    const statusFragment = res.status ? ` (${res.status})` : "";
    const message =
      detail?.trim() || `Failed to resume clarifier${statusFragment}`;
    throw new Error(message);
  }
}

