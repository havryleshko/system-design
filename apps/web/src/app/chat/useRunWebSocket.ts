import { useCallback, useEffect, useRef } from "react";

import { buildRunStreamUrl } from "@/utils/langgraph";

type RunStreamPayload = {
  type: "message-delta" | "values-updated" | "run-completed" | "error" | "ping" | "interrupt";
  content?: string;
  output?: string;
  status?: string;
  error?: string;
  values?: Record<string, unknown>;
};

type RunWebSocketHandlers = {
  onDelta?: (content: string) => void;
  onValuesUpdated?: (payload: { output?: string; values?: Record<string, unknown> }) => void;
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
  // Store handlers in a ref so they can be updated without recreating the socket
  const handlersRef = useRef<RunWebSocketHandlers>({});

  const clearRetry = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    console.log("[WS Client] disconnect() called, stopRef was:", stopRef.current);
    stopRef.current = true;
    clearRetry();
    if (socketRef.current) {
      console.log("[WS Client] Closing socket from disconnect()");
      socketRef.current.close();
      socketRef.current = null;
    }
  }, [clearRetry]);

  // Cleanup on unmount only
  useEffect(() => {
    return () => {
      console.log("[WS Client] Cleanup effect running (unmount)");
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
      // Close any existing connection first
      if (socketRef.current) {
        console.log("[WS Client] Closing existing socket before new connection");
        socketRef.current.close();
        socketRef.current = null;
      }
      
      stopRef.current = false;
      attemptRef.current = 0;
      clearRetry();
      
      // Store handlers in ref so message handler always has latest
      handlersRef.current = handlers;

      const backoffMs = [400, 1200];

      const handleMessage = (raw: MessageEvent<string>) => {
        const currentHandlers = handlersRef.current;
        try {
          const data = JSON.parse(raw.data) as RunStreamPayload;
          if (data.type === "ping" || data.type === "interrupt") return;
          if (data.type === "message-delta") {
            currentHandlers.onDelta?.(data.content ?? "");
            return;
          }
          if (data.type === "values-updated") {
            currentHandlers.onValuesUpdated?.({
              output: data.output,
              values: data.values,
            });
            return;
          }
          if (data.type === "run-completed") {
            console.log("[WS Client] Received run-completed, closing socket");
            stopRef.current = true;
            currentHandlers.onCompleted?.(data.status);
            socketRef.current?.close();
            return;
          }
          if (data.type === "error") {
            console.log("[WS Client] Received error event:", data.error);
            stopRef.current = true;
            currentHandlers.onError?.(data.error || "WebSocket error");
            socketRef.current?.close();
            return;
          }
        } catch (err) {
          console.error("[WS Client] Failed to parse message:", err);
          stopRef.current = true;
          currentHandlers.onError?.("Failed to parse WebSocket message");
          socketRef.current?.close();
        }
      };

      const openSocket = () => {
        if (stopRef.current) {
          console.log("[WS Client] openSocket called but stopRef is true, aborting");
          return;
        }
        
        const url = buildRunStreamUrl({ threadId, runId, token });
        console.log("[WS Client] Opening WebSocket to:", url.substring(0, 100) + "...");
        const ws = new WebSocket(url);
        socketRef.current = ws;

        ws.onmessage = handleMessage;
        ws.onopen = () => {
          console.log("[WS Client] WebSocket opened successfully, readyState:", ws.readyState);
          attemptRef.current = 0;
        };
        ws.onerror = (event) => {
          console.error("[WS Client] WebSocket error event, readyState:", ws.readyState);
          if (stopRef.current) {
            console.log("[WS Client] Error but stopRef is true, ignoring");
            return;
          }
          stopRef.current = true;
          handlersRef.current.onError?.("WebSocket connection failed");
          ws.close();
        };
        ws.onclose = (event) => {
          console.log("[WS Client] WebSocket closed. Code:", event.code, "Reason:", event.reason, "stopRef:", stopRef.current, "wasClean:", event.wasClean);
          socketRef.current = null;
          if (stopRef.current) {
            console.log("[WS Client] Close but stopRef is true, not retrying");
            return;
          }

          // Don't retry on policy violation (1008) - indicates permanent error like invalid run
          // Also limit max retries to prevent infinite loops
          const maxRetries = 5;
          if (event.code === 1008 || attemptRef.current >= maxRetries) {
            console.log("[WS Client] Not retrying - code:", event.code, "attempts:", attemptRef.current);
            stopRef.current = true;
            handlersRef.current.onError?.(event.reason || "Connection closed permanently");
            return;
          }

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
