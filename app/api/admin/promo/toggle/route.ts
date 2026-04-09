import { NextResponse } from "next/server";
import { prisma } from "@/app/lib/db";
import { isAdminRequest } from "@/app/lib/auth";

export async function POST(req: Request) {
  const ok = await isAdminRequest();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as
    | { promoId?: unknown; disabled?: unknown }
    | null;

  const promoId = typeof body?.promoId === "string" ? body.promoId : "";
  const disabled = typeof body?.disabled === "boolean" ? body.disabled : null;

  if (!promoId || disabled === null) {
    return NextResponse.json({ error: "Bad request" }, { status: 400 });
  }

  await prisma.promoCode.update({
    where: { id: promoId },
    data: { isDisabled: disabled },
  });

  return NextResponse.json({ ok: true });
}

