import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
  pgAdapter?: PrismaPg;
};

const connectionString =
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@localhost:5432/nexus";

/**
 * node-pg + облачный Postgres: часто нужен TLS, а в URL нет sslmode=require.
 * Включаем смягчённый TLS для типичных хостов Railway/Neon/Supabase и по явным флагам.
 */
const useRelaxedTls =
  process.env.PGSSL_NO_VERIFY === "1" ||
  /[?&]sslmode=(require|prefer)/i.test(connectionString) ||
  /\brlwy\.net\b|railway\.internal|neon\.tech|supabase\.co|pooler\.supabase/i.test(
    connectionString,
  );

const adapter =
  globalForPrisma.pgAdapter ??
  new PrismaPg({
    connectionString,
    ...(useRelaxedTls ? { ssl: { rejectUnauthorized: false } } : {}),
  });

if (process.env.NODE_ENV !== "production") globalForPrisma.pgAdapter = adapter;

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
  });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
