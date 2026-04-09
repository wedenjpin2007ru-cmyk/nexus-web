import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { createUserSession, verifyPassword } from "@/app/lib/auth";
import { checkRateLimit } from "@/app/lib/rate-limit";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "ip:local";
  const rl = checkRateLimit(`login:${ip}`, { capacity: 8, refillPerSec: 0.2 }); // ~8 requests then 1 per 5s
  if (!rl.allowed) {
    return NextResponse.json(
      { error: "Слишком много попыток. Подожди немного." },
      { status: 429 },
    );
  }

  const body = (await req.json().catch(() => null)) as
    | { email?: unknown; password?: unknown }
    | null;

  const email = typeof body?.email === "string" ? body.email.trim() : "";
  const password = typeof body?.password === "string" ? body.password : "";

  if (!isValidEmail(email) || !password) {
    return NextResponse.json(
      { error: "Неверный email или пароль" },
      { status: 400 },
    );
  }

  const user = await prisma.user.findUnique({ where: { email } });
  if (!user || user.isBanned) {
    return NextResponse.json(
      { error: "Неверный email или пароль" },
      { status: 401 },
    );
  }

  const ok = await verifyPassword(password, user.passwordHash);
  if (!ok) {
    return NextResponse.json(
      { error: "Неверный email или пароль" },
      { status: 401 },
    );
  }

  await createUserSession(user.id);
  return NextResponse.json({ ok: true });
}

