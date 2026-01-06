"use server";
import "server-only";

import { randomUUID } from "crypto";
import { redirect } from "next/navigation";
import { createServerSupabase } from "@/utils/supabase/server";
import { backendHeaders, backendUrl } from "@/utils/langgraph";

type LogContext = {
  requestId?: string;
  scope?: string;
  target?: string;
};

type SessionInfo = {
  token: string;
  userId: string | null;
};

type ThreadState = {
  status?: string;
  run_id?: string | null;
  output?: string;
  values?: Record<string, unknown>;
};

type ThreadListItem = {
  thread_id: string;
  title: string;
  status: "running" | "completed" | "failed" | "queued";
  created_at: string | null;
};

async function extractBackendError(response: Response): Promise<string | null> {
  // FastAPI errors are usually `{ detail: string }`
  try {
    const data = (await response.json()) as { detail?: unknown; error?: unknown; message?: unknown };
    const detail = typeof data?.detail === "string" ? data.detail : null;
    const error = typeof data?.error === "string" ? data.error : null;
    const message = typeof data?.message === "string" ? data.message : null;
    return detail || error || message;
  } catch {
    return null;
  }
}

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

async function ensureSession(redirectTo: string, context?: LogContext): Promise<SessionInfo> {
  const requestId = context?.requestId ?? makeRequestId("ensureSession");
  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? null;
  const userId = session?.user?.id ?? null;
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
  return { token, userId };
}

async function getSessionUserId(
  redirectTo = "/chat",
  context?: LogContext
): Promise<string | null> {
  const { userId } = await ensureSession(redirectTo, context);
  return userId;
}

export async function createThread(token: string): Promise<string> {
  const response = await fetch(backendUrl("/threads"), {
    method: "POST",
    headers: backendHeaders(token, { json: true }),
  });

  if (!response.ok) {
    const msg = (await extractBackendError(response)) || response.statusText;
    throw new Error(`Failed to create thread: ${msg}`);
  }

  const data = (await response.json()) as { thread_id?: string };
  if (!data.thread_id) {
    throw new Error("Failed to create thread: missing thread_id");
  }
  return data.thread_id;
}

export async function startRun(threadId: string, input: string, token: string): Promise<string> {
  const response = await fetch(backendUrl(`/threads/${threadId}/runs`), {
    method: "POST",
    headers: backendHeaders(token, { json: true }),
    body: JSON.stringify({ input }),
  });

  if (!response.ok) {
    const msg = (await extractBackendError(response)) || response.statusText;
    throw new Error(`Failed to start run: ${msg}`);
  }

  const data = (await response.json()) as { run_id?: string };
  if (!data.run_id) {
    throw new Error("Failed to start run: missing run_id");
  }
  return data.run_id;
}

export async function getThreadState(threadId: string, token: string): Promise<ThreadState | null> {
  const response = await fetch(backendUrl(`/threads/${threadId}/state`), {
    headers: backendHeaders(token),
  });

  if (!response.ok) {
    if (response.status === 404) {
      return null;
    }
    const msg = (await extractBackendError(response)) || response.statusText;
    throw new Error(`Failed to get thread state: ${msg}`);
  }

  return (await response.json()) as ThreadState | null;
}

export async function listThreads(token: string): Promise<ThreadListItem[]> {
  const response = await fetch(backendUrl("/threads"), {
    headers: backendHeaders(token),
  });

  if (!response.ok) {
    if (response.status === 401) {
      return [];
    }
    const msg = (await extractBackendError(response)) || response.statusText;
    throw new Error(`Failed to list threads: ${msg}`);
  }

  const data = (await response.json()) as { threads?: ThreadListItem[] };
  return data.threads ?? [];
}
