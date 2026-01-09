"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import dagre from "@dagrejs/dagre";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Edge,
  type Node,
  type ReactFlowInstance,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";

type AscGraphNode = {
  id: string;
  type?: "agent" | "tool" | "human" | "external" | "start" | "end";
  label?: string;
  agent_id?: string;
};

type AscGraphEdge = {
  source: string;
  target: string;
  edge_type?: "control" | "data";
  label?: string;
  condition?: string;
};

type AgentGraphCanvasProps = {
  graph: {
    nodes?: AscGraphNode[];
    edges?: AscGraphEdge[];
  };
};

type LayoutDirection = "TB" | "LR";

const NODE_SIZES: Record<string, { w: number; h: number }> = {
  agent: { w: 240, h: 72 },
  start: { w: 120, h: 44 },
  end: { w: 120, h: 44 },
};

function safeNodeType(t?: string) {
  if (!t) return "agent";
  if (t === "agent" || t === "start" || t === "end") return t;
  return "agent";
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

function ToolNode(props: NodeProps) {
  const data = props.data as { label: string; subtitle?: string };
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[var(--foreground)]">
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="flex items-start gap-2">
        <div className="mt-0.5 flex h-7 w-7 items-center justify-center rounded-md bg-[var(--border)]/35 text-[var(--foreground-muted)]">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2v6m0 8v6" />
            <path d="M2 12h6m8 0h6" />
            <circle cx="12" cy="12" r="3" />
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

function buildLayout(nodes: Node[], edges: Edge[], direction: LayoutDirection): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));

  const rankdir = direction;
  g.setGraph({ rankdir, nodesep: 40, ranksep: 70, marginx: 20, marginy: 20 });

  for (const n of nodes) {
    const t = safeNodeType(n.type);
    const size = NODE_SIZES[t] ?? NODE_SIZES.tool;
    g.setNode(n.id, { width: size.w, height: size.h });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id) as { x: number; y: number } | undefined;
    const t = safeNodeType(n.type);
    const size = NODE_SIZES[t] ?? NODE_SIZES.tool;
    if (!pos) return n;
    // ReactFlow uses top-left; dagre gives center
    return {
      ...n,
      position: { x: pos.x - size.w / 2, y: pos.y - size.h / 2 },
    };
  });
}

export default function AgentGraphCanvas({ graph }: AgentGraphCanvasProps) {
  const [direction, setDirection] = useState<LayoutDirection>("TB");
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const rfRef = useRef<ReactFlowInstance | null>(null);

  const { nodes, edges } = useMemo(() => {
    const rawNodes = (graph.nodes ?? [])
      .filter((n) => n && typeof n.id === "string" && n.id.trim())
      .filter((n) => safeNodeType(n.type) === "agent" || safeNodeType(n.type) === "start" || safeNodeType(n.type) === "end");
    const rawEdges = (graph.edges ?? []).filter(
      (e) => e && typeof e.source === "string" && typeof e.target === "string" && e.source.trim() && e.target.trim()
    );

    const nodeById = new Map<string, AscGraphNode>();
    for (const n of rawNodes) nodeById.set(n.id, n);

    const allowedIds = new Set(Array.from(nodeById.keys()));
    const filteredEdges = rawEdges.filter((e) => allowedIds.has(e.source) && allowedIds.has(e.target));

    // Derive hierarchy signal from edges: supervises (control) and reports (data)
    const supervisesOut = new Set<string>();
    const supervisesIn = new Set<string>();
    for (const e of filteredEdges) {
      const label = (e.label || "").toLowerCase();
      if (e.edge_type === "control" && label.includes("supervis")) {
        supervisesOut.add(e.source);
        supervisesIn.add(e.target);
      }
    }

    const rfNodes: Node[] = Array.from(nodeById.values()).map((n) => {
      const t = safeNodeType(n.type);
      const label = n.label ?? n.id;
      const subtitle =
        t === "agent"
          ? supervisesOut.has(n.id)
            ? "Supervisor"
            : supervisesIn.has(n.id)
            ? "Worker"
            : "Agent"
          : t === "start" || t === "end"
          ? undefined
          : t;
      return {
        id: n.id,
        type: t,
        position: { x: 0, y: 0 },
        data: { label, subtitle },
      };
    });

    const rfEdges: Edge[] = filteredEdges.map((e, idx) => {
      const et = e.edge_type === "data" ? "data" : "control";
      const isControl = et === "control";
      const isReturnPath = et === "data" && (e.label || "").toLowerCase().includes("report");
      return {
        id: `${e.source}__${e.target}__${idx}`,
        source: e.source,
        target: e.target,
        label: showEdgeLabels ? (e.label ?? (isControl ? "control" : "data")) : undefined,
        animated: isControl,
        style: isControl
          ? { stroke: "var(--accent)", strokeWidth: 1.8 }
          : isReturnPath
          ? { stroke: "var(--accent)", strokeWidth: 1.4, strokeDasharray: "6 4" }
          : { stroke: "var(--foreground-muted)", strokeWidth: 1.4, strokeDasharray: "6 4" },
        labelStyle: { fill: "var(--foreground)", fontSize: 10, fontWeight: 600 },
        labelBgStyle: { fill: "var(--surface)" },
        labelBgPadding: [6, 3],
        labelBgBorderRadius: 6,
      };
    });

    // Layout based on control edges to keep a DAG-like layout even when return paths introduce cycles.
    const layoutEdges = rfEdges.filter((e) => e.animated);
    const laidOutNodes = buildLayout(rfNodes, layoutEdges, direction);
    return { nodes: laidOutNodes, edges: rfEdges };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes, graph.edges, direction, showEdgeLabels]);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    rfRef.current = instance;
    instance.fitView({ padding: 0.18 });
  }, []);

  const resetView = useCallback(() => {
    rfRef.current?.fitView({ padding: 0.18 });
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
            onClick={() => setDirection((d) => (d === "TB" ? "LR" : "TB"))}
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


