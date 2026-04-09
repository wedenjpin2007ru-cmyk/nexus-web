import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

export async function GET() {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const promos = await prisma.promoCode.findMany({
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      code: true,
      kind: true,
      durationDays: true,
      maxRedemptions: true,
      redeemedCount: true,
      startsAt: true,
      endsAt: true,
      isDisabled: true,
      createdAt: true,
    },
    take: 200,
  });

  return NextResponse.json({ ok: true, promos });
}

