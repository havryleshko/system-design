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


