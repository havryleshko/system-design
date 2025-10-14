import { NextResponse } from "next/server"
import { BASE } from "@/utils/langgraph"

export async function POST(req: Request) {
  const body = await req.json()
  const content = typeof body?.input === "string" && body.input.trim().length > 0
    ? body.input
    : typeof body?.content === "string"
      ? body.content
      : ""

  const r = await fetch(`${BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input: content }),
  })

  const json = await r.json()
  return NextResponse.json(json, { status: r.status })
}
