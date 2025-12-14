import type { ArchitectureByAspect, ChatMessage, DesignJson } from "./types";

export function extractContent(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object") {
          const segment = part as Record<string, unknown>;
          if (typeof segment.text === "string") return segment.text;
          if (typeof segment.content === "string") return segment.content;
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.text === "string") return record.text;
    if (typeof record.content === "string") return record.content;
  }
  return "";
}

export function normalizeMessages(raw: unknown): ChatMessage[] {
  if (!Array.isArray(raw)) return [];
  const normalized: ChatMessage[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const record = entry as Record<string, unknown>;
    const rawRole = typeof record.role === "string" ? record.role.toLowerCase() : undefined;
    const rawType = typeof record.type === "string" ? record.type.toLowerCase() : undefined;
    let role: ChatMessage["role"] = "assistant";
    if (rawRole === "assistant" || rawRole === "user" || rawRole === "system") role = rawRole;
    else if (rawType === "ai") role = "assistant";
    else if (rawType === "human") role = "user";
    const content = extractContent(record.content).trim();
    if (content) normalized.push({ role, content });
  }
  return normalized;
}

export function getValuesFromStateLike(input: unknown): Record<string, unknown> | null {
  if (typeof input !== "object" || input === null) return null;
  const rec = input as Record<string, unknown>;
  const values = rec.values;
  if (typeof values === "object" && values !== null) return values as Record<string, unknown>;
  return null;
}

export function pickDesignJson(values: Record<string, unknown> | null | undefined): DesignJson | null {
  const architecture = pickArchitecture(values);
  // Backwards-compatibility: surface the first aspect if callers still expect a single design json
  if (!architecture) return null;
  const firstKey = Object.keys(architecture)[0];
  return firstKey ? architecture[firstKey] ?? null : null;
}

export function pickArchitecture(values: Record<string, unknown> | null | undefined): ArchitectureByAspect | null {
  if (!values) return null;
  const raw = (values["architecture_json"] ?? values["design_json"]) as unknown;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;

  const record = raw as Record<string, unknown>;
  const looksLikeMap = Object.values(record).some((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return false;
    const rec = entry as Record<string, unknown>;
    return (
      "elements" in rec ||
      "relations" in rec ||
      "groups" in rec ||
      "notes" in rec ||
      "aspects" in rec ||
      "meta" in rec
    );
  });

  if (looksLikeMap) {
    const architecture: ArchitectureByAspect = {};
    for (const [key, value] of Object.entries(record)) {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        architecture[key] = value as DesignJson;
      }
    }
    return Object.keys(architecture).length > 0 ? architecture : null;
  }

  const design = record as DesignJson;
  const hasContent =
    !!design.elements?.length ||
    !!design.relations?.length ||
    !!design.groups?.length ||
    !!design.notes ||
    !!design.aspects?.length ||
    !!design.meta;

  if (!hasContent) return null;
  return { architecture: design };
}

