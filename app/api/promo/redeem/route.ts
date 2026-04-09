import { NextResponse } from "next/server";
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

  try {
    const result = await prisma.$transaction(async (tx) => {
      const already = await tx.promoRedemption.findUnique({
        where: { promoCodeId_userId: { promoCodeId: promo.id, userId: user.id } },
      });
      if (already) {
        return { ok: false as const, error: "Уже активировано" };
      }

      const currentUser = await tx.user.findUnique({
        where: { id: user.id },
        select: { subscriptionEndsAt: true },
      });
      if (!currentUser) return { ok: false as const, error: "User not found" };

      const base =
        currentUser.subscriptionEndsAt &&
        currentUser.subscriptionEndsAt.getTime() > now.getTime()
          ? currentUser.subscriptionEndsAt
          : now;

      const newEndsAt = new Date(
        base.getTime() + promo.durationDays * 24 * 60 * 60 * 1000,
      );

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

      return { ok: true as const, subscriptionEndsAt: newEndsAt };
    });

    if (!result.ok) {
      return NextResponse.json({ error: result.error }, { status: 400 });
    }

    return NextResponse.json({
      ok: true,
      subscriptionEndsAt: result.subscriptionEndsAt.toISOString(),
    });
  } catch {
    return NextResponse.json({ error: "Ошибка активации" }, { status: 500 });
  }
}

