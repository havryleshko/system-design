"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/app/providers/AuthProvider";

export default function ChatGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?redirect=${encodeURIComponent("/chat")}`);
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div 
        className="flex min-h-screen items-center justify-center"
        style={{ background: 'var(--background)', color: 'var(--foreground)' }}
      >
        <p className="text-sm" style={{ color: 'var(--foreground-muted)' }}>Checking your session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
