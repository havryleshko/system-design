import { NextRequest, NextResponse } from "next/server";

import { createThread } from "@/app/actions";

function safeRedirectPath(path: string | null): string {
  if (!path) return "/";
  return path.startsWith("/") ? path : "/";
}

export async function GET(req: NextRequest) {
  const search = req.nextUrl.searchParams;
  const redirectTarget = safeRedirectPath(search.get("redirect"));
  const force = search.get("force") === "1";

  await createThread({ force });

  const url = new URL(redirectTarget, req.nextUrl.origin);
  return NextResponse.redirect(url);
}

export async function POST(req: NextRequest) {
  return GET(req);
}

