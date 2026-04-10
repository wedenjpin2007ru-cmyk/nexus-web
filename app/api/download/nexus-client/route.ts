import path from "path";
import fs from "fs/promises";
import { PassThrough } from "node:stream";
import { buffer } from "node:stream/consumers";
import archiver from "archiver";
import { NextResponse } from "next/server";
import { getUserFromRequest } from "@/app/lib/auth";

const CLIENT_ROOT = path.join(process.cwd(), "client");
const ZIP_ROOT = "Nexus-client";
const DOWNLOAD_VERSION = "2026-04-13";

/** Файлы для ZIP: без exe, app_url.txt кладём динамически под домен сайта. */
const CLIENT_FILES = [
  "nexus_client.py",
  "run_panel_demo.py",
  "requirements.txt",
  "NEXUS.cmd",
  "NEXUS.vbs",
  "start_panel_demo.cmd",
  "start_panel_demo.ps1",
  "ЗАПУСК.txt",
] as const;

function siteBaseUrl(req: Request): string {
  const env = process.env.NEXT_PUBLIC_APP_URL?.trim();
  const host =
    req.headers.get("x-forwarded-host")?.split(",")[0]?.trim() ||
    req.headers.get("host")?.trim() ||
    "";
  const proto =
    req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() || "https";
  if (host) {
    return `${proto}://${host}`.replace(/\/$/, "");
  }
  if (env) {
    return env.replace(/\/$/, "");
  }
  return "https://nexus-web-production-13f1.up.railway.app";
}

async function buildZip(baseUrl: string): Promise<Buffer> {
  const archive = archiver("zip", { zlib: { level: 9 } });
  const pass = new PassThrough();
  archive.pipe(pass);
  const bufPromise = buffer(pass);

  for (const name of CLIENT_FILES) {
    const full = path.join(CLIENT_ROOT, name);
    const data = await fs.readFile(full);
    archive.append(data, { name: `${ZIP_ROOT}/${name}` });
  }
  archive.append(Buffer.from(`${baseUrl}\n`, "utf8"), {
    name: `${ZIP_ROOT}/app_url.txt`,
  });

  await archive.finalize();
  return bufPromise;
}

export async function GET(req: Request) {
  const user = await getUserFromRequest();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();
  if (!hasAccess) {
    return NextResponse.json({ error: "Subscription expired" }, { status: 403 });
  }

  const baseUrl = siteBaseUrl(req);

  let zip: Buffer;
  try {
    zip = await buildZip(baseUrl);
  } catch (e) {
    console.error("nexus-client zip:", e);
    return NextResponse.json(
      {
        error:
          "Не удалось собрать архив клиента. Проверь, что папка client/ есть в деплое.",
      },
      { status: 500 },
    );
  }

  const filename = `Nexus-client-${DOWNLOAD_VERSION}.zip`;
  return new NextResponse(new Uint8Array(zip) as BodyInit, {
    headers: {
      "content-type": "application/zip",
      "content-disposition": `attachment; filename="${filename}"`,
      "cache-control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      pragma: "no-cache",
      expires: "0",
      "x-nexus-download-version": DOWNLOAD_VERSION,
    },
  });
}
