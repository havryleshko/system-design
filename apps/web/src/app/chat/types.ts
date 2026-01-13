export type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export type DesignElement = {
  id: string;
  kind: string;
  label: string;
  description?: string;
  technology?: string;
  tags?: string[];
};

export type DesignRelation = {
  source: string;
  target: string;
  label: string;
  technology?: string;
  direction?: string;
};

export type DesignGroup = {
  id: string;
  kind: string;
  label: string;
  technology?: string;
  children: string[];
};

export type ArchitectureMeta = {
  aspectId?: string;
  title?: string;
  summary?: string;
  agent?: string;
  status?: string;
  updatedAt?: string;
  tags?: string[];
  sourceNode?: string;
};

export type ArchitectureAspect = {
  id: string;
  title: string;
  summary?: string;
  description?: string;
  tags?: string[];
  elements?: DesignElement[];
  relations?: DesignRelation[];
  notes?: string[];
  detail?: string;
};

export type DesignJson = {
  elements?: DesignElement[];
  relations?: DesignRelation[];
  groups?: DesignGroup[];
  notes?: string | string[];
  aspects?: ArchitectureAspect[];
  meta?: ArchitectureMeta | null;
};

export type ArchitectureByAspect = Record<string, DesignJson>;

export type StreamPhase = "idle" | "running" | "waiting" | "clarifier" | "error";

export type ClarifierPrompt = {
  question: string;
  interruptId: string | null;
  runId: string | null;
  threadId: string | null;
};

export type BlueprintToolAccess = {
  tool_id: string;
  scopes?: string[];
  usage_notes?: string | null;
};

export type BlueprintAgent = {
  id: string;
  name: string;
  role: string;
  responsibilities?: string[];
  inputs?: string[];
  outputs?: string[];
  reports_to?: string | null;
  subagents?: string[];
  model?: string | null;
  tools?: BlueprintToolAccess[];
};

export type BlueprintGraphNode = {
  id: string;
  type?: "agent" | "start" | "end";
  label?: string;
  agent_id?: string | null;
};

export type BlueprintGraphEdge = {
  source: string;
  target: string;
  kind?: "control" | "data" | "hitl";
  label?: string;
  condition?: string;
};

export type BlueprintGraph = {
  nodes: BlueprintGraphNode[];
  edges: BlueprintGraphEdge[];
  entry_point?: string | null;
  exit_points?: string[];
};

export type Blueprint = {
  version: "v1";
  generated_at: string;
  goal: string;
  agents: BlueprintAgent[];
  graph: BlueprintGraph;
};


