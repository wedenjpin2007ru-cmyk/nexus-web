/**
 * Создаёт таблицы в Postgres (prisma db push) и seed.
 * Вызывается из start-prod.cjs и из Railway preDeployCommand.
 */
require("./patch-database-url.cjs");

const { spawnSync } = require("child_process");

const prismaCli = require.resolve("prisma/build/index.js");
const env = process.env;

const dbUrl = (env.DATABASE_URL || "").trim();
if (env.NODE_ENV === "production") {
  if (!dbUrl || dbUrl.startsWith("file:")) {
    console.error(
      "[prisma-sync] Нужен PostgreSQL в DATABASE_URL.\n" +
        "Railway: Variables веб-сервиса → DATABASE_URL → Reference на Postgres.",
    );
    process.exit(1);
  }
}

function runStep(label, args) {
  console.log(`[prisma-sync] ${label}…`);
  const result = spawnSync(process.execPath, [prismaCli, ...args], {
    stdio: "inherit",
    env,
  });
  const code = typeof result.status === "number" ? result.status : 1;
  if (code !== 0) {
    console.error(`[prisma-sync] ${label} failed (${code})`);
    process.exit(code);
  }
}

runStep("db push", ["db", "push"]);
runStep("db seed", ["db", "seed"]);
console.log("[prisma-sync] OK");
process.exit(0);
