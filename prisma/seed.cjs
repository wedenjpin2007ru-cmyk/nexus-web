const { PrismaClient } = require("@prisma/client");
const { PrismaBetterSqlite3 } = require("@prisma/adapter-better-sqlite3");

const databaseUrl = process.env.DATABASE_URL ?? "file:./dev.db";
const adapter = new PrismaBetterSqlite3({ url: databaseUrl });
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
