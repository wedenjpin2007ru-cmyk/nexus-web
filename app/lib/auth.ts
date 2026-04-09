import bcrypt from "bcrypt";
import crypto from "crypto";
import { cookies } from "next/headers";
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

export async function setCookie(name: string, value: string, expires: Date) {
  const jar = await cookies();
  jar.set({
    name,
    value,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires,
  });
}

export async function clearCookie(name: string) {
  const jar = await cookies();
  jar.set({
    name,
    value: "",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(0),
  });
}

export async function createUserSession(userId: string) {
  const token = newToken();
  const tokenHash = sha256Hex(token);
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 24 * 30); // 30d

  await prisma.userSession.create({
    data: { userId, tokenHash, expiresAt },
  });

  await setCookie(USER_SESSION_COOKIE, token, expiresAt);
  return { token, expiresAt };
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

export async function destroyUserSession() {
  const jar = await cookies();
  const token = jar.get(USER_SESSION_COOKIE)?.value;
  await clearCookie(USER_SESSION_COOKIE);
  if (!token) return;
  await prisma.userSession.deleteMany({ where: { tokenHash: sha256Hex(token) } });
}

export async function createAdminSession() {
  const token = newToken();
  const tokenHash = sha256Hex(token);
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60 * 12); // 12h

  await prisma.adminSession.create({ data: { tokenHash, expiresAt } });
  await setCookie(ADMIN_SESSION_COOKIE, token, expiresAt);
  return { token, expiresAt };
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

export async function destroyAdminSession() {
  const jar = await cookies();
  const token = jar.get(ADMIN_SESSION_COOKIE)?.value;
  await clearCookie(ADMIN_SESSION_COOKIE);
  if (!token) return;
  await prisma.adminSession.deleteMany({
    where: { tokenHash: sha256Hex(token) },
  });
}

