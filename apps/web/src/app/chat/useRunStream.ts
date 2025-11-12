'use client'

import { useEffect, useRef } from 'react'

export type NormalizedStreamEvent =
  | { type: 'message-delta'; text: string }
  | { type: 'message-completed' }
  | { type: 'node-started'; node: string }
  | { type: 'node-completed'; node: string; tokens?: number }
  | { type: 'values-updated'; values: Record<string, unknown> }
  | { type: 'run-completed' }
  | { type: 'error'; message: string }
  | { type: 'raw'; event: string; data: unknown }

type OpenArgs = {
  threadId: string
  runId: string
  mode?: string
  onEvent: (evt: NormalizedStreamEvent) => void
  maxRetries?: number
  retryDelayMs?: number
}

export function openRunStream({ threadId, runId, mode, onEvent, maxRetries = 3, retryDelayMs = 1000 }: OpenArgs) {
  const params = new URLSearchParams()
  params.set('run_id', runId)
  params.set('mode', mode || 'messages,values,timeline')

  let es: EventSource | null = null
  let retries = 0

  const parseJson = (data: string): unknown => {
    try {
      return JSON.parse(data)
    } catch {
      return data
    }
  }

  const attach = () => {
    es = new EventSource(`/api/langgraph/threads/${threadId}/stream?${params.toString()}`)

    // Fallback generic handler
    es.onmessage = (e: MessageEvent<string>) => {
      const payload = parseJson(e.data)
      onEvent({ type: 'raw', event: 'message', data: payload })
    }

  const forward = (name: string) => (e: MessageEvent<string>) => {
    const data = parseJson(e.data)
    // Normalize a few common event shapes
    if (name === 'messages.delta') {
      const dataObj = typeof data === 'object' && data !== null ? data as Record<string, unknown> : null
      const text = typeof data === 'string' ? data : (typeof dataObj?.text === 'string' ? dataObj.text : '')
      if (text) onEvent({ type: 'message-delta', text: String(text) })
      else onEvent({ type: 'raw', event: name, data })
      return
    }
    if (name === 'messages.completed') {
      onEvent({ type: 'message-completed' })
      return
    }
    if (name === 'node.started') {
      const dataObj = typeof data === 'object' && data !== null ? data as Record<string, unknown> : null
      const node = typeof dataObj?.node === 'string' ? dataObj.node : (typeof dataObj?.name === 'string' ? dataObj.name : '')
      if (node) onEvent({ type: 'node-started', node })
      else onEvent({ type: 'raw', event: name, data })
      return
    }
    if (name === 'node.completed') {
      const dataObj = typeof data === 'object' && data !== null ? data as Record<string, unknown> : null
      const node = typeof dataObj?.node === 'string' ? dataObj.node : (typeof dataObj?.name === 'string' ? dataObj.name : '')
      const tokens = typeof dataObj?.total_tokens === 'number' ? dataObj.total_tokens : undefined
      if (node) onEvent({ type: 'node-completed', node, tokens })
      else onEvent({ type: 'raw', event: name, data })
      return
    }
    if (name === 'values.updated' || name === 'values') {
      const dataObj = typeof data === 'object' && data !== null ? data as Record<string, unknown> : null
      const values = dataObj?.values ?? (typeof data === 'object' && data !== null ? (data as Record<string, unknown>) : {})
      onEvent({ type: 'values-updated', values: (values as Record<string, unknown>) || {} })
      return
    }
    if (name === 'run.completed') {
      onEvent({ type: 'run-completed' })
      return
    }
    onEvent({ type: 'raw', event: name, data })
  }

  // Likely event names used by LangGraph servers
  const names = [
    'messages.delta',
    'messages.completed',
    'node.started',
    'node.completed',
    'values.updated',
    'values',
    'run.completed',
  ]
    names.forEach((n) => es!.addEventListener(n, forward(n)))

    es.onerror = () => {
      onEvent({ type: 'error', message: 'Stream connection error' })
      if (retries < maxRetries) {
        retries += 1
        const delay = retryDelayMs * Math.pow(2, retries - 1)
        es?.close()
        es = null
        setTimeout(() => attach(), delay)
      }
    }
  }

  attach()

  return {
    close: () => es?.close(),
    source: es,
  }
}

type HookArgs = {
  active: boolean
  threadId?: string | null
  runId?: string | null
  onEvent: (evt: NormalizedStreamEvent) => void
}

export function useRunStream({ active, threadId, runId, onEvent }: HookArgs) {
  const ref = useRef<{ close: () => void } | null>(null)

  useEffect(() => {
    if (!active || !threadId || !runId) return
    const h = openRunStream({ threadId, runId, onEvent })
    ref.current = h
    return () => {
      h.close()
      ref.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, threadId, runId])
}


