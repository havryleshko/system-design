"use client";

import { useMemo, useState, type ReactNode } from "react";

type ReasoningTabProps = {
  query: string;
  values: Record<string, unknown> | null;
};

type ReasoningEvent = {
  ts_iso?: string;
  node?: string;
  agent?: string;
  phase?: string;
  status?: string;
  duration_ms?: number;
  kind?: string;
  what?: string;
  why?: string;
  alternatives_considered?: unknown;
  inputs?: unknown;
  outputs?: unknown;
  debug?: unknown;
  error?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function coerceEvents(values: Record<string, unknown>): ReasoningEvent[] {
  const raw = values.reasoning_trace;
  if (!Array.isArray(raw)) return [];
  return raw.filter(isRecord) as ReasoningEvent[];
}

function safeText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  return null;
}

function summarizeNotes(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value)) {
    for (const item of value) {
      const t = safeText(item);
      if (t) return t;
    }
  }
  return null;
}

function fallbackSummary(ev: ReasoningEvent): string | null {
  const error = safeText(ev.error);
  if (error) return error;
  const out = isRecord(ev.outputs) ? (ev.outputs as Record<string, unknown>) : null;
  const reason = out ? safeText(out.reason) : null;
  const notes = out ? summarizeNotes(out.notes) : null;

  const highlightsCount = out && typeof out.highlights_count === "number" ? out.highlights_count : null;
  const citationsCount = out && typeof out.citations_count === "number" ? out.citations_count : null;
  const risksCount = out && typeof out.risks_count === "number" ? out.risks_count : null;

  const counts: string[] = [];
  if (highlightsCount != null) counts.push(`${highlightsCount} highlight(s)`);
  if (citationsCount != null) counts.push(`${citationsCount} citation(s)`);
  if (risksCount != null) counts.push(`${risksCount} risk(s)`);

  const bits = [reason, notes, counts.length ? counts.join(", ") : null].filter(Boolean) as string[];
  if (bits.length) return bits.join(" — ");
  return null;
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function statusColor(status: string | undefined) {
  const s = (status || "").toLowerCase();
  if (s === "failed") return "bg-red-500/10 text-red-400 border-red-500/20";
  if (s === "completed") return "bg-green-500/10 text-green-400 border-green-500/20";
  if (s === "skipped") return "bg-yellow-500/10 text-yellow-400 border-yellow-500/20";
  return "bg-[var(--background)] text-[var(--foreground-muted)] border-[var(--border)]";
}

function CollapsibleSection({
  title,
  defaultOpen,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[var(--background)]"
      >
        <span className="font-medium text-[var(--foreground)]">{title}</span>
        <svg
          viewBox="0 0 24 24"
          className={`h-4 w-4 text-[var(--foreground-muted)] transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open ? <div className="border-t border-[var(--border)] px-4 py-3">{children}</div> : null}
    </div>
  );
}

function EventCard({ ev }: { ev: ReasoningEvent }) {
  const status = (ev.status || "unknown").toLowerCase();
  const title = ev.node || "node";
  const time = ev.ts_iso ? new Date(ev.ts_iso).toLocaleString() : null;
  const duration = typeof ev.duration_ms === "number" ? `${ev.duration_ms}ms` : null;

  const what = safeText(ev.what);
  const why = safeText(ev.why);
  const error = safeText(ev.error);
  const fallback = !what && !why ? fallbackSummary(ev) : null;

  return (
    <div className="rounded border border-[var(--border)] bg-[var(--background)]">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[var(--foreground)]">{title}</span>
          <span className={`rounded-full border px-2 py-0.5 text-xs ${statusColor(status)}`}>{status}</span>
          {ev.kind && ev.kind !== "node_end" ? (
            <span className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--foreground-muted)]">
              {ev.kind}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-xs text-[var(--foreground-muted)]">
          {duration ? <span>{duration}</span> : null}
          {time ? <span>{time}</span> : null}
        </div>
      </div>

      <div className="px-3 pb-3">
        {what || why || error || fallback ? (
          <div className="mt-1 space-y-2">
            {what ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">What</div>
                <div className="text-sm text-[var(--foreground)]">{what}</div>
              </div>
            ) : null}
            {why ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Why</div>
                <div className="text-sm text-[var(--foreground)]">{why}</div>
              </div>
            ) : null}
            {!what && !why && fallback ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Summary</div>
                <div className="text-sm text-[var(--foreground)]">{fallback}</div>
              </div>
            ) : null}
            {error ? (
              <div className="rounded border border-red-500/20 bg-red-500/10 p-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}
          </div>
        ) : null}

        <details className="mt-3">
          <summary className="cursor-pointer select-none text-sm text-[var(--accent)] hover:underline">
            Details
          </summary>
          <div className="mt-2 grid gap-3">
            {ev.alternatives_considered != null ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                  Alternatives
                </div>
                <pre className="mt-1 max-h-72 overflow-auto rounded bg-[var(--surface)] p-2 text-xs text-[var(--foreground)]">
                  {formatJson(ev.alternatives_considered)}
                </pre>
              </div>
            ) : null}
            {ev.inputs != null ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Inputs</div>
                <pre className="mt-1 max-h-72 overflow-auto rounded bg-[var(--surface)] p-2 text-xs text-[var(--foreground)]">
                  {formatJson(ev.inputs)}
                </pre>
              </div>
            ) : null}
            {ev.outputs != null ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Outputs</div>
                <pre className="mt-1 max-h-72 overflow-auto rounded bg-[var(--surface)] p-2 text-xs text-[var(--foreground)]">
                  {formatJson(ev.outputs)}
                </pre>
              </div>
            ) : null}
            {ev.debug != null ? (
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Debug</div>
                <pre className="mt-1 max-h-72 overflow-auto rounded bg-[var(--surface)] p-2 text-xs text-[var(--foreground)]">
                  {formatJson(ev.debug)}
                </pre>
              </div>
            ) : null}
          </div>
        </details>
      </div>
    </div>
  );
}

function AgentPanel({ title, events }: { title: string; events: ReasoningEvent[] }) {
  const failures = events.filter((e) => (e.status || "").toLowerCase() === "failed" || e.kind === "run_failed");
  const decisions = events
    .filter((e) => safeText(e.what) || safeText(e.why))
    .slice(-3)
    .reverse();

  return (
    <CollapsibleSection title={title} defaultOpen={title === "Orchestrator"}>
      {events.length === 0 ? <p className="text-sm text-[var(--foreground-muted)]">No events.</p> : null}

      {failures.length > 0 || decisions.length > 0 ? (
        <div className="mb-3 rounded border border-[var(--border)] bg-[var(--surface)] p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Summary</div>
          <div className="mt-2 space-y-2">
            {failures.slice(0, 3).map((e, idx) => (
              <div key={`f-${idx}`} className="text-sm text-red-200">
                {safeText(e.error) || safeText(e.what) || "Failure"}
              </div>
            ))}
            {decisions.map((e, idx) => (
              <div key={`d-${idx}`} className="text-sm text-[var(--foreground)]">
                {safeText(e.what) || safeText(e.why) || "Decision"}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="space-y-3">
        {events.map((ev, idx) => (
          <EventCard key={`${ev.ts_iso || "t"}-${ev.node || "n"}-${idx}`} ev={ev} />
        ))}
      </div>
    </CollapsibleSection>
  );
}

export default function ReasoningTab({ query, values }: ReasoningTabProps) {
  const [showSkipped, setShowSkipped] = useState(false);
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [search, setSearch] = useState("");

  const trace = useMemo(() => (values ? coerceEvents(values) : []), [values]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return trace
      .slice()
      .sort((a, b) => {
        const ta = a.ts_iso ? Date.parse(a.ts_iso) : 0;
        const tb = b.ts_iso ? Date.parse(b.ts_iso) : 0;
        return ta - tb;
      })
      .filter((e) => (showSkipped ? true : (e.status || "").toLowerCase() !== "skipped"))
      .filter((e) => (failuresOnly ? (e.status || "").toLowerCase() === "failed" || e.kind === "run_failed" : true))
      .filter((e) => {
        if (!q) return true;
        const hay = [
          e.node,
          e.agent,
          e.phase,
          e.status,
          e.kind,
          safeText(e.what),
          safeText(e.why),
          safeText(e.error),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return hay.includes(q);
      });
  }, [trace, showSkipped, failuresOnly, search]);

  const byAgent = useMemo(() => {
    const groups: Record<string, ReasoningEvent[]> = {
      Orchestrator: [],
      Planner: [],
      Research: [],
      Design: [],
      Critic: [],
      Evals: [],
      Unknown: [],
    };
    for (const ev of filtered) {
      const agent = ev.agent || "Unknown";
      (groups[agent] || groups.Unknown).push(ev);
    }
    return groups;
  }, [filtered]);

  if (!values) {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <p className="text-[var(--foreground-muted)]">No reasoning data available yet.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Query</div>
            <p className="mt-1 whitespace-pre-wrap text-sm text-[var(--foreground)]">{query}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
              <input type="checkbox" checked={showSkipped} onChange={(e) => setShowSkipped(e.target.checked)} />
              Show skipped
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--foreground)]">
              <input type="checkbox" checked={failuresOnly} onChange={(e) => setFailuresOnly(e.target.checked)} />
              Only failures
            </label>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search trace…"
              className="h-9 w-56 rounded border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]"
            />
          </div>
        </div>

        <div className="text-xs text-[var(--foreground-muted)]">
          {filtered.length} event(s){trace.length !== filtered.length ? ` (filtered from ${trace.length})` : ""}
        </div>
      </div>

      {trace.length === 0 ? (
        <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">No reasoning trace available for this run yet.</p>
        </div>
      ) : null}

      <div className="space-y-4">
        <AgentPanel title="Orchestrator" events={byAgent.Orchestrator} />
        <AgentPanel title="Planner" events={byAgent.Planner} />
        <AgentPanel title="Research" events={byAgent.Research} />
        <AgentPanel title="Design" events={byAgent.Design} />
        <AgentPanel title="Critic" events={byAgent.Critic} />
        <AgentPanel title="Evals" events={byAgent.Evals} />
        {byAgent.Unknown.length > 0 ? <AgentPanel title="Unknown" events={byAgent.Unknown} /> : null}
      </div>

      <details className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
        <summary className="cursor-pointer select-none text-sm text-[var(--foreground)]">Raw state (dev)</summary>
        <pre className="mt-3 max-h-[520px] overflow-auto rounded bg-[var(--background)] p-3 text-xs text-[var(--foreground)]">
          {formatJson(values)}
        </pre>
      </details>
    </div>
  );
}
