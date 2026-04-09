/**
 * Подмешивает в DATABASE_URL параметры TLS для облачного Postgres (Prisma / libpq).
 * Вызывать до создания PrismaClient в CJS-скриптах (seed, prisma-sync).
 */
function patchDatabaseUrl() {
  const u = process.env.DATABASE_URL;
  if (!u || typeof u !== "string") return;
  const cloud = /\brlwy\.net\b|railway\.internal|neon\.tech|supabase\.co/i.test(u);
  if (!cloud && process.env.PGSSL_NO_VERIFY !== "1") return;
  if (/[?&]sslmode=/i.test(u)) return;
  const j = u.includes("?") ? "&" : "?";
  const tail =
    process.env.PGSSL_NO_VERIFY === "1"
      ? "sslmode=require&sslaccept=accept_invalid_certs"
      : "sslmode=require";
  process.env.DATABASE_URL = `${u}${j}${tail}`;
}

patchDatabaseUrl();
