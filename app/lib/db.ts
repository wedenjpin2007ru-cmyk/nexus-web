import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";
import type { PoolConfig } from "pg";

const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
  pgAdapter?: PrismaPg;
};

const connectionString =
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@localhost:5432/nexus";

const useRelaxedTls =
  process.env.PGSSL_NO_VERIFY === "1" ||
  /[?&]sslmode=(require|prefer)/i.test(connectionString) ||
  /\brlwy\.net\b|railway\.internal|neon\.tech|supabase\.co|pooler\.supabase/i.test(
    connectionString,
  );

function poolMax(): number {
  const raw = process.env.PG_POOL_MAX ?? "5";
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1) return 5;
  return Math.min(n, 20);
}

/** Не держать запрос вечно: иначе Railway отдаёт 502, пока ждёт upstream. */
function connectionTimeoutMillis(): number {
  const raw = process.env.PG_CONNECTION_TIMEOUT_MS ?? "20000";
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n) || n < 1000) return 20000;
  return Math.min(n, 120000);
}

function createAdapter(): PrismaPg {
  const poolConfig: PoolConfig = {
    connectionString,
    max: poolMax(),
    connectionTimeoutMillis: connectionTimeoutMillis(),
    idleTimeoutMillis: 30_000,
  };
  if (useRelaxedTls) {
    poolConfig.ssl = { rejectUnauthorized: false };
  }
  return new PrismaPg(poolConfig);
}

const adapter = globalForPrisma.pgAdapter ?? createAdapter();
if (!globalForPrisma.pgAdapter) {
  globalForPrisma.pgAdapter = adapter;
}

const prismaClient =
  globalForPrisma.prisma ??
  new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
  });

if (!globalForPrisma.prisma) {
  globalForPrisma.prisma = prismaClient;
}

export const prisma = prismaClient;
