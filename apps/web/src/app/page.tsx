import Link from "next/link";
import { redirect } from "next/navigation";
import { createServerSupabase } from "@/utils/supabase/server";

const particles = [
  { top: "6%", left: "10%", size: 4, duration: 18, delay: 0 },
  { top: "18%", left: "28%", size: 3, duration: 14, delay: 2 },
  { top: "12%", left: "52%", size: 5, duration: 16, delay: 4 },
  { top: "8%", left: "76%", size: 3, duration: 12, delay: 1.5 },
  { top: "24%", left: "64%", size: 4, duration: 19, delay: 3.2 },
  { top: "28%", left: "14%", size: 3, duration: 15, delay: 5 },
  { top: "36%", left: "48%", size: 3, duration: 13, delay: 2.4 },
  { top: "38%", left: "78%", size: 4, duration: 17, delay: 4.4 },
  { top: "52%", left: "20%", size: 5, duration: 20, delay: 1.8 },
  { top: "56%", left: "44%", size: 3, duration: 14, delay: 3.6 },
  { top: "50%", left: "66%", size: 3, duration: 15, delay: 2.1 },
  { top: "64%", left: "82%", size: 4, duration: 18, delay: 5.2 },
  { top: "70%", left: "32%", size: 3, duration: 13, delay: 0.6 },
  { top: "74%", left: "58%", size: 4, duration: 16, delay: 4.9 },
  { top: "82%", left: "22%", size: 3, duration: 15, delay: 1.2 },
  { top: "86%", left: "72%", size: 5, duration: 19, delay: 3.8 },
];

const cardParticles = [
  { top: "8%", left: "12%", size: 6, duration: 14, delay: 0.5 },
  { top: "18%", left: "78%", size: 5, duration: 16, delay: 1.3 },
  { top: "46%", left: "10%", size: 4, duration: 12, delay: 0.9 },
  { top: "58%", left: "86%", size: 6, duration: 15, delay: 1.7 },
  { top: "72%", left: "26%", size: 5, duration: 13, delay: 1.1 },
  { top: "86%", left: "70%", size: 4, duration: 12, delay: 1.9 },
];

type HomeProps = {
  searchParams?: Promise<{
    redirect?: string;
  }>;
};

const miniFeatures = [
  "multi-agent researching and evaluation of architectures",
  "running on fine-tuned Llama 3.1 8B (soon)",
];

export default async function Home({ searchParams }: HomeProps) {
  const supabase = await createServerSupabase();
  const { data } = await supabase.auth.getSession();
  const session = data.session;

  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const redirectParam =
    typeof resolvedSearchParams?.redirect === "string"
      ? resolvedSearchParams.redirect
      : null;
  const safeRedirect =
    redirectParam && redirectParam.startsWith("/") ? redirectParam : null;

  if (session && safeRedirect) {
    redirect(safeRedirect);
  }

  const isAuthed = Boolean(session);
  const ctaHref = isAuthed ? "/chat" : "/login?redirect=/chat";
  const ctaLabel = isAuthed ? "Go to Chat" : "Log in";

  return (
    <div className="landing-shell">
      <div className="landing-particles" aria-hidden="true">
        {particles.map((particle, index) => (
          <span
            key={`${particle.top}-${particle.left}-${index}`}
            className="landing-particle"
            style={{
              top: particle.top,
              left: particle.left,
              width: `${particle.size}px`,
              height: `${particle.size}px`,
              animationDuration: `${particle.duration}s`,
              animationDelay: `${particle.delay}s`,
            }}
          />
        ))}
      </div>

      <header className="landing-nav">
        <div className="landing-brand">
          <span className="brand-mark" />
          <span className="brand-name">Systesign</span>
        </div>
        <div className="landing-nav-actions">
          <a
            href="https://github.com/havryleshko/system-design/tree/main/docs"
            target="_blank"
            rel="noreferrer"
            className="nav-link"
          >
            Docs
          </a>
          <a
            href="https://github.com/havryleshko/system-design"
            target="_blank"
            rel="noreferrer"
            className="nav-link"
          >
            GitHub
          </a>
          <Link href={ctaHref} className="cta-button subtle">
            {isAuthed ? "Go to Chat" : "Log in"}
          </Link>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="landing-copy">
            <p className="eyebrow">Multi-agent system design lab</p>
            <h1>Systesign</h1>
            <p className="lede">
              Systesign is an agentic system for building architectures for
              agentic systems.
            </p>
            <div className="cta-row">
              <Link href={ctaHref} className="cta-button primary">
                {ctaLabel}
                <span className="cta-icon">→</span>
              </Link>
            </div>
            <div className="landing-mini-features">
              {miniFeatures.map((item) => (
                <div key={item} className="mini-feature">
                  <span className="mini-dot" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="landing-card">
            <div className="card-particles" aria-hidden="true">
              {cardParticles.map((particle, idx) => (
                <span
                  key={`${particle.top}-${particle.left}-${idx}`}
                  className="landing-particle card-particle"
                  style={{
                    top: particle.top,
                    left: particle.left,
                    width: `${particle.size}px`,
                    height: `${particle.size}px`,
                    animationDuration: `${particle.duration}s`,
                    animationDelay: `${particle.delay}s`,
                  }}
                />
              ))}
            </div>
            <Link href={ctaHref} className="cta-button primary full">
              {ctaLabel}
              <span className="cta-icon">→</span>
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}