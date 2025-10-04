import { NextRequest } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST(req: NextRequest) {
  try {
 
    // 1. Insert run trace into `trace_logs`
    const runTrace = {
      thread_id: payload.thread_id ?? null,
      run_id: payload.run_id ?? null,
      user_id: payload.user_id ?? null, // You can try to infer/set this (optional)
      level: payload.status === 'failed' ? 'error' : 'info',
      message: payload.status ?? payload.node ?? payload.state?.last_node ?? 'run completed',
      data: payload, // Store the full payload for auditing/debugging
    };

    const { error: traceError } = await supabase.from('trace_logs').insert(runTrace);
    if (traceError) {
      return new Response('Failed trace_logs insert: ' + traceError.message, { status: 500 });
    }


    const values = payload.state?.values ?? {};
    const messages: Array<{ role: string; content: any }> = Array.isArray(values.messages) ? values.messages : [];
    const qnaRows = messages
    .filter(m => m.role === "user" || m.role === "assistant")
    .map((m, i) => ({
        thread_id: payload.thread_id,
        turn_index: i,
        role: m.role,
        content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
    }));
    if (qnaRows.length) {
    const { error: qnaError } = await supabase.from("qna").upsert(qnaRows, { onConflict: "thread_id,turn_index" });
    if (qnaError) {
        return new Response("Failed qna upsert: " + qnaError.message, { status: 500 });
    }
    }

  }
}