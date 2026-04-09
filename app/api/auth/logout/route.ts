import { logoutUserResponse } from "@/app/lib/auth";

export const dynamic = "force-dynamic";

export async function POST() {
  return logoutUserResponse();
}

