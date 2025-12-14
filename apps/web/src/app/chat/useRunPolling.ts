import { useCallback, useEffect, useRef } from "react";

import { getThreadState } from "@/app/actions";

type PollingHandlers = {
  onValuesUpdated?: (payload: { finalJudgement?: string; output?: string; values?: Record<string, unknown> }) => void;
  onCompleted?: (status?: string) => void;
  onError?: (error: string) => void;
};

type StartPollingParams = {
  threadId: string;
  token: string;
  intervalMs?: number;
  handlers: PollingHandlers;
};

export function useRunPolling() {
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  const stop = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  const start = useCallback(
    ({ threadId, token, intervalMs = 2000, handlers }: StartPollingParams) => {
      stop();

      pollRef.current = setInterval(async () => {
        try {
          const state = await getThreadState(threadId, token);
          if (!state) return;

          handlers.onValuesUpdated?.({
            finalJudgement: state.final_judgement,
            output: state.output,
            values: state.values,
          });

          if (state.final_judgement || state.output || state.status === "completed" || state.status === "failed") {
            handlers.onCompleted?.(state.status);
            stop();
          }
        } catch (err) {
          handlers.onError?.("Polling failed");
          stop();
        }
      }, intervalMs);
    },
    [stop]
  );

  return {
    start,
    stop,
    isPolling: () => pollRef.current !== null,
  };
}
