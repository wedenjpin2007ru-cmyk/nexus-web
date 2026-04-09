import { NextResponse } from "next/server";
import { getClientIp } from "@/app/lib/client-ip";
import {
  attachAdminSessionCookie,
  createAdminSessionRecord,
} from "@/app/lib/auth";
import { checkRateLimit } from "@/app/lib/rate-limit";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const ip = getClientIp(req);
  if (ip) {
    const rl = checkRateLimit(`admin_login:${ip}`, { capacity: 6, refillPerSec: 0.1 });
    if (!rl.allowed) {
      return NextResponse.json(
        { error: "Слишком много попыток. Подожди немного." },
        { status: 429 },
      );
    }
  } else if (process.env.NODE_ENV === "production") {
    console.warn(
      "[admin/login] client IP не определён — rate limit по IP отключён для этого запроса",
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

  const expectedUser = (process.env.ADMIN_USERNAME || "").trim();
  const expectedPass = process.env.ADMIN_PASSWORD || "";

  if (!expectedUser || !expectedPass) {
    return NextResponse.json(
      {
        error:
          "Админка не настроена: в Railway → Variables задай ADMIN_USERNAME и ADMIN_PASSWORD (не оставляй пароль пустым).",
      },
      { status: 503 },
    );
  }

  if (username !== expectedUser || password !== expectedPass) {
    return NextResponse.json({ error: "Неверные данные" }, { status: 401 });
  }

  const session = await createAdminSessionRecord();
  const res = NextResponse.json({ ok: true });
  attachAdminSessionCookie(res, session.token, session.expiresAt);
  return res;
}

