require("../scripts/patch-database-url.cjs");

const { PrismaClient } = require("@prisma/client");
const { PrismaPg } = require("@prisma/adapter-pg");

const connectionString =
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@localhost:5432/nexus";

const useRelaxedTls =
  process.env.PGSSL_NO_VERIFY === "1" ||
  /[?&]sslmode=(require|prefer)/i.test(connectionString) ||
  /\brlwy\.net\b|railway\.internal|neon\.tech|supabase\.co|pooler\.supabase/i.test(
    connectionString,
  );

const adapter = new PrismaPg({
  connectionString,
  ...(useRelaxedTls ? { ssl: { rejectUnauthorized: false } } : {}),
});

const prisma = new PrismaClient({ adapter });

async function main() {
  await prisma.promoCode.upsert({
    where: { code: "NEXUS7" },
    create: {
      code: "NEXUS7",
      kind: "TRIAL_7D",
      durationDays: 7,
      redeemedCount: 0,
      isDisabled: false,
    },
    update: { isDisabled: false },
  });

  await prisma.promoCode.upsert({
    where: { code: "DEMO3" },
    create: {
      code: "DEMO3",
      kind: "CUSTOM",
      durationDays: 3,
      redeemedCount: 0,
      isDisabled: false,
    },
    update: { isDisabled: false },
  });
}

main()
  .then(() => {
    console.log("Seed OK: NEXUS7 (+7 дней), DEMO3 (+3 дня)");
  })
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
