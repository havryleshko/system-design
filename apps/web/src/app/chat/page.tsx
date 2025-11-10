import ChatClient from "./ChatClient";
import ChatGuard from "./Guard";
import { createThread, getState } from "../actions";
import type { DesignJson } from "./ArchitecturePanel";

export default async function Page() {
  let runId: string | null = null;
  let designJson: DesignJson | null = null;
  try {
    const { runId: r, state } = await getState(undefined, { redirectTo: "/chat" });
    runId = r;
    // Prefer architecture_json for the left panel; fall back to design_json if present
    designJson =
      (state?.values?.architecture_json as DesignJson) ||
      (state?.values?.design_json as DesignJson) ||
      null;
  } catch {
    // Ensure a valid thread cookie exists so the UI can start a new run
    await createThread({ force: true });
    runId = null;
    designJson = null;
  }
  const initialMessages: { role: "user" | "assistant" | "system"; content: string }[] = [];
  const userId = null;
  return (
    <ChatGuard>
      <ChatClient userId={userId} initialMessages={initialMessages} runId={runId} designJson={designJson} />
    </ChatGuard>
  );
}

