import { NextResponse } from "next/server";

import { createServerSupabase } from "@/utils/supabase/server";

const DEBUG_ENABLED = process.env.SUPABASE_TOKEN_DEBUG === "true";

export async function GET() {
  if (!DEBUG_ENABLED || process.env.NODE_ENV === "production") {
    return NextResponse.json({ error: "Disabled" }, { status: 404 });
  }

  const supabase = await createServerSupabase();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? null;

  if (!token) {
    return NextResponse.json({ error: "No token" }, { status: 404 });
  }

  return NextResponse.json({ token });
}

