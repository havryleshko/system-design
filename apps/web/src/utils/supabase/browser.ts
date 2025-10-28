'use client';

import { createBrowserClient, SupabaseClient } from '@supabase/ssr';

let client: SupabaseClient | null = null;

export function getBrowserSupabase(): SupabaseClient {
  if (!client) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !anonKey) {
      throw new Error('Supabase environment variables are not configured');
    }
    client = createBrowserClient(url, anonKey);
  }
  return client;
}

