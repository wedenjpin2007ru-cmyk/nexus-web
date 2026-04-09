import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";

function randomCode() {
  // 8 chars, readable
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let out = "";
  for (let i = 0; i < 8; i++) out += alphabet[Math.floor(Math.random() * alphabet.length)];
  return out;
}

export async function POST() {
  const expiresAt = new Date(Date.now() + 1000 * 60 * 10); // 10 min

  // try a few times to avoid collisions
  for (let i = 0; i < 5; i++) {
    const userCode = randomCode();
    try {
      const reqRow = await prisma.deviceAuthRequest.create({
        data: { userCode, expiresAt },
        select: { id: true, userCode: true, expiresAt: true },
      });
      return NextResponse.json({
        ok: true,
        requestId: reqRow.id,
        userCode: reqRow.userCode,
        expiresAt: reqRow.expiresAt.toISOString(),
      });
    } catch {
      // collision, retry
    }
  }

  return NextResponse.json({ error: "Try again" }, { status: 500 });
}

