"use client";

import { useMemo, useState } from "react";
import {
  ArchitectureDecision,
  AgentGraph,
  AgentCards,
  ExecutionFlow,
  DeployabilityMatrix,
} from "./results_v2";

type ResultsV2Props = {
  output: string | null;
  startedAt: Date | null;
  values: Record<string, unknown> | null;
  runStatus: string | null;
};

// Type definitions for ASC v1.1
type ASCV11 = {
  version?: string;
  generated_at?: string;
  goal?: string;
  product_state?: {
    status?: "ready_to_build" | "draft";
    missing_for_ready?: string[];
    assumptions_made?: string[];
    confidence_score?: number;
  };
  decision?: {
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
  };
  agents?: Array<{
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
    tools?: Array<{
      tool_id?: string;
      scopes?: string[];
      usage_notes?: string;
    }>;
    memory?: Array<{
      type?: string;
      purpose?: string;
      implementation_hint?: string;
    }>;
    orchestration_constraints?: string[];
  }>;
  graph?: {
    nodes?: Array<{
      id: string;
      type?: "agent" | "tool" | "human" | "external" | "start" | "end";
      label?: string;
      agent_id?: string;
    }>;
    edges?: Array<{
      source: string;
      target: string;
      edge_type?: "control" | "data";
      label?: string;
      condition?: string;
    }>;
    loops?: Array<{
      id: string;
      name: string;
      entry_node?: string;
      exit_node?: string;
      max_iterations?: number;
      termination_conditions?: string[];
    }>;
    entry_point?: string;
    exit_points?: string[];
    termination_conditions?: string[];
  };
  execution_flow?: {
    steps?: Array<{
      order?: number;
      agent_id?: string;
      action?: string;
      inputs_from?: string[];
      outputs_to?: string[];
      can_loop?: boolean;
      human_checkpoint?: boolean;
    }>;
    parallel_groups?: string[][];
    critical_path?: number[];
  };
  tooling?: {
    tool_catalog_version?: string;
    tools?: Array<{
      id?: string;
      display_name?: string;
      category?: string;
      default_choice_reason?: string;
      alternatives?: Array<{
        tool_id?: string;
        reason?: string;
      }>;
      auth_config?: { auth_type?: string; scopes_examples?: string[] } | null;
      failure_handling?: string;
      agent_permissions?: Record<string, string[]>;
    }>;
  };
  deployability?: {
    constraints?: Array<{
      agent_id?: string;
      model_class?: string;
      estimated_latency_ms?: number;
      estimated_cost_per_call?: string;
      scaling_notes?: string;
      failure_modes?: string[];
      safeguards?: string[];
      degrades_to?: string;
      recovery_strategy?: string;
    }>;
    orchestration_platform?: string;
    orchestration_platform_reason?: string;
    infrastructure_notes?: string[];
  };
  kickoff?: {
    summary?: string;
    open_questions?: string[];
    risks?: string[];
  };
  research?: {
    highlights?: string[];
    citations?: Array<{ source?: string; url?: string; title?: string }>;
    risks?: string[];
  };
};

