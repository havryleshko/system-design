"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

type ResultsTabProps = {
  output: string | null;
  startedAt: Date | null;
};

export default function ResultsTab({ output, startedAt }: ResultsTabProps) {
  const [copied, setCopied] = useState(false);
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    setImageError(false);
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
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!output) {
    return (
      <div className="flex flex-1 items-center justify-center py-12">
        <p className="text-[var(--foreground-muted)]">No results available yet.</p>
      </div>
    );
  }

  return (
    <div className="results-tab flex flex-col gap-6">
      {/* Results Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center rounded-sm border border-[#22c55e]/30 bg-[#22c55e]/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-[#22c55e]">
            SUCCESS
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
            className="flex items-center gap-1.5 rounded-sm border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7" />
              <path d="M16 6l-4-4-4 4" />
              <path d="M12 2v13" />
            </svg>
            Share
          </button>
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
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>

      {/* Markdown Content */}
      <div className="rounded border border-[var(--border)] bg-[var(--surface)] p-6">
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
                <h2
                  className="mb-3 mt-6 text-xl font-bold text-[var(--foreground)]"
                  {...props}
                />
              ),
              h3: ({ node, ...props }) => (
                <h3
                  className="mb-2 mt-4 text-lg font-semibold text-[var(--foreground)]"
                  {...props}
                />
              ),
              p: ({ node, ...props }) => (
                <p className="mb-3 leading-relaxed text-[var(--foreground)]" {...props} />
              ),
              ul: ({ node, ...props }) => (
                <ul
                  className="mb-4 ml-4 list-disc space-y-1 text-[var(--foreground)]"
                  {...props}
                />
              ),
              ol: ({ node, ...props }) => (
                <ol
                  className="mb-4 ml-4 list-decimal space-y-1 text-[var(--foreground)]"
                  {...props}
                />
              ),
              li: ({ node, ...props }) => (
                <li className="text-[var(--foreground)]" {...props} />
              ),
              code: ({ node, className, children, ...props }) => {
                const isInline = !className;
                const isMermaid = className?.includes("language-mermaid");
                
                if (isInline) {
                  return (
                    <code
                      className="rounded bg-[var(--background)] px-1.5 py-0.5 font-mono text-sm text-[var(--accent)]"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }
                
                // Special styling for mermaid code blocks
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
                    className="block overflow-x-auto rounded-sm bg-[var(--background)] p-4 font-mono text-sm text-[var(--foreground)]"
                    {...props}
                  >
                    {children}
                  </code>
                );
              },
              pre: ({ node, ...props }) => (
                <pre
                  className="mb-4 overflow-x-auto rounded-sm border border-[var(--border)] bg-[var(--background)] p-0"
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
                  className="my-4 border-l-4 border-[var(--accent)] bg-[var(--background)] py-2 pl-4 italic text-[var(--foreground-muted)]"
                  {...props}
                />
              ),
              table: ({ node, ...props }) => (
                <div className="my-4 overflow-x-auto">
                  <table
                    className="w-full border-collapse border border-[var(--border)] text-sm"
                    {...props}
                  />
                </div>
              ),
              th: ({ node, ...props }) => (
                <th
                  className="border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-left font-semibold text-[var(--foreground)]"
                  {...props}
                />
              ),
              td: ({ node, ...props }) => (
                <td
                  className="border border-[var(--border)] px-3 py-2 text-[var(--foreground)]"
                  {...props}
                />
              ),
              strong: ({ node, ...props }) => (
                <strong className="font-semibold text-[var(--foreground)]" {...props} />
              ),
              em: ({ node, ...props }) => (
                <em className="italic text-[var(--foreground)]" {...props} />
              ),
              hr: ({ node, ...props }) => (
                <hr className="my-6 border-[var(--border)]" {...props} />
              ),
              // Architecture diagram image with fallback
              img: ({ node, src, alt, ...props }) => {
                if (imageError || !src) {
                  return (
                    <div className="my-4 flex items-center justify-center rounded border border-[var(--border)] bg-[var(--background)] p-8 text-[var(--foreground-muted)]">
                      <span>Diagram image unavailable</span>
                    </div>
                  );
                }
                return (
                  <div className="my-4">
                    <img
                      src={src}
                      alt={alt || "Architecture Diagram"}
                      className="max-w-full rounded border border-[var(--border)] bg-white"
                      onError={() => setImageError(true)}
                      {...props}
                    />
                  </div>
                );
              },
              // Style details/summary for collapsible diagram code
              details: ({ node, ...props }) => (
                <details
                  className="my-4 rounded border border-[var(--border)] bg-[var(--background)]"
                  {...props}
                />
              ),
              summary: ({ node, ...props }) => (
                <summary
                  className="cursor-pointer px-4 py-2 font-semibold text-[var(--foreground)] hover:bg-[var(--surface)]"
                  {...props}
                />
              ),
            }}
          >
            {output}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

