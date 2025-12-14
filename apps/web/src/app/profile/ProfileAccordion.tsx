"use client";

import { useState } from "react";

type ProfileAccordionProps = {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
};

export default function ProfileAccordion({
  title,
  defaultOpen = false,
  children,
}: ProfileAccordionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)]">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-[var(--background)]"
      >
        <span className="text-base font-semibold text-[var(--foreground)]">{title}</span>
        <svg
          viewBox="0 0 24 24"
          className={`h-5 w-5 text-[var(--foreground-muted)] transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {isOpen && (
        <div className="border-t border-[var(--border)] px-6 py-6">{children}</div>
      )}
    </div>
  );
}

