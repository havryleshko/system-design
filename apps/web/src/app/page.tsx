"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { getBrowserSupabase } from "@/utils/supabase/browser";
import type { Session } from "@supabase/supabase-js";

// Live Architecture Visualization Component
function LiveArchitectureViz() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const updateSize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };
    updateSize();
    window.addEventListener("resize", updateSize);

    // Architecture nodes that build over time
    const nodes = [
      { x: 0.2, y: 0.3, label: "API", delay: 0, radius: 0 },
      { x: 0.5, y: 0.2, label: "Cache", delay: 800, radius: 0 },
      { x: 0.8, y: 0.3, label: "DB", delay: 1600, radius: 0 },
      { x: 0.35, y: 0.6, label: "Queue", delay: 2400, radius: 0 },
      { x: 0.65, y: 0.6, label: "Worker", delay: 3200, radius: 0 },
    ];

    const connections = [
      { from: 0, to: 1, progress: 0, delay: 1000 },
      { from: 1, to: 2, progress: 0, delay: 1800 },
      { from: 0, to: 3, progress: 0, delay: 2600 },
      { from: 3, to: 4, progress: 0, delay: 3400 },
      { from: 4, to: 2, progress: 0, delay: 4200 },
    ];

    let startTime = Date.now();
    const maxRadius = 20;

    function animate() {
      if (!canvas || !ctx) return;
      const elapsed = Date.now() - startTime;
      const rect = canvas.getBoundingClientRect();

      ctx.clearRect(0, 0, rect.width, rect.height);

      // Draw connections
      connections.forEach((conn) => {
        if (elapsed > conn.delay) {
          const timeSinceStart = elapsed - conn.delay;
          conn.progress = Math.min(timeSinceStart / 500, 1);

          const from = nodes[conn.from];
          const to = nodes[conn.to];

          if (from.radius > 0 && to.radius > 0) {
            const fromX = from.x * rect.width;
            const fromY = from.y * rect.height;
            const toX = to.x * rect.width;
            const toY = to.y * rect.height;

            const currentX = fromX + (toX - fromX) * conn.progress;
            const currentY = fromY + (toY - fromY) * conn.progress;

            ctx.strokeStyle = `rgba(198, 180, 255, ${0.3 * conn.progress})`;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(currentX, currentY);
            ctx.stroke();
          }
        }
      });

      // Draw nodes
      nodes.forEach((node) => {
        if (elapsed > node.delay) {
          const timeSinceStart = elapsed - node.delay;
          node.radius = Math.min((timeSinceStart / 400) * maxRadius, maxRadius);

          const x = node.x * rect.width;
          const y = node.y * rect.height;

          // Node circle
          ctx.fillStyle = "rgba(62, 43, 115, 0.6)";
          ctx.strokeStyle = "rgba(198, 180, 255, 0.8)";
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(x, y, node.radius, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();

          // Node label
          if (node.radius >= maxRadius * 0.8) {
            ctx.fillStyle = "#E0D8FF";
            ctx.font = "11px var(--font-space-grotesk)";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(node.label, x, y);
          }
        }
      });

      // Loop animation
      if (elapsed < 5000) {
        requestAnimationFrame(animate);
      } else {
        // Reset and restart
        nodes.forEach((n) => (n.radius = 0));
        connections.forEach((c) => (c.progress = 0));
        setTimeout(() => {
          startTime = Date.now();
          animate();
        }, 2000);
      }
    }

    animate();

    return () => {
      window.removeEventListener("resize", updateSize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full opacity-40"
      style={{ mixBlendMode: "screen" }}
    />
  );
}

// Feature Card Component
function FeatureCard({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: string;
}) {
  return (
    <div
      className="glass-panel rounded-lg p-8 transition-all duration-300 hover:scale-105 hover:shadow-2xl"
      style={{
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.3)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow =
          "0 8px 40px rgba(198, 180, 255, 0.3)";
        e.currentTarget.style.borderColor = "rgba(198, 180, 255, 0.4)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "0 4px 20px rgba(0, 0, 0, 0.3)";
        e.currentTarget.style.borderColor = "rgba(198, 180, 255, 0.15)";
      }}
    >
      {icon && <div className="text-4xl mb-4">{icon}</div>}
      <h3
        className="text-xl font-semibold mb-3"
        style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
      >
        {title}
      </h3>
      <p className="text-sm leading-relaxed" style={{ color: "#C6B4FF" }}>
        {description}
      </p>
    </div>
  );
}

