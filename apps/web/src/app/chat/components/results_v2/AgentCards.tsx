"use client";

import { useState } from "react";

type AgentToolAccess = {
  tool_id?: string;
  scopes?: string[];
  usage_notes?: string;
};

type AgentMemorySpec = {
  type?: string;
  purpose?: string;
  implementation_hint?: string;
};

type AgentSpec = {
  id?: string;
  name?: string;
  role?: string;
  boundaries?: string[];
  inputs?: string[];
  outputs?: string[];
  reports_to?: string | null;
  subagents?: string[];
  model_class?: "frontier" | "mid" | "small" | "embedding" | "fine_tuned";
  model_class_rationale?: string;
  tools?: AgentToolAccess[];
  memory?: AgentMemorySpec[];
  orchestration_constraints?: string[];
};

type AgentCardsProps = {
  agents: AgentSpec[] | null;
  tooling?: {
    tools?: Array<{ id?: string; display_name?: string }>;
  } | null;
};

const modelClassConfig: Record<string, { label: string; color: string; badge: string }> = {
  frontier: { label: "Frontier", color: "bg-purple-500/20 text-purple-400 border-purple-500/30", badge: "F" },
  mid: { label: "Mid-tier", color: "bg-blue-500/20 text-blue-400 border-blue-500/30", badge: "M" },
  small: { label: "Small", color: "bg-green-500/20 text-green-400 border-green-500/30", badge: "S" },
  embedding: { label: "Embedding", color: "bg-amber-500/20 text-amber-400 border-amber-500/30", badge: "E" },
  fine_tuned: { label: "Fine-tuned", color: "bg-pink-500/20 text-pink-400 border-pink-500/30", badge: "FT" },
};

