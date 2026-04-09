import { Prisma } from "@prisma/client";
import { NextResponse } from "next/server";
import { getClientIp } from "@/app/lib/client-ip";
import { prisma } from "@/app/lib/db";
import {
  attachUserSessionCookie,
  createUserSessionRecord,
  hashPassword,
} from "@/app/lib/auth";

export const dynamic = "force-dynamic";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function dayKey(d: Date) {
  return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

export async function POST(req: Request) {
  const ip = getClientIp(req);
  const today = dayKey(new Date());

  const body = (await req.json().catch(() => null)) as
    | { email?: unknown; password?: unknown }
    | null;

  const email = typeof body?.email === "string" ? body.email.trim() : "";
  const password = typeof body?.password === "string" ? body.password : "";

  if (!isValidEmail(email)) {
    return NextResponse.json({ error: "Некорректный email" }, { status: 400 });
  }
  if (password.length < 8) {
    return NextResponse.json(
      { error: "Пароль минимум 8 символов" },
      { status: 400 },
    );
  }

  try {
    const existing = await prisma.user.findUnique({ where: { email } });
    if (existing) {
      return NextResponse.json(
        { error: "Email уже зарегистрирован" },
        { status: 409 },
      );
    }

    if (ip) {
      const ipRow = await prisma.ipRegistration.upsert({
        where: { ip_day: { ip, day: today } },
        create: { ip, day: today, count: 1 },
        update: { count: { increment: 1 } },
        select: { count: true },
      });
      if (ipRow.count > 3) {
        return NextResponse.json(
          { error: "Лимит регистраций с этого IP на сегодня исчерпан" },
          { status: 429 },
        );
      }
    } else if (process.env.NODE_ENV === "production") {
      console.warn(
        "[auth/register] client IP не определён — дневной лимит по IP пропущен (проверь прокси / X-Forwarded-For)",
      );
    }

    const passwordHash = await hashPassword(password);
    const user = await prisma.user.create({
      data: { email, passwordHash },
      select: { id: true },
    });

    const session = await createUserSessionRecord(user.id);
    const res = NextResponse.json({ ok: true });
    attachUserSessionCookie(res, session.token, session.expiresAt);
    return res;
  } catch (e) {
    console.error("[auth/register]", e);
    const missingTables =
      (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2021") ||
      /TableDoesNotExist|does not exist in the current database|P2021/i.test(
        e instanceof Error ? e.message : String(e),
      );
    if (missingTables) {
      return NextResponse.json(
        {
          error:
            "База без таблиц: дождись успешного деплоя (в логах должны быть строки [prisma-sync]) или в Railway отключи кастомный Start Command — должен быть node scripts/start-prod.cjs.",
        },
        { status: 503 },
      );
    }
    return NextResponse.json(
      {
        error:
          "Не удалось записать в базу. Проверь Postgres, DATABASE_URL и логи деплоя.",
      },
      { status: 500 },
    );
  }
}

