
"use server";

import { cookies } from "next/headers";
import { ASSISTANT_ID, BASE } from "@/utils/langgraph"; // if no path alias, use "../../utils/langgraph"

// Read the thread_id cookie (Server Action only)
async function getThreadCookie(): Promise<string | null> {
  const store = await cookies(); // cookies() must be awaited in Server Actions
  return store.get("thread_id")?.value ?? null;
}

// Write the thread_id cookie
async function setThreadCookie(id: string): Promise<void> {
  const store = await cookies();
  store.set("thread_id", id, { path: "/", httpOnly: true });
}

// Create a thread if missing and persist its id in a cookie
export async function createThread(): Promise<string> {
  const existing = await getThreadCookie();
  if (existing) return existing;

  const res = await fetch(`${BASE}/threads`, { method: "POST" }); // POST /threads creates a thread
  if (!res.ok) throw new Error(`Failed to create thread: ${res.status}`);
  const data = await res.json();
  const id: string = data.thread_id || data.id;
  await setThreadCookie(id);
  return id;
}

// Fetch current thread state (values, next, metadata)
export async function getState(threadId?: string) {
  const tid = threadId || (await getThreadCookie()) || (await createThread());
  const res = await fetch(`${BASE}/threads/${tid}/state`, { cache: "no-store" }); // GET thread state
  if (!res.ok) throw new Error(`Failed to fetch state: ${res.status}`);
  const state = await res.json();
  return { threadId: tid, state };
}

// Submit clarifier answers to resume the graph
export async function submitClarifier(formData: FormData) {
  const tid = (await getThreadCookie()) || (await createThread());
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
  const tid = (await getThreadCookie()) || (await createThread());

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
