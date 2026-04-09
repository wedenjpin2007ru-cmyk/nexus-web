import { NextResponse } from "next/server";
import { destroyUserSession } from "@/app/lib/auth";

export async function POST() {
  await destroyUserSession();
  return NextResponse.json({ ok: true });
}

