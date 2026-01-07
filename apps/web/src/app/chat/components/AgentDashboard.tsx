"use client";

import { useState } from "react";
import CubeLoader from "./CubeLoader";
import ResultsV2 from "./ResultsV2";
import PlaceholderTab from "./PlaceholderTab";

type TabId = "results" | "notebook" | "reasoning" | "download";

type AgentDashboardProps = {
  question: string;
  progress: number;
  startedAt: Date | null;
  runId: string | null;
  values: Record<string, unknown> | null;
  finalMarkdown: string | null;
  isComplete: boolean;
  runStatus: string | null;
  onCancel: () => void;
  onShare?: () => void;
  onNewAnalysis?: () => void;
};

export default function AgentDashboard({
  question,
  progress,
  startedAt,
  runId,
  values,
  finalMarkdown,
  isComplete,
  runStatus,
  onCancel,
  onShare,
  onNewAnalysis,
}: AgentDashboardProps) {
  const [showBanner, setShowBanner] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("results");
  const [followUpInput, setFollowUpInput] = useState("");

  const formatTimestamp = (date: Date | null) => {
    if (!date) return "";
    return date.toLocaleString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true,
    });
  };


  const getOutput = (): string | null => {
    if (finalMarkdown) return finalMarkdown;
    const valuesOutput = typeof (values as any)?.output === "string" ? ((values as any).output as string) : null;
    if (valuesOutput) return valuesOutput;
    const designOutput = (values?.design_state as any)?.output?.formatted_output;
    if (typeof designOutput === "string") return designOutput;
    
    return null;
  };
  
  const output = getOutput();
  const roundedProgress = Math.round(progress);
  const displayProgress = isComplete ? 100 : roundedProgress;
  const normalizedStatus = (runStatus ?? "").toLowerCase();
  const statusLabel =
    normalizedStatus === "failed"
      ? "FAILED"
      : isComplete
      ? "SUCCESS"
      : roundedProgress < 5
      ? "QUEUED"
      : "RUNNING";

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    {
      id: "results",
      label: "Results",
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      ),
    },
    {
      id: "notebook",
      label: "Notebook",
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 3v18h18" />
          <path d="M7 14l4-4 4 4 5-5" />
        </svg>
      ),
    },
    {
      id: "reasoning",
      label: "Reasoning",
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 3c-1.5 0-2.5 1-3 2s-1.5 2-3 2 2 2 2 5-3.5 3-3.5 5c0 1.5 2 3 7.5 3s7.5-1.5 7.5-3c0-2-3.5-3-3.5-5s3.5-3 2-5-1.5-2-3-2-1.5-2-3-2z" />
        </svg>
      ),
    },
    {
      id: "download",
      label: "Download",
      icon: (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 3v12m0 0l-4-4m4 4l4-4" />
          <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
        </svg>
      ),
    },
  ];

  const handleFollowUpSubmit = () => {
    // Placeholder - will be implemented later
    console.log("Follow-up submitted:", followUpInput);
    setFollowUpInput("");
  };

  const renderTabContent = () => {
    if (!isComplete) {
      return (
        <div className="flex flex-1 items-center justify-center">
          <CubeLoader size={80} color="var(--accent)" />
        </div>
      );
    }

    switch (activeTab) {
      case "results":

        return (
          <ResultsV2
            output={output}
            startedAt={startedAt}
            values={values}
            runStatus={runStatus}
          />
        );
      case "notebook":
        return <PlaceholderTab title="Notebook" note="Tab reset for Results V2 rebuild." />;
      case "reasoning":
        return <PlaceholderTab title="Reasoning" note="Tab reset for Results V2 rebuild." />;
      case "download":
        return <PlaceholderTab title="Download" note="Exports will be rebuilt after Results V2." />;
      default:
        return null;
    }
  };

  return (
    <div className="agent-dashboard flex flex-1 flex-col bg-[var(--background)]">
      {/* Notification Banner */}
      {showBanner && !isComplete && (
        <div className="flex items-center justify-between gap-4 border-b border-[var(--border)] bg-[var(--surface)] px-6 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent)]/20">
              <svg viewBox="0 0 24 24" className="h-4 w-4 text-[var(--accent)]" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 9v4m0 4h.01" />
                <circle cx="12" cy="12" r="9" />
              </svg>
            </div>
            <span className="text-sm text-[var(--foreground)]">
              Agents often take a few minutes to research, analyze, and respond. We will display results as soon as the agent has processed some data.
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-sm border border-[var(--accent)] bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-[var(--accent)]/90"
            >
              Notify me
            </button>
            <button
              type="button"
              onClick={() => setShowBanner(false)}
              className="rounded-sm border border-[var(--border)] bg-transparent px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:bg-[var(--background)] hover:text-[var(--foreground)]"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 flex-col px-6 py-6">
        {/* Question Display */}
        <div className="mb-6">
          <p className="max-w-4xl truncate text-lg font-medium text-[var(--foreground)]">
            {question}
          </p>
        </div>

        {/* Status Header */}
        <div className="mb-4 flex flex-wrap items-center gap-4 border-b border-[var(--border)] pb-4">
          {/* Analysis Label */}
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold text-[var(--foreground)]">Analysis</span>
            <button
              type="button"
              className="flex h-5 w-5 items-center justify-center rounded-full border border-[var(--border)] text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
              aria-label="Info"
            >
              <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8h.01M11 12h1v4h1" />
              </svg>
            </button>
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Status Badge */}
          <div className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1">
            <div
              className={`h-2 w-2 rounded-full ${
                statusLabel === "SUCCESS"
                  ? "bg-[#22c55e]"
                  : statusLabel === "FAILED"
                  ? "bg-red-500"
                  : statusLabel === "QUEUED"
                  ? "bg-[#6b7280]"
                  : "bg-[#22c55e] animate-pulse"
              }`}
            />
            <span className="text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              {statusLabel}
            </span>
          </div>

          {/* Progress (only show when waiting on results) */}
          {!isComplete && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--foreground)]">{displayProgress}%</span>
              <div className="h-2 w-16 overflow-hidden rounded-full bg-[var(--surface)]">
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                  style={{ width: `${displayProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Cancel Button (only show when not complete) */}
          {!isComplete && (
            <button
              type="button"
              onClick={onCancel}
              className="flex items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-red-500/50 hover:bg-red-500/10 hover:text-red-400"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M15 9l-6 6m0-6l6 6" />
              </svg>
              Cancel
            </button>
          )}

          {/* Started Timestamp */}
          {startedAt && (
            <span className="text-xs text-[var(--foreground-muted)]">
              Started: {formatTimestamp(startedAt)}
            </span>
          )}

          {/* Share Button */}
          <button
            type="button"
            onClick={onShare}
            className="flex items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7" />
              <path d="M16 6l-4-4-4 4" />
              <path d="M12 2v13" />
            </svg>
            Share
          </button>

          {/* New Analysis Button (only show when results are ready) */}
          {isComplete && onNewAnalysis && (
            <button
              type="button"
              onClick={onNewAnalysis}
              className="flex items-center gap-1.5 rounded-sm border border-[var(--accent)] bg-[var(--accent)] px-3 py-1.5 text-xs font-semibold text-white transition-all hover:shadow-[0_0_12px_rgba(139,90,43,0.3)]"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14" />
                <path d="M5 12h14" />
              </svg>
              New Analysis
            </button>
          )}
        </div>

        {/* Tab Bar */}
        <div className="mb-6 flex items-center gap-1 border-b border-[var(--border)]">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            const isEnabled = isComplete;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => isEnabled && setActiveTab(tab.id)}
                disabled={!isEnabled}
                className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                  isActive && isEnabled
                    ? "border-[var(--accent)] text-[var(--foreground)]"
                    : isEnabled
                    ? "border-transparent text-[var(--foreground-muted)] hover:border-[var(--accent)]/50 hover:text-[var(--foreground)]"
                    : "cursor-not-allowed border-transparent text-[var(--foreground-muted)]/50"
                }`}
              >
                <span className={!isEnabled ? "opacity-50" : ""}>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto">
          {renderTabContent()}
        </div>

        {/* Follow-up Input (only show when results are available) */}
        {isComplete && (
          <div className="mt-6 border-t border-[var(--border)] pt-6">
            <div className="flex items-center gap-3 rounded border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
              <input
                type="text"
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && followUpInput.trim()) {
                    handleFollowUpSubmit();
                  }
                }}
                placeholder="Ask a follow-up question"
                className="flex-1 bg-transparent text-sm text-[var(--foreground)] placeholder-[var(--foreground-muted)] outline-none"
              />
              <button
                type="button"
                onClick={handleFollowUpSubmit}
                disabled={!followUpInput.trim()}
                className="flex h-8 w-8 items-center justify-center rounded-sm bg-[var(--accent)] text-white transition-all hover:shadow-[0_0_12px_rgba(139,90,43,0.3)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
