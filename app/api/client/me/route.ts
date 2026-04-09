import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { sha256Hex } from "@/app/lib/auth";

export async function GET(req: Request) {
  const auth = req.headers.get("authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice("Bearer ".length).trim() : "";
  if (!token) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const tokenHash = sha256Hex(token);
  const t = await prisma.apiToken.findUnique({
    where: { tokenHash },
    select: { revokedAt: true, user: { select: { id: true, isBanned: true, subscriptionEndsAt: true } } },
  });
  if (!t || t.revokedAt) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (t.user.isBanned) return NextResponse.json({ error: "Banned" }, { status: 403 });

  await prisma.apiToken.update({
    where: { tokenHash },
    data: { lastUsedAt: new Date() },
  });

  const hasAccess =
    t.user.subscriptionEndsAt && t.user.subscriptionEndsAt.getTime() > Date.now();

  return NextResponse.json({
    ok: true,
    hasAccess,
    subscriptionEndsAt: t.user.subscriptionEndsAt?.toISOString() ?? null,
  });
}

