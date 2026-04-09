import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

export async function GET() {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const users = await prisma.user.findMany({
    orderBy: { createdAt: "desc" },
    select: {
      id: true,
      email: true,
      createdAt: true,
      isBanned: true,
      subscriptionEndsAt: true,
    },
    take: 200,
  });

  return NextResponse.json({ ok: true, users });
}

