import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { getState } from "../actions";

export default async function Page() {
  const { runId } = await getState(undefined, { redirectTo: "/chat" });
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  return (
    <ChatGuard>
      <ChatClient initialMessages={initialMessages} runId={runId} />
    </ChatGuard>
  );
}

