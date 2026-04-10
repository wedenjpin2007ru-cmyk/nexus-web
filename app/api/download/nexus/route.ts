import { NextResponse } from "next/server";
import path from "path";
import fs from "fs/promises";
import { getUserFromRequest } from "@/app/lib/auth";

const DOWNLOAD_EXE_PATH = path.join(
  /*turbopackIgnore: true*/ process.cwd(),
  "downloads",
  "Nexus.exe",
);
const DOWNLOAD_VERSION = "2026-04-13";

export async function GET() {
  const user = await getUserFromRequest();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();
  if (!hasAccess) {
    return NextResponse.json({ error: "Subscription expired" }, { status: 403 });
  }

  let buf: Buffer | null = null;
  try {
    buf = await fs.readFile(/*turbopackIgnore: true*/ DOWNLOAD_EXE_PATH);
  } catch {
    buf = null;
  }

  if (!buf) {
    return NextResponse.json(
      {
        error: "Файл Nexus.exe не найден на сервере (ожидается в папке downloads/).",
      },
      { status: 404 },
    );
  }

  return new NextResponse(new Uint8Array(buf) as BodyInit, {
    headers: {
      "content-type": "application/octet-stream",
      "content-disposition": `attachment; filename="Nexus-${DOWNLOAD_VERSION}.exe"`,
      "cache-control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      pragma: "no-cache",
      expires: "0",
      "x-nexus-download-version": DOWNLOAD_VERSION,
    },
  });
}

