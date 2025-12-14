import { useCallback, useEffect, useRef } from "react";

import { buildRunStreamUrl } from "@/utils/langgraph";

type RunStreamPayload = {
  type: "message-delta" | "values-updated" | "run-completed" | "error" | "ping" | "interrupt";
  content?: string;
  final_judgement?: string;
  output?: string;
  status?: string;
  error?: string;
  values?: Record<string, unknown>;
};

type RunWebSocketHandlers = {
  onDelta?: (content: string) => void;
  onValuesUpdated?: (payload: { finalJudgement?: string; output?: string; values?: Record<string, unknown> }) => void;
  onCompleted?: (status?: string) => void;
  onError?: (error: string) => void;
};

type ConnectParams = {
  threadId: string;
  runId: string;
  token: string;
  handlers: RunWebSocketHandlers;
};

export function useRunWebSocket() {
  const socketRef = useRef<WebSocket | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const stopRef = useRef(false);
  const attemptRef = useRef(0);

  const clearRetry = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    stopRef.current = true;
    clearRetry();
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
  }, [clearRetry]);

  // Cleanup on unmount only - use a ref to avoid re-running on disconnect changes
  useEffect(() => {
    return () => {
      // Clear retry timeout
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      // Close socket
      stopRef.current = true;
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, []); // Empty deps - only run on unmount

  const connect = useCallback(
    ({ threadId, runId, token, handlers }: ConnectParams) => {
      stopRef.current = false;
      attemptRef.current = 0;
      clearRetry();

      const backoffMs = [400, 1200];

      const handleMessage = (raw: MessageEvent<string>) => {
        try {
          const data = JSON.parse(raw.data) as RunStreamPayload;
          if (data.type === "ping" || data.type === "interrupt") return;
          if (data.type === "message-delta") {
            handlers.onDelta?.(data.content ?? "");
            return;
          }
          if (data.type === "values-updated") {
            handlers.onValuesUpdated?.({
              finalJudgement: data.final_judgement,
              output: data.output,
              values: data.values,
            });
            return;
          }
          if (data.type === "run-completed") {
            stopRef.current = true;
            handlers.onCompleted?.(data.status);
            socketRef.current?.close();
            return;
          }
          if (data.type === "error") {
            stopRef.current = true;
            handlers.onError?.(data.error || "WebSocket error");
            socketRef.current?.close();
            return;
          }
        } catch (err) {
          stopRef.current = true;
          handlers.onError?.("Failed to parse WebSocket message");
          socketRef.current?.close();
        }
      };

      const openSocket = () => {
        const url = buildRunStreamUrl({ threadId, runId, token });
        console.log("[WS Client] Opening WebSocket to:", url.substring(0, 100) + "...");
        const ws = new WebSocket(url);
        socketRef.current = ws;

        ws.onmessage = handleMessage;
        ws.onopen = () => {
          console.log("[WS Client] WebSocket opened successfully");
          attemptRef.current = 0;
        };
        ws.onerror = (event) => {
          console.error("[WS Client] WebSocket error:", event);
          if (stopRef.current) return;
          stopRef.current = true;
          handlers.onError?.("WebSocket connection failed");
          ws.close();
        };
        ws.onclose = (event) => {
          console.log("[WS Client] WebSocket closed. Code:", event.code, "Reason:", event.reason, "stopRef:", stopRef.current);
          socketRef.current = null;
          if (stopRef.current) return;

          const attempt = attemptRef.current;
          const delay = backoffMs[Math.min(attempt, backoffMs.length - 1)];
          attemptRef.current = attempt + 1;
          console.log("[WS Client] Will retry in", delay, "ms (attempt", attempt + 1, ")");
          retryTimeoutRef.current = setTimeout(() => {
            openSocket();
          }, delay);
        };
      };

      openSocket();

      return () => {
        disconnect();
      };
    },
    [clearRetry, disconnect]
  );

  return { connect, disconnect };
}
