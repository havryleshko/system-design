"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/app/providers/AuthProvider";
import { getBrowserSupabase } from "@/utils/supabase/browser";

type ProfilePopupProps = {
  onClose: () => void;
  anchorRef: React.RefObject<HTMLButtonElement | null>;
};

export default function ProfilePopup({ onClose, anchorRef }: ProfilePopupProps) {
  const { user } = useAuth();
  const router = useRouter();
  const popupRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        popupRef.current &&
        !popupRef.current.contains(event.target as Node) &&
        anchorRef.current &&
        !anchorRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose, anchorRef]);

  // Close on Escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  const handleSignOut = async () => {
    const supabase = getBrowserSupabase();
    await supabase.auth.signOut();
    router.push("/");
  };

  return (
    <div
      ref={popupRef}
      className="absolute bottom-full left-0 mb-2 w-[220px] rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-[0_8px_32px_rgba(0,0,0,0.4)]"
      style={{ zIndex: 50 }}
    >
      {/* Contact Section */}
      <div className="border-b border-[var(--border)] px-4 py-3">
        <div className="text-xs font-medium uppercase tracking-wider text-[var(--foreground-muted)]">
          Contact
        </div>
        <div className="mt-1 truncate text-sm text-[var(--foreground)]">
          {user?.email ?? "—"}
        </div>
      </div>

      {/* Organizations Placeholder */}
      <div className="border-b border-[var(--border)] px-4 py-3">
        <div className="text-xs font-medium uppercase tracking-wider text-[var(--foreground-muted)]">
          Organizations
        </div>
        <div className="mt-1 text-sm text-[var(--foreground)]">My Organization</div>
      </div>

      {/* Menu Items */}
      <div className="flex flex-col py-1">
        <Link
          href="/profile"
          onClick={onClose}
          className="flex items-center gap-2 px-4 py-2.5 text-sm text-[var(--foreground-muted)] transition-colors hover:bg-[var(--background)] hover:text-[var(--foreground)]"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="8" r="3.5" />
            <path d="M6 19c0-3 2.7-5 6-5s6 2 6 5" />
          </svg>
          Profile
        </Link>

        <button
          type="button"
          onClick={handleSignOut}
          className="flex items-center gap-2 px-4 py-2.5 text-sm text-[var(--foreground-muted)] transition-colors hover:bg-[var(--background)] hover:text-[var(--foreground)]"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16,17 21,12 16,7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Sign out
        </button>
      </div>
    </div>
  );
}

