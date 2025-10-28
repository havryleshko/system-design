'use client'

import { useState, useTransition } from 'react'
import { fetchTrace } from '../actions'

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
}

export default function ChatClient({
    initialMessages,
    runId,
    userId
}: ChatClientProps) {
    const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
    const [input, setInput] = useState('')
    const [traceOpen, setTraceOpen] = useState(false)
    const [trace, setTrace] = useState<RunTrace | null>(null)
    const [traceError, setTraceError] = useState<string | null>(null)
    const [isPending, startTransition] = useTransition()
    const [currentRunId, setCurrentRunId] = useState<string | null>(runId)

    const loadTrace = () => {
        if (!currentRunId) {
            setTraceError('Run ID not available yet')
            setTraceOpen(true)
            return
        }
        setTraceOpen(true)
        if (trace || isPending) return
        startTransition(async () => {
            try {
                const data = await fetchTrace(currentRunId)
                setTrace(data)
                setTraceError(null)
            } catch (err) {
                setTrace(null)
                setTraceError(err instanceof Error ? err.message : 'Failed to load trace')
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
                setTraceError(err instanceof Error ? err.message : 'Failed to load trace')
            }
        })
    }

    async function send() {
        const trimmed = input.trim()
        if (!trimmed) return

        const userMessage: ChatMessage = { role: 'user', content: trimmed }
        setMessages((prev) => [...prev, userMessage])
        setInput('')

        const res = await fetch('/api/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: trimmed })
        })
        if (!res.ok) {
            console.error('Request failed', res.status)
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: 'Sorry, something went wrong starting that run.' }
            ])
            return
        }
        const data = await res.json()
        const newRunId = typeof data?.id === 'string' ? data.id : null
        if (newRunId) {
            setCurrentRunId(newRunId)
            setTrace(null)
        }

        const reply = data?.reply
        if (reply && typeof reply === 'object' && typeof reply.content === 'string') {
            const replyRole = reply.role === 'user' || reply.role === 'assistant' || reply.role === 'system' ? reply.role : 'assistant'
            setMessages((prev) => [...prev, { role: replyRole, content: reply.content }])
            return
        }

        if (newRunId) {
            const status = typeof data?.status === 'string' ? data.status : 'created'
            setMessages((prev) => [
                ...prev,
                { role: 'assistant', content: `Run ${status} (${newRunId})` }
            ])
        }
    }

    return (
        <div className="min-h-screen bg-black text-white">
            <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-10">
                <div className="flex items-center justify-between gap-3">
                    <div>
                        <h2 className="text-xl font-semibold tracking-wide">Chat</h2>
                        <p className="text-xs uppercase text-white/40">system design assistant</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            className="rounded border border-white px-3 py-2 text-xs uppercase tracking-wide text-white transition hover:bg-white hover:text-black"
                            onClick={async () => {
                                const res = await fetch('/api/stripe/checkout', { method: 'POST' })
                                if (!res.ok) {
                                    console.error('Checkout failed', res.status)
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
                        <button className="text-sm text-white/70 underline-offset-4 hover:text-white" onClick={loadTrace}>
                            Show trace
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-hidden">
                    <div className="flex h-[32rem] flex-col gap-3 overflow-y-auto border border-white/15 bg-black/40 p-5">
                        {messages.length === 0 ? (
                            <p className="text-sm text-white/40">No messages yet. Ask the assistant anything about system design.</p>
                        ) : (
                            messages.map((m, i) => (
                                <div key={i} className="space-y-1 border border-white/20 px-4 py-3">
                                    <div className="text-xs uppercase tracking-wide text-white/40">{m.role}</div>
                                    <div className="text-sm leading-relaxed text-white">{m.content}</div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-3 border border-white/15 bg-black/60 px-4 py-3">
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

            {traceOpen && <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setTraceOpen(false)} />}
            {traceOpen && (
                <div className="fixed top-0 right-0 z-50 flex h-full w-full max-w-md flex-col border-l border-white/10 bg-black text-white shadow-[0_0_30px_rgba(0,0,0,0.6)]">
                    <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide">Trace</h3>
                        <div className="flex items-center gap-3 text-xs uppercase tracking-wide">
                            <button
                                className="text-white/70 hover:text-white disabled:text-white/30"
                                onClick={refreshTrace}
                                disabled={isPending || !currentRunId}
                            >
                                {isPending ? 'Refreshing…' : 'Refresh'}
                            </button>
                            <button className="text-white/70 hover:text-white" onClick={() => setTraceOpen(false)}>
                                Close
                            </button>
                        </div>
                    </div>
                    <div className="flex-1 space-y-4 overflow-auto px-5 py-4">
                        {!runId && <p className="text-xs uppercase text-white/40">Run has not started yet.</p>}
                        {traceError && <p className="text-xs uppercase text-red-400">{traceError}</p>}
                        {isPending && !trace && <p className="text-xs uppercase text-white/40">Loading trace…</p>}
                        {trace && trace.events.length === 0 && <p className="text-xs uppercase text-white/40">No trace events yet.</p>}
                        {trace?.events.map((event, idx) => (
                            <div key={idx} className="border border-white/15 px-4 py-3">
                                <div className="flex justify-between text-[10px] uppercase tracking-wide text-white/40">
                                    <span>{new Date(event.ts_ms).toLocaleString()}</span>
                                    <span>{event.level}</span>
                                </div>
                                <p className="mt-2 text-sm leading-relaxed text-white">{event.message}</p>
                                {event.data ? (
                                    <pre className="mt-3 max-h-40 overflow-auto border border-white/10 bg-black/60 p-3 text-[11px] leading-snug text-white">
                                        {JSON.stringify(event.data, null, 2)}
                                    </pre>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}



