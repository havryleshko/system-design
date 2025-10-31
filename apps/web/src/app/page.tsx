"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";

import { getBrowserSupabase } from "@/utils/supabase/browser";

export default function Home() {
  const router = useRouter();
  const isProcessingRef = useRef(false);
  const redirectTarget = useMemo(() => {
    if (typeof window === "undefined") return "/chat";
    const params = new URLSearchParams(window.location.search);
    const candidate = params.get("redirect");
    if (candidate && candidate.startsWith("/")) {
      return candidate;
    }
    return "/chat";
  }, []);

  useEffect(() => {
    const supabase = getBrowserSupabase();
    let isMounted = true;

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) return;
      if (session) {
        router.replace(redirectTarget);
      }
    });

    async function handleAuthExchange() {
      if (isProcessingRef.current) return;
      isProcessingRef.current = true;

      const search = window.location.search;
      const params = new URLSearchParams(search);

      if (params.has("code")) {
        const { error } = await supabase.auth.exchangeCodeForSession(window.location.href);
        if (error) {
          console.error("Supabase sign-in exchange failed", error.message);
          isProcessingRef.current = false;
          return;
        }
      }

      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (session) {
        router.replace(redirectTarget);
      } else {
        isProcessingRef.current = false;
      }
    }

    handleAuthExchange();

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [redirectTarget, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-black text-white">
      <p className="text-sm text-white/60">Redirecting to chat…</p>
    </div>
  );
}

