"use client";

type PlaceholderTabProps = {
  title: string;
  note?: string;
};

export default function PlaceholderTab({ title, note }: PlaceholderTabProps) {
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="text-lg font-semibold text-[var(--foreground)]">{title}</div>
      <div className="mt-2 text-sm text-[var(--foreground-muted)]">
        Coming soon. We’re rebuilding this tab from scratch.
      </div>
      {note ? (
        <div className="mt-3 rounded border border-[var(--border)] bg-[var(--background)] p-3 text-xs text-[var(--foreground)]">
          {note}
        </div>
      ) : null}
    </div>
  );
}


