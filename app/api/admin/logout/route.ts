import { logoutAdminResponse } from "@/app/lib/auth";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const cleared = await logoutAdminResponse();
  const redirect = NextResponse.redirect(new URL("/admin/login", request.url), 303);
  for (const cookie of cleared.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  return redirect;
}

