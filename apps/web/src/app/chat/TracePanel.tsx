'use client'

import { useState } from 'react'

type TraceEvent = {
    ts_ms: number
    level: 'info' | 'warn' | 'error'
    message: string
    data?: Record<string, unknown> | null
}

type TimelineEntry = {
    node: string
    duration_ms: number
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    started_ts_ms: number
    finished_ts_ms: number | null
}

type RunTrace = {
    id: string
    events: TraceEvent[]
    timeline?: TimelineEntry[]
    branch_path?: string[]
}

type TracePanelProps = {
    trace: RunTrace | null
    isLoading: boolean
    error: string | null
    onRefresh: () => void
}

export default function TracePanel({ trace, isLoading, error, onRefresh }: TracePanelProps) {
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

    const toggleNode = (node: string) => {
        setExpandedNodes((prev) => {
            const next = new Set(prev)
            if (next.has(node)) {
                next.delete(node)
            } else {
                next.add(node)
            }
            return next
        })
    }

    const timeline = trace?.timeline || []
    const events = trace?.events || []
    const branchPath = trace?.branch_path || []

    // Group events by node based on timestamps
    const getEventsForNode = (nodeEntry: TimelineEntry): TraceEvent[] => {
        if (!nodeEntry.started_ts_ms) return []
        const endTime = nodeEntry.finished_ts_ms || Date.now()
        return events.filter(
            (evt) => evt.ts_ms >= nodeEntry.started_ts_ms && evt.ts_ms <= endTime
        )
    }

    const formatDuration = (ms: number) => {
        if (ms < 1000) return `${Math.round(ms)}ms`
        return `${(ms / 1000).toFixed(1)}s`
    }

    const formatTime = (ts: number) => {
        const date = new Date(ts)
        return date.toLocaleTimeString()
    }

    return (
        <div className="flex h-screen flex-col border-l border-white/15 bg-black">
            <div className="flex items-center justify-between border-b border-white/15 px-5 py-4">
                <div>
                    <h2 className="text-sm font-semibold uppercase tracking-wide text-white">Trace</h2>
                    <p className="mt-1 text-xs text-white/40">Agent execution flow</p>
                </div>
                <button
                    onClick={onRefresh}
                    disabled={isLoading}
                    className="rounded-sm border border-white/20 px-3 py-1.5 text-xs uppercase tracking-wide text-white/70 transition hover:bg-white/5 hover:text-white disabled:opacity-40"
                >
                    {isLoading ? 'Loading...' : 'Refresh'}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5">
                {error && (
                    <div className="rounded-md border border-red-500/20 bg-red-500/5 px-4 py-3">
                        <p className="text-xs text-red-400">{error}</p>
                    </div>
                )}

                {!trace && !isLoading && !error && (
                    <div className="flex h-full items-center justify-center">
                        <p className="text-center text-sm text-white/40">
                            No trace available yet.
                            <br />
                            Start a run to see details.
                        </p>
                    </div>
                )}

                {isLoading && !trace && (
                    <div className="flex h-full items-center justify-center">
                        <p className="text-sm text-white/40">Loading trace...</p>
                    </div>
                )}

                {timeline.length > 0 && (
                    <div className="space-y-3">
                        {timeline.map((entry, idx) => {
                            const isExpanded = expandedNodes.has(entry.node)
                            const isActive = !entry.finished_ts_ms
                            const nodeEvents = getEventsForNode(entry)
                            const hasEvents = nodeEvents.length > 0

                            return (
                                <div key={idx} className="rounded-md border border-white/15 bg-white/5">
                                    <button
                                        onClick={() => toggleNode(entry.node)}
                                        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-white/5"
                                    >
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                <span className={`text-sm font-medium ${isActive ? 'text-white' : 'text-white/90'}`}>
                                                    {entry.node}
                                                </span>
                                                {isActive && (
                                                    <span className="rounded-sm bg-blue-500/20 px-2 py-0.5 text-[10px] uppercase tracking-wide text-blue-400">
                                                        Running
                                                    </span>
                                                )}
                                                {!isActive && (
                                                    <span className="text-xs text-green-500">✓</span>
                                                )}
                                            </div>
                                            <div className="mt-1 flex items-center gap-3 text-[10px] uppercase tracking-wide text-white/40">
                                                <span>{formatTime(entry.started_ts_ms)}</span>
                                                {entry.duration_ms > 0 && <span>{formatDuration(entry.duration_ms)}</span>}
                                                {entry.total_tokens > 0 && <span>{entry.total_tokens} tokens</span>}
                                            </div>
                                        </div>
                                        <span className={`text-xs text-white/40 transition ${isExpanded ? 'rotate-180' : ''}`}>
                                            ▼
                                        </span>
                                    </button>

                                    {isExpanded && (
                                        <div className="border-t border-white/10 px-4 py-3">
                                            {entry.total_tokens > 0 && (
                                                <div className="mb-3 rounded-sm bg-white/5 px-3 py-2">
                                                    <div className="text-[10px] uppercase tracking-wide text-white/40">Token Usage</div>
                                                    <div className="mt-1 flex gap-4 text-xs text-white/70">
                                                        <span>Prompt: {entry.prompt_tokens}</span>
                                                        <span>Completion: {entry.completion_tokens}</span>
                                                        <span>Total: {entry.total_tokens}</span>
                                                    </div>
                                                </div>
                                            )}

                                            {hasEvents ? (
                                                <div className="space-y-2">
                                                    <div className="text-[10px] uppercase tracking-wide text-white/40">Events</div>
                                                    {nodeEvents.map((event, eventIdx) => (
                                                        <div key={eventIdx} className="rounded-sm border border-white/10 bg-black/40 px-3 py-2">
                                                            <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-white/40">
                                                                <span>{formatTime(event.ts_ms)}</span>
                                                                <span className={
                                                                    event.level === 'error' ? 'text-red-400' :
                                                                    event.level === 'warn' ? 'text-yellow-400' :
                                                                    'text-white/40'
                                                                }>
                                                                    {event.level}
                                                                </span>
                                                            </div>
                                                            <p className="mt-1.5 text-xs leading-relaxed text-white/80">{event.message}</p>
                                                            {event.data && (
                                                                <details className="mt-2">
                                                                    <summary className="cursor-pointer text-[10px] uppercase tracking-wide text-white/40 hover:text-white/60">
                                                                        Show data
                                                                    </summary>
                                                                    <pre className="mt-2 max-h-40 overflow-auto rounded-sm bg-black/60 p-2 text-[10px] leading-snug text-white/70">
                                                                        {JSON.stringify(event.data, null, 2)}
                                                                    </pre>
                                                                </details>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-xs text-white/40">No events captured for this node.</p>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                )}

                {/* Show branch path summary at the bottom */}
                {branchPath.length > 0 && (
                    <div className="mt-6 rounded-md border border-white/10 bg-white/5 px-4 py-3">
                        <div className="text-[10px] uppercase tracking-wide text-white/40">Execution Path</div>
                        <div className="mt-2 flex flex-wrap gap-1">
                            {branchPath.map((node, idx) => (
                                <span key={idx} className="flex items-center gap-1 text-xs text-white/70">
                                    {node}
                                    {idx < branchPath.length - 1 && <span className="text-white/40">→</span>}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

