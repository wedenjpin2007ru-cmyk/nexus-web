import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

export async function POST(req: Request) {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as
    | { userId?: unknown; ban?: unknown; clearSubscription?: unknown }
    | null;

  const userId = typeof body?.userId === "string" ? body.userId : "";
  const ban = typeof body?.ban === "boolean" ? body.ban : false;
  const clearSubscription =
    typeof body?.clearSubscription === "boolean" ? body.clearSubscription : true;

  if (!userId) {
    return NextResponse.json({ error: "userId required" }, { status: 400 });
  }

  await prisma.user.update({
    where: { id: userId },
    data: {
      isBanned: ban,
      subscriptionEndsAt: clearSubscription ? null : undefined,
    },
  });

  return NextResponse.json({ ok: true });
}

