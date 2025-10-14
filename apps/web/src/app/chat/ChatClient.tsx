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

export default function ChatClient({
    userId,
    initialMessages,
    runId
}: {
    userId: string | null
    initialMessages: ChatMessage[]
    runId: string | null
}) {
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
        <div className="max-w-2xl mx-auto p-4 space-y-3 relative">
            <div className="flex justify-between items-center">
                <h2 className="text-lg font-semibold">Chat</h2>
                <button className="text-sm text-black-600 underline" onClick={loadTrace}>
                    Show trace
                </button>
            </div>
            <div className="border border-black rounded p-3 h-80 overflow-auto bg-white">
                {messages.map((m, i) => (
                    <div key={i} className="mb-2">
                        <b>{m.role}:</b> {m.content}
                    </div>
                ))}
            </div>
            <div className="flex gap-2">
                <input className="flex-1 border rounded p-2" value={input} onChange={(e) => setInput(e.target.value)} />
                <button className="px-3 py-2 bg-black-600 text-white rounded" onClick={send}>
                    Send
                </button>
            </div>

            {traceOpen && <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setTraceOpen(false)} />}
            {traceOpen && (
                <div className="fixed top-0 right-0 h-full w-full max-w-md bg-white shadow-xl z-50 flex flex-col">
                    <div className="p-4 border-b flex justify-between items-center">
                        <h3 className="text-base font-semibold">Trace</h3>
                        <div className="flex items-center gap-2">
                            <button className="text-sm text-black-600" onClick={refreshTrace} disabled={isPending || !currentRunId}>
                                {isPending ? 'Refreshing…' : 'Refresh'}
                            </button>
                            <button className="text-sm" onClick={() => setTraceOpen(false)}>
                                Close
                            </button>
                        </div>
                    </div>
                    <div className="flex-1 overflow-auto p-4 space-y-4">
                        {!runId && <p className="text-sm text-gray-600">Run has not started yet.</p>}
                        {traceError && <p className="text-sm text-red-600">{traceError}</p>}
                        {isPending && !trace && <p className="text-sm text-gray-600">Loading trace…</p>}
                        {trace && trace.events.length === 0 && <p className="text-sm text-gray-600">No trace events yet.</p>}
                        {trace?.events.map((event, idx) => (
                            <div key={idx} className="border rounded p-3 bg-gray-50">
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>{new Date(event.ts_ms).toLocaleString()}</span>
                                    <span className="uppercase">{event.level}</span>
                                </div>
                                <p className="mt-2 text-sm font-medium">{event.message}</p>
                                {event.data ? (
                                    <pre className="mt-2 text-xs bg-white border rounded p-2 overflow-auto">
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



