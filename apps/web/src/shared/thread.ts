export function buildEnsureThreadUrl(redirectTo: string, force = false): string {
  const params = new URLSearchParams({ redirect: redirectTo });
  if (force) params.set("force", "1");
  return `/api/thread/ensure?${params.toString()}`;
}


