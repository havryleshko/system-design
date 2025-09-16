'use client'

import {useState} from 'react'

export default function ChatClient({
    userId,
    initialMessages
}: {
    userId: string | null
    initialMessages: { role: 'user'|'assistant'|'system'; content: string }[]
}) {
    const [messages, setMessages] = useState(initialMessages)
    const [input, setInput] = useState('')
    async function send() {
        if (!input) return
        const res = await fetch('/api/messages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: input }) })
        if (!res.ok) {
        console.error('Request failed', res.status)
        return
        }
        const data = await res.json()
        setMessages((m) => [...m, {role: 'user', content: input }, data.reply])
        setInput('')
    }
    return (
        <div className="max-w-2xl mx-auto p-4 space-y-3">
            <div className="border rounded p-3 h-80 overflow-auto">
                {messages.map((m, i) => <div key={i}><b>{m.role}:</b> {m.content}</div>)}
            </div>
            <div className="flex gap-2">
                <input className="flex-1 border rounded p-2" value={input} onChange={(e) => setInput(e.target.value)}/>
                <button className="px-3 py-2 bg-blue-600 text-white rounded" onClick={send}>Send</button>
                </div>   
            </div>
    )
}