function AgentCard({
  agent,
  allAgents,
  toolNameById,
}: {
  agent: AgentSpec;
  allAgents: AgentSpec[];
  toolNameById: Map<string, string>;
}) {
  const [expanded, setExpanded] = useState(false);
  
  const modelConfig = modelClassConfig[agent.model_class ?? "mid"] ?? modelClassConfig.mid;
  const reportsToAgent = agent.reports_to
    ? allAgents.find((a) => a.id === agent.reports_to)
    : null;
  const subagentDetails = (agent.subagents ?? [])
    .map((id) => allAgents.find((a) => a.id === id))
    .filter(Boolean);

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] overflow-hidden">
      {/* Header */}
      <div
        className="flex cursor-pointer items-center justify-between p-4 transition-colors hover:bg-[var(--surface)]"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-sm font-semibold text-[var(--accent)]">
            {modelConfig.badge}
          </div>
          <div>
            <h3 className="font-semibold text-[var(--foreground)]">{agent.name || agent.id}</h3>
            <p className="text-sm text-[var(--foreground-muted)]">{agent.role}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${modelConfig.color}`}>
            {modelConfig.label}
          </span>
          <svg
            viewBox="0 0 24 24"
            className={`h-5 w-5 text-[var(--foreground-muted)] transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="border-t border-[var(--border)] p-4 space-y-4">
          {/* Inputs / Outputs */}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Inputs
              </div>
              {agent.inputs && agent.inputs.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {agent.inputs.slice(0, 8).map((i, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                      <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                      {i}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--foreground-muted)]">Not specified</p>
              )}
            </div>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Outputs
              </div>
              {agent.outputs && agent.outputs.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {agent.outputs.slice(0, 8).map((o, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                      <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                      {o}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-[var(--foreground-muted)]">Not specified</p>
              )}
            </div>
          </div>

          {/* Model Rationale */}
          {agent.model_class_rationale && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Model Selection Rationale
              </div>
              <p className="mt-1 text-sm text-[var(--foreground)]">{agent.model_class_rationale}</p>
            </div>
          )}

          {/* Boundaries */}
          {agent.boundaries && agent.boundaries.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Boundaries & Responsibilities
              </div>
              <ul className="mt-1 space-y-1">
                {agent.boundaries.map((boundary, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-[var(--foreground)]">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                    {boundary}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Relationships */}
          {(reportsToAgent || subagentDetails.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2">
              {reportsToAgent && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                    Reports To
                  </div>
                  <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
                    {reportsToAgent.name || reportsToAgent.id}
                  </div>
                </div>
              )}
              {subagentDetails.length > 0 && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                    Manages
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {subagentDetails.map((sub) => (
                      <span
                        key={sub?.id}
                        className="rounded bg-[var(--accent)]/10 px-2 py-0.5 text-xs font-medium text-[var(--foreground)]"
                      >
                        {sub?.name || sub?.id}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tools */}
          {agent.tools && agent.tools.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Tool Access
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {agent.tools.map((tool, idx) => (
                  <div
                    key={idx}
                    className="group relative rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
                  >
                    <div className="text-sm font-medium text-[var(--foreground)]">
                      {tool.tool_id ? toolNameById.get(tool.tool_id) ?? tool.tool_id : "Tool"}
                    </div>
                    {tool.tool_id && toolNameById.get(tool.tool_id) && (
                      <div className="mt-0.5 text-[10px] text-[var(--foreground-muted)]">{tool.tool_id}</div>
                    )}
                    {tool.scopes && tool.scopes.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {tool.scopes.map((scope, sidx) => (
                          <span
                            key={sidx}
                            className="rounded bg-[var(--background)] px-1.5 py-0.5 text-[10px] text-[var(--foreground-muted)]"
                          >
                            {scope}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Memory */}
          {agent.memory && agent.memory.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Owned Memory
              </div>
              <div className="mt-2 space-y-2">
                {agent.memory.map((mem, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-[var(--accent)]/10 px-2 py-0.5 text-xs font-medium text-[var(--accent)]">
                        {mem.type}
                      </span>
                      <span className="rounded bg-[var(--background)] px-2 py-0.5 text-[10px] font-medium text-[var(--foreground-muted)]">
                        Owned by this agent
                      </span>
                      {mem.implementation_hint && (
                        <span className="text-xs text-[var(--foreground-muted)]">
                          ({mem.implementation_hint})
                        </span>
                      )}
                    </div>
                    {mem.purpose && (
                      <p className="mt-1 text-sm text-[var(--foreground)]">{mem.purpose}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Orchestration Constraints */}
          {agent.orchestration_constraints && agent.orchestration_constraints.length > 0 && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-400">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                Orchestration Constraints
              </div>
              <ul className="mt-2 space-y-1">
                {agent.orchestration_constraints.map((constraint, idx) => (
                  <li key={idx} className="text-sm text-[var(--foreground)]">
                    • {constraint}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AgentCards({ agents, tooling }: AgentCardsProps) {
  if (!agents || agents.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Agent Specifications</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No agents defined</p>
      </section>
    );
  }

  const toolNameById = new Map<string, string>();
  for (const t of tooling?.tools ?? []) {
    if (t?.id && t?.display_name) toolNameById.set(t.id, t.display_name);
  }

  // Group agents by hierarchy
  const supervisors = agents.filter((a) => !a.reports_to && (a.subagents?.length ?? 0) > 0);
  const workers = agents.filter((a) => a.reports_to || (a.subagents?.length ?? 0) === 0);

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">
            Objective 2 & 4: Agent Specifications
          </h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">
            Decomposition, boundaries, and deployability constraints
          </p>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-xs text-[var(--foreground-muted)]">
          {agents.length} agent{agents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Agent Cards */}
      <div className="mt-6 space-y-3">
        {/* Supervisors first */}
        {supervisors.length > 0 && (
          <>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Supervisors
            </div>
            {supervisors.map((agent) => (
              <AgentCard key={agent.id} agent={agent} allAgents={agents} toolNameById={toolNameById} />
            ))}
          </>
        )}

        {/* Workers */}
        {workers.length > 0 && (
          <>
            {supervisors.length > 0 && (
              <div className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Workers
              </div>
            )}
            {workers.map((agent) => (
              <AgentCard key={agent.id} agent={agent} allAgents={agents} toolNameById={toolNameById} />
            ))}
          </>
        )}
      </div>
    </section>
  );
}

