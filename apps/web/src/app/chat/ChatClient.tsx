"use client";

import { ReactNode, useMemo, useState, useEffect, useCallback, useRef, type CSSProperties } from "react";
import { useAuth } from "@/app/providers/AuthProvider";
import { createThread, startRun, getThreadState } from "@/app/actions";
import { useRunPolling } from "./useRunPolling";
import { useRunWebSocket } from "./useRunWebSocket";
import ReactMarkdown from "react-markdown";
import AgentDashboard from "./components/AgentDashboard";
import ProfilePopup from "./components/ProfilePopup";
import ThreadList from "./components/ThreadList";

type NavItem = {
  label: string;
  icon: ReactNode;
  active?: boolean;
};

const navItems: NavItem[] = [
  {
    label: "Home",
    active: true,
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="4" y="4" width="6" height="6" rx="1.5" />
        <rect x="14" y="4" width="6" height="6" rx="1.5" />
        <rect x="4" y="14" width="6" height="6" rx="1.5" />
        <rect x="14" y="14" width="6" height="6" rx="1.5" />
      </svg>
    ),
  },
  {
    label: "Search",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M11 4a7 7 0 1 1-4.95 11.95L4 17" />
        <circle cx="11" cy="11" r="5" />
      </svg>
    ),
  },
  {
    label: "Projects",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M5 6.5A1.5 1.5 0 0 1 6.5 5h11A1.5 1.5 0 0 1 19 6.5V18a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1Z" />
        <path d="M8 9h8" />
        <path d="M8 12h5" />
      </svg>
    ),
  },
  {
    label: "Alerts",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 4a6 6 0 0 0-6 6v3.8l-1.2 2.1A1 1 0 0 0 5.7 17h12.6a1 1 0 0 0 .9-1.1L18 13.8V10a6 6 0 0 0-6-6Z" />
        <path d="M10.5 19a1.5 1.5 0 0 0 3 0" />
      </svg>
    ),
  },
  {
    label: "Docs",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M7 4h7l4 4v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
        <path d="M14 4v4h4" />
      </svg>
    ),
  },
  {
    label: "Feedback",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M6 7h12" />
        <path d="M6 12h12" />
        <path d="M6 17h7" />
        <path d="M4 4h16v14H8l-4 4Z" />
      </svg>
    ),
  },
  {
    label: "Data Storage",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <ellipse cx="12" cy="6" rx="6" ry="2.5" />
        <path d="M6 6v6c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V6" />
        <path d="M6 12v6c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-6" />
      </svg>
    ),
  },
  {
    label: "Profile",
    icon: (
      <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="8" r="3.5" />
        <path d="M6 19c0-3 2.7-5 6-5s6 2 6 5" />
      </svg>
    ),
  },
];

const footerNav: NavItem = {
  label: "Settings",
  icon: (
    <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z" />
      <path d="M19.4 15a1 1 0 0 0 .2-1.1l-.6-1a1 1 0 0 1 0-.9l.6-1a1 1 0 0 0-.2-1.1l-1.1-1.1a1 1 0 0 0-1.1-.2l-1 .6a1 1 0 0 1-.9 0l-1-.6a1 1 0 0 0-1.1.2L10 8.6a1 1 0 0 0-.2 1.1l.6 1a1 1 0 0 1 0 .9l-.6 1a1 1 0 0 0 .2 1.1l1.1 1.1a1 1 0 0 0 1.1.2l1-.6a1 1 0 0 1 .9 0l1 .6a1 1 0 0 0 1.1-.2Z" />
    </svg>
  ),
};

