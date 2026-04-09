import bcrypt from "bcrypt";
import crypto from "crypto";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { prisma } from "./db";

const USER_SESSION_COOKIE = "nexus_session";
const ADMIN_SESSION_COOKIE = "nexus_admin_session";

export function sha256Hex(input: string) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

export async function hashPassword(password: string) {
  return bcrypt.hash(password, 12);
}

export async function verifyPassword(password: string, passwordHash: string) {
  return bcrypt.compare(password, passwordHash);
}

export function newToken() {
  return crypto.randomBytes(32).toString("hex");
}

function sessionCookieBase() {
  return {
    httpOnly: true as const,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  };
}

/** Запись сессии в БД; cookie вешаем через attachUserSessionCookie на NextResponse (иначе в проде часто не уходит Set-Cookie). */
export async function createUserSessionRecord(userId: string) {
  const token = newToken();
  const tokenHash = sha256Hex(token);
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 24 * 30);
  await prisma.userSession.create({
    data: { userId, tokenHash, expiresAt },
  });
  return { token, expiresAt };
}

export function attachUserSessionCookie(
  res: NextResponse,
  token: string,
  expiresAt: Date,
) {
  res.cookies.set(USER_SESSION_COOKIE, token, {
    ...sessionCookieBase(),
    expires: expiresAt,
  });
}

export async function logoutUserResponse(): Promise<NextResponse> {
  const jar = await cookies();
  const token = jar.get(USER_SESSION_COOKIE)?.value;
  if (token) {
    await prisma.userSession.deleteMany({
      where: { tokenHash: sha256Hex(token) },
    });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(USER_SESSION_COOKIE, "", {
    ...sessionCookieBase(),
    expires: new Date(0),
  });
  return res;
}

export async function getUserFromRequest() {
  const jar = await cookies();
  const token = jar.get(USER_SESSION_COOKIE)?.value;
  if (!token) return null;

  const tokenHash = sha256Hex(token);
  const session = await prisma.userSession.findUnique({
    where: { tokenHash },
    include: { user: true },
  });
  if (!session) return null;
  if (session.expiresAt.getTime() <= Date.now()) return null;
  if (session.user.isBanned) return null;

  return session.user;
}

export async function createAdminSessionRecord() {
  const token = newToken();
  const tokenHash = sha256Hex(token);
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 12);
  await prisma.adminSession.create({ data: { tokenHash, expiresAt } });
  return { token, expiresAt };
}

export function attachAdminSessionCookie(
  res: NextResponse,
  token: string,
  expiresAt: Date,
) {
  res.cookies.set(ADMIN_SESSION_COOKIE, token, {
    ...sessionCookieBase(),
    expires: expiresAt,
  });
}

export async function isAdminRequest() {
  const jar = await cookies();
  const token = jar.get(ADMIN_SESSION_COOKIE)?.value;
  if (!token) return false;
  const tokenHash = sha256Hex(token);
  const session = await prisma.adminSession.findUnique({ where: { tokenHash } });
  if (!session) return false;
  if (session.expiresAt.getTime() <= Date.now()) return false;
  return true;
}

export async function logoutAdminResponse(): Promise<NextResponse> {
  const jar = await cookies();
  const token = jar.get(ADMIN_SESSION_COOKIE)?.value;
  if (token) {
    await prisma.adminSession.deleteMany({
      where: { tokenHash: sha256Hex(token) },
    });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(ADMIN_SESSION_COOKIE, "", {
    ...sessionCookieBase(),
    expires: new Date(0),
  });
  return res;
}
