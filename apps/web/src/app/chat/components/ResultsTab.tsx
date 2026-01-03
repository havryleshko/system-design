"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

type ResultsTabProps = {
  output: string | null;
  startedAt: Date | null;
  values: Record<string, unknown> | null;
  runStatus: string | null;
};

type TocItem = { id: string; label: string; show: boolean };

function safeString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function safeArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function safeObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function SectionHeader({
  title,
  right,
}: {
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-[var(--foreground)]">{title}</h2>
      {right}
    </div>
  );
}

function SmallButton({
  onClick,
  children,
  disabled,
}: {
  onClick?: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export default function ResultsTab({ output, startedAt, values, runStatus }: ResultsTabProps) {
  const [copiedOutput, setCopiedOutput] = useState(false);
  const [copiedMermaid, setCopiedMermaid] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const [diagramImageError, setDiagramImageError] = useState(false);
  const [markdownImageError, setMarkdownImageError] = useState(false);

  useEffect(() => {
    setDiagramImageError(false);
    setMarkdownImageError(false);
  }, [output]);

  const formatDate = (date: Date | null) => {
    if (!date) return "";
    return date.toLocaleDateString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
    });
  };

  const handleCopy = async () => {
    if (output) {
      await navigator.clipboard.writeText(output);
      setCopiedOutput(true);
      setTimeout(() => setCopiedOutput(false), 2000);
    }
  };

  const designState = safeObject((values as any)?.design_state);
  const architectureArtifact = safeObject((designState as any)?.architecture);
  const diagramArtifact = safeObject((designState as any)?.diagram);
  const outputArtifact = safeObject((designState as any)?.output);

  const architecture = safeObject((architectureArtifact as any)?.architecture);
  const agents = safeArray<Record<string, unknown>>((architecture as any)?.agents);
  const tools = safeArray<Record<string, unknown>>((architecture as any)?.tools);
  const memory = safeObject((architecture as any)?.memory);
  const controlLoop = safeObject((architecture as any)?.control_loop);
  const boundedAutonomy = safeObject((architecture as any)?.bounded_autonomy);

  const diagramImageUrl = safeString((diagramArtifact as any)?.diagram_image_url);
  const mermaidCode = safeString((diagramArtifact as any)?.mermaid);

  const architectureNotes = safeArray<string>((architectureArtifact as any)?.notes);
  const diagramNotes = safeArray<string>((diagramArtifact as any)?.notes);
  const outputNotes = safeArray<string>((outputArtifact as any)?.notes);

  const showDiagram = Boolean(diagramImageUrl || mermaidCode);
  const showArchitecture =
    Boolean(agents.length) ||
    Boolean(tools.length) ||
    Boolean(Object.keys(memory).length) ||
    Boolean(Object.keys(controlLoop).length) ||
    Boolean(Object.keys(boundedAutonomy).length);
  const showSafety = Boolean(Object.keys(boundedAutonomy).length);
  const showNotes = architectureNotes.length + diagramNotes.length + outputNotes.length > 0;
  const showExports = Object.keys(designState).length > 0;
  const showMarkdown = Boolean(output);

  const hasAnyResults = Boolean(output || showDiagram || showArchitecture || showExports);

  const handleCopyMermaid = async () => {
    if (!mermaidCode) return;
    await navigator.clipboard.writeText(mermaidCode);
    setCopiedMermaid(true);
    setTimeout(() => setCopiedMermaid(false), 2000);
  };

  const jsonExport = useMemo(() => JSON.stringify(designState, null, 2), [designState]);

  const handleCopyJson = async () => {
    if (!showExports) return;
    await navigator.clipboard.writeText(jsonExport);
    setCopiedJson(true);
    setTimeout(() => setCopiedJson(false), 2000);
  };

  const handleDownloadJson = () => {
    if (!showExports) return;
    const blob = new Blob([jsonExport], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "design_state.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const toc: TocItem[] = useMemo(
    () =>
      [
        { id: "overview", label: "Overview", show: true },
        { id: "diagram", label: "Diagram", show: showDiagram },
        { id: "agents", label: "Agents", show: agents.length > 0 },
        { id: "tools", label: "Tools", show: tools.length > 0 },
        { id: "memory", label: "Memory", show: Object.keys(memory).length > 0 },
        { id: "control-loop", label: "Control Loop", show: Object.keys(controlLoop).length > 0 },
        { id: "safety", label: "Safety", show: showSafety },
        { id: "notes", label: "Notes / Status", show: showNotes },
        { id: "exports", label: "Exports", show: showExports },
        { id: "markdown", label: "Markdown", show: showMarkdown },
      ].filter((t) => t.show),
    [
      agents.length,
      controlLoop,
      memory,
      showDiagram,
      showExports,
      showMarkdown,
      showNotes,
      showSafety,
      tools.length,
    ]
  );

  if (!hasAnyResults) {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <p className="text-[var(--foreground-muted)]">No results available yet.</p>
      </div>
    );
  }

  const normalizedStatus = (runStatus ?? "").toLowerCase();
  const resultsBadgeLabel = normalizedStatus === "failed" ? "FAILED" : "SUCCESS";
  const resultsBadgeClass =
    normalizedStatus === "failed"
      ? "border-red-500/30 bg-red-500/10 text-red-400"
      : "border-[#22c55e]/30 bg-[#22c55e]/10 text-[#22c55e]";

  return (
    <div className="results-tab grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]">
      {/* TOC */}
      <aside className="hidden lg:block">
        <div className="sticky top-4 rounded border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
            Contents
          </div>
          <nav className="flex flex-col gap-2 text-sm">
            {toc.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="rounded-sm px-2 py-1 text-[var(--foreground-muted)] transition-colors hover:bg-[var(--background)] hover:text-[var(--foreground)]"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      <div className="flex flex-col gap-6">
      {/* Results Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center rounded-sm border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${resultsBadgeClass}`}>
            {resultsBadgeLabel}
          </span>
          {startedAt && (
            <span className="text-sm text-[var(--foreground-muted)]">
              Started: {formatDate(startedAt)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <path d="M14 2v6h6" />
              <path d="M16 13H8" />
              <path d="M16 17H8" />
              <path d="M10 9H8" />
            </svg>
            {copiedOutput ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>

      {/* Overview */}
      <section id="overview" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
        <SectionHeader
          title="Overview"
          right={
            <div className="flex items-center gap-2">
              {mermaidCode && (
                <SmallButton onClick={handleCopyMermaid}>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                  {copiedMermaid ? "Mermaid copied!" : "Copy Mermaid"}
                </SmallButton>
              )}
              {showExports && (
                <SmallButton onClick={handleCopyJson}>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <path d="M14 2v6h6" />
                    <path d="M16 13H8" />
                    <path d="M16 17H8" />
                    <path d="M10 9H8" />
                  </svg>
                  {copiedJson ? "JSON copied!" : "Copy JSON"}
                </SmallButton>
              )}
            </div>
          }
        />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Artifact Status
            </div>
            <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
              <li>
                <span className="font-semibold">Architecture:</span>{" "}
                {safeString((architectureArtifact as any)?.status) || "unknown"}
              </li>
              <li>
                <span className="font-semibold">Diagram:</span> {safeString((diagramArtifact as any)?.status) || "unknown"}
              </li>
              <li>
                <span className="font-semibold">Output:</span> {safeString((outputArtifact as any)?.status) || "unknown"}
              </li>
            </ul>
          </div>

          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
              Quick Stats
            </div>
            <ul className="mt-2 space-y-1 text-sm text-[var(--foreground)]">
              <li>
                <span className="font-semibold">Agents:</span> {agents.length}
              </li>
              <li>
                <span className="font-semibold">Tools:</span> {tools.length}
              </li>
              <li>
                <span className="font-semibold">Mermaid:</span> {mermaidCode ? "yes" : "no"}
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* Diagram */}
      {showDiagram && (
        <section id="diagram" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader
            title="Diagram"
            right={
              mermaidCode ? (
                <SmallButton onClick={handleCopyMermaid}>
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                  {copiedMermaid ? "Copied!" : "Copy Mermaid"}
                </SmallButton>
              ) : null
            }
          />

          {diagramImageUrl && !diagramImageError ? (
            <div className="rounded border border-[var(--border)] bg-white p-2">
              <img
                src={diagramImageUrl}
                alt="Architecture Diagram"
                className="max-w-full rounded"
                onError={() => setDiagramImageError(true)}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center rounded border border-[var(--border)] bg-[var(--background)] p-8 text-[var(--foreground-muted)]">
              Diagram image unavailable
            </div>
          )}

          {mermaidCode && (
            <details className="mt-4 rounded border border-[var(--border)] bg-[var(--background)]">
              <summary className="cursor-pointer px-4 py-2 font-semibold text-[var(--foreground)] hover:bg-[var(--surface)]">
                View Mermaid code
              </summary>
              <pre className="overflow-x-auto p-4 text-sm">
                <code className="block whitespace-pre text-[var(--foreground)]">{mermaidCode}</code>
              </pre>
            </details>
          )}
        </section>
      )}

      {/* Agents */}
      {agents.length > 0 && (
        <section id="agents" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Agents" />
          <div className="overflow-x-auto rounded border border-[var(--border)] bg-[var(--background)]">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[var(--surface)]">
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Agent
                  </th>
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Responsibility
                  </th>
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Tools
                  </th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent, idx) => {
                  const name = safeString(agent.name) || safeString(agent.id) || `Agent ${idx + 1}`;
                  const responsibility = safeString(agent.responsibility) || "-";
                  const agentTools = safeArray<string>(agent.tools).slice(0, 6);
                  return (
                    <tr key={`${safeString(agent.id) || idx}`} className="border-t border-[var(--border)]">
                      <td className="px-3 py-2 text-[var(--foreground)]">
                        <span className="font-semibold">{name}</span>
                      </td>
                      <td className="px-3 py-2 text-[var(--foreground)]">{responsibility}</td>
                      <td className="px-3 py-2 text-[var(--foreground)]">
                        {agentTools.length ? agentTools.join(", ") : "None"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Tools */}
      {tools.length > 0 && (
        <section id="tools" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Tools" />
          <div className="overflow-x-auto rounded border border-[var(--border)] bg-[var(--background)]">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[var(--surface)]">
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Tool
                  </th>
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Type
                  </th>
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    I/O Schema
                  </th>
                  <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                    Failure Handling
                  </th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool, idx) => {
                  const name = safeString(tool.name) || safeString(tool.id) || `Tool ${idx + 1}`;
                  const type = safeString(tool.type) || "other";
                  const io = safeString(tool.io_schema) || "-";
                  const failure = safeString(tool.failure_handling) || "-";
                  return (
                    <tr key={`${safeString(tool.id) || idx}`} className="border-t border-[var(--border)]">
                      <td className="px-3 py-2 text-[var(--foreground)]">
                        <span className="font-semibold">{name}</span>
                      </td>
                      <td className="px-3 py-2 text-[var(--foreground)]">{type}</td>
                      <td className="px-3 py-2 font-mono text-[12px] text-[var(--foreground)]">{io}</td>
                      <td className="px-3 py-2 text-[var(--foreground)]">{failure}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Memory */}
      {Object.keys(memory).length > 0 && (
        <section id="memory" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Memory" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {Object.entries(memory).map(([key, value]) => {
              const cfg = safeObject(value);
              const purpose = safeString(cfg.purpose) || "-";
              const implementation = safeString(cfg.implementation) || "-";
              return (
                <div key={key} className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
                  <div className="mb-2 text-sm font-semibold text-[var(--foreground)]">
                    {key.replace(/_/g, " ")}
                  </div>
                  <div className="space-y-1 text-sm text-[var(--foreground)]">
                    <div>
                      <span className="font-semibold">Purpose:</span> {purpose}
                    </div>
                    <div>
                      <span className="font-semibold">Implementation:</span> {implementation}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Control Loop */}
      {Object.keys(controlLoop).length > 0 && (
        <section id="control-loop" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Control Loop" />
          <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4 text-sm text-[var(--foreground)]">
            <div className="mb-2">
              <span className="font-semibold">Flow:</span>{" "}
              <code className="rounded bg-[var(--surface)] px-1.5 py-0.5 font-mono text-[13px] text-[var(--accent)]">
                {safeString((controlLoop as any)?.flow) || "Not specified"}
              </code>
            </div>
            {safeArray<string>((controlLoop as any)?.termination_conditions).length > 0 && (
              <div>
                <div className="mb-1 font-semibold">Termination conditions</div>
                <ul className="ml-4 list-disc space-y-1">
                  {safeArray<string>((controlLoop as any)?.termination_conditions).map((c, idx) => (
                    <li key={`${c}-${idx}`}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Safety */}
      {showSafety && (
        <section id="safety" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Safety & Bounded Autonomy" />
          <div className="space-y-4">
            {safeArray<Record<string, unknown>>((boundedAutonomy as any)?.constraints).length > 0 && (
              <div>
                <div className="mb-2 text-sm font-semibold text-[var(--foreground)]">Constraints</div>
                <div className="overflow-x-auto rounded border border-[var(--border)] bg-[var(--background)]">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr className="bg-[var(--surface)]">
                        <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                          Constraint
                        </th>
                        <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                          Value
                        </th>
                        <th className="border-b border-[var(--border)] px-3 py-2 text-left font-semibold text-[var(--foreground)]">
                          Action on Breach
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {safeArray<Record<string, unknown>>((boundedAutonomy as any)?.constraints).map((c, idx) => (
                        <tr key={idx} className="border-t border-[var(--border)]">
                          <td className="px-3 py-2 text-[var(--foreground)]">{safeString(c.constraint) || "-"}</td>
                          <td className="px-3 py-2 text-[var(--foreground)]">{safeString(c.value) || "-"}</td>
                          <td className="px-3 py-2 text-[var(--foreground)]">{safeString(c.action_on_breach) || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Notes / Status */}
      {showNotes && (
        <section id="notes" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Notes / Status" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Architecture Notes
              </div>
              {architectureNotes.length ? (
                <ul className="ml-4 list-disc space-y-1 text-sm text-[var(--foreground)]">
                  {architectureNotes.map((n, idx) => (
                    <li key={idx}>{n}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-[var(--foreground-muted)]">None</div>
              )}
            </div>
            <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Diagram Notes
              </div>
              {diagramNotes.length ? (
                <ul className="ml-4 list-disc space-y-1 text-sm text-[var(--foreground)]">
                  {diagramNotes.map((n, idx) => (
                    <li key={idx}>{n}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-[var(--foreground-muted)]">None</div>
              )}
            </div>
            <div className="rounded border border-[var(--border)] bg-[var(--background)] p-4">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">
                Output Notes
              </div>
              {outputNotes.length ? (
                <ul className="ml-4 list-disc space-y-1 text-sm text-[var(--foreground)]">
                  {outputNotes.map((n, idx) => (
                    <li key={idx}>{n}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-[var(--foreground-muted)]">None</div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Exports */}
      {showExports && (
        <section id="exports" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Exports" />
          <div className="flex flex-wrap items-center gap-2">
            <SmallButton onClick={handleCopyJson} disabled={!showExports}>
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M16 13H8" />
                <path d="M16 17H8" />
                <path d="M10 9H8" />
              </svg>
              {copiedJson ? "JSON copied!" : "Copy design_state JSON"}
            </SmallButton>
            <SmallButton onClick={handleDownloadJson} disabled={!showExports}>
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3v12m0 0l-4-4m4 4l4-4" />
                <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
              </svg>
              Download JSON
            </SmallButton>
            <SmallButton onClick={handleCopyMermaid} disabled={!mermaidCode}>
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <path d="M14 2v6h6" />
              </svg>
              {copiedMermaid ? "Mermaid copied!" : "Copy Mermaid"}
            </SmallButton>
          </div>
        </section>
      )}

      {/* Markdown (secondary narrative) */}
      {output && (
        <section id="markdown" className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
          <SectionHeader title="Markdown" />
          <details className="rounded border border-[var(--border)] bg-[var(--background)]">
            <summary className="cursor-pointer px-4 py-2 font-semibold text-[var(--foreground)] hover:bg-[var(--surface)]">
              View rendered markdown output
            </summary>
            <div className="p-4">
              <div className="prose prose-sm prose-invert max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={{
                    h1: ({ node, ...props }) => (
                      <h1
                        className="mb-4 mt-0 border-b border-[var(--border)] pb-3 text-2xl font-bold text-[var(--foreground)]"
                        {...props}
                      />
                    ),
                    h2: ({ node, ...props }) => (
                      <h2 className="mb-3 mt-6 text-xl font-bold text-[var(--foreground)]" {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3 className="mb-2 mt-4 text-lg font-semibold text-[var(--foreground)]" {...props} />
                    ),
                    p: ({ node, ...props }) => (
                      <p className="mb-3 leading-relaxed text-[var(--foreground)]" {...props} />
                    ),
                    ul: ({ node, ...props }) => (
                      <ul className="mb-4 ml-4 list-disc space-y-1 text-[var(--foreground)]" {...props} />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol className="mb-4 ml-4 list-decimal space-y-1 text-[var(--foreground)]" {...props} />
                    ),
                    li: ({ node, ...props }) => <li className="text-[var(--foreground)]" {...props} />,
                    code: ({ node, className, children, ...props }) => {
                      const isInline = !className;
                      const isMermaid = className?.includes("language-mermaid");

                      if (isInline) {
                        return (
                          <code
                            className="rounded bg-[var(--surface)] px-1.5 py-0.5 font-mono text-sm text-[var(--accent)]"
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      }

                      if (isMermaid) {
                        return (
                          <code
                            className="block overflow-x-auto rounded-sm bg-[#1a1a2e] p-4 font-mono text-sm text-[#a8dadc]"
                            {...props}
                          >
                            {children}
                          </code>
                        );
                      }

                      return (
                        <code
                          className="block overflow-x-auto rounded-sm bg-[var(--surface)] p-4 font-mono text-sm text-[var(--foreground)]"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    },
                    pre: ({ node, ...props }) => (
                      <pre
                        className="mb-4 overflow-x-auto rounded-sm border border-[var(--border)] bg-[var(--surface)] p-0"
                        {...props}
                      />
                    ),
                    a: ({ node, ...props }) => (
                      <a
                        className="text-[var(--accent)] underline decoration-[var(--accent)]/30 underline-offset-2 transition-colors hover:decoration-[var(--accent)]"
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                      />
                    ),
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        className="my-4 border-l-4 border-[var(--accent)] bg-[var(--surface)] py-2 pl-4 italic text-[var(--foreground-muted)]"
                        {...props}
                      />
                    ),
                    table: ({ node, ...props }) => (
                      <div className="my-4 overflow-x-auto">
                        <table className="w-full border-collapse border border-[var(--border)] text-sm" {...props} />
                      </div>
                    ),
                    th: ({ node, ...props }) => (
                      <th
                        className="border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-left font-semibold text-[var(--foreground)]"
                        {...props}
                      />
                    ),
                    td: ({ node, ...props }) => (
                      <td className="border border-[var(--border)] px-3 py-2 text-[var(--foreground)]" {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                      <strong className="font-semibold text-[var(--foreground)]" {...props} />
                    ),
                    em: ({ node, ...props }) => <em className="italic text-[var(--foreground)]" {...props} />,
                    hr: ({ node, ...props }) => <hr className="my-6 border-[var(--border)]" {...props} />,
                    img: ({ node, src, alt, ...props }) => {
                      if (markdownImageError || !src) {
                        return (
                          <span className="my-4 flex items-center justify-center rounded border border-[var(--border)] bg-[var(--surface)] p-8 text-[var(--foreground-muted)] block">
                            <span>Image unavailable</span>
                          </span>
                        );
                      }
                      return (
                        <span className="my-4 block">
                          <img
                            src={src}
                            alt={alt || "Image"}
                            className="max-w-full rounded border border-[var(--border)] bg-white"
                            onError={() => setMarkdownImageError(true)}
                            {...props}
                          />
                        </span>
                      );
                    },
                    details: ({ node, ...props }) => (
                      <details className="my-4 rounded border border-[var(--border)] bg-[var(--surface)]" {...props} />
                    ),
                    summary: ({ node, ...props }) => (
                      <summary
                        className="cursor-pointer px-4 py-2 font-semibold text-[var(--foreground)] hover:bg-[var(--background)]"
                        {...props}
                      />
                    ),
                  }}
                >
                  {output}
                </ReactMarkdown>
              </div>
            </div>
          </details>
        </section>
      )}
      </div>
    </div>
  );
}