export default function ChatClient() {
  const { session } = useAuth();
  const { connect, disconnect } = useRunWebSocket();
  const polling = useRunPolling();
  const [collapsed, setCollapsed] = useState(false);
  const [contextInput, setContextInput] = useState("");
  const [questionInput, setQuestionInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [streamText, setStreamText] = useState("");
  const [finalMarkdown, setFinalMarkdown] = useState<string | null>(null);
  const [runValues, setRunValues] = useState<Record<string, unknown> | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPollingActive, setIsPollingActive] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  
  // New state for dashboard
  const [startedAt, setStartedAt] = useState<Date | null>(null);
  const [progress, setProgress] = useState(0);
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Profile popup state
  const [showProfilePopup, setShowProfilePopup] = useState(false);
  const profileButtonRef = useRef<HTMLButtonElement>(null);

  // Thread list refresh trigger
  const [threadListRefresh, setThreadListRefresh] = useState(0);

  const themeVars = useMemo(
    () => ({
      "--background": "#eee7d7",
      "--surface": "#e5dccb",
      "--foreground": "#333333",
      "--foreground-muted": "#666666",
      "--accent": "#8b5a2b",
      "--border": "#d4c9b5",
      "--app-font": "var(--font-ibm-plex-mono)",
    }),
    []
  );

  const stopAll = useCallback(() => {
    disconnect();
    polling.stop();
    setIsPollingActive(false);
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
  }, [disconnect, polling]);

  // Store stopAll in a ref so cleanup only runs on unmount
  const stopAllRef = useRef(stopAll);
  stopAllRef.current = stopAll;

  useEffect(() => {
    return () => {
      stopAllRef.current();
    };
  }, []); // Empty deps - only run cleanup on unmount

  // Simulated progress (since backend may not provide real progress)
  useEffect(() => {
    if (isRunning && !progressIntervalRef.current) {
      setProgress(1);
      progressIntervalRef.current = setInterval(() => {
        setProgress((prev) => {
          // Slow down as we approach 95% (never reach 100 until actually complete)
          if (prev >= 95) return prev;
          const increment = Math.max(0.5, (95 - prev) * 0.02);
          return Math.min(95, prev + increment);
        });
      }, 500);
    } else if (!isRunning && progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
      if (finalMarkdown) {
        setProgress(100);
      }
    }
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, [isRunning, finalMarkdown]);

  const handleValuesUpdated = useCallback(
    (payload: { output?: string; values?: Record<string, unknown> }) => {
      // Store full values object for tab content
      if (payload.values) {
        setRunValues(payload.values);
      }
      // Store output regardless of length
      if (payload.output) {
        setFinalMarkdown(payload.output);
      }
    },
    []
  );

  // Reset local run/session state (used for errors or new analysis)
  const resetSession = useCallback((options?: { message?: string; clearThread?: boolean }) => {
    if (options?.message) {
      setError(options.message);
    }
    setRunValues(null);
    setFinalMarkdown(null);
    setStreamText("");
    setProgress(0);
    setStartedAt(null);
    setSubmittedQuestion("");
    setIsComplete(false);
    setIsRunning(false);
    setIsPollingActive(false);
    if (options?.clearThread) {
      setThreadId(null);
    }
    setRunId(null);
  }, []);

  const startPollingFallback = useCallback(
    (activeThreadId: string, token: string) => {
      // Prevent starting polling if already active
      if (polling.isPolling()) {
        console.log("[ChatClient] startPollingFallback called but already polling, ignoring");
        return;
      }
      console.log("[ChatClient] Starting polling fallback for thread:", activeThreadId);
      setIsPollingActive(true);
      polling.start({
        threadId: activeThreadId,
        token,
        intervalMs: 3000, // Slightly longer interval to reduce load
        handlers: {
          onValuesUpdated: handleValuesUpdated,
          onCompleted: () => {
            console.log("[ChatClient] Polling completed");
            setIsRunning(false);
            setIsPollingActive(false);
            setIsComplete(true);
            setProgress(100);
            setThreadListRefresh((n) => n + 1);
          },
          onError: (message) => {
            console.error("[ChatClient] Polling error:", message);
            // If polling cannot find state, likely the thread/run was lost on the backend
            resetSession({ message, clearThread: true });
          },
        },
      });
    },
    [handleValuesUpdated, polling, resetSession]
  );

  // Store thread/token for polling fallback
  const fallbackParamsRef = useRef<{ threadId: string; token: string } | null>(null);
  
  const attachWebSocket = useCallback(
    (activeThreadId: string, activeRunId: string, token: string) => {
      // Store params for potential polling fallback
      fallbackParamsRef.current = { threadId: activeThreadId, token };
      
      console.log("[ChatClient] Attaching WebSocket for thread:", activeThreadId, "run:", activeRunId);
      connect({
        threadId: activeThreadId,
        runId: activeRunId,
        token,
        handlers: {
          onDelta: (chunk) => {
            setStreamText((prev) => prev + chunk);
          },
          onValuesUpdated: handleValuesUpdated,
          onCompleted: () => {
            console.log("[ChatClient] WebSocket completed");
            setIsRunning(false);
            setIsPollingActive(false);
            setIsComplete(true);
            setProgress(100);
            setThreadListRefresh((n) => n + 1);
            polling.stop();
          },
          onError: (message) => {
            console.error("[ChatClient] WebSocket error:", message);
            
            // Don't fall back to polling for auth errors - it won't help
            // Auth errors indicate the backend can't process the request at all
            const isAuthError = message.toLowerCase().includes("authentication") || 
                               message.toLowerCase().includes("token") ||
                               message.toLowerCase().includes("401") ||
                               message.toLowerCase().includes("supabase");
            
            if (isAuthError) {
              console.log("[ChatClient] Auth error detected, not falling back to polling");
              resetSession({ message, clearThread: true });
              return;
            }
            
            // Handle missing thread (e.g., backend restarted and lost in-memory state)
            if (message.toLowerCase().includes("thread not found")) {
              resetSession({ message: "Session expired on the backend. Please start again.", clearThread: true });
              return;
            }
            
            // Only fall back to polling for transient errors
            // The WebSocket hook will have already retried before calling onError
            if (fallbackParamsRef.current) {
              console.log("[ChatClient] WebSocket failed after retries, falling back to polling");
              startPollingFallback(fallbackParamsRef.current.threadId, fallbackParamsRef.current.token);
            } else {
              resetSession({ message });
            }
          },
        },
      });
    },
    [connect, handleValuesUpdated, polling, startPollingFallback]
  );

  const handleSubmit = async () => {
    const question = questionInput.trim();
    const context = contextInput.trim();
    if (!question) {
      setError("Please enter a question to start a run.");
      return;
    }

    if (!session?.access_token) {
      setError("Not authenticated");
      return;
    }

    const token = session.access_token;

    try {
      resetSession();
      setError(null);
      setIsRunning(true);
      setStartedAt(new Date());
      setProgress(0);
      setSubmittedQuestion(context ? `${context}\n\n${question}` : question);

      // Create thread if needed
      let currentThreadId = threadId;
      if (!currentThreadId) {
        currentThreadId = await createThread(token);
        setThreadId(currentThreadId);
      }

      const prompt = context ? `${context}\n\n${question}` : question;
      const newRunId = await startRun(currentThreadId, prompt, token);
      setRunId(newRunId);

      attachWebSocket(currentThreadId, newRunId, token);
    } catch (err) {
      console.error("Submit error:", err);
      const message = err instanceof Error ? err.message : "Failed to start run";
      // If the backend lost in-memory state, clear the thread so the next attempt creates a new one
      if (message.toLowerCase().includes("thread") || message.includes("404")) {
        resetSession({ message: "Session expired on the backend. Please start again.", clearThread: true });
      } else {
        resetSession({ message });
      }
      stopAll();
    }
  };

  const handleCancel = useCallback(() => {
    setIsRunning(false);
    setStartedAt(null);
    setProgress(0);
    stopAll();
  }, [stopAll]);

  const handleShare = useCallback(() => {
    // TODO: Implement share functionality
    console.log("Share clicked");
  }, []);

  // Handler to go back to input screen (start new analysis)
  const handleNewAnalysis = useCallback(() => {
    resetSession();
    setError(null); // Clear any previous errors
  }, [resetSession]);

  // Handler to load a thread from the sidebar
  const handleSelectThread = useCallback(async (selectedThreadId: string) => {
    if (!session?.access_token) return;
    
    try {
      const state = await getThreadState(selectedThreadId, session.access_token);
      if (state) {
        setThreadId(selectedThreadId);
        setRunId(state.run_id ?? null);
        setRunValues(state.values ?? null);
        setFinalMarkdown(state.output ?? null);
        setSubmittedQuestion(state.values?.goal as string ?? "");
        setIsComplete(state.status === "completed" || state.status === "failed");
        setIsRunning(state.status === "running");
        setStartedAt(new Date()); // Set to show dashboard
        setProgress(state.status === "completed" ? 100 : 0);
        setError(null);
      }
    } catch (err) {
      console.error("Failed to load thread:", err);
      setError(err instanceof Error ? err.message : "Failed to load thread");
    }
  }, [session?.access_token]);

  // Show dashboard when running OR when we have completed results
  // Use startedAt to prevent flash - if we started a run, stay on dashboard until explicitly reset
  const hasStartedRun = startedAt !== null;
  const hasResults = runValues !== null || finalMarkdown !== null;
  const showDashboard = isRunning || hasStartedRun || hasResults;
  
  if (showDashboard) {
    return (
      <div
        className="flex min-h-screen bg-[var(--background)] text-[var(--foreground)]"
        style={{ ...(themeVars as CSSProperties), fontFamily: "var(--app-font)" }}
      >
        {/* Sidebar */}
        <aside
          className={`sticky top-0 z-10 flex h-screen flex-col border-r border-[var(--border)] bg-[var(--surface)] px-3 py-4 transition-[width] duration-150 ${
            collapsed ? "w-[80px]" : "w-[240px]"
          }`}
        >
          <div className="mb-4 flex items-center justify-between gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--background)] text-sm font-semibold tracking-tight text-[var(--foreground)]">
              S
            </div>
            <button
              type="button"
              aria-label="Toggle sidebar"
              onClick={() => setCollapsed((c) => !c)}
              className="flex h-8 w-8 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--background)] text-[var(--foreground-muted)] transition-colors duration-150 hover:border-[var(--accent)] hover:text-[var(--foreground)]"
            >
              <svg
                viewBox="0 0 24 24"
                className={`h-4 w-4 transition-transform ${collapsed ? "" : "rotate-180"}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
              <path d="m10 8 4 4-4 4" />
            </svg>
          </button>
        </div>

          <ThreadList
            token={session?.access_token ?? null}
            activeThreadId={threadId}
            onSelectThread={handleSelectThread}
            collapsed={collapsed}
            refreshTrigger={threadListRefresh}
          />

          <nav className="mt-auto flex flex-col gap-1.5">
            {["Profile", "Data Storage", "Feedback", "Docs"].map((label) => {
              const item = navItems.find((it) => it.label === label);
              if (!item) return null;
              const isProfile = label === "Profile";
              return (
                <div key={item.label} className="relative">
                  <button
                    ref={isProfile ? profileButtonRef : undefined}
                    type="button"
                    onClick={isProfile ? () => setShowProfilePopup((v) => !v) : undefined}
                    className={`group flex w-full items-center gap-3 rounded border text-[var(--foreground-muted)] transition-all duration-150 hover:border-[var(--accent)] hover:text-[var(--foreground)] ${
                      item.active
                        ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_10%,var(--surface))] text-[var(--foreground)]"
                        : "border-[var(--border)] bg-[var(--background)]"
                    } ${collapsed ? "h-9 w-9 justify-center" : "h-10 px-3 justify-start"}`}
                    aria-label={item.label}
                  >
                    <span className="flex h-3 w-3 items-center justify-center">{item.icon}</span>
                    {!collapsed && <span className="text-sm font-semibold tracking-tight">{item.label}</span>}
                  </button>
                  {isProfile && showProfilePopup && (
                    <ProfilePopup
                      onClose={() => setShowProfilePopup(false)}
                      anchorRef={profileButtonRef}
                    />
                  )}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* Main Dashboard */}
        <AgentDashboard
          question={submittedQuestion}
          progress={progress}
          startedAt={startedAt}
          runId={runId}
          values={runValues}
          finalMarkdown={finalMarkdown}
          isComplete={isComplete}
          onCancel={handleCancel}
          onShare={handleShare}
          onNewAnalysis={handleNewAnalysis}
        />
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen bg-[var(--background)] text-[var(--foreground)]"
      style={{ ...(themeVars as CSSProperties), fontFamily: "var(--app-font)" }}
    >
      <aside
        className={`sticky top-0 z-10 flex h-screen flex-col border-r border-[var(--border)] bg-[var(--surface)] px-3 py-4 transition-[width] duration-150 ${
          collapsed ? "w-[80px]" : "w-[240px]"
        }`}
      >
        <div className="mb-4 flex items-center justify-between gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--background)] text-sm font-semibold tracking-tight text-[var(--foreground)]">
            S
          </div>
          <button
            type="button"
            aria-label="Toggle sidebar"
            onClick={() => setCollapsed((c) => !c)}
            className="flex h-8 w-8 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--background)] text-[var(--foreground-muted)] transition-colors duration-150 hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <svg
              viewBox="0 0 24 24"
              className={`h-4 w-4 transition-transform ${collapsed ? "" : "rotate-180"}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
            >
              <path d="m10 8 4 4-4 4" />
            </svg>
          </button>
        </div>

        <ThreadList
          token={session?.access_token ?? null}
          activeThreadId={threadId}
          onSelectThread={handleSelectThread}
          collapsed={collapsed}
          refreshTrigger={threadListRefresh}
        />

        <nav className="mt-auto flex flex-col gap-1.5">
          {["Profile", "Data Storage", "Feedback", "Docs"].map((label) => {
            const item = navItems.find((it) => it.label === label);
            if (!item) return null;
            const isProfile = label === "Profile";
            return (
              <div key={item.label} className="relative">
                <button
                  ref={isProfile ? profileButtonRef : undefined}
                  type="button"
                  onClick={isProfile ? () => setShowProfilePopup((v) => !v) : undefined}
                  className={`group flex w-full items-center gap-3 rounded border text-[var(--foreground-muted)] transition-all duration-150 hover:border-[var(--accent)] hover:text-[var(--foreground)] ${
                    item.active
                      ? "border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_10%,var(--surface))] text-[var(--foreground)]"
                      : "border-[var(--border)] bg-[var(--background)]"
                  } ${collapsed ? "h-9 w-9 justify-center" : "h-10 px-3 justify-start"}`}
                  aria-label={item.label}
                >
                  <span className="flex h-3 w-3 items-center justify-center">{item.icon}</span>
                  {!collapsed && <span className="text-sm font-semibold tracking-tight">{item.label}</span>}
                </button>
                {isProfile && showProfilePopup && (
                  <ProfilePopup
                    onClose={() => setShowProfilePopup(false)}
                    anchorRef={profileButtonRef}
                  />
                )}
              </div>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col">
        <header className="flex items-center justify-end gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
          <div className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-sm text-[var(--foreground-muted)]">
            <span>Remaining Credits:</span>
            <span className="font-semibold text-[var(--foreground)]">10</span>
          </div>
          <button className="rounded-full border border-[var(--border)] bg-[var(--background)] px-4 py-2 text-sm font-semibold text-[var(--accent)] transition-colors duration-150 hover:border-[var(--accent)] hover:bg-[color-mix(in_srgb,var(--accent)_12%,var(--background))]">
            Get more
          </button>
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--background)] text-sm font-semibold text-[var(--foreground)]">
            U
          </div>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-5xl flex-col gap-5 px-6 pb-12 pt-8">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-3xl font-semibold tracking-tight text-[var(--foreground)]">Analysis</h1>
              <span className="inline-flex items-center rounded-sm border border-[color-mix(in_srgb,var(--accent)_45%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--foreground)]">
                Explain the system you need in details to start research
              </span>
            </div>

            {(finalMarkdown || streamText) && (
              <div className="space-y-4 rounded-sm border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_18px_40px_rgba(0,0,0,0.08)]">
                <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-[var(--foreground)]">
                      {finalMarkdown ? "Run completed" : "Waiting for output"}
                    </span>
                  </div>
                  {runId && <span className="text-[var(--foreground-muted)]">Run ID: {runId}</span>}
                </div>

                {streamText && !finalMarkdown && (
                  <div className="rounded border border-[var(--border)] bg-[var(--background)] p-3 text-sm text-[var(--foreground)]">
                    <div className="mb-2 text-xs font-semibold uppercase text-[var(--foreground-muted)]">Live output</div>
                    <div className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed">{streamText}</div>
                  </div>
                )}

                {finalMarkdown && (
                  <div className="prose prose-sm prose-invert max-w-none">
                    <ReactMarkdown components={{
                      h1: ({node, ...props}) => <h1 className="text-2xl font-bold mb-4 text-[var(--foreground)]" {...props} />,
                      h2: ({node, ...props}) => <h2 className="text-xl font-bold mb-3 mt-4 text-[var(--foreground)]" {...props} />,
                      h3: ({node, ...props}) => <h3 className="text-lg font-semibold mb-2 mt-3 text-[var(--foreground)]" {...props} />,
                      p: ({node, ...props}) => <p className="mb-2 text-[var(--foreground)]" {...props} />,
                      ul: ({node, ...props}) => <ul className="list-disc list-inside mb-2 text-[var(--foreground)]" {...props} />,
                      li: ({node, ...props}) => <li className="mb-1 text-[var(--foreground)]" {...props} />,
                      code: ({node, ...props}) => <code className="bg-[var(--background)] px-1 rounded text-[var(--accent)]" {...props} />,
                      a: ({node, ...props}) => <a className="text-[var(--accent)] underline" {...props} />,
                    }}>{finalMarkdown}</ReactMarkdown>
                  </div>
                )}
              </div>
            )}

            {error && (
              <div className="rounded-sm border border-red-500/30 bg-red-500/10 p-4 text-red-400">
                Error: {error}
              </div>
            )}

            <div className="rounded-sm border border-[var(--border)] bg-[var(--surface)] shadow-[0_18px_40px_rgba(0,0,0,0.08)]">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--background)] px-6 py-4">
                <div className="flex flex-col gap-1 text-sm">
                  <span className="text-[var(--foreground)]">Systesign is here!</span>
                  <span className="text-[var(--foreground-muted)]">
                    Build agentic architectures with Systesign - Agentic system researcher!
                  </span>
                </div>
                <button className="rounded-sm border border-[var(--accent)] bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] px-4 py-2 text-sm font-semibold text-[var(--foreground)] transition-colors duration-150 hover:bg-[color-mix(in_srgb,var(--accent)_22%,transparent)]">
                  Try Systesign:
                </button>
              </div>

              <div className="space-y-5 px-6 py-6">
                <label className="block rounded border border-[var(--border)] bg-[var(--background)] px-4 py-3">
                  <div className="mb-2 text-sm font-semibold text-[var(--foreground)]">Context / Data</div>
                  <textarea
                    value={contextInput}
                    onChange={(e) => setContextInput(e.target.value)}
                    aria-label="Context input"
                    className="w-full resize-none rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_35%,transparent)]"
                    rows={4}
                    placeholder=""
                  />
                </label>

                <label className="block rounded border border-[var(--border)] bg-[var(--background)] px-4 py-3">
                  <div className="mb-2 text-sm font-semibold text-[var(--foreground)]">Question</div>
                  <textarea
                    value={questionInput}
                    onChange={(e) => setQuestionInput(e.target.value)}
                    aria-label="Question input"
                    className="w-full resize-none rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--foreground)] outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--accent)_35%,transparent)]"
                    rows={6}
                    placeholder=""
                  />
                </label>

                <div className="flex flex-col gap-4 border-t border-[var(--border)] pt-4 md:flex-row md:items-center md:justify-between">
                  <div className="flex flex-1 items-center gap-3 rounded border border-dashed border-[color-mix(in_srgb,var(--accent)_55%,var(--border))] bg-[var(--background)] px-4 py-4 text-sm text-[var(--foreground)]">
                    <div className="flex h-10 w-10 items-center justify-center rounded-sm border border-[color-mix(in_srgb,var(--accent)_55%,var(--border))] bg-[color-mix(in_srgb,var(--accent)_15%,transparent)] text-base font-semibold text-[var(--foreground)]">
                      ↑
                    </div>
                    <div className="flex flex-col">
                      <span className="font-semibold">Drag Here or Click to Upload</span>
                      <span className="text-[var(--foreground-muted)]">Max 100MB</span>
                    </div>
                  </div>

                  <div className="flex flex-col items-start gap-2 md:items-end">
                    <div className="rounded-full border border-[var(--border)] bg-[var(--background)] px-3 py-1 text-sm text-[var(--foreground-muted)]">
                      Cost <span className="font-semibold text-[var(--foreground)]">1 Credit</span>
                    </div>
                    <button
                      type="button"
                      onClick={handleSubmit}
                      disabled={isRunning}
                      className="inline-flex items-center justify-center gap-2 rounded-sm border border-[var(--accent)] bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white transition-transform duration-150 hover:-translate-y-0.5 hover:shadow-[0_0_16px_rgba(139,90,43,0.3)] disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isRunning ? "Running..." : "Start →"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
