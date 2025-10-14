
"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { ASSISTANT_ID, BASE } from "@/utils/langgraph";

async function getThreadCookie(): Promise<string | null> {
  const store = await cookies();
  return store.get("thread_id")?.value ?? null;
}

export async function setThreadCookie(id: string): Promise<void> {
  const store = await cookies();
  store.set("thread_id", id, { path: "/", httpOnly: true });
}

export async function forceCreateThread(): Promise<string> {
  const res = await fetch(`${BASE}/threads`, { method: "POST" });
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
  const res = await fetch(`${BASE}/threads/${tid}/state`, { cache: "no-store" });
  if (res.status === 404) {
    redirect(buildEnsureThreadUrl(redirectTo, true));
  }
  if (!res.ok) throw new Error(`Failed to fetch state: ${res.status}`);
  const state = await res.json();
  const runId = state?.values?.run_id ?? null;
  return { threadId: tid, state, runId };
}

export async function fetchTrace(runId: string) {
  const res = await fetch(`${BASE}/runs/${runId}/trace`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to fetch trace: ${res.status} ${text}`);
  }
  return res.json();
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

  const res = await fetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}/wait`, {
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
  const histRes = await fetch(`${BASE}/threads/${tid}/history`, { cache: "no-store" }); // GET history
  if (!histRes.ok) throw new Error(`Failed to fetch history: ${histRes.status}`);
  const states = await histRes.json();
  if (!Array.isArray(states) || states.length < 2) return; // nothing to backtrack

  const prev = states[1]; // previous checkpoint

  // 2) Optionally edit state at that checkpoint (no edits here, just fork)
  const updRes = await fetch(`${BASE}/threads/${tid}/state`, {
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
  const runRes = await fetch(`${BASE}/threads/${tid}/runs/${ASSISTANT_ID}/wait`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ input: null, checkpoint_id: newCfg.checkpoint_id }),
  }); // POST runs.wait from checkpoint
  if (!runRes.ok) throw new Error(`Failed to resume from checkpoint: ${runRes.status}`);
}
