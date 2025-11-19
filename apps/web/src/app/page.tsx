"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { getBrowserSupabase } from "@/utils/supabase/browser";
import type { Session } from "@supabase/supabase-js";

// Live Architecture Visualization Component
function LiveArchitectureViz() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [statusText, setStatusText] = useState("INITIALIZING");

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
      { x: 0.2, y: 0.3, label: "API_GATEWAY", delay: 0, radius: 0 },
      { x: 0.5, y: 0.2, label: "CACHE_LAYER", delay: 800, radius: 0 },
      { x: 0.8, y: 0.3, label: "PRIMARY_DB", delay: 1600, radius: 0 },
      { x: 0.35, y: 0.6, label: "MSG_QUEUE", delay: 2400, radius: 0 },
      { x: 0.65, y: 0.6, label: "WORKER_POOL", delay: 3200, radius: 0 },
    ];

    const connections = [
      { from: 0, to: 1, progress: 0, delay: 1000 },
      { from: 1, to: 2, progress: 0, delay: 1800 },
      { from: 0, to: 3, progress: 0, delay: 2600 },
      { from: 3, to: 4, progress: 0, delay: 3400 },
      { from: 4, to: 2, progress: 0, delay: 4200 },
    ];

    let startTime = Date.now();
    const maxRadius = 6;

    function animate() {
      if (!canvas || !ctx) return;
      const elapsed = Date.now() - startTime;
      const rect = canvas.getBoundingClientRect();

      ctx.clearRect(0, 0, rect.width, rect.height);

      // Update status based on elapsed time
      if (elapsed < 800) setStatusText("PLANNING_TOPOLOGY");
      else if (elapsed < 2400) setStatusText("OPTIMIZING_DATA_FLOW");
      else if (elapsed < 4000) setStatusText("SCALING_WORKERS");
      else if (elapsed < 5000) setStatusText("VALIDATING_ARCH");

      // Draw grid overlay
      ctx.strokeStyle = "rgba(198, 180, 255, 0.05)";
      ctx.lineWidth = 1;
      const gridSize = 40;
      
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

            // Connection line
            ctx.strokeStyle = `rgba(198, 180, 255, ${0.4 * conn.progress})`;
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(currentX, currentY);
            ctx.stroke();
            ctx.setLineDash([]);

            // Moving packet
            if (conn.progress === 1) {
                const packetProgress = (Date.now() / 1000) % 1;
                const packetX = fromX + (toX - fromX) * packetProgress;
                const packetY = fromY + (toY - fromY) * packetProgress;
                
                ctx.fillStyle = "#E0D8FF";
                ctx.beginPath();
                ctx.arc(packetX, packetY, 2, 0, Math.PI * 2);
                ctx.fill();
            }
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

          // Node marker
          ctx.fillStyle = "#111319";
          ctx.strokeStyle = "#C6B4FF";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.rect(x - node.radius, y - node.radius, node.radius * 2, node.radius * 2);
          ctx.fill();
          ctx.stroke();

          // Tech decoration
          if (node.radius >= maxRadius * 0.8) {
             // Crosshair
             ctx.strokeStyle = "rgba(198, 180, 255, 0.5)";
             ctx.beginPath();
             ctx.moveTo(x - 10, y);
             ctx.lineTo(x + 10, y);
             ctx.moveTo(x, y - 10);
             ctx.lineTo(x, y + 10);
             ctx.stroke();

             // Label
            ctx.fillStyle = "rgba(224, 216, 255, 0.8)";
            ctx.font = "10px 'Space Mono', monospace";
            ctx.textAlign = "left";
            ctx.textBaseline = "bottom";
            ctx.fillText(node.label, x + 12, y - 4);
            
            // Coordinates
            ctx.fillStyle = "rgba(198, 180, 255, 0.4)";
            ctx.font = "9px 'Space Mono', monospace";
            ctx.fillText(`[${Math.round(x)},${Math.round(y)}]`, x + 12, y + 8);
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
    <div className="relative w-full h-full rounded border border-white/10 bg-black/20 overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full grid-background opacity-50 pointer-events-none" />
        <div className="absolute top-4 left-4 font-mono text-[10px] text-[#C6B4FF] tracking-wider">
            <span className="opacity-50">SYS.STATUS // </span>
            <span className="text-[#E0D8FF]">{statusText}</span>
        </div>
        <div className="absolute top-4 right-4 font-mono text-[10px] text-white/30">
            V.2.0.4
        </div>
        <div className="scanner-line" />
        <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ mixBlendMode: "screen" }}
        />
    </div>
  );
}

