"use client";

type ExecutionStep = {
  order?: number;
  agent_id?: string;
  action?: string;
  inputs_from?: string[];
  outputs_to?: string[];
  can_loop?: boolean;
  human_checkpoint?: boolean;
};

type ExecutionFlowProps = {
  executionFlow: {
    steps?: ExecutionStep[];
    parallel_groups?: string[][];
    critical_path?: number[];
  } | null;
  agents?: Array<{ id?: string; name?: string }> | null;
};

export default function ExecutionFlow({ executionFlow, agents }: ExecutionFlowProps) {
  if (!executionFlow?.steps || executionFlow.steps.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Execution Flow</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No execution flow defined</p>
      </section>
    );
  }

  const { steps, parallel_groups, critical_path } = executionFlow;
  const criticalPathSet = new Set(critical_path ?? []);

  // Helper to get agent name
  const getAgentName = (agentId: string) => {
    const agent = agents?.find((a) => a.id === agentId);
    return agent?.name || agentId;
  };

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">
            Objective 3: Execution Flow
          </h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">
            Ordered runbook with loops and human checkpoints
          </p>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-xs text-[var(--foreground-muted)]">
          {steps.length} step{steps.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Execution Steps */}
      <div className="mt-6 relative">
        {/* Vertical line connector */}
        <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-[var(--border)]" />

        <div className="space-y-4">
          {steps.map((step, idx) => {
            const isOnCriticalPath = criticalPathSet.has(step.order ?? idx + 1);
            const isFirst = idx === 0;
            const isLast = idx === steps.length - 1;

            return (
              <div key={idx} className="relative flex gap-4">
                {/* Step number indicator */}
                <div
                  className={`relative z-10 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border-2 ${
                    isOnCriticalPath
                      ? "border-[var(--accent)] bg-[var(--accent)] text-white"
                      : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)]"
                  }`}
                >
                  {step.human_checkpoint ? (
                    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="8" r="4" />
                      <path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
                    </svg>
                  ) : (
                    <span className="text-sm font-semibold">{step.order ?? idx + 1}</span>
                  )}
                </div>

                {/* Step content */}
                <div
                  className={`flex-1 rounded-lg border p-4 ${
                    isOnCriticalPath
                      ? "border-[var(--accent)]/30 bg-[var(--accent)]/5"
                      : "border-[var(--border)] bg-[var(--background)]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-[var(--foreground)]">
                          {getAgentName(step.agent_id ?? "")}
                        </span>
                        {step.can_loop && (
                          <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium text-amber-400">
                            Can Loop
                          </span>
                        )}
                        {step.human_checkpoint && (
                          <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400">
                            Human Checkpoint
                          </span>
                        )}
                      </div>
                      {step.action && (
                        <p className="mt-1 text-sm text-[var(--foreground-muted)]">{step.action}</p>
                      )}
                    </div>
                    {isOnCriticalPath && (
                      <span className="rounded-full bg-[var(--accent)]/20 px-2 py-0.5 text-[10px] font-medium text-[var(--accent)]">
                        Critical Path
                      </span>
                    )}
                  </div>

                  {/* Data flow indicators */}
                  <div className="mt-3 flex flex-wrap gap-3 text-xs">
                    {step.inputs_from && step.inputs_from.length > 0 && !isFirst && (
                      <div className="flex items-center gap-1 text-[var(--foreground-muted)]">
                        <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 19V5M5 12l7-7 7 7" />
                        </svg>
                        <span>
                          From: {step.inputs_from.map((id) => (id === "user" ? "User" : getAgentName(id))).join(", ")}
                        </span>
                      </div>
                    )}
                    {step.outputs_to && step.outputs_to.length > 0 && !isLast && (
                      <div className="flex items-center gap-1 text-[var(--foreground-muted)]">
                        <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M12 5v14M5 12l7 7 7-7" />
                        </svg>
                        <span>
                          To: {step.outputs_to.map((id) => (id === "user" ? "User" : getAgentName(id))).join(", ")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Parallel Groups */}
      {parallel_groups && parallel_groups.length > 0 && (
        <div className="mt-6 rounded-lg border border-blue-500/30 bg-blue-500/5 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-400">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
            </svg>
            Parallel Execution Groups
          </div>
          <div className="mt-2 space-y-2">
            {parallel_groups.map((group, idx) => (
              <div key={idx} className="flex items-center gap-2 text-sm text-[var(--foreground)]">
                <span className="text-[var(--foreground-muted)]">Group {idx + 1}:</span>
                <span>Steps {group.join(", ")} can run in parallel</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex flex-wrap items-center gap-4 text-xs text-[var(--foreground-muted)]">
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-[var(--accent)]" />
          Critical path
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-amber-500" />
          Can loop
        </div>
        <div className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-full bg-blue-500" />
          Human checkpoint
        </div>
      </div>
    </section>
  );
}

