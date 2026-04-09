import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { createUserSession, hashPassword } from "@/app/lib/auth";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function dayKey(d: Date) {
  return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "ip:local";
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

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    return NextResponse.json(
      { error: "Email уже зарегистрирован" },
      { status: 409 },
    );
  }

  // anti-abuse: limit registrations per IP per day
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

  const passwordHash = await hashPassword(password);
  const user = await prisma.user.create({
    data: { email, passwordHash },
    select: { id: true },
  });

  await createUserSession(user.id);
  return NextResponse.json({ ok: true });
}

