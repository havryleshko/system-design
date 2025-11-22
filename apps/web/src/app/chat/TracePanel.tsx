'use client'

import { useEffect, useState } from 'react'

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

    // Fallback refresh: if there are active nodes, poll every 3s
    useEffect(() => {
        const hasActive = timeline.some((t) => !t.finished_ts_ms)
        if (!hasActive) return
        const id = setInterval(() => onRefresh(), 3000)
        return () => clearInterval(id)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [JSON.stringify(timeline)])

    return (
        <div className="flex h-full min-h-0 flex-col" style={{ background: 'var(--background)' }}>
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--border)' }}>
                <div>
                    <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-ibm-plex-mono)', color: 'var(--foreground)' }}>Trace</h2>
                    <p className="mt-1 text-xs" style={{ color: 'var(--foreground-muted)' }}>Agent execution flow</p>
                </div>
                <button
                    onClick={onRefresh}
                    disabled={isLoading}
                    className="rounded border px-3 py-1.5 text-xs uppercase tracking-wider transition-all duration-200"
                    style={{ 
                        borderColor: 'var(--border)',
                        background: 'rgba(35, 37, 47, 0.2)',
                        color: 'var(--foreground-muted)'
                    }}
                    onMouseEnter={(e) => {
                        if (!isLoading) {
                            e.currentTarget.style.background = 'var(--accent)';
                            e.currentTarget.style.color = 'var(--surface)';
                        }
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(35, 37, 47, 0.2)';
                        e.currentTarget.style.color = 'var(--foreground-muted)';
                    }}
                >
                    {isLoading ? 'Loading...' : 'Refresh'}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5">
                {error && (
                    <div className="glass-panel rounded px-4 py-3" style={{ borderColor: 'rgba(255, 100, 100, 0.4)' }}>
                        <p className="text-xs" style={{ color: '#ffaaaa' }}>{error}</p>
                    </div>
                )}

                {!trace && !isLoading && !error && (
                    <div className="flex h-full items-center justify-center">
                        <p className="text-center text-sm" style={{ color: 'var(--foreground-muted)', lineHeight: '1.6' }}>
                            No trace available yet.
                            <br />
                            Start a run to see details.
                        </p>
                    </div>
                )}

                {isLoading && !trace && (
                    <div className="flex h-full items-center justify-center">
                        <p className="text-sm" style={{ color: 'var(--foreground-muted)' }}>Loading trace...</p>
                    </div>
                )}

                {timeline.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
                        {timeline.map((entry, idx) => {
                            const isExpanded = expandedNodes.has(entry.node)
                            const isActive = !entry.finished_ts_ms
                            const nodeEvents = getEventsForNode(entry)
                            const hasEvents = nodeEvents.length > 0

                            return (
                                <div key={idx} className="glass-panel rounded">
                                    <button
                                        onClick={() => toggleNode(entry.node)}
                                        className="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-white/5"
                                    >
                                        <div className="flex-1">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-medium" style={{ color: isActive ? 'var(--foreground)' : 'var(--foreground-muted)' }}>
                                                    {entry.node}
                                                </span>
                                                {isActive && (
                                                    <span className="rounded px-2 py-0.5 text-[10px] uppercase tracking-wider" style={{ background: 'rgba(154, 182, 194, 0.2)', color: 'var(--accent)' }}>
                                                        Running
                                                    </span>
                                                )}
                                                {!isActive && (
                                                    <span className="text-xs" style={{ color: 'var(--accent)' }}>✓</span>
                                                )}
                                            </div>
                                            <div className="mt-1 flex items-center gap-3 text-[10px] uppercase tracking-wider" style={{ color: 'var(--foreground-muted)' }}>
                                                <span>{formatTime(entry.started_ts_ms)}</span>
                                                {entry.duration_ms > 0 && <span>{formatDuration(entry.duration_ms)}</span>}
                                                {entry.total_tokens > 0 && <span>{entry.total_tokens} tokens</span>}
                                            </div>
                                        </div>
                                        <span className={`text-xs transition ${isExpanded ? 'rotate-180' : ''}`} style={{ color: 'var(--foreground-muted)' }}>
                                            ▼
                                        </span>
                                    </button>

                                    {isExpanded && (
                                        <div className="border-t px-4 py-3" style={{ borderColor: 'var(--border)' }}>
                                            {entry.total_tokens > 0 && (
                                                <div className="mb-3 rounded-sm px-3 py-2" style={{ background: 'rgba(0,0,0,0.2)' }}>
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
                                                        <div key={eventIdx} className="rounded-sm border px-3 py-2" style={{ borderColor: 'var(--border)', background: 'rgba(0,0,0,0.3)' }}>
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
                    <div className="mt-6 rounded-md border px-4 py-3" style={{ borderColor: 'var(--border)', background: 'rgba(35, 37, 47, 0.2)' }}>
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
