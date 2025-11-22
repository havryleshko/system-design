"use client"

import { useEffect, useRef, useState, useTransition } from "react"
import { useRouter } from "next/navigation"

import { fetchTrace, startRunStream, type StartStreamResult } from "../actions"
import ArchitecturePanel, { type DesignJson } from "./ArchitecturePanel"
import TracePanel from "./TracePanel"
import { openRunStream, type NormalizedStreamEvent } from "./useRunStream"
import ClarifierCard from "./ClarifierCard"
import NodeStatusRibbon from "./NodeStatusRibbon"
import MolecularLoader from "./MolecularLoader"

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

type StreamFailure = Extract<StartStreamResult, { ok: false }>

function formatStreamFailure(failure: StreamFailure): string {
  const detail = typeof failure.detail === "string" && failure.detail.trim() ? failure.detail.trim() : null
  const hints: string[] = []
  if (failure.status === 404) {
    hints.push("We couldn't find the existing thread. Please try again to create a fresh session.")
  } else if (typeof failure.status === "number" && failure.status >= 500) {
    hints.push("The backend is temporarily unavailable. Please retry in a moment.")
  }
  const segments = [failure.error]
  if (detail && detail !== failure.error) segments.push(detail)
  if (hints.length > 0) segments.push(hints.join(" "))
  return segments.filter(Boolean).join(" — ")
}

const TOKEN_DEBUG_ENABLED = process.env.NEXT_PUBLIC_SUPABASE_TOKEN_DEBUG === "true"

