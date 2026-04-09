import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

export async function POST(req: Request) {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as
    | { userId?: unknown; days?: unknown }
    | null;

  const userId = typeof body?.userId === "string" ? body.userId : "";
  const days = typeof body?.days === "number" ? body.days : NaN;

  if (!userId || !Number.isFinite(days) || days < 1 || days > 3650) {
    return NextResponse.json({ error: "Bad request" }, { status: 400 });
  }

  const now = new Date();
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { subscriptionEndsAt: true },
  });
  if (!user) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const base =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > now.getTime()
      ? user.subscriptionEndsAt
      : now;
  const subscriptionEndsAt = new Date(
    base.getTime() + days * 24 * 60 * 60 * 1000,
  );

  await prisma.user.update({
    where: { id: userId },
    data: { subscriptionEndsAt, isBanned: false },
  });

  return NextResponse.json({ ok: true, subscriptionEndsAt: subscriptionEndsAt.toISOString() });
}

