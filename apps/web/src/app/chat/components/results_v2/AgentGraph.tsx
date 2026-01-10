"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";

const AgentGraphCanvas = dynamic(() => import("./AgentGraphCanvas"), {
  ssr: false,
  loading: () => (
    <div className="mt-6 h-[520px] rounded-lg border border-[var(--border)] bg-[var(--background)] p-6">
      <div className="text-sm font-semibold text-[var(--foreground)]">Loading graph…</div>
      <div className="mt-1 text-sm text-[var(--foreground-muted)]">
        Initializing interactive visualizer.
      </div>
    </div>
  ),
});

type GraphNode = {
  id: string;
  type?: "agent" | "tool" | "human" | "external" | "start" | "end";
  label?: string;
  agent_id?: string;
};

type GraphEdge = {
  source: string;
  target: string;
  edge_type?: "control" | "data";
  label?: string;
  condition?: string;
};

type AgentGraphProps = {
  graph: {
    nodes?: GraphNode[];
    edges?: GraphEdge[];
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
  } | null;
};

export default function AgentGraph({ graph }: AgentGraphProps) {
  const graphVisualization = useMemo(() => {
    if (!graph?.nodes || !graph?.edges) return null;
    return { totalNodes: graph.nodes.length, totalEdges: graph.edges.length };
  }, [graph]);

  if (!graph) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Agent Graph</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No graph data available</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">
            Objective 3: Agent Interaction Graph
          </h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">
            Control flow, data flow, and agent relationships
          </p>
        </div>
        {graphVisualization && (
          <div className="flex gap-3 text-xs">
            <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-[var(--foreground-muted)]">
              {graphVisualization.totalNodes} nodes
            </span>
            <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-[var(--foreground-muted)]">
              {graphVisualization.totalEdges} edges
            </span>
          </div>
        )}
      </div>

      <div className="mt-6">
        <AgentGraphCanvas graph={graph} />
      </div>

      {/* Termination Conditions */}
      {graph?.termination_conditions && graph.termination_conditions.length > 0 && (
        <div className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Termination Conditions
          </div>
          <ul className="mt-2 space-y-1">
            {graph.termination_conditions.map((condition, idx) => (
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
                {condition}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Loops */}
      {graph?.loops && graph.loops.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-400">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 1l4 4-4 4" />
              <path d="M3 11V9a4 4 0 0 1 4-4h14" />
              <path d="M7 23l-4-4 4-4" />
              <path d="M21 13v2a4 4 0 0 1-4 4H3" />
            </svg>
            Iteration Loops
          </div>
          <div className="mt-2 space-y-2">
            {graph.loops.map((loop) => (
              <div key={loop.id} className="text-sm text-[var(--foreground)]">
                <span className="font-medium">{loop.name}</span>
                {loop.max_iterations && (
                  <span className="ml-2 text-[var(--foreground-muted)]">
                    (max {loop.max_iterations} iterations)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </section>
  );
}

