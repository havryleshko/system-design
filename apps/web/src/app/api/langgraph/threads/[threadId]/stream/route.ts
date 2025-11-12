import { createServerSupabase } from "@/utils/supabase/server";
import { BASE } from "@/utils/langgraph";

export const runtime = "nodejs"; // ensure Node runtime for streaming proxy

export async function GET(
  req: Request,
  context: unknown
) {
  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return new Response("Unauthorized", { status: 401 });
  }

  const params =
    typeof context === "object" && context !== null && "params" in context
      ? (context as { params?: unknown }).params
      : undefined;
  const threadParam =
    typeof params === "object" && params !== null && "threadId" in params
      ? (params as { threadId?: unknown }).threadId
      : undefined;
  const threadId = Array.isArray(threadParam) ? threadParam[0] : threadParam;
  if (!threadId) {
    return new Response("Thread ID missing", { status: 400 });
  }
  const url = new URL(req.url);
  const search = url.search || ""; // forward mode params
  const upstreamUrl = `${BASE}/threads/${threadId}/stream${search}`;

  const upstream = await fetch(upstreamUrl, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
    signal: req.signal,
  });

  console.log("[stream] proxy upstream", {
    threadId,
    upstreamStatus: upstream.status,
    ok: upstream.ok,
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    return new Response(`Upstream error ${upstream.status}: ${text}`, {
      status: upstream.status,
    });
  }

  // Proxy the stream to the client
  const responseHeaders = new Headers({
    "Content-Type": upstream.headers.get("content-type") || "text/event-stream",
    "Cache-Control": "no-store",
  });

  return new Response(upstream.body, { headers: responseHeaders });
}


