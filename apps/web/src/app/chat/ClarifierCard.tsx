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
    <div className="space-y-2 border border-white/15 bg-white/5 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-white/40">agent</div>
      <div className="text-sm leading-relaxed text-white">{question}</div>

      <form onSubmit={handleSubmit} className="mt-2 grid gap-3">
        <input type="hidden" name="run_id" value={runId ?? ''} />
        <input type="hidden" name="interrupt_id" value={interruptId ?? ''} />
        {fields.map((name) => (
          <label key={name} className="text-xs text-white/70">
            <span className="mb-1 block text-[10px] uppercase tracking-wide text-white/40">{name}</span>
            <input
              name={name}
              className="w-full rounded-sm border border-white/15 bg-transparent px-2 py-1 text-sm text-white placeholder:text-white/40 focus:outline-none"
              placeholder={name}
              disabled={disabled || isPending}
            />
          </label>
        ))}
        {formError && (
          <p className="text-xs text-red-300" role="alert">
            {formError}
          </p>
        )}
        <div className="mt-1 flex items-center gap-2">
          <button
            type="submit"
            disabled={disabled || isPending}
            className="border border-white px-3 py-1.5 text-xs uppercase tracking-wide text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-white/30 disabled:text-white/40 disabled:hover:bg-transparent disabled:hover:text-white/40"
          >
            {isPending ? 'Submitting…' : 'Submit answers'}
          </button>
          <button
            type="button"
            onClick={handleBacktrack}
            disabled={disabled || isPending}
            className="border border-white/40 px-3 py-1.5 text-xs uppercase tracking-wide text-white/80 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:border-white/20 disabled:text-white/30"
          >
            Backtrack last turn
          </button>
        </div>
      </form>
    </div>
  )
}


