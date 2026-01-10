"use client";

type ArchitectureDecisionProps = {
  decision: {
    single_vs_multi?: "single" | "multi";
    architecture_type?: string;
    architecture_type_reason?: string;
    architecture_class?:
      | "hierarchical_orchestrator"
      | "supervisor_worker"
      | "planner_executor_evaluator_loop"
      | "hybrid";
    architecture_class_reason?: string;
    tradeoffs?: Array<{
      decision?: string;
      alternatives?: string[];
      why?: string;
    }>;
    confidence?: number;
    assumptions?: string[];
    missing_info?: string[];
    pattern_influences?: string[];
    pattern_deviation_notes?: string[];
  } | null;
  productState: {
    status?: "ready_to_build" | "draft";
    missing_for_ready?: string[];
    assumptions_made?: string[];
    confidence_score?: number;
  } | null;
};

export default function ArchitectureDecision({ decision, productState }: ArchitectureDecisionProps) {
  if (!decision) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Architecture Decision</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No decision data available</p>
      </section>
    );
  }

  const {
    single_vs_multi,
    architecture_type,
    architecture_type_reason,
    architecture_class,
    architecture_class_reason,
    tradeoffs,
    confidence,
    assumptions,
    missing_info,
    pattern_influences,
  } = decision;

  const status = productState?.status ?? "draft";
  const confidencePercent = Math.round((confidence ?? 0.5) * 100);

  // Pattern display names
  const patternNames: Record<string, string> = {
    react: "ReAct (Reasoning + Acting)",
    "plan-and-execute": "Plan-and-Execute",
    reflection: "Reflection",
    supervisor: "Supervisor (Hierarchical)",
    "tool-use": "Tool-Use",
    mrkl: "MRKL (Modular Reasoning)",
    "self-ask": "Self-Ask",
    "chain-of-thought": "Chain-of-Thought",
    "tree-of-thought": "Tree-of-Thought",
    "multi-agent-debate": "Multi-Agent Debate",
  };

  const resolvedArchitectureClass = (() => {
    if (architecture_class) return architecture_class;
    // Defensive mapping for older runs that only had architecture_type.
    const t = (architecture_type || "").toLowerCase();
    if (t === "supervisor" || t === "supervisor_worker") return "supervisor_worker";
    if (t === "plan-and-execute" || t === "planner_executor_evaluator_loop") return "planner_executor_evaluator_loop";
    if (t === "reflection" || t === "react" || t === "tool-use" || t === "mrkl" || t === "self-ask") {
      return "hierarchical_orchestrator";
    }
    return null;
  })();

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      {/* Header with Status Badge */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">
            Objective 1: Architecture Decision
          </h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">
            Single vs multi-agent determination with rationale
          </p>
        </div>
        <div
          className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${
            status === "ready_to_build"
              ? "bg-green-500/20 text-green-400 border border-green-500/30"
              : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
          }`}
        >
          {status === "ready_to_build" ? "Ready to Build" : "Draft"}
        </div>
      </div>

      {/* Main Decision */}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {/* Architecture Class Card */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Architecture Class
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-[var(--accent)]/20 px-2.5 py-1 text-xs font-semibold text-[var(--accent)]">
              {single_vs_multi === "multi" ? "Multi-Agent" : "Single Agent"}
            </span>
            <span className="text-sm font-medium text-[var(--foreground)]">
              <span className="font-mono">
                {resolvedArchitectureClass ?? "—"}
              </span>
            </span>
          </div>
          {resolvedArchitectureClass === "hybrid" && architecture_class_reason && (
            <p className="mt-3 text-sm text-[var(--foreground-muted)]">{architecture_class_reason}</p>
          )}
          {!architecture_class && (
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              Backfilled from legacy runs (architecture_type).
            </p>
          )}
        </div>

        {/* Architecture Type Card */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Architecture Type
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                single_vs_multi === "multi"
                  ? "bg-[var(--accent)]/20 text-[var(--accent)]"
                  : "bg-blue-500/20 text-blue-400"
              }`}
            >
              {single_vs_multi === "multi" ? "Multi-Agent" : "Single Agent"}
            </span>
            {architecture_type && (
              <span className="text-sm font-medium text-[var(--foreground)]">
                {patternNames[architecture_type] ?? architecture_type}
              </span>
            )}
          </div>
          {architecture_type_reason && (
            <p className="mt-3 text-sm text-[var(--foreground-muted)]">
              {architecture_type_reason}
            </p>
          )}
        </div>
      </div>

      {/* Confidence Card */}
      <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
          Confidence Score
        </div>
        <div className="mt-2 flex items-end gap-2">
          <span className="text-3xl font-bold text-[var(--foreground)]">{confidencePercent}%</span>
          <span className="mb-1 text-sm text-[var(--foreground-muted)]">
            {confidencePercent >= 80
              ? "High confidence"
              : confidencePercent >= 50
              ? "Moderate confidence"
              : "Low confidence"}
          </span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--border)]">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              confidencePercent >= 80
                ? "bg-green-500"
                : confidencePercent >= 50
                ? "bg-amber-500"
                : "bg-red-500"
            }`}
            style={{ width: `${confidencePercent}%` }}
          />
        </div>
      </div>

      {/* Trade-offs */}
      <div className="mt-6">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
          Trade-offs
        </div>
        {tradeoffs && tradeoffs.length > 0 ? (
          <div className="mt-3 space-y-3">
            {tradeoffs.slice(0, 8).map((t, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4"
              >
                <div className="text-sm font-semibold text-[var(--foreground)]">
                  {t.decision || "Decision"}
                </div>
                {t.alternatives && t.alternatives.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {t.alternatives.slice(0, 6).map((alt, aidx) => (
                      <span
                        key={aidx}
                        className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--foreground)]"
                      >
                        {alt}
                      </span>
                    ))}
                  </div>
                )}
                {t.why && (
                  <p className="mt-2 text-sm text-[var(--foreground-muted)]">{t.why}</p>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-[var(--foreground-muted)]">No trade-offs provided for this run.</p>
        )}
      </div>

      {/* Pattern Influences */}
      {pattern_influences && pattern_influences.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Pattern Influences
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {pattern_influences.map((pattern, idx) => (
              <span
                key={idx}
                className="inline-flex items-center rounded-full border border-[var(--border)] bg-[var(--background)] px-3 py-1 text-xs font-medium text-[var(--foreground)]"
              >
                {patternNames[pattern] ?? pattern}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Assumptions & Missing Info */}
      {((assumptions && assumptions.length > 0) || (missing_info && missing_info.length > 0)) && (
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {/* Assumptions */}
          {assumptions && assumptions.length > 0 && (
            <div className="rounded-lg border border-dashed border-amber-500/30 bg-amber-500/5 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-400">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Assumptions Made
              </div>
              <ul className="mt-2 space-y-1">
                {assumptions.slice(0, 5).map((assumption, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground-muted)]">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-amber-400" />
                    {assumption}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Missing Info */}
          {missing_info && missing_info.length > 0 && (
            <div className="rounded-lg border border-dashed border-red-500/30 bg-red-500/5 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-400">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 8v4m0 4h.01" />
                </svg>
                Missing Information
              </div>
              <ul className="mt-2 space-y-1">
                {missing_info.slice(0, 5).map((info, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground-muted)]">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-red-400" />
                    {info}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

