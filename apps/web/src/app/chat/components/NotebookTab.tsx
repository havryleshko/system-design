"use client";

export default function NotebookTab() {
  return (
    <div className="notebook-tab flex flex-1 flex-col items-center justify-center py-16">
      <div className="flex flex-col items-center gap-4 text-center">
        {/* Notebook Icon */}
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--surface)] border border-[var(--border)]">
          <svg viewBox="0 0 24 24" className="h-8 w-8 text-[var(--accent)]" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 3v18h18" />
            <path d="M7 14l4-4 4 4 5-5" />
          </svg>
        </div>

        {/* Title */}
        <div className="space-y-2">
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Python Notebook</h3>
          <p className="max-w-md text-sm text-[var(--foreground-muted)]">
            Interactive Python notebooks with analysis code will be available here soon.
          </p>
        </div>

        {/* Coming Soon Badge */}
        <span className="inline-flex items-center rounded-full border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-3 py-1 text-xs font-semibold text-[var(--accent)]">
          Coming Soon
        </span>
      </div>
    </div>
  );
}

