import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";

function dbCheckTimeoutMs(): number {
  const raw = process.env.HEALTH_DB_TIMEOUT_MS ?? "10000";
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1000) return 10_000;
  return Math.min(n, 60_000);
}

export async function GET() {
  const base = {
    ok: true as const,
    service: "web",
    uptimeSec: Math.floor(process.uptime()),
    now: new Date().toISOString(),
  };

  const skipDb =
    process.env.HEALTH_SKIP_DB === "1" || process.env.HEALTH_SKIP_DB === "true";
  if (skipDb) {
    return NextResponse.json({ ...base, db: "skipped" }, { status: 200 });
  }

  const ms = dbCheckTimeoutMs();
  try {
    await Promise.race([
      prisma.$queryRaw`SELECT 1`,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`db ping timeout ${ms}ms`)), ms),
      ),
    ]);
    return NextResponse.json({ ...base, db: "ok" }, { status: 200 });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { ...base, ok: false, db: "error", dbError: message },
      { status: 503 },
    );
  }
}
