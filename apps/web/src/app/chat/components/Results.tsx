"use client";

import { useMemo, useState } from "react";

import type { Blueprint } from "../types";
import BlueprintGraph from "./blueprint/BlueprintGraph";
import BlueprintAgents from "./blueprint/BlueprintAgents";

type ResultsProps = {
  values: Record<string, unknown> | null;
  runStatus: string | null;
};

function coerceBlueprint(values: Record<string, unknown> | null): Blueprint | null {
  if (!values) return null;
  const bp = (values as any).blueprint;
  if (!bp || typeof bp !== "object") return null;
  if ((bp as any).version !== "v1") return null;
  return bp as Blueprint;
}

export default function Results({ values, runStatus }: ResultsProps) {
  const [showDebug, setShowDebug] = useState(false);

  const blueprint = useMemo(() => coerceBlueprint(values), [values]);

  const status = (runStatus ?? "").toLowerCase() || "unknown";
  const valuesJson = useMemo(() => {
    if (!values) return "";
    try {
      return JSON.stringify(values, null, 2);
    } catch {
      return "[unserializable values]";
    }
  }, [values]);

  if (!blueprint) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[var(--foreground)]">Results</h2>
            <p className="mt-1 text-sm text-[var(--foreground-muted)]">
              Waiting for architecture (status: {status})
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowDebug((v) => !v)}
            className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            {showDebug ? "Hide debug" : "Debug"}
          </button>
        </div>

        {showDebug && (
          <pre className="mt-4 max-h-[420px] overflow-auto rounded border border-[var(--border)] bg-[var(--background)] p-3 text-xs text-[var(--foreground)]">
            <code className="block whitespace-pre">{valuesJson || "No values available."}</code>
          </pre>
        )}
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={() => setShowDebug((v) => !v)}
          className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
        >
          {showDebug ? "Hide debug" : "Debug"}
        </button>
      </div>

      <BlueprintGraph graph={blueprint.graph} />
      <BlueprintAgents agents={blueprint.agents} />

      {showDebug && (
        <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Debug: raw values</h3>
            <button
              type="button"
              onClick={async () => {
                if (!valuesJson) return;
                await navigator.clipboard.writeText(valuesJson);
              }}
              disabled={!valuesJson}
              className="rounded-sm border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              Copy JSON
            </button>
          </div>
          <pre className="max-h-[420px] overflow-auto rounded border border-[var(--border)] bg-[var(--background)] p-3 text-xs text-[var(--foreground)]">
            <code className="block whitespace-pre">{valuesJson || "No values available."}</code>
          </pre>
        </section>
      )}
    </div>
  );
}