export default function ResultsV2({ output, startedAt, values, runStatus }: ResultsV2Props) {
  const [showDebug, setShowDebug] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("all");

  // Extract ASC v1.1 from values
  const asc: ASCV11 | null = useMemo(() => {
    if (!values) return null;
    
    // Try to find ASC v1.1 in design_state
    const designState = values.design_state as Record<string, unknown> | undefined;
    if (designState?.asc_v11) {
      return designState.asc_v11 as ASCV11;
    }
    
    // Fallback to asc_v1 and try to use it
    if (designState?.asc_v1) {
      const v1 = designState.asc_v1 as Record<string, unknown>;
      // Map v1 to v1.1 structure for backward compatibility
      return {
        version: "v1",
        goal: v1.goal as string,
        kickoff: v1.kickoff as ASCV11["kickoff"],
        research: v1.research as ASCV11["research"],
      };
    }
    
    return null;
  }, [values]);

  const valuesJson = useMemo(() => {
    if (!values) return "";
    try {
      return JSON.stringify(values, null, 2);
    } catch {
      return "[unserializable values]";
    }
  }, [values]);

  const status = (runStatus ?? "").toLowerCase() || "unknown";
  const started = startedAt ? startedAt.toLocaleString() : "";
  const isV11 = asc?.version === "v1.1";

  // Section navigation
  const sections = [
    { id: "all", label: "All" },
    { id: "outputs", label: "Outputs" },
    { id: "decision", label: "Decision" },
    { id: "agents", label: "Agents" },
    { id: "graph", label: "Graph" },
    { id: "flow", label: "Flow" },
    { id: "deploy", label: "Deploy" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-semibold text-[var(--foreground)]">
                Architecture Blueprint
              </h2>
              {asc?.product_state?.status && (
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wider ${
                    asc.product_state.status === "ready_to_build"
                      ? "bg-green-500/20 text-green-400 border border-green-500/30"
                      : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                  }`}
                >
                  {asc.product_state.status === "ready_to_build" ? "Ready to Build" : "Draft"}
                </span>
              )}
            </div>
            {asc?.goal && (
              <p className="mt-2 text-sm text-[var(--foreground-muted)]">{asc.goal}</p>
            )}
          </div>
          <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShowDebug((v) => !v)}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
              {showDebug ? "Hide debug" : "Debug"}
          </button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Status
            </div>
            <div className="mt-1 text-sm font-medium text-[var(--foreground)]">{status}</div>
          </div>
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Agents
            </div>
            <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
              {asc?.agents?.length ?? 0}
            </div>
          </div>
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Tools
            </div>
            <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
              {asc?.tooling?.tools?.length ?? 0}
            </div>
          </div>
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              ASC Version
            </div>
            <div className="mt-1 text-sm font-medium text-[var(--foreground)]">
              {asc?.version ?? "—"}
            </div>
          </div>
        </div>

        {/* Section Navigation */}
        <div className="mt-4 flex flex-wrap gap-2">
          {sections.map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveSection(section.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                activeSection === section.id
                  ? "bg-[var(--accent)] text-white"
                  : "border border-[var(--border)] bg-[var(--background)] text-[var(--foreground-muted)] hover:border-[var(--accent)] hover:text-[var(--foreground)]"
              }`}
            >
              {section.label}
            </button>
          ))}
        </div>
      </section>

      {/* ASC v1.1 Sections */}
      {isV11 ? (
        <>
          {/* Produced Outputs */}
          {(activeSection === "all" || activeSection === "outputs") && (
            <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
              <h2 className="text-lg font-semibold text-[var(--foreground)]">Produced Outputs</h2>
              <p className="mt-1 text-sm text-[var(--foreground-muted)]">
                When the run completes, this system produces:
              </p>
              <ul className="mt-4 space-y-2 text-sm text-[var(--foreground)]">
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                  Multi-agent architecture spec
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                  Deployable workflow graph (agents-only) with return paths
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                  Explicit trade-offs
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                  Failure modes and safeguards (per agent)
                </li>
                <li className="flex items-start gap-2">
                  <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                  Implementation-ready agent specs (inputs, outputs, tools, memory ownership)
                </li>
              </ul>
            </section>
          )}

          {/* Objective 1: Architecture Decision */}
          {(activeSection === "all" || activeSection === "decision") && (
            <ArchitectureDecision
              decision={asc.decision ?? null}
              productState={asc.product_state ?? null}
            />
          )}

          {/* Objective 2 & 4: Agent Specifications */}
          {(activeSection === "all" || activeSection === "agents") && (
            <AgentCards agents={asc.agents ?? null} tooling={asc.tooling ?? null} />
          )}

          {/* Objective 3: Agent Graph */}
          {(activeSection === "all" || activeSection === "graph") && (
            <AgentGraph
              graph={asc.graph ?? null}
            />
          )}

          {/* Objective 3: Execution Flow */}
          {(activeSection === "all" || activeSection === "flow") && (
            <ExecutionFlow
              executionFlow={asc.execution_flow ?? null}
              agents={asc.agents}
            />
          )}

          {/* Objective 4: Deployability Matrix */}
          {(activeSection === "all" || activeSection === "deploy") && (
            <DeployabilityMatrix
              deployability={asc.deployability ?? null}
              tooling={asc.tooling ?? null}
              agents={asc.agents}
            />
          )}
        </>
      ) : (
        /* Fallback for non-v1.1 or missing ASC */
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
          <div className="text-center py-8">
            <h3 className="text-lg font-semibold text-[var(--foreground)]">
              Architecture Data Loading...
            </h3>
            <p className="mt-2 text-sm text-[var(--foreground-muted)]">
              {status === "running"
                ? "The architecture is being generated. Results will appear here when complete."
                : status === "completed"
                ? "Architecture generation complete. Parsing results..."
                : "Waiting for architecture data."}
            </p>
            {asc?.kickoff?.summary && (
              <div className="mt-6 max-w-2xl mx-auto text-left rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                  Summary
                </div>
                <p className="mt-2 text-sm text-[var(--foreground)]">{asc.kickoff.summary}</p>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Research Highlights (always show if available) */}
      {asc?.research?.highlights && asc.research.highlights.length > 0 && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Research Highlights</h2>
          <ul className="mt-4 space-y-2">
            {asc.research.highlights.map((highlight, idx) => (
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
                {highlight}
              </li>
            ))}
          </ul>
          
          {/* Citations */}
          {asc.research.citations && asc.research.citations.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[var(--border)]">
              <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Citations
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {asc.research.citations.map((citation, idx) => (
                  <a
                    key={idx}
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs text-[var(--foreground-muted)] hover:border-[var(--accent)] hover:text-[var(--foreground)]"
                  >
                    {citation.title || citation.source || citation.url}
                  </a>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Debug Panel */}
      {showDebug && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Debug: raw values</h3>
            <button
              type="button"
              onClick={async () => {
                if (!valuesJson) return;
                await navigator.clipboard.writeText(valuesJson);
              }}
              disabled={!valuesJson}
              className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Copy JSON
            </button>
          </div>
          <pre className="max-h-[420px] overflow-auto rounded border border-[var(--border)] bg-[var(--background)] p-3 text-xs text-[var(--foreground)]">
            <code className="block whitespace-pre">{valuesJson || "No values available."}</code>
          </pre>
        </section>
      )}
    </div>
  );
}
