import { redirect } from "next/navigation";
import { getProfile } from "./actions";
import ProfileForm from "./ProfileForm";
import ProfileAccordion from "./ProfileAccordion";
import Link from "next/link";

export default async function ProfilePage() {
  const result = await getProfile();

  if (!result.success || !result.data) {
    redirect("/login");
  }

  const profile = result.data;

  const themeVars = {
    "--background": "#1b1d26",
    "--surface": "#23252f",
    "--foreground": "#d7d7d7",
    "--foreground-muted": "#8c8c8c",
    "--accent": "#9ab6c2",
    "--border": "#333746",
  };

  return (
    <div
      className="min-h-screen bg-[var(--background)] text-[var(--foreground)]"
      style={themeVars as React.CSSProperties}
    >
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 z-10 flex h-screen w-[240px] flex-col border-r border-[var(--border)] bg-[var(--surface)] px-3 py-4">
        <div className="mb-4 flex items-center gap-2">
          <Link
            href="/chat"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm font-semibold tracking-tight text-[var(--foreground)] transition-colors hover:border-[var(--accent)]"
          >
            S
          </Link>
        </div>

        {/* Recent Section */}
        <div className="mb-4">
          <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wider text-[var(--foreground-muted)]">
            Recent
          </div>
          <div className="text-sm text-[var(--foreground-muted)]">No recent items</div>
        </div>

        {/* View More */}
        <button className="mb-6 self-start rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs font-medium text-[var(--foreground-muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--foreground)]">
          View More
        </button>

        {/* Bottom Nav */}
        <nav className="mt-auto flex flex-col gap-1.5">
          {[
            { label: "Docs", href: "#" },
            { label: "Feedback", href: "#" },
            { label: "Data Storage", href: "#" },
            { label: "Theme", href: "#" },
            { label: "Account", href: "#" },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="flex h-10 items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 text-sm font-semibold tracking-tight text-[var(--foreground-muted)] transition-all duration-150 hover:border-[var(--accent)] hover:text-[var(--foreground)]"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="ml-[240px] min-h-screen px-8 py-8">
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-8 text-2xl font-semibold tracking-tight text-[var(--foreground)]">
            User Settings
          </h1>

          {/* Accordion Sections */}
          <div className="space-y-4">
            {/* Profile Settings - Expanded by default */}
            <ProfileAccordion title="Profile Settings" defaultOpen>
              <ProfileForm initialData={profile} />
            </ProfileAccordion>

            {/* API Tokens - Collapsed placeholder */}
            <ProfileAccordion title="API Tokens">
              <div className="py-4 text-sm text-[var(--foreground-muted)]">
                API token management coming soon.
              </div>
            </ProfileAccordion>

            {/* Rate Limit Increase - Collapsed placeholder */}
            <ProfileAccordion title="Rate Limit Increase">
              <div className="py-4 text-sm text-[var(--foreground-muted)]">
                Rate limit increase requests coming soon.
              </div>
            </ProfileAccordion>

            {/* Privacy & Consent - Collapsed placeholder */}
            <ProfileAccordion title="Privacy & Consent">
              <div className="py-4 text-sm text-[var(--foreground-muted)]">
                Privacy and consent settings coming soon.
              </div>
            </ProfileAccordion>
          </div>
        </div>
      </main>
    </div>
  );
}

