import { NextResponse } from "next/server";

import { createServerSupabase } from "@/utils/supabase/server";

export async function GET() {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ error: "Not available" }, { status: 404 });
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

