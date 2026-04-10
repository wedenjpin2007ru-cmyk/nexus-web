import { logoutUserResponse } from "@/app/lib/auth";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const cleared = await logoutUserResponse();
  const redirect = NextResponse.redirect(new URL("/", request.url), 303);
  for (const cookie of cleared.cookies.getAll()) {
    redirect.cookies.set(cookie);
  }
  return redirect;
}

