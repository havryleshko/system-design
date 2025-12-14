"use client";

import { useCallback } from "react";

type DownloadTabProps = {
  values: Record<string, unknown> | null;
  runId: string | null;
};

type DownloadFile = {
  name: string;
  type: string;
  size: string;
  date: string;
  available: boolean;
};

export default function DownloadTab({ values, runId }: DownloadTabProps) {
  const architectureJson = values?.architecture_json as Record<string, unknown> | undefined;
  const hasArchitecture = architectureJson && Object.keys(architectureJson).length > 0;

  const formatDate = () => {
    return new Date().toLocaleDateString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
    });
  };

  // Generate files list based on available data
  const files: DownloadFile[] = [
    {
      name: "architecture_diagram.png",
      type: "PNG",
      size: hasArchitecture ? "~150 KB" : "N/A",
      date: formatDate(),
      available: !!hasArchitecture,
    },
    {
      name: "notebook.ipynb",
      type: "IPYNB",
      size: "Coming Soon",
      date: formatDate(),
      available: false,
    },
  ];

  const handleDownloadArchitecture = useCallback(() => {
    if (!architectureJson) return;

    // Create a simple SVG diagram from architecture_json
    const elements = (architectureJson.elements as Array<Record<string, unknown>>) || [];
    const relations = (architectureJson.relations as Array<Record<string, unknown>>) || [];

    // Generate SVG content
    const nodeWidth = 180;
    const nodeHeight = 60;
    const horizontalGap = 80;
    const verticalGap = 40;
    const cols = Math.min(3, elements.length);
    const rows = Math.ceil(elements.length / cols);

    const svgWidth = cols * (nodeWidth + horizontalGap) + 100;
    const svgHeight = rows * (nodeHeight + verticalGap) + 100;

    // Position nodes
    const nodePositions: Record<string, { x: number; y: number }> = {};
    elements.forEach((el, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      nodePositions[String(el.id)] = {
        x: 50 + col * (nodeWidth + horizontalGap),
        y: 50 + row * (nodeHeight + verticalGap),
      };
    });

    // Generate SVG
    let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgWidth} ${svgHeight}" width="${svgWidth}" height="${svgHeight}">
  <style>
    .node { fill: #23252f; stroke: #333746; stroke-width: 2; rx: 8; }
    .node-label { fill: #d7d7d7; font-family: system-ui, sans-serif; font-size: 12px; font-weight: 600; }
    .node-type { fill: #9ab6c2; font-family: system-ui, sans-serif; font-size: 10px; }
    .edge { stroke: #9ab6c2; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
    .edge-label { fill: #8c8c8c; font-family: system-ui, sans-serif; font-size: 9px; }
  </style>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ab6c2"/>
    </marker>
  </defs>
  <rect width="100%" height="100%" fill="#1b1d26"/>
`;

    // Draw edges first (so they appear behind nodes)
    relations.forEach((rel) => {
      const source = nodePositions[String(rel.source)];
      const target = nodePositions[String(rel.target)];
      if (source && target) {
        const startX = source.x + nodeWidth / 2;
        const startY = source.y + nodeHeight;
        const endX = target.x + nodeWidth / 2;
        const endY = target.y;

        // Simple curved path
        const midY = (startY + endY) / 2;
        svg += `  <path class="edge" d="M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}"/>
`;
        if (rel.label) {
          svg += `  <text class="edge-label" x="${(startX + endX) / 2}" y="${midY}" text-anchor="middle">${String(rel.label)}</text>
`;
        }
      }
    });

    // Draw nodes
    elements.forEach((el) => {
      const pos = nodePositions[String(el.id)];
      if (!pos) return;

      svg += `  <rect class="node" x="${pos.x}" y="${pos.y}" width="${nodeWidth}" height="${nodeHeight}"/>
`;
      svg += `  <text class="node-label" x="${pos.x + nodeWidth / 2}" y="${pos.y + 25}" text-anchor="middle">${String(el.label || el.id)}</text>
`;
      if (el.kind) {
        svg += `  <text class="node-type" x="${pos.x + nodeWidth / 2}" y="${pos.y + 42}" text-anchor="middle">${String(el.kind)}</text>
`;
      }
    });

    svg += "</svg>";

    // Convert SVG to PNG using canvas
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const img = new Image();
    const svgBlob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      canvas.width = svgWidth * 2; // 2x for better quality
      canvas.height = svgHeight * 2;
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);

      // Download as PNG
      canvas.toBlob((blob) => {
        if (!blob) return;
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `architecture_diagram_${runId || "export"}.png`;
        link.click();
        URL.revokeObjectURL(link.href);
      }, "image/png");
    };

    img.src = url;
  }, [architectureJson, runId]);

  const handleDownloadAll = useCallback(() => {
    // For now, just download the architecture diagram
    if (hasArchitecture) {
      handleDownloadArchitecture();
    }
  }, [hasArchitecture, handleDownloadArchitecture]);

  return (
    <div className="download-tab flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Available Files</h3>
        <button
          type="button"
          onClick={handleDownloadAll}
          disabled={!hasArchitecture}
          className="flex items-center gap-2 rounded-lg border border-[var(--accent)] bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--background)] transition-all hover:shadow-[0_0_16px_rgba(154,182,194,0.3)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <path d="M7 10l5 5 5-5" />
            <path d="M12 15V3" />
          </svg>
          Download All
        </button>
      </div>

      {/* Files List */}
      <div className="space-y-3">
        {files.map((file) => (
          <div
            key={file.name}
            className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
          >
            <div className="flex items-center gap-4">
              {/* File Icon */}
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--background)]">
                {file.type === "PNG" ? (
                  <svg viewBox="0 0 24 24" className="h-5 w-5 text-[#22c55e]" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="M21 15l-5-5L5 21" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" className="h-5 w-5 text-[var(--accent)]" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                    <path d="M14 2v6h6" />
                    <path d="M10 9l-2 6 2 6" />
                    <path d="M14 9l2 6-2 6" />
                  </svg>
                )}
              </div>

              {/* File Info */}
              <div className="flex flex-col">
                <span className="font-medium text-[var(--foreground)]">{file.name}</span>
                <div className="flex items-center gap-3 text-xs text-[var(--foreground-muted)]">
                  <span className="rounded bg-[var(--background)] px-1.5 py-0.5 font-semibold">
                    {file.type}
                  </span>
                  <span>{file.size}</span>
                  <span>{file.date}</span>
                </div>
              </div>
            </div>

            {/* Download Button */}
            <button
              type="button"
              onClick={file.type === "PNG" ? handleDownloadArchitecture : undefined}
              disabled={!file.available}
              className="flex items-center gap-2 rounded-lg border border-[var(--accent)] bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--background)] transition-all hover:shadow-[0_0_12px_rgba(154,182,194,0.25)] disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-[var(--surface)] disabled:text-[var(--foreground-muted)] disabled:shadow-none"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <path d="M7 10l5 5 5-5" />
                <path d="M12 15V3" />
              </svg>
              Download
            </button>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {!hasArchitecture && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--background)] py-12">
          <svg viewBox="0 0 24 24" className="mb-3 h-10 w-10 text-[var(--foreground-muted)]" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
            <path d="M13 2v7h7" />
          </svg>
          <p className="text-sm text-[var(--foreground-muted)]">
            No files available for download yet.
          </p>
          <p className="mt-1 text-xs text-[var(--foreground-muted)]">
            Files will appear here once the analysis is complete.
          </p>
        </div>
      )}
    </div>
  );
}

