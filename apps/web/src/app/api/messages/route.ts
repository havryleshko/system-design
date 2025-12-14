import { NextResponse } from "next/server"

// TODO: Rebuild messages API route when frontend↔backend wiring is reimplemented
// This route previously used BASE from langgraph utils which was removed as part of wiring reset

export async function POST(req: Request) {
  return NextResponse.json(
    { error: "Messages API route is being rebuilt as part of frontend↔backend wiring redesign" },
    { status: 501 }
  )
}
