"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { getBrowserSupabase } from "@/utils/supabase/browser";

function LoginContent() {
  const supabase = getBrowserSupabase();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const redirectTo = searchParams.get("redirect") || "/chat";
  const callbackUrl = `${window.location.origin}?redirect=${encodeURIComponent(redirectTo)}`;

  async function handleMagicLink(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: callbackUrl,
      },
    });
    if (error) {
      setMessage(error.message);
    } else {
      setMessage("Check your inbox for the login link.");
    }
    setLoading(false);
  }

  async function handleGoogle() {
    setLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: callbackUrl,
      },
    });
    if (error) {
      setMessage(error.message);
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-black text-white">
      <div className="w-full max-w-md rounded-lg border border-white/10 bg-white/5 p-8 shadow-xl">
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-sm text-white/60">
          Use a magic link or Google to access the System Design Agent.
        </p>

        <form onSubmit={handleMagicLink} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-white/80" htmlFor="email">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded border border-white/20 bg-black/40 px-3 py-2 text-sm text-white placeholder:text-white/40 focus:outline-none focus:ring"
            placeholder="you@example.com"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-white px-4 py-2 text-sm font-semibold uppercase tracking-wide text-black transition hover:bg-white/80 disabled:cursor-not-allowed disabled:bg-white/30"
          >
            {loading ? "Sending..." : "Send Magic Link"}
          </button>
        </form>

        <div className="my-6 text-center text-xs uppercase text-white/40">or</div>

        <button
          onClick={handleGoogle}
          disabled={loading}
          className="w-full rounded border border-white px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-white/30 disabled:text-white/30"
        >
          Continue with Google
        </button>

        {message && <p className="mt-4 text-sm text-white/70">{message}</p>}

        <p className="mt-6 text-xs text-white/40">
          By signing in you agree to our {""}
          <Link className="text-white hover:underline" href="/terms">
            Terms
          </Link>
          {" "}and{" "}
          <Link className="text-white hover:underline" href="/privacy">
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-black text-white">
          <p className="text-sm text-white/60">Loading…</p>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}

