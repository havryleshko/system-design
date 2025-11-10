import { createClient } from "@supabase/supabase-js";

export function createAdminSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceKey) {
    throw new Error("Supabase service role environment variables are not configured");
  }

  return createClient(url, serviceKey, {
    auth: {
      persistSession: false,
    },
  });
}

