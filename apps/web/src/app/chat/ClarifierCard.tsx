'use client'

import { useState, useTransition, type FormEvent } from 'react'

import { submitClarifier } from '../actions'

type ClarifierCardProps = {
  question: string
  runId: string | null
  interruptId: string | null
  threadId: string | null
}

export default function ClarifierCard({ question, runId, interruptId, threadId }: ClarifierCardProps) {
  const disabled = !runId || !interruptId || !threadId
  const [formError, setFormError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (disabled || isPending) return
    const form = event.currentTarget
    const formData = new FormData(form)
    setFormError(null)
    startTransition(async () => {
      try {
        await submitClarifier(formData)
        form.reset()
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to submit answers. Please try again.'
        setFormError(message)
      }
    })
  }

  return (
    <div className="glass-panel rounded px-5 py-4" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xs)' }}>
      <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--foreground-muted)', fontFamily: 'var(--font-ibm-plex-mono)' }}>agent</div>
      <div className="text-sm leading-relaxed" style={{ color: 'var(--foreground)', lineHeight: '1.7' }}>{question}</div>

      <form onSubmit={handleSubmit} className="grid" style={{ marginTop: 'var(--spacing-sm)', gap: 'var(--spacing-md)' }}>
        <input type="hidden" name="run_id" value={runId ?? ''} />
        <input type="hidden" name="interrupt_id" value={interruptId ?? ''} />
        <input type="hidden" name="thread_id" value={threadId ?? ''} />
        <label className="text-xs" style={{ color: 'rgba(255, 255, 255, 0.8)' }}>
          <span className="mb-1 block text-[10px] uppercase tracking-wider" style={{ color: 'var(--foreground-muted)' }}>Your answer</span>
          <textarea
            name="answer"
            className="w-full rounded border bg-transparent px-3 py-2 text-sm focus:outline-none resize-none"
            style={{ borderColor: 'var(--border)', color: 'var(--foreground)', caretColor: 'var(--accent)', minHeight: '96px' }}
            placeholder="Provide any extra detail the agent needs"
            disabled={disabled || isPending}
            required
          />
        </label>
        {formError && (
          <p
            className="text-xs"
            style={{ color: '#ffaaaa', whiteSpace: 'pre-wrap' }}
            role="alert"
          >
            {formError}
          </p>
        )}
        <div className="flex items-center" style={{ marginTop: 'var(--spacing-xs)', gap: 'var(--spacing-sm)' }}>
          <button
            type="submit"
            disabled={disabled || isPending}
            className="border px-4 py-2 text-xs font-medium uppercase tracking-wider transition-all duration-200"
            style={{ 
              borderColor: disabled || isPending ? 'var(--border)' : 'var(--accent)',
              background: disabled || isPending ? 'rgba(35, 37, 47, 0.1)' : 'var(--surface)',
              color: disabled || isPending ? 'var(--foreground-muted)' : 'var(--accent)',
              cursor: disabled || isPending ? 'not-allowed' : 'pointer'
            }}
            onMouseEnter={(e) => {
              if (!disabled && !isPending) {
                e.currentTarget.style.background = 'var(--accent)';
                e.currentTarget.style.color = 'var(--surface)';
                e.currentTarget.style.boxShadow = '0 0 20px rgba(154, 182, 194, 0.2)';
              }
            }}
            onMouseLeave={(e) => {
              if (!disabled && !isPending) {
                e.currentTarget.style.background = 'var(--surface)';
                e.currentTarget.style.color = 'var(--accent)';
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
          >
            {isPending ? 'Submitting…' : 'Submit answers'}
          </button>
        </div>
      </form>
    </div>
  )
}
