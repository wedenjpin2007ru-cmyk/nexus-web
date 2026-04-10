const { spawnSync } = require("child_process");
const path = require("path");

const nextBin = require.resolve("next/dist/bin/next");
const port = process.env.PORT || "3000";
const prismaSync = path.join(__dirname, "prisma-sync.cjs");

const shouldRunSyncOnStart =
  process.env.RUN_DB_SYNC_ON_START === "1" ||
  process.env.RUN_DB_SYNC_ON_START === "true";

if (shouldRunSyncOnStart) {
  console.log("[start-prod] RUN_DB_SYNC_ON_START enabled, running prisma-sync");
  const syncResult = spawnSync(process.execPath, [prismaSync], {
    stdio: "inherit",
    env: process.env,
  });
  if (syncResult.status !== 0) {
    process.exit(typeof syncResult.status === "number" ? syncResult.status : 1);
  }
} else {
  console.log(
    "[start-prod] skip prisma-sync on boot (preDeploy should handle schema/seed)",
  );
}

console.log(`[start-prod] next start on 0.0.0.0:${port}`);
const result = spawnSync(process.execPath, [nextBin, "start", "-H", "0.0.0.0", "-p", port], {
  stdio: "inherit",
  env: process.env,
});

process.exit(typeof result.status === "number" ? result.status : 1);
