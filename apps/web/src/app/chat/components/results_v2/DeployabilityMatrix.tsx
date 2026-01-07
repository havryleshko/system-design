"use client";

type DeployabilityConstraint = {
  agent_id?: string;
  model_class?: string;
  estimated_latency_ms?: number;
  estimated_cost_per_call?: string;
  scaling_notes?: string;
  failure_modes?: string[];
  recovery_strategy?: string;
};

type ToolAlternative = {
  tool_id?: string;
  reason?: string;
};

type SelectedTool = {
  id?: string;
  display_name?: string;
  category?: string;
  default_choice_reason?: string;
  alternatives?: ToolAlternative[];
  auth_config?: { auth_type?: string; scopes_examples?: string[] } | null;
  failure_handling?: string;
  agent_permissions?: Record<string, string[]>;
};

type DeployabilityMatrixProps = {
  deployability: {
    constraints?: DeployabilityConstraint[];
    orchestration_platform?: string;
    orchestration_platform_reason?: string;
    infrastructure_notes?: string[];
  } | null;
  tooling: {
    tool_catalog_version?: string;
    tools?: SelectedTool[];
  } | null;
  agents?: Array<{ id?: string; name?: string }> | null;
};

const categoryIcons: Record<string, string> = {
  orchestration: "🔄",
  db_storage: "🗄️",
  vector_store: "📊",
  queue_workflow: "📬",
  observability: "👁️",
  deployment_hosting: "☁️",
  auth_identity: "🔐",
};

const modelClassColors: Record<string, string> = {
  frontier: "bg-purple-500/20 text-purple-400",
  mid: "bg-blue-500/20 text-blue-400",
  small: "bg-green-500/20 text-green-400",
  embedding: "bg-amber-500/20 text-amber-400",
  fine_tuned: "bg-pink-500/20 text-pink-400",
};

