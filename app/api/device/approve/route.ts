import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { getUserFromRequest, newToken, sha256Hex } from "@/app/lib/auth";

function normalizeCode(code: string) {
  return code.trim().toUpperCase();
}

export async function POST(req: Request) {
  const user = await getUserFromRequest();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as { userCode?: unknown } | null;
  const userCode = normalizeCode(typeof body?.userCode === "string" ? body.userCode : "");
  if (!userCode) return NextResponse.json({ error: "Bad request" }, { status: 400 });

  const row = await prisma.deviceAuthRequest.findUnique({
    where: { userCode },
    select: { id: true, expiresAt: true, approvedAt: true },
  });
  if (!row) return NextResponse.json({ error: "Не найдено" }, { status: 404 });
  if (row.expiresAt.getTime() <= Date.now()) {
    return NextResponse.json({ error: "Код истёк" }, { status: 400 });
  }
  if (row.approvedAt) {
    return NextResponse.json({ error: "Уже подтверждено" }, { status: 400 });
  }

  const token = newToken();
  const tokenHash = sha256Hex(token);

  await prisma.$transaction(async (tx: any) => {
    const apiToken = await tx.apiToken.create({
      data: { userId: user.id, tokenHash },
      select: { id: true },
    });
    await tx.deviceAuthRequest.update({
      where: { id: row.id },
      data: { approvedAt: new Date(), tokenId: apiToken.id, tokenPlain: token },
    });
  });

  return NextResponse.json({ ok: true });
}

