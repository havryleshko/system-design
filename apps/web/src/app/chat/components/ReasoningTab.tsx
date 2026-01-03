"use client";

import { useState } from "react";

type ReasoningTabProps = {
  query: string;
  values: Record<string, unknown> | null;
};

type CollapsibleSectionProps = {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
};

// Helper to safely get string value
function getString(value: unknown): string | null {
  if (typeof value === "string" && value) return value;
  return null;
}

// Helper to safely get array
function getArray(value: unknown): unknown[] | null {
  if (Array.isArray(value) && value.length > 0) return value;
  return null;
}

// Helper to check if object has keys
function hasKeys(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && Object.keys(value).length > 0;
}

function CollapsibleSection({ title, icon, defaultOpen = false, children }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-[var(--background)]"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-6 w-6 items-center justify-center rounded-sm bg-[var(--background)] text-[var(--accent)]">
            {icon}
          </span>
          <span className="font-medium text-[var(--foreground)]">{title}</span>
        </div>
        <svg
          viewBox="0 0 24 24"
          className={`h-4 w-4 text-[var(--foreground-muted)] transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {isOpen && (
        <div className="border-t border-[var(--border)] px-4 py-3">
          {children}
        </div>
      )}
    </div>
  );
}

function DataItem({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex gap-2 text-sm">
      <span className="font-medium text-[var(--foreground-muted)]">{label}:</span>
      <span className="text-[var(--foreground)]">{String(value)}</span>
    </div>
  );
}

function ListItems({ items, emptyText = "No items" }: { items: unknown[] | null | undefined; emptyText?: string }) {
  if (!items || !Array.isArray(items) || items.length === 0) {
    return <p className="text-sm text-[var(--foreground-muted)]">{emptyText}</p>;
  }
  return (
    <ul className="space-y-1 text-sm">
      {items.map((item, idx) => (
        <li key={idx} className="flex items-start gap-2 text-[var(--foreground)]">
          <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[var(--accent)]" />
          <span>{typeof item === "object" ? JSON.stringify(item) : String(item)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function ReasoningTab({ query, values }: ReasoningTabProps) {
  if (!values) {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <p className="text-[var(--foreground-muted)]">No reasoning data available yet.</p>
      </div>
    );
  }

  const planState = (values.plan_state as Record<string, unknown>) || {};
  const planScope = (values.plan_scope as Record<string, unknown>) || {};
  const researchState = (values.research_state as Record<string, unknown>) || {};
  const designState = (values.design_state as Record<string, unknown>) || {};
  const criticState = (values.critic_state as Record<string, unknown>) || {};
  const evalState = (values.eval_state as Record<string, unknown>) || {};

  // Extract research nodes
  const researchNodes = (researchState.nodes as Record<string, Record<string, unknown>>) || {};
  const knowledgeBase = researchNodes.knowledge_base || {};
  const githubApi = researchNodes.github_api || {};
  const webSearch = researchNodes.web_search || {};

  // Extract design components
  const componentsData = (designState.components as Record<string, unknown>) || {};
  const components = getArray(componentsData.components) || [];
  const costsData = (designState.costs as Record<string, unknown>) || {};
  const diagramData = (designState.diagram as Record<string, unknown>) || {};

  // Extract critic data
  const reviewData = (criticState.review as Record<string, unknown>) || {};
  const hallucinationData = (criticState.hallucination as Record<string, unknown>) || {};
  const riskData = (criticState.risk as Record<string, unknown>) || {};

  // Extract eval data
  const telemetryData = (evalState.telemetry as Record<string, unknown>) || {};
  const scoresData = (evalState.scores as Record<string, unknown>) || {};

  // Extract typed values
  const planSummary = getString(planState.summary);
  const planSteps = getArray(planState.steps);
  const planRisks = getArray(planState.risks);
  const scopeIssues = getArray(planScope.issues);

  const kbStatus = getString(knowledgeBase.status);
  const kbHighlights = getArray(knowledgeBase.highlights);
  const ghStatus = getString(githubApi.status);
  const ghHighlights = getArray(githubApi.highlights);
  const wsStatus = getString(webSearch.status);
  const wsHighlights = getArray(webSearch.highlights);
  const wsCitations = getArray(webSearch.citations);

  const diagramStatus = getString(diagramData.status);
  const reviewStatus = getString(reviewData.status);
  const reviewNotes = reviewData.notes;
  const hallucinationStatus = getString(hallucinationData.status);
  const hallucinationIssues = getArray(hallucinationData.issues);
  const riskStatus = getString(riskData.status);
  const riskRisks = getArray(riskData.risks);

  const telemetryStatus = getString(telemetryData.status);
  const telemetryMetrics = telemetryData.telemetry;
  const scoresStatus = getString(scoresData.status);
  const scoresMetrics = scoresData.scores;

  return (
    <div className="reasoning-tab flex flex-col gap-4">
      {/* Query Section */}
      <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-4">
        <div className="mb-2 flex items-center gap-2">
          <svg viewBox="0 0 24 24" className="h-4 w-4 text-[var(--accent)]" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" />
          </svg>
          <span className="font-semibold text-[var(--foreground)]">Query</span>
        </div>
        <p className="whitespace-pre-wrap text-sm text-[var(--foreground)]">{query}</p>
      </div>

      {/* Planner Section */}
      <CollapsibleSection
        title="Planner Agent"
        defaultOpen={true}
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
            <rect x="9" y="3" width="6" height="4" rx="1" />
            <path d="M9 12h6" />
            <path d="M9 16h6" />
          </svg>
        }
      >
        <div className="space-y-4">
          {planSummary && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Summary</h4>
              <p className="text-sm text-[var(--foreground)]">{planSummary}</p>
            </div>
          )}
          {planSteps && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Steps</h4>
              <div className="space-y-2">
                {(planSteps as Array<Record<string, unknown>>).map((step, idx) => (
                  <div key={idx} className="rounded-sm bg-[var(--background)] p-3">
                    <div className="flex items-start gap-2">
                      <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/20 text-xs font-semibold text-[var(--accent)]">
                        {idx + 1}
                      </span>
                      <div>
                        <p className="font-medium text-[var(--foreground)]">{String(step.title || "Step")}</p>
                        {step.detail != null && (
                          <p className="mt-1 text-sm text-[var(--foreground-muted)]">{String(step.detail)}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {planRisks && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Risks</h4>
              <ListItems items={planRisks} />
            </div>
          )}
          {scopeIssues && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Issues</h4>
              <ListItems items={scopeIssues} />
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Research Section */}
      <CollapsibleSection
        title="Research Agent"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        }
      >
        <div className="space-y-4">
          {/* Knowledge Base */}
          {hasKeys(knowledgeBase) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Knowledge Base</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {kbStatus && <DataItem label="Status" value={kbStatus} />}
                {kbHighlights && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Highlights:</span>
                    <ListItems items={kbHighlights} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* GitHub API */}
          {hasKeys(githubApi) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">GitHub API</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {ghStatus && <DataItem label="Status" value={ghStatus} />}
                {ghHighlights && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Highlights:</span>
                    <ListItems items={ghHighlights} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Web Search */}
          {hasKeys(webSearch) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Web Search</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {wsStatus && <DataItem label="Status" value={wsStatus} />}
                {wsHighlights && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Highlights:</span>
                    <ListItems items={wsHighlights} />
                  </div>
                )}
                {wsCitations && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Citations:</span>
                    <ul className="mt-1 space-y-1">
                      {(wsCitations as Array<Record<string, unknown>>).slice(0, 6).map((cite, idx) => (
                        <li key={idx} className="text-sm">
                          {cite.url ? (
                            <a
                              href={String(cite.url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[var(--accent)] hover:underline"
                            >
                              {String(cite.title || cite.url)}
                            </a>
                          ) : (
                            <span className="text-[var(--foreground)]">{String(cite.title || "Source")}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {!hasKeys(knowledgeBase) && !hasKeys(githubApi) && !hasKeys(webSearch) && (
            <p className="text-sm text-[var(--foreground-muted)]">No research data available.</p>
          )}
        </div>
      </CollapsibleSection>

      {/* Design Section */}
      <CollapsibleSection
        title="Design Agent"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 21V9" />
          </svg>
        }
      >
        <div className="space-y-4">
          {/* Components */}
          {components.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Components</h4>
              <div className="space-y-2">
                {(components as Array<Record<string, unknown>>).slice(0, 10).map((comp, idx) => (
                  <div key={idx} className="rounded-sm bg-[var(--background)] p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-[var(--foreground)]">
                        {String(comp.name || comp.id || `Component ${idx + 1}`)}
                      </span>
                      {comp.type != null && (
                        <span className="rounded-full bg-[var(--accent)]/10 px-2 py-0.5 text-xs text-[var(--accent)]">
                          {String(comp.type)}
                        </span>
                      )}
                    </div>
                    {comp.description != null && (
                      <p className="mt-1 text-sm text-[var(--foreground-muted)]">{String(comp.description)}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Costs */}
          {hasKeys(costsData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Cost Estimates</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {Object.entries(costsData).map(([key, value]) => (
                  <DataItem key={key} label={key} value={typeof value === "object" ? JSON.stringify(value) : String(value)} />
                ))}
              </div>
            </div>
          )}

          {/* Diagram */}
          {diagramStatus && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Diagram</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                <DataItem label="Status" value={diagramStatus} />
              </div>
            </div>
          )}

          {components.length === 0 && !hasKeys(costsData) && (
            <p className="text-sm text-[var(--foreground-muted)]">No design data available.</p>
          )}
        </div>
      </CollapsibleSection>

      {/* Critic Section */}
      <CollapsibleSection
        title="Critic Agent"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
        }
      >
        <div className="space-y-4">
          {/* Review */}
          {hasKeys(reviewData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Review</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {reviewStatus && <DataItem label="Status" value={reviewStatus} />}
                {reviewNotes != null && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Notes:</span>
                    {Array.isArray(reviewNotes) ? (
                      <ListItems items={reviewNotes} />
                    ) : (
                      <p className="text-sm text-[var(--foreground)]">{String(reviewNotes)}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Hallucination Check */}
          {hasKeys(hallucinationData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Hallucination Check</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {hallucinationStatus && <DataItem label="Status" value={hallucinationStatus} />}
                {hallucinationIssues && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Issues Found:</span>
                    <ListItems items={hallucinationIssues} emptyText="No issues found" />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Risk Analysis */}
          {hasKeys(riskData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Risk Analysis</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {riskStatus && <DataItem label="Status" value={riskStatus} />}
                {riskRisks && (
                  <div className="mt-2">
                    <span className="text-xs font-medium text-[var(--foreground-muted)]">Risks:</span>
                    <ListItems items={riskRisks} />
                  </div>
                )}
              </div>
            </div>
          )}

          {!hasKeys(reviewData) && !hasKeys(hallucinationData) && !hasKeys(riskData) && (
            <p className="text-sm text-[var(--foreground-muted)]">No critic data available.</p>
          )}
        </div>
      </CollapsibleSection>

      {/* Evals Section */}
      <CollapsibleSection
        title="Evals Agent"
        icon={
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
            <path d="M22 4L12 14.01l-3-3" />
          </svg>
        }
      >
        <div className="space-y-4">
          {/* Telemetry */}
          {hasKeys(telemetryData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Telemetry</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {telemetryStatus && <DataItem label="Status" value={telemetryStatus} />}
                {hasKeys(telemetryMetrics) && (
                  <div className="mt-2 space-y-1">
                    {Object.entries(telemetryMetrics).map(([key, value]) => (
                      <DataItem key={key} label={key} value={typeof value === "object" ? JSON.stringify(value) : String(value)} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Scores */}
          {hasKeys(scoresData) && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--foreground-muted)]">Scores</h4>
              <div className="rounded-sm bg-[var(--background)] p-3">
                {scoresStatus && <DataItem label="Status" value={scoresStatus} />}
                {hasKeys(scoresMetrics) && (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {Object.entries(scoresMetrics).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between rounded-sm bg-[var(--surface)] px-3 py-2">
                        <span className="text-sm text-[var(--foreground-muted)]">{key}</span>
                        <span className="font-medium text-[var(--foreground)]">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {!hasKeys(telemetryData) && !hasKeys(scoresData) && (
            <p className="text-sm text-[var(--foreground-muted)]">No evaluation data available.</p>
          )}
        </div>
      </CollapsibleSection>
    </div>
  );
}
