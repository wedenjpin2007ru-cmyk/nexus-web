import { NextResponse } from "next/server";
import { destroyAdminSession } from "@/app/lib/auth";

export async function POST() {
  await destroyAdminSession();
  return NextResponse.json({ ok: true });
}

