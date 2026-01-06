import { NextResponse } from "next/server";
import { createServerSupabase } from "@/utils/supabase/server";
import type { EmailOtpType } from "@supabase/supabase-js";

const EMAIL_OTP_TYPES: ReadonlySet<string> = new Set([
  "signup",
  "invite",
  "magiclink",
  "recovery",
  "email_change",
]);

function parseEmailOtpType(value: string | null): EmailOtpType | null {
  if (!value) return null;
  return EMAIL_OTP_TYPES.has(value) ? (value as EmailOtpType) : null;
}

function getSafeRedirectPath(value: string | null): string {
  if (!value) return "/chat";
  return value.startsWith("/") ? value : "/chat";
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const redirectPath = getSafeRedirectPath(url.searchParams.get("redirect"));

  const token_hash = url.searchParams.get("token_hash");
  const type = url.searchParams.get("type");
  const emailOtpType = parseEmailOtpType(type);

  if (code || (token_hash && type)) {
    const supabase = await createServerSupabase();

    if (code) {
      await supabase.auth.exchangeCodeForSession(code);
    } else if (token_hash && emailOtpType) {
      await supabase.auth.verifyOtp({
        token_hash,
        type: emailOtpType,
      });
    }
  }
  return NextResponse.redirect(new URL(redirectPath, url.origin));
}


