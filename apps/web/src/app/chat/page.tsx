import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { getState } from "../actions";

export default async function Page() {
  const { runId, state } = await getState(undefined, { redirectTo: "/chat" });
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  const userId = state?.values?.user_id ?? null;
  // Prefer architecture_json for the left panel; fall back to design_json if present
  const designJson = (state?.values?.architecture_json as any) || (state?.values?.design_json as any) || null;
  return (
    <ChatGuard>
      <ChatClient userId={userId} initialMessages={initialMessages} runId={runId} designJson={designJson} />
    </ChatGuard>
  );
}

