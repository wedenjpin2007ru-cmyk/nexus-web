import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";
import { getUserFromRequest } from "@/app/lib/auth";

const CANDIDATE_EXE_PATHS = [
  path.join(process.cwd(), "downloads", "Nexus.exe"),
  path.join(process.cwd(), "client", "dist", "Nexus.exe"),
];

export async function GET() {
  const user = await getUserFromRequest();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();
  if (!hasAccess) {
    return NextResponse.json({ error: "Subscription expired" }, { status: 403 });
  }

  let buf: Buffer | null = null;
  for (const exePath of CANDIDATE_EXE_PATHS) {
    try {
      buf = await fs.readFile(exePath);
      break;
    } catch {
      /* try next */
    }
  }

  if (!buf) {
    return NextResponse.json(
      {
        error:
          "Файл Nexus.exe не найден на сервере. Собери клиент (client/dist) или положи EXE в папку downloads/.",
      },
      { status: 404 },
    );
  }

  return new NextResponse(buf, {
    headers: {
      "content-type": "application/octet-stream",
      "content-disposition": "attachment; filename=\"Nexus.exe\"",
      "cache-control": "no-store",
    },
  });
}

