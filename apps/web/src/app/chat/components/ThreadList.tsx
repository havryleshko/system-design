"use client";

import { useEffect, useState, useCallback } from "react";
import { listThreads } from "@/app/actions";

type ThreadItem = {
  thread_id: string;
  title: string;
  status: "running" | "completed" | "failed" | "queued";
  created_at: string | null;
};

type ThreadListProps = {
  token: string | null;
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  collapsed: boolean;
  refreshTrigger?: number;
};

export default function ThreadList({
  token,
  activeThreadId,
  onSelectThread,
  collapsed,
  refreshTrigger,
}: ThreadListProps) {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchThreads = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await listThreads(token);
      setThreads(data);
    } catch (err) {
      console.error("Failed to fetch threads:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchThreads();
  }, [fetchThreads, refreshTrigger]);

  if (collapsed) {
    return null;
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--foreground-muted)]">
        Recent
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading && threads.length === 0 && (
          <div className="px-1 py-2 text-xs text-[var(--foreground-muted)]">
            Loading...
          </div>
        )}
        {!loading && threads.length === 0 && (
          <div className="px-1 py-2 text-xs text-[var(--foreground-muted)]">
            No queries yet
          </div>
        )}
        <div className="flex flex-col gap-1">
          {threads.map((thread) => {
            const isActive = thread.thread_id === activeThreadId;
            return (
              <button
                key={thread.thread_id}
                type="button"
                onClick={() => onSelectThread(thread.thread_id)}
                className={`group flex w-full items-center gap-2 rounded border px-2 py-2 text-left text-xs transition-all duration-150 ${
                  isActive
                    ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_10%,var(--surface))] text-[var(--foreground)]"
                    : "border-transparent bg-transparent text-[var(--foreground-muted)] hover:border-[var(--border)] hover:bg-[var(--background)] hover:text-[var(--foreground)]"
                }`}
                title={thread.title}
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-3 w-3 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
                </svg>
                <span className="truncate">{thread.title}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

