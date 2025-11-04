import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { getState } from "../actions";
import type { DesignJson } from "./ArchitecturePanel";

export default async function Page() {
  const { runId, state } = await getState(undefined, { redirectTo: "/chat" });
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  const userId = state?.values?.user_id ?? null;
  // Prefer architecture_json for the left panel; fall back to design_json if present
  const designJson =
    (state?.values?.architecture_json as DesignJson) ||
    (state?.values?.design_json as DesignJson) ||
    null;
  return (
    <ChatGuard>
      <ChatClient userId={userId} initialMessages={initialMessages} runId={runId} designJson={designJson} />
    </ChatGuard>
  );
}

