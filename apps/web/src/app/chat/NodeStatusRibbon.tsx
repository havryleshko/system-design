'use client'

type Status = 'idle' | 'running' | 'done'

type NodeStatusRibbonProps = {
  nodes: Array<{ name: string; status: Status }>
}

export default function NodeStatusRibbon({ nodes }: NodeStatusRibbonProps) {
  if (!nodes || nodes.length === 0) return null
  return (
    <div className="sticky top-0 z-10 -mx-5 mb-2 overflow-x-auto border-b border-white/10 bg-black/70 px-5 py-2 backdrop-blur">
      <div className="flex gap-2">
        {nodes.map((n, idx) => (
          <span
            key={`${n.name}-${idx}`}
            className={
              `inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs ` +
              (n.status === 'running'
                ? 'border border-blue-400/40 bg-blue-500/10 text-blue-300'
                : n.status === 'done'
                ? 'border border-green-400/30 bg-green-500/10 text-green-300'
                : 'border border-white/15 bg-white/5 text-white/70')
            }
            title={n.name}
          >
            <span className="truncate max-w-[160px]">{n.name}</span>
            {n.status === 'running' && <span className="animate-pulse">●</span>}
            {n.status === 'done' && <span>✓</span>}
          </span>
        ))}
      </div>
    </div>
  )
}


