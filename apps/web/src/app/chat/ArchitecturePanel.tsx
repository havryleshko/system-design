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
            <div className="flex h-screen flex-col border-r border-white/15 bg-black">
                <div className="border-b border-white/15 px-5 py-4">
                    <h2 className="text-sm font-semibold uppercase tracking-wide text-white">Architecture</h2>
                    <p className="mt-1 text-xs text-white/40">System design output</p>
                </div>
                <div className="flex flex-1 items-center justify-center px-6">
                    <p className="text-center text-sm text-white/40">
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
        <div className="flex h-screen flex-col border-r border-white/15 bg-black">
            <div className="border-b border-white/15 px-5 py-4">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-white">Architecture</h2>
                <p className="mt-1 text-xs text-white/40">
                    {elements.length} element{elements.length !== 1 ? 's' : ''} · {relations.length} relation{relations.length !== 1 ? 's' : ''}
                </p>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
                {/* Elements */}
                {elements.length > 0 && (
                    <section>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-white/70">Elements</h3>
                        <div className="space-y-2">
                            {elements.map((el) => (
                                <div key={el.id} className="rounded-md border border-white/20 bg-white/5 px-4 py-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="flex-1">
                                            <div className="text-sm font-medium text-white">{el.label}</div>
                                            <div className="mt-1 text-xs text-white/40">{el.kind}</div>
                                        </div>
                                        {el.technology && (
                                            <span className="rounded bg-white/10 px-2 py-1 text-[10px] uppercase tracking-wide text-white/60">
                                                {el.technology}
                                            </span>
                                        )}
                                    </div>
                                    {el.description && (
                                        <p className="mt-2 text-xs leading-relaxed text-white/60">{el.description}</p>
                                    )}
                                    {el.tags && el.tags.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {el.tags.map((tag, idx) => (
                                                <span key={idx} className="rounded-sm bg-white/5 px-2 py-0.5 text-[10px] text-white/50">
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
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-white/70">Relations</h3>
                        <div className="space-y-2">
                            {relations.map((rel, idx) => (
                                <div key={idx} className="rounded-md border border-white/15 bg-white/5 px-4 py-2.5">
                                    <div className="flex items-center gap-2 text-xs">
                                        <span className="font-medium text-white">{rel.source}</span>
                                        <span className="text-white/40">{rel.direction || '→'}</span>
                                        <span className="font-medium text-white">{rel.target}</span>
                                    </div>
                                    <p className="mt-1.5 text-xs text-white/60">{rel.label}</p>
                                    {rel.technology && (
                                        <span className="mt-2 inline-block rounded bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/60">
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
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-white/70">Groups</h3>
                        <div className="space-y-2">
                            {groups.map((group) => (
                                <div key={group.id} className="rounded-md border border-white/15 bg-white/5 px-4 py-3">
                                    <div className="text-sm font-medium text-white">{group.label}</div>
                                    <div className="mt-1 text-xs text-white/40">{group.kind}</div>
                                    {group.technology && (
                                        <div className="mt-2 text-[10px] uppercase tracking-wide text-white/60">{group.technology}</div>
                                    )}
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        {group.children.map((childId, idx) => (
                                            <span key={idx} className="rounded-sm bg-white/10 px-2 py-1 text-[10px] text-white/70">
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
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-white/70">Notes</h3>
                        <div className="rounded-md border border-white/15 bg-white/5 px-4 py-3">
                            <p className="text-xs leading-relaxed text-white/60">{notes}</p>
                        </div>
                    </section>
                )}
            </div>
        </div>
    )
}

