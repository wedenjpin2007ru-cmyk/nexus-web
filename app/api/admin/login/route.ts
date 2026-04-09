import { NextResponse } from "next/server";
import { createAdminSession } from "@/app/lib/auth";
import { checkRateLimit } from "@/app/lib/rate-limit";

export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "ip:local";
  const rl = checkRateLimit(`admin_login:${ip}`, { capacity: 6, refillPerSec: 0.1 }); // ~6 then 1 per 10s
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "Слишком много попыток. Подожди немного." },
      { status: 429 },
    );
  }

  const body = (await req.json().catch(() => null)) as
    | { username?: unknown; password?: unknown }
    | null;

  const username = typeof body?.username === "string" ? body.username.trim() : "";
  const password = typeof body?.password === "string" ? body.password : "";

  if (!username || !password) {
    return NextResponse.json({ error: "Неверные данные" }, { status: 400 });
  }

  const expectedUser = process.env.ADMIN_USERNAME || "";
  const expectedPass = process.env.ADMIN_PASSWORD || "";

  if (username !== expectedUser || password !== expectedPass) {
    return NextResponse.json({ error: "Неверные данные" }, { status: 401 });
  }

  await createAdminSession();
  return NextResponse.json({ ok: true });
}

