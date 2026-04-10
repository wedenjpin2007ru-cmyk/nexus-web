import { NextResponse } from "next/server";
import { Prisma } from "@prisma/client";
import { prisma } from "@/app/lib/db";
import { getUserFromRequest } from "@/app/lib/auth";

function normalizeCode(code: string) {
  return code.trim().toUpperCase();
}

export async function POST(req: Request) {
  const user = await getUserFromRequest();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await req.json().catch(() => null)) as { code?: unknown } | null;
  const raw = typeof body?.code === "string" ? body.code : "";
  const code = normalizeCode(raw);
  if (code.length < 3 || code.length > 64) {
    return NextResponse.json({ error: "Некорректный промокод" }, { status: 400 });
  }

  const promo = await prisma.promoCode.findUnique({ where: { code } });
  if (!promo || promo.isDisabled) {
    return NextResponse.json({ error: "Промокод не найден" }, { status: 404 });
  }

  const now = new Date();
  if (promo.startsAt && promo.startsAt.getTime() > now.getTime()) {
    return NextResponse.json(
      { error: "Промокод ещё не активен" },
      { status: 400 },
    );
  }
  if (promo.endsAt && promo.endsAt.getTime() <= now.getTime()) {
    return NextResponse.json({ error: "Промокод истёк" }, { status: 400 });
  }
  if (promo.maxRedemptions !== null && promo.maxRedemptions !== undefined) {
    if (promo.redeemedCount >= promo.maxRedemptions) {
      return NextResponse.json(
        { error: "Лимит активаций исчерпан" },
        { status: 400 },
      );
    }
  }

  const already = await prisma.promoRedemption.findUnique({
    where: { promoCodeId_userId: { promoCodeId: promo.id, userId: user.id } },
  });
  if (already) {
    return NextResponse.json({ error: "Уже активировано" }, { status: 400 });
  }

  const currentUser = await prisma.user.findUnique({
    where: { id: user.id },
    select: { subscriptionEndsAt: true },
  });
  if (!currentUser) {
    return NextResponse.json({ error: "Ошибка активации" }, { status: 400 });
  }

  const base =
    currentUser.subscriptionEndsAt &&
    currentUser.subscriptionEndsAt.getTime() > now.getTime()
      ? currentUser.subscriptionEndsAt
      : now;

  const newEndsAt = new Date(
    base.getTime() + promo.durationDays * 24 * 60 * 60 * 1000,
  );

  // maxWait — сколько ждать свободный коннект из пула (по умолчанию 2s → «Unable to start a transaction in the given time»).
  try {
    await prisma.$transaction(
      async (tx) => {
        await tx.promoRedemption.create({
          data: { promoCodeId: promo.id, userId: user.id },
        });
        await tx.promoCode.update({
          where: { id: promo.id },
          data: { redeemedCount: { increment: 1 } },
        });
        await tx.user.update({
          where: { id: user.id },
          data: { subscriptionEndsAt: newEndsAt },
        });
      },
      { maxWait: 25_000, timeout: 25_000 },
    );

    return NextResponse.json({
      ok: true,
      subscriptionEndsAt: newEndsAt.toISOString(),
    });
  } catch (e: unknown) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      return NextResponse.json({ error: "Уже активировано" }, { status: 400 });
    }
    return NextResponse.json({ error: "Ошибка активации" }, { status: 500 });
  }
}

