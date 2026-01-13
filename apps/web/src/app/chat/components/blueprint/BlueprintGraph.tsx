"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

import type { BlueprintGraph as BlueprintGraphType } from "../../types";

const BlueprintGraphCanvas = dynamic(() => import("./BlueprintGraphCanvas"), {
  ssr: false,
  loading: () => (
    <div className="mt-6 h-[520px] rounded-lg border border-[var(--border)] bg-[var(--background)] p-6">
      <div className="text-sm font-semibold text-[var(--foreground)]">Loading graph…</div>
      <div className="mt-1 text-sm text-[var(--foreground-muted)]">Initializing interactive visualizer.</div>
    </div>
  ),
});

export default function BlueprintGraph({ graph }: { graph: BlueprintGraphType }) {
  const graphStats = useMemo(() => {
    const nodes = graph?.nodes?.length ?? 0;
    const edges = graph?.edges?.length ?? 0;
    return { nodes, edges };
  }, [graph]);

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Multi-agent System</h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">Control flow and data flow between agents</p>
        </div>
        <div className="flex gap-3 text-xs">
          <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-[var(--foreground-muted)]">
            {graphStats.nodes} nodes
          </span>
          <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-[var(--foreground-muted)]">
            {graphStats.edges} edges
          </span>
        </div>
      </div>

      <div className="mt-6">
        <BlueprintGraphCanvas graph={graph} />
      </div>
    </section>
  );
}

