// Client-side instrumentation hook.
// Importing this ensures `sentry.client.config.ts` runs in the browser bundle.
import "./sentry.client.config";

export function register() {
  // no-op; side-effect import above initializes Sentry.
}


