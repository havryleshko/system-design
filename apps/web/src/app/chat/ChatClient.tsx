"use client"

import { useRef, useState, useTransition } from "react"
import { fetchTrace, startRunStream } from "../actions"
import ArchitecturePanel, { type DesignJson } from "./ArchitecturePanel"
import TracePanel from "./TracePanel"
import { openRunStream, type NormalizedStreamEvent } from "./useRunStream"
import ClarifierCard from "./ClarifierCard"
import NodeStatusRibbon from "./NodeStatusRibbon"

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
  const [streamingContent, setStreamingContent] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const streamHandleRef = useRef<{ close: () => void } | null>(null)
  const [clarifier, setClarifier] = useState<{ question: string; fields: string[] } | null>(null)
  const [nodeStatuses, setNodeStatuses] = useState<Array<{ name: string; status: 'idle' | 'running' | 'done' }>>([])

  console.log('[chat] render', messages.length)

  const extractContent = (value: unknown): string => {
    if (!value) return ""
    if (typeof value === "string") return value
    if (Array.isArray(value)) {
      return value
        .map((part) => {
          if (typeof part === "string") return part
          if (part && typeof part === "object") {
            const segment = part as Record<string, unknown>
            if (typeof segment.text === "string") return segment.text
            if (typeof segment.content === "string") return segment.content
          }
          return ""
        })
        .filter(Boolean)
        .join("\n")
    }
    if (value && typeof value === "object") {
      const record = value as Record<string, unknown>
      if (typeof record.text === "string") return record.text
      if (typeof record.content === "string") return record.content
    }
    return ""
  }

  const normalizeMessages = (raw: unknown): ChatMessage[] | null => {
    if (!Array.isArray(raw)) return null
    const normalized: ChatMessage[] = []
    for (const entry of raw) {
      if (!entry || typeof entry !== "object") continue
      const record = entry as Record<string, unknown>
      const rawRole = typeof record.role === "string" ? record.role.toLowerCase() : undefined
      const rawType = typeof record.type === "string" ? record.type.toLowerCase() : undefined
      let role: ChatMessage["role"] = "assistant"
      if (rawRole === "assistant" || rawRole === "user" || rawRole === "system") role = rawRole
      else if (rawType === "ai") role = "assistant"
      else if (rawType === "human") role = "user"
      const content = extractContent(record.content).trim()
      if (content) normalized.push({ role, content })
    }
    return normalized
  }

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
      const result = await startRunStream(trimmed)
      if (!result.ok) {
        const errorMessage = result.error || 'Run failed'
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: `Sorry, something went wrong: ${errorMessage}` },
        ])
        return
      }
      if (!result.runId) {
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: 'Run created but no run ID was returned' },
        ])
        return
      }
      const { runId: newRunId } = result
      setCurrentRunId(newRunId)
      setStreamingContent("")
      streamingContentRef.current = ""
      setIsStreaming(true)
      setClarifier(null)
      setNodeStatuses([])

      if (streamHandleRef.current) {
        try { streamHandleRef.current.close() } catch {}
        streamHandleRef.current = null
      }

      const handle = openRunStream({
        threadId: result.threadId,
        runId: newRunId,
        onEvent: (evt: NormalizedStreamEvent) => {
          console.log("[chat] stream event", evt);
          if (evt.type === 'message-delta') {
            setStreamingContent((prev) => {
              const next = prev + evt.text
              streamingContentRef.current = next
              return next
            })
            return
          }
          if (evt.type === 'message-completed') {
            const content = streamingContentRef.current?.trim() ?? ''
            if (content.length > 0) {
              setMessages((prev) => [...prev, { role: 'assistant', content }])
            }
            setStreamingContent("")
            streamingContentRef.current = ""
            setIsStreaming(false)
            return
          }
          if (evt.type === 'node-started') {
            const node = evt.node
            setNodeStatuses((prev) => {
              const existing = prev.find((p) => p.name === node)
              if (existing) return prev.map((p) => (p.name === node ? { ...p, status: 'running' } : p))
              return [...prev, { name: node, status: 'running' }]
            })
            return
          }
          if (evt.type === 'node-completed') {
            const node = evt.node
            setNodeStatuses((prev) => prev.map((p) => (p.name === node ? { ...p, status: 'done' } : p)))
            return
          }
          if (evt.type === 'values-updated') {
            const values = getValuesFromStateLike(evt.values)
            if (values) {
              const arch = (values["architecture_json"] || values["design_json"]) as unknown
              if (arch && typeof arch === "object") setArchitecture(arch as DesignJson)
              const question = typeof values["clarifier_question"] === "string" ? values["clarifier_question"] : null
              const missingFields = values["missing_fields"]
              const missing = Array.isArray(missingFields) ? missingFields : []
              if (question && missing.length > 0) {
                setClarifier({ question, fields: missing as string[] })
                setIsStreaming(false)
              }

              const normalized = normalizeMessages(values["messages"])
              if (normalized && normalized.length > 0) {
                console.log('[chat] normalized messages', normalized.length)
                setMessages(normalized)
                setIsStreaming(false)
                setStreamingContent("")
                streamingContentRef.current = ""
              }
              const output = typeof values["output"] === "string" ? values["output"].trim() : ""
              if (output) {
                setIsStreaming(false)
                setStreamingContent("")
                streamingContentRef.current = ""
              }
            }
            return
          }
          if (evt.type === 'run-completed') {
            setIsStreaming(false)
            setClarifier(null)
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
            return
          }
          if (evt.type === 'error') {
            setIsStreaming(false)
          }
        },
      })
      streamHandleRef.current = handle
    } catch (err) {
      console.error("Run failed", err)
      const message = err instanceof Error ? err.message : "Unknown error"
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Sorry, something went wrong: ${message}` },
      ])
    }
  }

  // track latest streaming content for completion
  const streamingContentRef = useRef(streamingContent)
  if (streamingContentRef.current !== streamingContent) streamingContentRef.current = streamingContent

  return (
    <div className="h-screen bg-black text-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-3">
        <div>
          <h2 className="text-base font-semibold tracking-wide">System Design Agent</h2>
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
              <NodeStatusRibbon nodes={nodeStatuses} />
              {messages.length === 0 ? (
                <p className="text-sm text-white/40">
                  No messages yet. Ask the assistant anything about system design.
                </p>
              ) : (
                messages.map((m, i) => (
                  <div key={i} className="space-y-1 border border-white/15 bg-white/5 px-4 py-3">
                    <div className="text-xs uppercase tracking-wide text-white/40">{m.role === 'assistant' ? 'agent' : m.role}</div>
                    <div className="text-sm leading-relaxed text-white whitespace-pre-wrap">{m.content}</div>
                  </div>
                ))
              )}
              {isStreaming && (
                <div className="space-y-1 border border-white/15 bg-white/5 px-4 py-3">
                  <div className="text-xs uppercase tracking-wide text-white/40">agent</div>
                  <div className="text-sm leading-relaxed text-white whitespace-pre-wrap">{streamingContent || '█'}</div>
                </div>
              )}
              {clarifier && (
                <ClarifierCard question={clarifier.question} fields={clarifier.fields} />
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



