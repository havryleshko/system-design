import { getState, submitClarifier, backtrackLast } from "../actions";
import Link from "next/link";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function lastAiQuestion(state: any): string {
    const msgs = state?.values?.messages || [];
    for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i];
        const role = (m?.role || "").toLowerCase();
        if (role === "assistant" || role === "ai") {
            const text = typeof m.content === "string" ? m.content : m?.content?.toString?.() || "";
            if (text) return text; 
        }
    }
    return "Please provide the missing details"
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractInterruptId(state: any): string | null {
    const interrupts = Array.isArray(state?.values?.__interrupt__)
        ? state?.values?.__interrupt__
        : [];
    if (!interrupts.length) return null;
    const first = interrupts[0] ?? null;
    const raw = typeof first?.id === "string" ? first.id : typeof first?.interrupt_id === "string" ? first.interrupt_id : null;
    return raw && raw.trim() ? raw.trim() : null;
}

export default async function ClarifierPage() {
    const { state, threadId, runId } = await getState(undefined, { redirectTo: "/clarifier" });
    const interruptId = extractInterruptId(state);
    const missing = state?.values?.missing_fields || [];
    const question = lastAiQuestion(state);
    const done = !missing || missing.length === 0;
    const resumeReady = Boolean(threadId && runId && interruptId);

    if (done) {
        return (
            <div style={{ padding: 24}}>
                <p>Clarification complete. Continue to results.</p>
                <Link href="/result">Go to result</Link>
            </div>
        );
    };

    return (
    <div style={{ maxWidth: 640, margin: "40px auto", padding: 24 }}>
      <h1>Clarifier</h1>
      <p style={{ marginTop: 8 }}>{question}</p>

      {!resumeReady && (
        <div style={{ marginTop: 12, padding: 12, background: "#2a1a1a", color: "#f8b4b4", borderRadius: 8 }}>
          We lost the session metadata needed to resume the agent. Please go back to the chat, ask again, and return here.
        </div>
      )}

      <form action={submitClarifier} style={{ marginTop: 16, display: "grid", gap: 12 }}>
        <input type="hidden" name="thread_id" value={threadId ?? ""} />
        <input type="hidden" name="run_id" value={runId ?? ""} />
        <input type="hidden" name="interrupt_id" value={interruptId ?? ""} />
        <label>
          Use case
          <input name="use_case" placeholder="e.g., real-time chat with 10k QPS" />
        </label>
        <label>
          Constraints
          <input name="constraints" placeholder="e.g., budget $500/mo, <100ms p95" />
        </label>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="submit" disabled={!resumeReady}>Submit answers</button>
          <button formAction={backtrackLast} type="submit" disabled={!resumeReady}>Backtrack last turn</button>
        </div>
      </form>

      <div style={{ marginTop: 24 }}>
        <Link href="/result">Skip to result</Link>
      </div>
    </div>
  );
}