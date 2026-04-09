import { NextResponse } from "next/server";
import { getClientIp } from "@/app/lib/client-ip";
import { prisma } from "@/app/lib/db";
import { prismaErrorForClient } from "@/app/lib/prisma-user-error";
import {
  attachUserSessionCookie,
  createUserSessionRecord,
  verifyPassword,
} from "@/app/lib/auth";
import { checkRateLimit } from "@/app/lib/rate-limit";

export const dynamic = "force-dynamic";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export async function POST(req: Request) {
  const ip = getClientIp(req);
  if (ip) {
    const rl = checkRateLimit(`login:${ip}`, { capacity: 8, refillPerSec: 0.2 });
    if (!rl.allowed) {
      return NextResponse.json(
        { error: "Слишком много попыток. Подожди немного." },
        { status: 429 },
      );
    }
  } else if (process.env.NODE_ENV === "production") {
    console.warn(
      "[auth/login] client IP не определён — rate limit по IP отключён для этого запроса",
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

  try {
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

    const session = await createUserSessionRecord(user.id);
    const res = NextResponse.json({ ok: true });
    attachUserSessionCookie(res, session.token, session.expiresAt);
    return res;
  } catch (e) {
    console.error("[auth/login]", e);
    const hint = prismaErrorForClient(e);
    return NextResponse.json(
      {
        error:
          hint ??
          "База недоступна. Проверь DATABASE_URL, Postgres в том же проекте Railway и логи ([prisma-sync], SSL).",
      },
      { status: 500 },
    );
  }
}

