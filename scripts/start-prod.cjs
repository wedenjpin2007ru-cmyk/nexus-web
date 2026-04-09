const { spawnSync } = require("child_process");

const nextBin = require.resolve("next/dist/bin/next");
const port = process.env.PORT || "3000";

const result = spawnSync(process.execPath, [nextBin, "start", "-H", "0.0.0.0", "-p", port], {
  stdio: "inherit",
  env: process.env,
});

process.exit(typeof result.status === "number" ? result.status : 1);