export default function Home() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sectionsVisible, setSectionsVisible] = useState({
    features: false,
    howItWorks: false,
    examples: false,
  });

  useEffect(() => {
    const supabase = getBrowserSupabase();

    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setIsLoading(false);
    });

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Intersection observer for scroll animations
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.id;
            setSectionsVisible((prev) => ({ ...prev, [id]: true }));
          }
        });
      },
      { threshold: 0.1 }
    );

    const sections = ["features", "howItWorks", "examples"];
    sections.forEach((id) => {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    });

    return () => observer.disconnect();
  }, []);

  const handleCTA = () => {
    if (session) {
      router.push("/chat");
    } else {
      router.push("/login?redirect=/chat");
    }
  };

  return (
    <div
      className="relative min-h-screen text-white overflow-x-hidden"
      style={{
        background:
          "linear-gradient(135deg, #111319 0%, #3E2B73 50%, #C6B4FF 100%)",
      }}
    >
      {/* Particle Background */}
      <div className="particle-background">
        <div className="particle" style={{ top: "10%", left: "15%" }}></div>
        <div className="particle"></div>
        <div className="particle"></div>
        <div className="particle"></div>
        <div className="particle"></div>
      </div>

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-6 py-20">
        <div className="max-w-6xl mx-auto text-center relative z-10">
          {/* Live Architecture Visualization */}
          <div className="relative w-full max-w-2xl mx-auto mb-12 h-64 hidden md:block">
            <LiveArchitectureViz />
          </div>

          <h1
            className="text-5xl md:text-7xl font-bold mb-6 leading-tight"
            style={{
              fontFamily: "var(--font-space-grotesk)",
              background:
                "linear-gradient(135deg, #E0D8FF 0%, #C6B4FF 50%, #E0D8FF 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            System Design Agent
            <br />
            for building AI architectures
          </h1>

          <p
            className="text-xl md:text-2xl mb-12 max-w-3xl mx-auto leading-relaxed"
            style={{ color: "rgba(198, 180, 255, 0.8)" }}
          >
            Multi-agent system for researching and architecting systems
          </p>

          <button
            onClick={handleCTA}
            disabled={isLoading}
            className="px-10 py-4 text-lg font-semibold uppercase tracking-wider transition-all duration-300 rounded-lg"
            style={{
              background:
                "linear-gradient(135deg, rgba(62, 43, 115, 0.8), rgba(198, 180, 255, 0.3))",
              border: "2px solid rgba(198, 180, 255, 0.5)",
              color: "#E0D8FF",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background =
                "linear-gradient(135deg, rgba(62, 43, 115, 1), rgba(198, 180, 255, 0.5))";
              e.currentTarget.style.boxShadow =
                "0 0 30px rgba(198, 180, 255, 0.5)";
              e.currentTarget.style.transform = "translateY(-2px)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background =
                "linear-gradient(135deg, rgba(62, 43, 115, 0.8), rgba(198, 180, 255, 0.3))";
              e.currentTarget.style.boxShadow = "none";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            {isLoading ? "Loading..." : session ? "Go to Chat" : "Get Started"}
          </button>
        </div>
      </section>

      {/* Features Section */}
      <section
        id="features"
        className={`relative py-24 px-6 transition-all duration-1000 ${
          sectionsVisible.features
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
        style={{
          background: "rgba(17, 19, 25, 0.6)",
          backdropFilter: "blur(20px)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <h2
            className="text-3xl md:text-5xl font-bold text-center mb-16"
            style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
          >
            How it works
          </h2>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon=""
              title="Autonomous Planning"
              description="Agent intelligently breaks down your requirements and determines the optimal research and design strategy."
            />
            <FeatureCard
              icon=""
              title="Knowledge & Web Search"
              description="Automatically researches best practices, architectural patterns, and current technologies from knowledge bases and the web."
            />
            <FeatureCard
              icon=""
              title="Iterative Refinement"
              description="Built-in critic validates and improves designs through multiple iterations until quality targets are met."
            />
          </div>
        </div>
      </section>

      {/* How It Works Flow */}
      <section
        id="howItWorks"
        className={`relative py-24 px-6 transition-all duration-1000 ${
          sectionsVisible.howItWorks
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-5xl mx-auto">
          <h2
            className="text-3xl md:text-5xl font-bold text-center mb-20"
            style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
          >
            Simple workflow
          </h2>

          <div className="flex flex-col md:flex-row items-center justify-between gap-8">
            {/* Step 1 */}
            <div className="flex-1 text-center">
              <div
                className="w-20 h-20 rounded-full mx-auto mb-6 flex items-center justify-center text-2xl font-bold"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(62, 43, 115, 0.8), rgba(198, 180, 255, 0.3))",
                  border: "2px solid rgba(198, 180, 255, 0.5)",
                  color: "#E0D8FF",
                }}
              >
                1
              </div>
              <h3
                className="text-xl font-semibold mb-3"
                style={{
                  fontFamily: "var(--font-space-grotesk)",
                  color: "#E0D8FF",
                }}
              >
                Describe
              </h3>
              <p className="text-sm" style={{ color: "rgba(198, 180, 255, 0.7)" }}>
                Share your system requirements and constraints
              </p>
            </div>

            {/* Arrow */}
            <div className="hidden md:block text-4xl" style={{ color: "#C6B4FF" }}>
              →
            </div>

            {/* Step 2 */}
            <div className="flex-1 text-center">
              <div
                className="w-20 h-20 rounded-full mx-auto mb-6 flex items-center justify-center text-2xl font-bold"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(62, 43, 115, 0.8), rgba(198, 180, 255, 0.3))",
                  border: "2px solid rgba(198, 180, 255, 0.5)",
                  color: "#E0D8FF",
                }}
              >
                2
              </div>
              <h3
                className="text-xl font-semibold mb-3"
                style={{
                  fontFamily: "var(--font-space-grotesk)",
                  color: "#E0D8FF",
                }}
              >
                Agent Works
              </h3>
              <p className="text-sm" style={{ color: "rgba(198, 180, 255, 0.7)" }}>
                AI plans, researches, and designs your architecture
              </p>
            </div>

            {/* Arrow */}
            <div className="hidden md:block text-4xl" style={{ color: "#C6B4FF" }}>
              →
            </div>

            {/* Step 3 */}
            <div className="flex-1 text-center">
              <div
                className="w-20 h-20 rounded-full mx-auto mb-6 flex items-center justify-center text-2xl font-bold"
                style={{
                  background:
                    "linear-gradient(135deg, rgba(62, 43, 115, 0.8), rgba(198, 180, 255, 0.3))",
                  border: "2px solid rgba(198, 180, 255, 0.5)",
                  color: "#E0D8FF",
                }}
              >
                3
              </div>
              <h3
                className="text-xl font-semibold mb-3"
                style={{
                  fontFamily: "var(--font-space-grotesk)",
                  color: "#E0D8FF",
                }}
              >
                Review
              </h3>
              <p className="text-sm" style={{ color: "rgba(198, 180, 255, 0.7)" }}>
                Get detailed architecture with explanations
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Example Outputs */}
      <section
        id="examples"
        className={`relative py-24 px-6 transition-all duration-1000 ${
          sectionsVisible.examples
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
        style={{
          background: "rgba(17, 19, 25, 0.6)",
          backdropFilter: "blur(20px)",
        }}
      >
        <div className="max-w-6xl mx-auto">
          <h2
            className="text-3xl md:text-5xl font-bold text-center mb-16"
            style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
          >
            Example architectures
          </h2>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            {/* Example 1 */}
            <div className="glass-panel rounded-lg p-6">
              <h4
                className="text-lg font-semibold mb-4"
                style={{
                  fontFamily: "var(--font-space-grotesk)",
                  color: "#E0D8FF",
                }}
              >
                Real-time Chat Application
              </h4>
              <div
                className="bg-black/30 rounded p-4 text-xs font-mono"
                style={{ color: "#C6B4FF" }}
              >
                <div className="mb-2">→ WebSocket Gateway</div>
                <div className="mb-2 ml-4">→ Redis Pub/Sub</div>
                <div className="mb-2 ml-4">→ Message Queue</div>
                <div className="mb-2 ml-8">→ PostgreSQL</div>
                <div className="ml-8">→ S3 Media Storage</div>
              </div>
            </div>

            {/* Example 2 */}
            <div className="glass-panel rounded-lg p-6">
              <h4
                className="text-lg font-semibold mb-4"
                style={{
                  fontFamily: "var(--font-space-grotesk)",
                  color: "#E0D8FF",
                }}
              >
                AI Model Serving Platform
              </h4>
              <div
                className="bg-black/30 rounded p-4 text-xs font-mono"
                style={{ color: "#C6B4FF" }}
              >
                <div className="mb-2">→ API Gateway + Load Balancer</div>
                <div className="mb-2 ml-4">→ Model Registry</div>
                <div className="mb-2 ml-4">→ Inference Workers</div>
                <div className="mb-2 ml-8">→ GPU Cluster</div>
                <div className="ml-8">→ Vector Database</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative py-12 px-6 text-center border-t" style={{ borderColor: "rgba(198, 180, 255, 0.15)" }}>
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <span
                className="text-xs px-3 py-1 rounded-full"
                style={{
                  background: "rgba(198, 180, 255, 0.2)",
                  border: "1px solid rgba(198, 180, 255, 0.3)",
                  color: "#C6B4FF",
                }}
              >
                Beta
              </span>
              <span className="text-sm" style={{ color: "rgba(198, 180, 255, 0.6)" }}>
                In Development
              </span>
            </div>

            <div className="flex gap-6">
              <button
                onClick={() => router.push("/login")}
                className="text-sm transition-colors duration-200"
                style={{ color: "rgba(198, 180, 255, 0.8)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#E0D8FF";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "rgba(198, 180, 255, 0.8)";
                }}
              >
                Login
              </button>
              <button
                onClick={() => router.push("/login")}
                className="text-sm transition-colors duration-200"
                style={{ color: "rgba(198, 180, 255, 0.8)" }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#E0D8FF";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "rgba(198, 180, 255, 0.8)";
                }}
              >
                Sign Up
              </button>
            </div>
          </div>

          <div className="mt-8 text-xs" style={{ color: "rgba(198, 180, 255, 0.4)" }}>
            © 2025 Systesign. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
