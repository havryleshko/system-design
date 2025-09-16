import { NextResponse } from "next/server";

const BASE = process.env.BACKEND_URL!;

export async function POST(req: Request) {
  const body = await req.json();       
  const r = await fetch(`${BASE}/runs`, { 
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input: body?.input ?? "" }),
    
  });
  const json = await r.json();
  return NextResponse.json(json, { status: r.status }); 
}
