export const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:10000";
export const DEV_BASE_CANDIDATES: string[] = [
  "http://localhost:10000",
  "http://127.0.0.1:10000",
];
export const WS_BASE = BASE.replace(/^http/i, "ws");
export const ASSISTANT_ID = "system_design_agent";

export function backendUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return new URL(normalized, BASE).toString();
}

export function backendHeaders(token: string, options?: { json?: boolean }): HeadersInit {
  const headers: HeadersInit = {
    Authorization: `Bearer ${token}`,
  };
  if (options?.json) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

export function buildRunStreamUrl(params: { threadId: string; runId: string; token: string }): string {
  const { threadId, runId, token } = params;
  const url = new URL(`/threads/${threadId}/stream`, WS_BASE);
  url.searchParams.set("run_id", runId);
  url.searchParams.set("token", token);
  return url.toString();
}

