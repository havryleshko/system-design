import { NextRequest } from "next/server";

export async function POST(req: Request) {
  try {
    const { content } = await req.json()
    const reply = { role: 'assistant', content: `Echo: ${content}` }
    return new Response(JSON.stringify({ ok: true, reply }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: 'Bad request' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}


export async function GET() {
  return new Response(JSON.stringify({ ok: true, items: [] }), {
    headers: { 'Content-Type': 'application/json' },
  })
}