"use client";

import type { BlueprintAgent } from "../../types";

export default function BlueprintAgents({ agents }: { agents: BlueprintAgent[] }) {
  if (!agents || agents.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Agents</h2>
        <p className="mt-2 text-sm text-[var(--foreground-muted)]">No agents defined</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Agents</h2>
          <p className="mt-1 text-sm text-[var(--foreground-muted)]">Roles and responsibilities</p>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-xs text-[var(--foreground-muted)]">
          {agents.length} agent{agents.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="mt-6 space-y-3">
        {agents.map((a) => (
          <div key={a.id} className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-[var(--foreground)]">{a.name}</div>
                <div className="mt-0.5 text-xs text-[var(--foreground-muted)]">id: {a.id}</div>
                <p className="mt-2 text-sm text-[var(--foreground)]">{a.role}</p>
              </div>
              {a.model ? (
                <span className="rounded bg-[var(--accent)]/15 px-2 py-0.5 text-[10px] font-semibold text-[var(--accent)]">
                  {a.model}
                </span>
              ) : null}
            </div>

            {(a.responsibilities?.length ?? 0) > 0 && (
              <ul className="mt-3 space-y-1 text-sm text-[var(--foreground)]">
                {a.responsibilities!.slice(0, 8).map((r, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-[var(--accent)]" />
                    {r}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

