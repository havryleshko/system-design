"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import dagre from "@dagrejs/dagre";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type Edge,
  type Node,
  type ReactFlowInstance,
  type EdgeProps,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";

import type { BlueprintGraph as BlueprintGraphType } from "../../types";

type LayoutDirection = "TB" | "LR";

const NODE_SIZES: Record<string, { w: number; h: number }> = {
  agent: { w: 260, h: 76 },
  start: { w: 120, h: 44 },
  end: { w: 120, h: 44 },
};

function safeNodeType(t?: string) {
  if (!t) return "agent";
  if (t === "agent" || t === "start" || t === "end") return t;
  return "agent";
}

function safeEdgeKind(e?: { kind?: string }) {
  const k = (e?.kind ?? "control").toString().toLowerCase();
  if (k === "control" || k === "data" || k === "hitl") return k as "control" | "data" | "hitl";
  return "control";
}

function KindBadgeEdge(props: EdgeProps) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style, markerEnd, data } = props;
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  const kind = (data as any)?.kind as "control" | "data" | "hitl" | undefined;
  const label = (data as any)?.label as string | undefined;

  const badgeClass =
    kind === "hitl"
      ? "bg-blue-500/20 text-blue-400"
      : kind === "data"
      ? "bg-[var(--border)]/50 text-[var(--foreground-muted)]"
      : "bg-[var(--accent)]/20 text-[var(--accent)]";

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "none",
          }}
          className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 shadow-sm"
        >
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badgeClass}`}>
            {kind ?? "control"}
          </span>
          {label ? (
            <span className="max-w-[180px] truncate text-[11px] font-semibold text-[var(--foreground)]">{label}</span>
          ) : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

function AgentNode(props: NodeProps) {
  const data = props.data as { label: string; subtitle?: string };
  return (
    <div className="rounded-lg border border-[var(--accent)]/35 bg-[var(--surface)] px-3 py-2 text-[var(--foreground)] shadow-sm">
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="flex items-start gap-2">
        <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-md bg-[var(--accent)]/15 text-[var(--accent)]">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="8" r="4" />
            <path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" />
          </svg>
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{data.label}</div>
          {data.subtitle && <div className="truncate text-xs text-[var(--foreground-muted)]">{data.subtitle}</div>}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

function StartEndNode(props: NodeProps) {
  const data = props.data as { label: string };
  return (
    <div className="rounded-full border border-[var(--border)] bg-[var(--background)] px-4 py-2 text-xs font-semibold text-[var(--foreground)]">
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      {data.label}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = {
  agent: AgentNode,
  start: StartEndNode,
  end: StartEndNode,
} as const;

const edgeTypes = {
  kindBadge: KindBadgeEdge,
} as const;

function buildLayout(nodes: Node[], edges: Edge[], direction: LayoutDirection): Node[] {
  const nodeIds = new Set(nodes.map((n) => n.id));
  const adj = new Map<string, Set<string>>();
  for (const id of nodeIds) adj.set(id, new Set());
  for (const e of edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue;
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  }

  // Find connected components (undirected)
  const comps: string[][] = [];
  const seen = new Set<string>();
  for (const id of nodeIds) {
    if (seen.has(id)) continue;
    const stack = [id];
    const comp: string[] = [];
    seen.add(id);
    while (stack.length) {
      const cur = stack.pop()!;
      comp.push(cur);
      for (const nxt of adj.get(cur) || []) {
        if (!seen.has(nxt)) {
          seen.add(nxt);
          stack.push(nxt);
        }
      }
    }
    comps.push(comp);
  }

  const nodeById = new Map(nodes.map((n) => [n.id, n] as const));
  const edgesInComp = (compSet: Set<string>) =>
    edges.filter((e) => compSet.has(e.source) && compSet.has(e.target));

  // Layout each component separately to avoid overlap, then pack them into rows.
  const packed: Node[] = [];
  let cursorX = 0;
  let cursorY = 0;
  let rowH = 0;
  const maxRowW = 1400;
  const gapX = 140;
  const gapY = 140;

  for (const comp of comps.sort((a, b) => b.length - a.length)) {
    const set = new Set(comp);
    const compNodes = comp.map((id) => nodeById.get(id)!).filter(Boolean);
    const compEdges = edgesInComp(set);

    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: direction,
      nodesep: 70,
      ranksep: 120,
      marginx: 40,
      marginy: 40,
    });

    for (const n of compNodes) {
      const t = safeNodeType(n.type);
      const size = NODE_SIZES[t] ?? NODE_SIZES.agent;
      g.setNode(n.id, { width: size.w, height: size.h });
    }
    for (const e of compEdges) g.setEdge(e.source, e.target);

    dagre.layout(g);

    // Convert positions and compute bounds
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    const laid = compNodes.map((n) => {
      const pos = g.node(n.id) as { x: number; y: number } | undefined;
      const t = safeNodeType(n.type);
      const size = NODE_SIZES[t] ?? NODE_SIZES.agent;
      const x = pos ? pos.x - size.w / 2 : 0;
      const y = pos ? pos.y - size.h / 2 : 0;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + size.w);
      maxY = Math.max(maxY, y + size.h);
      return { ...n, position: { x, y } };
    });

    const compW = Math.max(1, maxX - minX);
    const compH = Math.max(1, maxY - minY);

    if (cursorX > 0 && cursorX + compW > maxRowW) {
      cursorX = 0;
      cursorY += rowH + gapY;
      rowH = 0;
    }

    // Normalize to (0,0) and apply packing offsets
    for (const n of laid) {
      n.position = {
        x: n.position.x - minX + cursorX,
        y: n.position.y - minY + cursorY,
      };
      packed.push(n);
    }

    cursorX += compW + gapX;
    rowH = Math.max(rowH, compH);
  }

  return packed;
}

export default function BlueprintGraphCanvas({ graph }: { graph: BlueprintGraphType }) {
  const [direction, setDirection] = useState<LayoutDirection>("TB");
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const rfRef = useRef<ReactFlowInstance | null>(null);

  const { nodes, edges } = useMemo(() => {
    const rawNodes = (graph.nodes ?? []).filter((n) => n && typeof n.id === "string" && n.id.trim());
    const rawEdges = (graph.edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string" && e.source.trim() && e.target.trim()
    );

    const nodeById = new Map<string, any>();
    for (const n of rawNodes) nodeById.set(n.id, n);

    const allowedIds = new Set(Array.from(nodeById.keys()));
    const filteredEdges = rawEdges.filter((e) => allowedIds.has(e.source) && allowedIds.has(e.target));

    const rfNodes: Node[] = Array.from(nodeById.values()).map((n) => {
      const t = safeNodeType(n.type);
      const label = n.label ?? n.id;
      const subtitle = t === "agent" ? "Agent" : undefined;
      return {
        id: n.id,
        type: t,
        position: { x: 0, y: 0 },
        data: { label, subtitle },
      };
    });

    const rfEdges: Edge[] = filteredEdges.map((e, idx) => {
      const kind = safeEdgeKind(e);
      const isControl = kind === "control";
      const isHitl = kind === "hitl";
      return {
        id: `${e.source}__${e.target}__${idx}`,
        source: e.source,
        target: e.target,
        type: "kindBadge",
        data: { kind, label: showEdgeLabels ? (e.label ?? "") : "" },
        animated: isControl,
        style: isHitl
          ? { stroke: "#60a5fa", strokeWidth: 1.8, strokeDasharray: "2 4" }
          : isControl
          ? { stroke: "var(--accent)", strokeWidth: 1.8 }
          : { stroke: "var(--foreground-muted)", strokeWidth: 1.4, strokeDasharray: "6 4" },
      };
    });

    // Layout should use ALL edges (control + data + hitl) so connectivity is preserved
    // and disconnected components don't overlap.
    const laidOutNodes = buildLayout(rfNodes, rfEdges, direction);
    return { nodes: laidOutNodes, edges: rfEdges };
  }, [graph.nodes, graph.edges, direction, showEdgeLabels]);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    rfRef.current = instance;
    instance.fitView({ padding: 0.18 });
  }, []);

  const resetView = useCallback(() => {
    rfRef.current?.fitView({ padding: 0.18 });
  }, []);

  const toggleDirection = useCallback(() => {
    setDirection((d) => (d === "TB" ? "LR" : "TB"));
    // Let the next render commit, then fit.
    setTimeout(() => {
      rfRef.current?.fitView({ padding: 0.18 });
    }, 0);
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={resetView}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            Reset view
          </button>
          <button
            type="button"
            onClick={toggleDirection}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            Layout: {direction === "TB" ? "Top-Down" : "Left-Right"}
          </button>
          <button
            type="button"
            onClick={() => setShowEdgeLabels((v) => !v)}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            {showEdgeLabels ? "Hide labels" : "Show labels"}
          </button>
        </div>
        <div className="text-xs text-[var(--foreground-muted)]">
          {nodes.length} nodes • {edges.length} edges
        </div>
      </div>

      <div className="h-[520px] overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--background)]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onInit={handleInit}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          proOptions={{ hideAttribution: true }}
        >
          <MiniMap pannable zoomable />
          <Controls showInteractive={false} />
          <Background gap={18} size={1} />
        </ReactFlow>
      </div>
    </div>
  );
}