// Interactive Blueprint Component
function InteractiveBlueprint({ title, components }: { title: string; components: Array<{ name: string; sub: string[] }> }) {
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

    return (
        <div className="glass-panel corner-bracket p-6 h-full group transition-colors duration-500 hover:border-[#C6B4FF]/40">
            <div className="flex justify-between items-start mb-6 border-b border-white/5 pb-4">
                <h4 className="text-lg font-bold tracking-tight" style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}>
                    {title}
                </h4>
                <div className="font-mono text-[10px] text-[#C6B4FF]/50 border border-[#C6B4FF]/20 px-2 py-0.5 rounded">
                    ARCH.REF_0{Math.floor(Math.random() * 9) + 1}
                </div>
            </div>
            
            <div className="space-y-4">
                {components.map((comp, idx) => (
                    <div 
                        key={idx}
                        className={`relative pl-4 border-l transition-all duration-300 ${
                            hoveredIndex === idx 
                                ? "border-[#C6B4FF] bg-white/5" 
                                : "border-white/10 hover:border-white/30"
                        }`}
                        onMouseEnter={() => setHoveredIndex(idx)}
                        onMouseLeave={() => setHoveredIndex(null)}
                    >
                        <div className={`text-xs font-mono mb-1 transition-colors ${
                            hoveredIndex === idx ? "text-[#E0D8FF]" : "text-[#C6B4FF]"
                        }`}>
                            0{idx + 1} // {comp.name}
                        </div>
                        <div className={`text-[11px] transition-colors ${
                            hoveredIndex === idx ? "text-white/80" : "text-white/40"
                        }`}>
                            {comp.sub.join(" + ")}
                        </div>
                    </div>
                ))}
            </div>
            
            {/* Technical decorations */}
            <div className="absolute bottom-2 right-2 w-2 h-2 border-b border-r border-[#C6B4FF]/30" />
            <div className="absolute bottom-2 left-2 font-mono text-[9px] text-white/20">
                SECURE_HASH: {Math.random().toString(36).substring(7).toUpperCase()}
            </div>
        </div>
    )
}

