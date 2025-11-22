import { redirect } from "next/navigation";

import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { buildEnsureThreadUrl } from "@/shared/thread";
import { getState } from "../actions";
import type { DesignJson } from "./ArchitecturePanel";

export default async function Page() {
  let runId: string | null = null;
  let threadId: string | null = null;
  let designJson: DesignJson | null = null;
  try {
    const { runId: r, threadId: tid, state } = await getState(undefined, { redirectTo: "/chat" });
    runId = r;
    threadId = tid;
    // Prefer architecture_json for the left panel; fall back to design_json if present
    designJson =
      (state?.values?.architecture_json as DesignJson) ||
      (state?.values?.design_json as DesignJson) ||
      null;
  } catch {
    redirect(buildEnsureThreadUrl("/chat", true));
  }
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  const userId = null;
  return (
    <ChatGuard>
      <ChatClient
        userId={userId}
        initialMessages={initialMessages}
        runId={runId}
        threadId={threadId}
        designJson={designJson}
      />
    </ChatGuard>
  );
}

