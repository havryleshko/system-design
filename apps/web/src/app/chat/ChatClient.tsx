"use client"

import { useState, useTransition } from "react"
import { fetchTrace, startRunWait } from "../actions"
import ArchitecturePanel, { type DesignJson } from "./ArchitecturePanel"
import TracePanel from "./TracePanel"

type TraceEvent = {
    ts_ms: number
    level: 'info' | 'warn' | 'error'
    message: string
    data?: Record<string, unknown> | null
}

type RunTrace = {
    id: string
    events: TraceEvent[]
}

type ChatMessage = {
    role: 'user' | 'assistant' | 'system'
    content: string
}

type ChatClientProps = {
  initialMessages: ChatMessage[]
  runId: string | null
  userId?: string | null
  designJson?: DesignJson | null
}

export default function ChatClient({
  initialMessages,
  runId,
  designJson,
}: ChatClientProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [input, setInput] = useState("")
  const [trace, setTrace] = useState<RunTrace | null>(null)
  const [traceError, setTraceError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const [currentRunId, setCurrentRunId] = useState<string | null>(runId)
  const [architecture, setArchitecture] = useState<DesignJson | null>(designJson ?? null)

  function getValuesFromStateLike(input: unknown): Record<string, unknown> | null {
    if (typeof input !== "object" || input === null) return null
    const rec = input as Record<string, unknown>
    const values = rec.values
    if (typeof values === "object" && values !== null) return values as Record<string, unknown>
    return null
  }

  const loadTrace = () => {
    if (!currentRunId) {
      setTraceError("Run ID not available yet")
      return
    }
    if (trace || isPending) return
    startTransition(async () => {
      try {
        const data = await fetchTrace(currentRunId)
        setTrace(data)
        setTraceError(null)
      } catch (err) {
        setTrace(null)
        setTraceError(err instanceof Error ? err.message : "Failed to load trace")
      }
    })
  }

  const refreshTrace = () => {
    if (!currentRunId) return
    startTransition(async () => {
      try {
        const data = await fetchTrace(currentRunId)
        setTrace(data)
        setTraceError(null)
      } catch (err) {
        setTrace(null)
        setTraceError(err instanceof Error ? err.message : "Failed to load trace")
      }
    })
  }

  async function send() {
    const trimmed = input.trim()
    if (!trimmed) return

    const userMessage: ChatMessage = { role: "user", content: trimmed }
    setMessages((prev) => [...prev, userMessage])
    setInput("")

    try {
      const { runId: newRunId, state } = await startRunWait(trimmed)
      const values = getValuesFromStateLike(state)
      const arch = (values?.["architecture_json"] || values?.["design_json"]) as unknown
      if (arch && typeof arch === "object") setArchitecture(arch as DesignJson)
      const outVal = values?.["output"]
      const output = typeof outVal === "string" ? outVal : null
      if (output && output.trim().length > 0) {
        setMessages((prev) => [...prev, { role: "assistant", content: output }])
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "Run completed." }])
      }
      if (newRunId) {
        setCurrentRunId(newRunId)
        setTrace(null)
        startTransition(async () => {
          try {
            const data = await fetchTrace(newRunId)
            setTrace(data)
            setTraceError(null)
          } catch (err) {
            setTrace(null)
            setTraceError(err instanceof Error ? err.message : "Failed to load trace")
          }
        })
      }
    } catch (err) {
      console.error("Run failed", err)
      const message = err instanceof Error ? err.message : "Unknown error"
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Sorry, something went wrong: ${message}` },
      ])
    }
  }

  return (
    <div className="h-screen bg-black text-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-3">
        <div>
          <h2 className="text-base font-semibold tracking-wide">System Design Assistant</h2>
          <p className="text-[11px] uppercase text-white/40">Three-panel workspace</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="rounded border border-white px-3 py-1.5 text-[11px] uppercase tracking-wide text-white transition hover:bg-white hover:text-black"
            onClick={async () => {
              const res = await fetch("/api/stripe/checkout", { method: "POST" })
              if (!res.ok) {
                console.error("Checkout failed", res.status)
                return
              }
              const data = await res.json()
              if (data?.url) {
                window.location.href = data.url as string
              }
            }}
          >
            Upgrade to Pro
          </button>
        </div>
      </div>

      {/* 3-panel layout */}
      <div className="grid h-[calc(100vh-49px)] grid-cols-12">
        {/* Left: Architecture */}
        <div className="col-span-3 min-w-0 border-r border-white/10">
          <ArchitecturePanel designJson={architecture ?? null} />
        </div>

        {/* Center: Chat */}
        <div className="col-span-6 flex min-w-0 flex-col">
          <div className="flex-1 overflow-hidden">
            <div className="flex h-full flex-col gap-3 overflow-y-auto p-5">
              {messages.length === 0 ? (
                <p className="text-sm text-white/40">
                  No messages yet. Ask the assistant anything about system design.
                </p>
              ) : (
                messages.map((m, i) => (
                  <div key={i} className="space-y-1 border border-white/15 bg-white/5 px-4 py-3">
                    <div className="text-xs uppercase tracking-wide text-white/40">{m.role}</div>
                    <div className="text-sm leading-relaxed text-white">{m.content}</div>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="flex items-center gap-3 border-t border-white/10 bg-black/60 px-4 py-3">
            <input
              className="flex-1 bg-transparent text-sm text-white placeholder:text-white/40 focus:outline-none"
              placeholder="Type your message"
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              className="border border-white px-4 py-2 text-sm uppercase tracking-wide text-white transition hover:bg-white hover:text-black"
              onClick={send}
            >
              Send
            </button>
          </div>
        </div>

        {/* Right: Trace */}
        <div className="col-span-3 min-w-0 border-l border-white/10">
          <TracePanel
            trace={trace}
            isLoading={isPending && !trace}
            error={traceError}
            onRefresh={() => (trace ? refreshTrace() : loadTrace())}
          />
        </div>
      </div>
    </div>
  )
}



