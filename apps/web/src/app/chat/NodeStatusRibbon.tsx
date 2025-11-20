'use client'

type Status = 'idle' | 'running' | 'done'

type NodeStatusRibbonProps = {
  nodes: Array<{ name: string; status: Status }>
}

export default function NodeStatusRibbon({ nodes }: NodeStatusRibbonProps) {
  if (!nodes || nodes.length === 0) return null
  return (
    <div 
      className="sticky top-0 z-10 -mx-5 mb-2 overflow-x-auto border-b bg-black/70 px-5 py-2 backdrop-blur"
      style={{ borderColor: 'var(--border)', background: 'rgba(35, 37, 47, 0.9)' }}
    >
      <div className="flex gap-2">
        {nodes.map((n, idx) => (
          <span
            key={`${n.name}-${idx}`}
            className={
              `inline-flex items-center gap-1 rounded-sm px-2 py-1 text-xs `
            }
            style={{
              borderColor: n.status === 'running' ? 'var(--accent)' : n.status === 'done' ? 'rgba(74, 222, 128, 0.3)' : 'var(--border)',
              background: n.status === 'running' ? 'rgba(154, 182, 194, 0.1)' : n.status === 'done' ? 'rgba(74, 222, 128, 0.1)' : 'rgba(255, 255, 255, 0.05)',
              color: n.status === 'running' ? 'var(--accent)' : n.status === 'done' ? '#4ade80' : 'var(--foreground-muted)',
              borderWidth: '1px',
              borderStyle: 'solid'
            }}
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