// Feature Card Component
function FeatureCard({
  index,
  title,
  description,
  icon,
}: {
  index: string;
  title: string;
  description: string;
  icon: string;
}) {
  return (
    <div
      className="glass-panel corner-bracket rounded-sm p-8 transition-all duration-300 hover:-translate-y-1 group"
    >
      <div className="flex justify-between items-start mb-6">
          <div className="text-4xl opacity-80 group-hover:opacity-100 transition-opacity group-hover:scale-110 duration-300 transform origin-left">{icon}</div>
          <div className="font-mono text-xs text-[#C6B4FF]/40">
              {index}
          </div>
      </div>
      
      <h3
        className="text-xl font-bold mb-3 tracking-tight"
        style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
      >
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-[#C6B4FF]/80 font-light">
        {description}
      </p>
    </div>
  );
}

// Typing text hook
function useTypewriter(text: string, speed = 30) {
    const [displayedText, setDisplayText] = useState("");
    
    useEffect(() => {
        let i = 0;
        const timer = setInterval(() => {
            if (i < text.length) {
                setDisplayText(text.substring(0, i + 1));
                i++;
            } else {
                clearInterval(timer);
            }
        }, speed);
        return () => clearInterval(timer);
    }, [text, speed]);
    
    return displayedText;
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
  
  const subheadline = useTypewriter("Multi-agent system for researching and architecting systems", 20);

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
      className="relative min-h-screen text-white overflow-x-hidden selection:bg-[#3E2B73] selection:text-[#E0D8FF]"
      style={{
        background:
          "linear-gradient(135deg, #111319 0%, #1A1D26 100%)",
      }}
    >
      <div className="absolute inset-0 grid-background opacity-30 pointer-events-none fixed" />
      
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
        <div className="max-w-6xl mx-auto text-center relative z-10 w-full">
          
          {/* Top label */}
          <div className="inline-block mb-6 border border-[#C6B4FF]/20 bg-[#C6B4FF]/5 px-3 py-1 rounded-full backdrop-blur-sm">
              <span className="font-mono text-[10px] tracking-widest text-[#C6B4FF] uppercase">
                  AI-Powered Architecture • V1.0
              </span>
          </div>

          {/* Live Architecture Visualization */}
          <div className="relative w-full max-w-3xl mx-auto mb-16 h-64 hidden md:block shadow-2xl shadow-purple-900/10">
            <LiveArchitectureViz />
          </div>

          <h1
            className="text-5xl md:text-7xl font-bold mb-8 leading-tight tracking-tight"
            style={{
              fontFamily: "var(--font-space-grotesk)",
            }}
          >
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#E0D8FF] via-[#C6B4FF] to-[#E0D8FF]">
                System Design Agent
            </span>
            <br />
            <span className="text-3xl md:text-4xl text-[#C6B4FF]/60 font-light block mt-4">
                for autonomous AI architectures
            </span>
          </h1>

          <div className="h-8 mb-12">
            <p
                className="text-sm font-mono max-w-3xl mx-auto typing-cursor"
                style={{ color: "#C6B4FF" }}
            >
                {subheadline}
            </p>
          </div>

          <button
            onClick={handleCTA}
            disabled={isLoading}
            className="group relative px-8 py-4 text-sm font-mono font-bold uppercase tracking-widest transition-all duration-300 overflow-hidden"
            style={{
              background: "rgba(62, 43, 115, 0.4)",
              border: "1px solid rgba(198, 180, 255, 0.3)",
              color: "#E0D8FF",
            }}
          >
            <div className="absolute inset-0 w-full h-full bg-[#C6B4FF]/10 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
            <span className="relative z-10">
                {isLoading ? "Loading..." : session ? "Initialize Session" : "Start Research"}
            </span>
          </button>
        </div>
      </section>

      {/* Features Section */}
      <section
        id="features"
        className={`relative py-32 px-6 transition-all duration-1000 ${
          sectionsVisible.features
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-6xl mx-auto">
          <div className="flex items-end gap-4 mb-16 border-b border-white/5 pb-4">
              <span className="font-mono text-4xl font-light text-[#C6B4FF]/20">01</span>
              <h2
                className="text-2xl font-bold tracking-tight mb-1"
                style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
              >
                Core Capabilities
              </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              index="MOD.01"
              icon="🎯"
              title="Autonomous Planning"
              description="Agent intelligently breaks down your requirements and determines the optimal research and design strategy based on current best practices."
            />
            <FeatureCard
              index="MOD.02"
              icon="🔍"
              title="Deep Research"
              description="Automatically researches architectural patterns, performs competitive analysis, and validates decisions against real-world constraints."
            />
            <FeatureCard
              index="MOD.03"
              icon="🔄"
              title="Iterative Logic"
              description="Built-in critic feedback loop validates and improves designs through multiple generations until quality metrics are satisfied."
            />
          </div>
        </div>
      </section>

      {/* How It Works Flow */}
      <section
        id="howItWorks"
        className={`relative py-32 px-6 bg-white/[0.02] transition-all duration-1000 ${
          sectionsVisible.howItWorks
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-5xl mx-auto">
          <div className="flex items-end justify-center gap-4 mb-20">
              <span className="font-mono text-xs text-[#C6B4FF]/40 tracking-[0.2em]">WORKFLOW_SEQUENCE</span>
          </div>

          <div className="flex flex-col md:flex-row items-start justify-between gap-12 relative">
            {/* Connection Line */}
            <div className="absolute top-8 left-0 w-full h-px bg-gradient-to-r from-transparent via-[#C6B4FF]/20 to-transparent hidden md:block" />

            {/* Step 1 */}
            <div className="flex-1 relative z-10 group">
              <div
                className="w-16 h-16 bg-[#111319] border border-[#C6B4FF]/30 mx-auto mb-8 flex items-center justify-center font-mono text-xl transition-colors group-hover:border-[#C6B4FF]"
                style={{ color: "#E0D8FF" }}
              >
                01
              </div>
              <h3 className="text-lg font-bold text-center mb-2 text-[#E0D8FF]">Input Parameters</h3>
              <p className="text-xs text-center font-mono text-[#C6B4FF]/60 uppercase tracking-wide">
                Define Constraints
              </p>
            </div>

            {/* Step 2 */}
            <div className="flex-1 relative z-10 group">
              <div
                className="w-16 h-16 bg-[#111319] border border-[#C6B4FF]/30 mx-auto mb-8 flex items-center justify-center font-mono text-xl transition-colors group-hover:border-[#C6B4FF]"
                style={{ color: "#E0D8FF" }}
              >
                02
              </div>
              <h3 className="text-lg font-bold text-center mb-2 text-[#E0D8FF]">Processing</h3>
              <p className="text-xs text-center font-mono text-[#C6B4FF]/60 uppercase tracking-wide">
                Analysis & Design
              </p>
            </div>

            {/* Step 3 */}
            <div className="flex-1 relative z-10 group">
              <div
                className="w-16 h-16 bg-[#111319] border border-[#C6B4FF]/30 mx-auto mb-8 flex items-center justify-center font-mono text-xl transition-colors group-hover:border-[#C6B4FF]"
                style={{ color: "#E0D8FF" }}
              >
                03
              </div>
              <h3 className="text-lg font-bold text-center mb-2 text-[#E0D8FF]">Output</h3>
              <p className="text-xs text-center font-mono text-[#C6B4FF]/60 uppercase tracking-wide">
                Architecture JSON
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Example Outputs */}
      <section
        id="examples"
        className={`relative py-32 px-6 transition-all duration-1000 ${
          sectionsVisible.examples
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-10"
        }`}
      >
        <div className="max-w-6xl mx-auto">
          <div className="flex items-end gap-4 mb-16 border-b border-white/5 pb-4">
              <span className="font-mono text-4xl font-light text-[#C6B4FF]/20">02</span>
              <h2
                className="text-2xl font-bold tracking-tight mb-1"
                style={{ fontFamily: "var(--font-space-grotesk)", color: "#E0D8FF" }}
              >
                Generated Architectures
              </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto h-96">
            {/* Example 1 */}
            <InteractiveBlueprint 
                title="Real-time Chat System" 
                components={[
                    { name: "Edge Layer", sub: ["Global CDN", "WAF", "DDoS Protection"] },
                    { name: "Access Gateway", sub: ["WebSocket Clusters", "Auth Service", "Rate Limiter"] },
                    { name: "Message Broker", sub: ["Redis Pub/Sub", "Kafka Streams"] },
                    { name: "Persistence", sub: ["ScyllaDB (Messages)", "PostgreSQL (Users)"] }
                ]}
            />

            {/* Example 2 */}
            <InteractiveBlueprint 
                title="ML Inference Platform" 
                components={[
                    { name: "Ingestion", sub: ["API Gateway", "Request Validator"] },
                    { name: "Orchestration", sub: ["Kubernetes Control Plane", "Job Queue"] },
                    { name: "Compute Layer", sub: ["GPU Nodes", "Model Registry"] },
                    { name: "Vector Store", sub: ["Pinecone / Weaviate", "Embeddings Cache"] }
                ]}
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative py-12 px-6 border-t border-white/5 bg-[#111319]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
            <div className="flex flex-col gap-2">
                <div className="font-mono text-xs text-[#C6B4FF] tracking-widest">SYSTESIGN.AI</div>
                <div className="text-[10px] text-white/30">
                    © 2025 • SYSTEM DESIGN AGENT
                </div>
            </div>

            <div className="flex items-center gap-6">
                <div className="flex items-center gap-2 px-3 py-1 bg-white/5 border border-white/10 rounded-full">
                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    <span className="font-mono text-[10px] text-white/60 uppercase">Systems Operational</span>
                </div>
            </div>
            
            <div className="flex gap-8 text-xs font-mono text-[#C6B4FF]/60">
                <button onClick={() => router.push("/login")} className="hover:text-[#E0D8FF] transition-colors">ACCESS_TERMINAL</button>
                <button onClick={() => router.push("/login")} className="hover:text-[#E0D8FF] transition-colors">INIT_ACCOUNT</button>
            </div>
        </div>
      </footer>
    </div>
  );
}
