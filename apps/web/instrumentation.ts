import * as Sentry from "@sentry/nextjs";

// Next.js instrumentation hook (App Router).
// This loads the correct Sentry config for server/edge runtimes and enables
// request error capturing.
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }

  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

export const onRequestError = Sentry.captureRequestError;


