"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";

import { useAuth } from "@/app/providers/AuthProvider";

type ChatGuardProps = {
  children: React.ReactNode;
  initialUser?: User | null;
};

export default function ChatGuard({
  children,
  initialUser,
}: ChatGuardProps) {
  const { user, loading } = useAuth();
  const router = useRouter();

  const fallbackUser = useMemo(() => initialUser ?? null, [initialUser]);
  const effectiveUser = user ?? fallbackUser;

  useEffect(() => {
    if (!loading && !user && !fallbackUser) {
      router.replace(`/login?redirect=${encodeURIComponent("/chat")}`);
    }
  }, [loading, user, fallbackUser, router]);

  if (loading && !fallbackUser) {
    return (
      <div
        className="flex min-h-screen items-center justify-center"
        style={{ background: "var(--background)", color: "var(--foreground)" }}
      >
        <p className="text-sm" style={{ color: "var(--foreground-muted)" }}>
          Checking your session…
        </p>
      </div>
    );
  }

  if (!effectiveUser) {
    return null;
  }

  return <>{children}</>;
}
