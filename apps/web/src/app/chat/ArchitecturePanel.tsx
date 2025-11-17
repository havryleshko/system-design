'use client'

type DesignElement = {
    id: string
    kind: string
    label: string
    description?: string
    technology?: string
    tags?: string[]
}

type DesignRelation = {
    source: string
    target: string
    label: string
    technology?: string
    direction?: string
}

type DesignGroup = {
    id: string
    kind: string
    label: string
    technology?: string
    children: string[]
}

export type DesignJson = {
    elements?: DesignElement[]
    relations?: DesignRelation[]
    groups?: DesignGroup[]
    notes?: string
}

type ArchitecturePanelProps = {
    designJson: DesignJson | null
}

export default function ArchitecturePanel({ designJson }: ArchitecturePanelProps) {
    const hasContent = designJson && (
        (designJson.elements && designJson.elements.length > 0) ||
        (designJson.relations && designJson.relations.length > 0)
    )

    if (!hasContent) {
        return (
            <div className="flex h-full min-h-0 flex-col" style={{ background: 'linear-gradient(180deg, rgba(6,7,12,0.9), rgba(17,19,25,0.95))' }}>
                <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(198, 180, 255, 0.15)' }}>
                    <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-space-grotesk)', color: '#ededed' }}>Architecture</h2>
                    <p className="mt-1 text-xs" style={{ color: 'rgba(198, 180, 255, 0.6)' }}>System design output</p>
                </div>
                <div className="flex flex-1 items-center justify-center px-6">
                    <p className="text-center text-sm" style={{ color: 'rgba(198, 180, 255, 0.5)', lineHeight: '1.6' }}>
                        No architecture yet.
                        <br />
                        Start by designing a system.
                    </p>
                </div>
            </div>
        )
    }

    const elements = designJson.elements || []
    const relations = designJson.relations || []
    const groups = designJson.groups || []
    const notes = designJson.notes || ''

    return (
        <div className="flex h-full min-h-0 flex-col" style={{ background: 'linear-gradient(180deg, rgba(6,7,12,0.9), rgba(17,19,25,0.95))' }}>
            <div className="px-5 py-4" style={{ borderBottom: '1px solid rgba(198, 180, 255, 0.15)' }}>
                <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ fontFamily: 'var(--font-space-grotesk)', color: '#ededed' }}>Architecture</h2>
                <p className="mt-1 text-xs" style={{ color: 'rgba(198, 180, 255, 0.6)' }}>
                    {elements.length} element{elements.length !== 1 ? 's' : ''} · {relations.length} relation{relations.length !== 1 ? 's' : ''}
                </p>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-5" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)' }}>
                {/* Elements */}
                {elements.length > 0 && (
                    <section>
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.7)', fontFamily: 'var(--font-space-grotesk)', marginBottom: 'var(--spacing-sm)' }}>Elements</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                            {elements.map((el) => (
                                <div key={el.id} className="glass-panel rounded px-4 py-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1">
                                            <div className="text-sm font-medium" style={{ color: '#ededed' }}>{el.label}</div>
                                            <div className="mt-1 text-xs" style={{ color: 'rgba(198, 180, 255, 0.6)' }}>{el.kind}</div>
                                        </div>
                                        {el.technology && (
                                            <span className="rounded px-2 py-1 text-[10px] uppercase tracking-wider" style={{ background: 'rgba(198, 180, 255, 0.1)', color: 'rgba(198, 180, 255, 0.8)' }}>
                                                {el.technology}
                                            </span>
                                        )}
                                    </div>
                                    {el.description && (
                                        <p className="text-xs leading-relaxed" style={{ marginTop: 'var(--spacing-xs)', color: 'rgba(255, 255, 255, 0.7)' }}>{el.description}</p>
                                    )}
                                    {el.tags && el.tags.length > 0 && (
                                        <div className="flex flex-wrap gap-1" style={{ marginTop: 'var(--spacing-xs)' }}>
                                            {el.tags.map((tag, idx) => (
                                                <span key={idx} className="rounded px-2 py-0.5 text-[10px]" style={{ background: 'rgba(198, 180, 255, 0.08)', color: 'rgba(198, 180, 255, 0.6)' }}>
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Relations */}
                {relations.length > 0 && (
                    <section>
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.7)', fontFamily: 'var(--font-space-grotesk)', marginBottom: 'var(--spacing-sm)' }}>Relations</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                            {relations.map((rel, idx) => (
                                <div key={idx} className="glass-panel rounded px-4 py-2.5">
                                    <div className="flex items-center gap-2 text-xs">
                                        <span className="font-medium" style={{ color: '#ededed' }}>{rel.source}</span>
                                        <span style={{ color: 'rgba(198, 180, 255, 0.6)' }}>{rel.direction || '→'}</span>
                                        <span className="font-medium" style={{ color: '#ededed' }}>{rel.target}</span>
                                    </div>
                                    <p className="text-xs" style={{ marginTop: 'var(--spacing-xs)', color: 'rgba(255, 255, 255, 0.7)' }}>{rel.label}</p>
                                    {rel.technology && (
                                        <span className="inline-block rounded px-2 py-0.5 text-[10px] uppercase tracking-wider" style={{ marginTop: 'var(--spacing-xs)', background: 'rgba(198, 180, 255, 0.1)', color: 'rgba(198, 180, 255, 0.8)' }}>
                                            {rel.technology}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Groups */}
                {groups.length > 0 && (
                    <section>
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.7)', fontFamily: 'var(--font-space-grotesk)', marginBottom: 'var(--spacing-sm)' }}>Groups</h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                            {groups.map((group) => (
                                <div key={group.id} className="glass-panel rounded px-4 py-3">
                                    <div className="text-sm font-medium" style={{ color: '#ededed' }}>{group.label}</div>
                                    <div className="mt-1 text-xs" style={{ color: 'rgba(198, 180, 255, 0.6)' }}>{group.kind}</div>
                                    {group.technology && (
                                        <div className="text-[10px] uppercase tracking-wider" style={{ marginTop: 'var(--spacing-xs)', color: 'rgba(198, 180, 255, 0.8)' }}>{group.technology}</div>
                                    )}
                                    <div className="flex flex-wrap gap-1" style={{ marginTop: 'var(--spacing-xs)' }}>
                                        {group.children.map((childId, idx) => (
                                            <span key={idx} className="rounded px-2 py-1 text-[10px]" style={{ background: 'rgba(198, 180, 255, 0.1)', color: 'rgba(198, 180, 255, 0.8)' }}>
                                                {childId}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* Notes */}
                {notes && (
                    <section>
                        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.7)', fontFamily: 'var(--font-space-grotesk)', marginBottom: 'var(--spacing-sm)' }}>Notes</h3>
                        <div className="glass-panel rounded px-4 py-3">
                            <p className="text-xs leading-relaxed" style={{ color: 'rgba(255, 255, 255, 0.7)' }}>{notes}</p>
                        </div>
                    </section>
                )}
            </div>
        </div>
    )
}

