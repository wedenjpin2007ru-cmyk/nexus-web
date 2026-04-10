import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(
    {
      ok: true,
      service: "web",
      uptimeSec: Math.floor(process.uptime()),
      now: new Date().toISOString(),
    },
    { status: 200 },
  );
}