export default function DeployabilityMatrix({
  deployability,
  tooling,
  agents,
}: DeployabilityMatrixProps) {
  const getAgentName = (agentId: string) => {
    const agent = agents?.find((a) => a.id === agentId);
    return agent?.name || agentId;
  };

  const hasData =
    (deployability?.constraints?.length ?? 0) > 0 ||
    (tooling?.tools?.length ?? 0) > 0;

  if (!hasData) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Deployability Matrix</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No deployability data available</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div>
        <h2 className="text-lg font-semibold text-[var(--foreground)]">
          Objective 4: Deployability Matrix
        </h2>
        <p className="mt-1 text-sm text-[var(--foreground-muted)]">
          Per-agent constraints, grounded tools, and infrastructure
        </p>
      </div>

      {/* Orchestration Platform */}
      {deployability?.orchestration_platform && (
        <div className="mt-6 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/5 p-4">
          <div className="flex items-center gap-2">
            <span className="text-lg">🔄</span>
            <div>
              <div className="text-sm font-semibold text-[var(--foreground)]">
                Orchestration: {deployability.orchestration_platform}
              </div>
              {deployability.orchestration_platform_reason && (
                <p className="text-sm text-[var(--foreground-muted)]">
                  {deployability.orchestration_platform_reason}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Agent Constraints Table */}
      {deployability?.constraints && deployability.constraints.length > 0 && (
        <div className="mt-6">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Agent Constraints
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="pb-2 text-left font-semibold text-[var(--foreground)]">Agent</th>
                  <th className="pb-2 text-left font-semibold text-[var(--foreground)]">Model</th>
                  <th className="pb-2 text-left font-semibold text-[var(--foreground)]">Latency</th>
                  <th className="pb-2 text-left font-semibold text-[var(--foreground)]">Cost</th>
                  <th className="pb-2 text-left font-semibold text-[var(--foreground)]">Recovery</th>
                </tr>
              </thead>
              <tbody>
                {deployability.constraints.map((constraint, idx) => (
                  <tr key={idx} className="border-b border-[var(--border)]/50">
                    <td className="py-3 font-medium text-[var(--foreground)]">
                      {getAgentName(constraint.agent_id ?? "")}
                    </td>
                    <td className="py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          modelClassColors[constraint.model_class ?? "mid"] ?? modelClassColors.mid
                        }`}
                      >
                        {constraint.model_class ?? "mid"}
                      </span>
                    </td>
                    <td className="py-3 text-[var(--foreground-muted)]">
                      {constraint.estimated_latency_ms
                        ? `~${constraint.estimated_latency_ms}ms`
                        : "—"}
                    </td>
                    <td className="py-3 text-[var(--foreground-muted)]">
                      {constraint.estimated_cost_per_call ?? "—"}
                    </td>
                    <td className="py-3 text-[var(--foreground-muted)]">
                      {constraint.recovery_strategy ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Failure Modes */}
          {deployability.constraints.some((c) => c.failure_modes?.length) && (
            <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-400">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 8v4m0 4h.01" />
                </svg>
                Potential Failure Modes
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {[...new Set(deployability.constraints.flatMap((c) => c.failure_modes ?? []))].map(
                  (mode, idx) => (
                    <span
                      key={idx}
                      className="rounded bg-red-500/10 px-2 py-1 text-xs text-red-400"
                    >
                      {mode}
                    </span>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Grounded Tools */}
      {tooling?.tools && tooling.tools.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Grounded Tools (Catalog v{tooling.tool_catalog_version ?? "1"})
            </div>
            <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-xs text-[var(--foreground-muted)]">
              {tooling.tools.length} tool{tooling.tools.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {tooling.tools.map((tool, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4"
              >
                {/* Tool Header */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{categoryIcons[tool.category ?? ""] ?? "🔧"}</span>
                    <div>
                      <div className="font-semibold text-[var(--foreground)]">
                        {tool.display_name ?? tool.id}
                      </div>
                      <div className="text-xs text-[var(--foreground-muted)]">
                        {tool.category?.replace("_", " ")}
                      </div>
                    </div>
                  </div>
                  {tool.auth_config?.auth_type && (
                    <span className="rounded bg-[var(--accent)]/10 px-2 py-0.5 text-[10px] font-medium text-[var(--accent)]">
                      {tool.auth_config.auth_type}
                    </span>
                  )}
                </div>

                {/* Why chosen */}
                {tool.default_choice_reason && (
                  <p className="mt-2 text-xs text-[var(--foreground-muted)]">
                    {tool.default_choice_reason}
                  </p>
                )}

                {/* Alternatives */}
                {tool.alternatives && tool.alternatives.length > 0 && (
                  <div className="mt-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                      Alternatives
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {tool.alternatives.map((alt, aidx) => (
                        <span
                          key={aidx}
                          className="group relative rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--foreground)]"
                          title={alt.reason}
                        >
                          {alt.tool_id}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Agent Permissions */}
                {tool.agent_permissions && Object.keys(tool.agent_permissions).length > 0 && (
                  <div className="mt-3 border-t border-[var(--border)] pt-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                      Agent Permissions
                    </div>
                    <div className="mt-1 space-y-1">
                      {Object.entries(tool.agent_permissions).map(([agentId, scopes]) => (
                        <div key={agentId} className="flex items-center gap-2 text-xs">
                          <span className="text-[var(--foreground)]">{getAgentName(agentId)}</span>
                          {scopes.length > 0 && (
                            <span className="text-[var(--foreground-muted)]">
                              ({scopes.join(", ")})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Failure Handling */}
                {tool.failure_handling && (
                  <div className="mt-3 text-xs text-[var(--foreground-muted)]">
                    <span className="font-medium">On failure:</span> {tool.failure_handling}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Infrastructure Notes */}
      {deployability?.infrastructure_notes && deployability.infrastructure_notes.length > 0 && (
        <div className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Infrastructure Notes
          </div>
          <ul className="mt-2 space-y-1">
            {deployability.infrastructure_notes.map((note, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                <svg
                  viewBox="0 0 24 24"
                  className="mt-0.5 h-4 w-4 flex-shrink-0 text-[var(--accent)]"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M9 12l2 2 4-4" />
                  <circle cx="12" cy="12" r="10" />
                </svg>
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

