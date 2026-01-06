// NOTE:
// - In production (Vercel), this must be set to https://api.systesign.com
// - If it is missing, server-side code may fall back to localhost and fail.
export const BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  // Server-only fallback (kept for safety if someone configured BACKEND_URL instead).
  process.env.BACKEND_URL ||
  "http://localhost:8000";
export const DEV_BASE_CANDIDATES: string[] = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
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

export function buildRunStreamUrl(params: { threadId: string; runId: string }): string {
  const { threadId, runId } = params;
  const url = new URL(`/threads/${threadId}/stream`, WS_BASE);
  url.searchParams.set("run_id", runId);
  return url.toString();
}

