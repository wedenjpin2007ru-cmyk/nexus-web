import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";
import { getUserFromRequest } from "@/app/lib/auth";

export async function GET() {
  const user = await getUserFromRequest();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();
  if (!hasAccess) {
    return NextResponse.json({ error: "Subscription expired" }, { status: 403 });
  }

  const exePath = path.join(process.cwd(), "downloads", "Nexus.exe");
  const buf = await fs.readFile(exePath);

  return new NextResponse(buf, {
    headers: {
      "content-type": "application/octet-stream",
      "content-disposition": "attachment; filename=\"Nexus.exe\"",
      "cache-control": "no-store",
    },
  });
}

