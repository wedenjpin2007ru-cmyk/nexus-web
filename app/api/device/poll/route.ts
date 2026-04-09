import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { requestId?: unknown } | null;
  const requestId = typeof body?.requestId === "string" ? body.requestId : "";
  if (!requestId) return NextResponse.json({ error: "Bad request" }, { status: 400 });

  const row = await prisma.deviceAuthRequest.findUnique({
    where: { id: requestId },
    select: {
      expiresAt: true,
      approvedAt: true,
      tokenId: true,
      tokenPlain: true,
      token: { select: { revokedAt: true } },
    },
  });
  if (!row) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (row.expiresAt.getTime() <= Date.now()) {
    return NextResponse.json({ ok: false, status: "expired" });
  }
  if (!row.approvedAt || !row.tokenId) {
    return NextResponse.json({ ok: true, status: "pending" });
  }
  if (!row.token || row.token.revokedAt) {
    return NextResponse.json({ ok: true, status: "revoked" });
  }

  // Return the raw token once, then clear it.
  if (!row.tokenPlain) {
    return NextResponse.json({ ok: true, status: "approved_no_token" });
  }

  await prisma.deviceAuthRequest.update({
    where: { id: requestId },
    data: { tokenPlain: null },
  });

  return NextResponse.json({ ok: true, status: "approved", token: row.tokenPlain });
}

