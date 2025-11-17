'use client'

import { useState, useTransition, type FormEvent, type MouseEvent } from 'react'

import { submitClarifier, backtrackLast } from '../actions'

type ClarifierCardProps = {
  question: string
  fields: string[]
  runId: string | null
  interruptId: string | null
}

export default function ClarifierCard({ question, fields, runId, interruptId }: ClarifierCardProps) {
  const disabled = !runId || !interruptId
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

  const handleBacktrack = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault()
    if (disabled || isPending) return
    setFormError(null)
    startTransition(async () => {
      try {
        await backtrackLast()
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to backtrack. Please try again.'
        setFormError(message)
      }
    })
  }

  return (
    <div className="glass-panel rounded px-5 py-4" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-xs)' }}>
      <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.7)', fontFamily: 'var(--font-space-grotesk)' }}>agent</div>
      <div className="text-sm leading-relaxed" style={{ color: '#ededed', lineHeight: '1.7' }}>{question}</div>

      <form onSubmit={handleSubmit} className="grid" style={{ marginTop: 'var(--spacing-sm)', gap: 'var(--spacing-md)' }}>
        <input type="hidden" name="run_id" value={runId ?? ''} />
        <input type="hidden" name="interrupt_id" value={interruptId ?? ''} />
        {fields.map((name) => (
          <label key={name} className="text-xs" style={{ color: 'rgba(255, 255, 255, 0.8)' }}>
            <span className="mb-1 block text-[10px] uppercase tracking-wider" style={{ color: 'rgba(198, 180, 255, 0.6)' }}>{name}</span>
            <input
              name={name}
              className="w-full rounded border bg-transparent px-3 py-2 text-sm focus:outline-none"
              style={{ borderColor: 'rgba(198, 180, 255, 0.3)', color: '#ededed', caretColor: '#C6B4FF' }}
              placeholder={name}
              disabled={disabled || isPending}
            />
          </label>
        ))}
        {formError && (
          <p className="text-xs" style={{ color: '#ffaaaa' }} role="alert">
            {formError}
          </p>
        )}
        <div className="flex items-center" style={{ marginTop: 'var(--spacing-xs)', gap: 'var(--spacing-sm)' }}>
          <button
            type="submit"
            disabled={disabled || isPending}
            className="border px-4 py-2 text-xs font-medium uppercase tracking-wider transition-all duration-200"
            style={{ 
              borderColor: disabled || isPending ? 'rgba(198, 180, 255, 0.2)' : 'rgba(198, 180, 255, 0.4)',
              background: disabled || isPending ? 'rgba(62, 43, 115, 0.1)' : 'linear-gradient(135deg, rgba(62, 43, 115, 0.3), rgba(198, 180, 255, 0.1))',
              color: disabled || isPending ? 'rgba(198, 180, 255, 0.4)' : '#E0D8FF',
              cursor: disabled || isPending ? 'not-allowed' : 'pointer'
            }}
            onMouseEnter={(e) => {
              if (!disabled && !isPending) {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(62, 43, 115, 0.5), rgba(198, 180, 255, 0.2))';
                e.currentTarget.style.boxShadow = '0 0 20px rgba(198, 180, 255, 0.3)';
              }
            }}
            onMouseLeave={(e) => {
              if (!disabled && !isPending) {
                e.currentTarget.style.background = 'linear-gradient(135deg, rgba(62, 43, 115, 0.3), rgba(198, 180, 255, 0.1))';
                e.currentTarget.style.boxShadow = 'none';
              }
            }}
          >
            {isPending ? 'Submitting…' : 'Submit answers'}
          </button>
          <button
            type="button"
            onClick={handleBacktrack}
            disabled={disabled || isPending}
            className="border px-4 py-2 text-xs uppercase tracking-wider transition-all duration-200"
            style={{ 
              borderColor: disabled || isPending ? 'rgba(198, 180, 255, 0.15)' : 'rgba(198, 180, 255, 0.3)',
              background: 'rgba(198, 180, 255, 0.05)',
              color: disabled || isPending ? 'rgba(198, 180, 255, 0.3)' : 'rgba(198, 180, 255, 0.7)',
              cursor: disabled || isPending ? 'not-allowed' : 'pointer'
            }}
            onMouseEnter={(e) => {
              if (!disabled && !isPending) {
                e.currentTarget.style.background = 'rgba(198, 180, 255, 0.1)';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'rgba(198, 180, 255, 0.05)';
            }}
          >
            Backtrack last turn
          </button>
        </div>
      </form>
    </div>
  )
}


