import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { getState } from "../actions";

export default async function Page() {
  const { runId, state } = await getState(undefined, { redirectTo: "/chat" });
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  const userId = state?.values?.user_id ?? null;
  return (
    <ChatGuard>
      <ChatClient userId={userId} initialMessages={initialMessages} runId={runId} />
    </ChatGuard>
  );
}

