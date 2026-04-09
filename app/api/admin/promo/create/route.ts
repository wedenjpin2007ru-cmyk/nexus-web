import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

function normalizeCode(code: string) {
  return code.trim().toUpperCase();
}

export async function POST(req: Request) {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as
    | {
        code?: unknown;
        durationDays?: unknown;
        maxRedemptions?: unknown;
        startsAt?: unknown;
        endsAt?: unknown;
      }
    | null;

  const code = normalizeCode(typeof body?.code === "string" ? body.code : "");
  const durationDays =
    typeof body?.durationDays === "number" ? body.durationDays : NaN;
  const maxRedemptions =
    typeof body?.maxRedemptions === "number" ? body.maxRedemptions : null;

  if (!code || code.length < 3 || code.length > 64) {
    return NextResponse.json({ error: "Некорректный code" }, { status: 400 });
  }
  if (!Number.isFinite(durationDays) || durationDays < 1 || durationDays > 3650) {
    return NextResponse.json(
      { error: "Некорректный срок (durationDays)" },
      { status: 400 },
    );
  }
  if (maxRedemptions !== null) {
    if (!Number.isFinite(maxRedemptions) || maxRedemptions < 1 || maxRedemptions > 1_000_000) {
      return NextResponse.json(
        { error: "Некорректный лимит (maxRedemptions)" },
        { status: 400 },
      );
    }
  }

  const startsAt =
    typeof body?.startsAt === "string" && body.startsAt
      ? new Date(body.startsAt)
      : null;
  const endsAt =
    typeof body?.endsAt === "string" && body.endsAt ? new Date(body.endsAt) : null;

  if (startsAt && Number.isNaN(startsAt.getTime())) {
    return NextResponse.json({ error: "Некорректный startsAt" }, { status: 400 });
  }
  if (endsAt && Number.isNaN(endsAt.getTime())) {
    return NextResponse.json({ error: "Некорректный endsAt" }, { status: 400 });
  }
  if (startsAt && endsAt && startsAt.getTime() >= endsAt.getTime()) {
    return NextResponse.json(
      { error: "startsAt должен быть раньше endsAt" },
      { status: 400 },
    );
  }

  try {
    const promo = await prisma.promoCode.create({
      data: {
        code,
        kind: durationDays === 7 ? "TRIAL_7D" : "CUSTOM",
        durationDays,
        maxRedemptions: maxRedemptions ?? undefined,
        startsAt: startsAt ?? undefined,
        endsAt: endsAt ?? undefined,
      },
      select: { id: true, code: true, durationDays: true },
    });
    return NextResponse.json({ ok: true, promo });
  } catch {
    return NextResponse.json(
      { error: "Не удалось создать промокод" },
      { status: 400 },
    );
  }
}