export default function ChatClient({
  initialMessages,
  runId,
  designJson,
}: ChatClientProps) {
  useEffect(() => {
    if (!TOKEN_DEBUG_ENABLED) return
    fetch("/api/debug/supabase-token")
      .then(async (res) => {
        if (!res.ok) return null
        try {
          return await res.json()
        } catch {
          return null
        }
      })
      .then((data) => {
        if (data?.token) {
          console.log("[debug] Supabase access_token", data.token)
        }
      })
      .catch(() => {
        // swallow errors – this is a debug helper
      })
  }, [])
  const router = useRouter()
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
  const [clarifier, setClarifier] = useState<{ question: string; fields: string[]; interruptId: string | null; runId: string | null } | null>(null)
  const [nodeStatuses, setNodeStatuses] = useState<Array<{ name: string; status: 'idle' | 'running' | 'done' }>>([])
  const [streamError, setStreamError] = useState<string | null>(null)

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
    setStreamError(null)

    try {
      const result = await startRunStream(trimmed)
      if (!result.ok) {
        if (result.status === 401) {
          setStreamError("Your session expired. Redirecting to login…")
          router.replace(`/login?redirect=${encodeURIComponent("/chat")}`)
          return
        }
        const errorMessage = formatStreamFailure(result)
        setStreamError(errorMessage)
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
      setStreamError(null)

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
            setStreamError(null)
            setStreamingContent((prev) => {
              const next = prev + evt.text
              streamingContentRef.current = next
              return next
            })
            return
          }
          if (evt.type === 'message-completed') {
            setStreamError(null)
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
            setStreamError(null)
            const node = evt.node
            setNodeStatuses((prev) => {
              const existing = prev.find((p) => p.name === node)
              if (existing) return prev.map((p) => (p.name === node ? { ...p, status: 'running' } : p))
              return [...prev, { name: node, status: 'running' }]
            })
            return
          }
          if (evt.type === 'node-completed') {
            setStreamError(null)
            const node = evt.node
            setNodeStatuses((prev) => prev.map((p) => (p.name === node ? { ...p, status: 'done' } : p)))
            return
          }
          if (evt.type === 'interrupt') {
            setStreamError(null)
            const first = evt.interrupts[0]
            if (first) {
              const payload = (first.value ?? {}) as Record<string, unknown>
              const question =
                typeof payload?.question === 'string'
                  ? payload.question
                  : 'The agent needs a bit more context before proceeding.'
              const rawFields = Array.isArray(payload?.missing_fields) ? payload.missing_fields : []
              const fields = rawFields
                .map((field) => (typeof field === 'string' ? field.trim() : ''))
                .filter((field): field is string => Boolean(field))
              setClarifier({
                question,
                fields,
                interruptId: first.id,
                runId: newRunId,
              })
              setIsStreaming(false)
            }
            return
          }
          if (evt.type === 'values-updated') {
            setStreamError(null)
            const values = getValuesFromStateLike(evt.values)
            if (values) {
              const arch = (values["architecture_json"] || values["design_json"]) as unknown
              if (arch && typeof arch === "object") setArchitecture(arch as DesignJson)
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
              const missingRaw = Array.isArray(values["missing_fields"]) ? values["missing_fields"] : []
              const missingFields = missingRaw
                .map((field) => (typeof field === 'string' ? field.trim() : ''))
                .filter((field): field is string => Boolean(field))
              const question =
                typeof values["clarifier_question"] === "string"
                  ? values["clarifier_question"].trim()
                  : ""
              if (missingFields.length === 0 || !question) {
                setClarifier((prev) => {
                  if (!prev) return prev
                  if (prev.runId && prev.runId !== newRunId) return prev
                  return null
                })
              } else {
                setClarifier((prev) => {
                  if (!prev || (prev.runId && prev.runId !== newRunId)) return prev
                  return {
                    ...prev,
                    question: question || prev.question,
                    fields: missingFields,
                  }
                })
              }
            }
            return
          }
          if (evt.type === 'run-completed') {
            setIsStreaming(false)
            setClarifier(null)
            setStreamError(null)
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
            setStreamError(evt.message || 'Stream connection error')
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
    <div className="relative flex h-screen flex-col text-[var(--foreground)]" style={{ background: 'var(--background)', overflow: 'hidden' }}>
      {/* Particle background */}
      <div className="particle-background">
        <div className="particle" style={{ top: '10%', left: '15%' }}></div>
        <div className="particle"></div>
        <div className="particle"></div>
        <div className="particle"></div>
        <div className="particle"></div>
      </div>

      {/* Header */}
      <div className="relative z-10 flex items-center justify-between border-b px-6 py-3 shrink-0" style={{ borderColor: 'var(--border)', background: 'var(--surface)', backdropFilter: 'blur(18px)' }}>
        <div>
          <h2 className="text-base font-semibold tracking-tight" style={{ fontFamily: 'var(--font-ibm-plex-mono)' }}>System Design Agent</h2>
          <p className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--foreground-muted)' }}>Autonomous system architecture</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            className="border px-4 py-1.5 text-[11px] font-medium uppercase tracking-wider transition-all duration-200"
            style={{ 
              borderColor: 'var(--border)',
              background: 'rgba(35, 37, 47, 0.3)',
              color: 'var(--accent)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--accent)';
              e.currentTarget.style.color = 'var(--surface)';
              e.currentTarget.style.boxShadow = '0 0 20px rgba(154, 182, 194, 0.2)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(35, 37, 47, 0.3)';
              e.currentTarget.style.color = 'var(--accent)';
              e.currentTarget.style.boxShadow = 'none';
            }}
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
      <div className="relative z-10 grid flex-1 min-h-0 grid-cols-12">
        {/* Left: Architecture */}
        <div className="col-span-3 min-w-0 flex flex-col min-h-0" style={{ borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
          <ArchitecturePanel designJson={architecture ?? null} />
        </div>

        {/* Center: Chat */}
        <div className="col-span-6 flex min-w-0 flex-col min-h-0">
          <div className="flex-1 min-h-0 overflow-y-auto p-6" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
              <NodeStatusRibbon nodes={nodeStatuses} />
              {streamError && (
                <div className="glass-panel rounded px-4 py-2 text-xs" style={{ borderColor: 'rgba(255, 100, 100, 0.4)', color: '#ffaaaa' }}>
                  {streamError} — attempting to reconnect…
                </div>
              )}
              {messages.length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--foreground-muted)', lineHeight: '1.6' }}>
                  No messages yet. Ask the assistant anything about system design.
                </p>
              ) : (
                messages.map((m, i) => (
                  <div key={i} className="glass-panel rounded px-5 py-4" style={{ gap: 'var(--spacing-xs)' }}>
                    <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--foreground-muted)', fontFamily: 'var(--font-ibm-plex-mono)' }}>
                      {m.role === 'assistant' ? 'agent' : m.role}
                    </div>
                    <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)', lineHeight: '1.7', marginTop: 'var(--spacing-xs)' }}>{m.content}</div>
                  </div>
                ))
              )}
              {isStreaming && (
                <div className="glass-panel rounded px-5 py-4">
                  <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--foreground-muted)', fontFamily: 'var(--font-ibm-plex-mono)' }}>agent</div>
                  {streamingContent ? (
                    <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)', lineHeight: '1.7', marginTop: 'var(--spacing-xs)' }}>{streamingContent}</div>
                  ) : (
                    <div className="flex items-center" style={{ marginTop: 'var(--spacing-sm)' }}>
                      <MolecularLoader />
                      <span className="ml-3 text-xs" style={{ color: 'var(--foreground-muted)' }}>Analyzing request...</span>
                    </div>
                  )}
                </div>
              )}
              {clarifier && (
                <ClarifierCard
                  question={clarifier.question}
                  fields={clarifier.fields}
                  runId={clarifier.runId}
                  interruptId={clarifier.interruptId}
                />
              )}
            </div>
          <div
            className="flex items-center px-4 py-2.5 shrink-0"
            style={{
              gap: 'var(--spacing-sm)',
              borderTop: '1px solid var(--border)',
              background: 'var(--surface)',
            }}
          >
            <input
              className="flex-1 bg-transparent text-sm focus:outline-none"
              style={{ color: 'var(--foreground)', caretColor: 'var(--accent)' }}
              placeholder="Type your message"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <button
              className="border px-4 py-1.5 text-xs font-medium uppercase tracking-wider transition-all duration-200"
              style={{ 
                borderColor: 'var(--border)',
                background: 'rgba(35, 37, 47, 0.3)',
                color: 'var(--accent)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--accent)';
                e.currentTarget.style.color = 'var(--surface)';
                e.currentTarget.style.boxShadow = '0 0 20px rgba(154, 182, 194, 0.2)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(35, 37, 47, 0.3)';
                e.currentTarget.style.color = 'var(--accent)';
                e.currentTarget.style.boxShadow = 'none';
              }}
              onClick={send}
            >
              Send
            </button>
          </div>
        </div>

        {/* Right: Trace */}
        <div className="col-span-3 min-w-0 flex flex-col min-h-0" style={{ borderLeft: '1px solid var(--border)', overflow: 'hidden' }}>
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
