import { redirect } from "next/navigation";

import ChatGuard from "./Guard";
import ChatClient from "./ChatClient";
import { createServerSupabase } from "@/utils/supabase/server";

export default async function Page() {
  const supabase = await createServerSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login?redirect=/chat");
  }

  return (
    <ChatGuard initialUser={user}>
      <main className="flex min-h-screen flex-col bg-[var(--background)] text-[var(--foreground)]">
        <ChatClient />
      </main>
    </ChatGuard>
  );
}

