import { useCallback, useEffect, useRef } from "react";

import { getThreadState } from "@/app/actions";

type PollingHandlers = {
  onValuesUpdated?: (payload: { output?: string; values?: Record<string, unknown> }) => void;
  onCompleted?: (status?: string) => void;
  onError?: (error: string) => void;
};

type StartPollingParams = {
  threadId: string;
  token: string;
  intervalMs?: number;
  maxDurationMs?: number; // Maximum time to poll before giving up
  handlers: PollingHandlers;
};

// Default max polling duration: 10 minutes
const DEFAULT_MAX_DURATION_MS = 10 * 60 * 1000;

export function useRunPolling() {
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef(false);
  const handlersRef = useRef<PollingHandlers>({});
  const pollCountRef = useRef(0);
  const lastStatusRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    console.log("[Polling] stop() called, isPolling:", isPollingRef.current, "pollCount:", pollCountRef.current);
    isPollingRef.current = false;
    pollCountRef.current = 0;
    lastStatusRef.current = null;
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      console.log("[Polling] Cleanup effect running (unmount)");
      stop();
    };
  }, [stop]);

  const start = useCallback(
    ({ threadId, token, intervalMs = 3000, maxDurationMs = DEFAULT_MAX_DURATION_MS, handlers }: StartPollingParams) => {
      // Prevent starting if already polling
      if (isPollingRef.current) {
        console.log("[Polling] start() called but already polling, ignoring");
        return;
      }
      
      console.log("[Polling] Starting polling for thread:", threadId, "interval:", intervalMs, "maxDuration:", maxDurationMs);
      stop(); // Clear any existing interval just in case
      
      isPollingRef.current = true;
      handlersRef.current = handlers;
      pollCountRef.current = 0;

      // Set up a maximum duration timeout
      timeoutRef.current = setTimeout(() => {
        if (isPollingRef.current) {
          console.log("[Polling] Max duration reached, stopping polling");
          handlersRef.current.onError?.("Polling timeout - run may have failed to start");
          stop();
        }
      }, maxDurationMs);

      const poll = async () => {
        // Check if we should still be polling
        if (!isPollingRef.current) {
          console.log("[Polling] poll() called but isPolling is false, skipping");
          return;
        }
        
        pollCountRef.current++;
        
        try {
          const state = await getThreadState(threadId, token);
          
          // Check again after async call
          if (!isPollingRef.current) {
            console.log("[Polling] Stopped during fetch, ignoring result");
            return;
          }
          
          if (!state) {
            console.log("[Polling] No state returned, poll #", pollCountRef.current);
            // If we've polled many times with no state, something is wrong
            if (pollCountRef.current > 20) {
              console.log("[Polling] Too many empty responses, stopping");
              handlersRef.current.onError?.("Run failed to start - no state available");
              stop();
            }
            return;
          }

          // Track if status is changing (run is making progress)
          const currentStatus = state.status || "unknown";
          if (lastStatusRef.current && lastStatusRef.current === currentStatus && pollCountRef.current > 30) {
            // Status hasn't changed after 30 polls (~90 seconds at 3s interval)
            // The run might be stuck or never started
            console.log("[Polling] Status unchanged for too long:", currentStatus);
          }
          lastStatusRef.current = currentStatus;

          handlersRef.current.onValuesUpdated?.({
            output: state.output,
            values: state.values,
          });
          const hasValidOutput = state.output && state.output.length >= 500;
          if (hasValidOutput || state.status === "completed" || state.status === "failed") {
            console.log("[Polling] Run completed, stopping polling. Status:", state.status, "hasOutput:", !!hasValidOutput);
            handlersRef.current.onCompleted?.(state.status);
            stop();
          }
        } catch (err) {
          console.error("[Polling] Error fetching state:", err);
          handlersRef.current.onError?.("Polling failed");
          stop();
        }
      };

      // Do an immediate poll
      poll();
      
      // Then set up interval
      pollRef.current = setInterval(poll, intervalMs);
    },
    [stop]
  );

  return {
    start,
    stop,
    isPolling: () => isPollingRef.current,
  };
}
