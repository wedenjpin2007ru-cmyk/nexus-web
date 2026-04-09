import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Prisma 7 + pg-адаптер: не бандлить в Turbopack (иначе в Docker «Can't resolve @prisma/adapter-pg»).
  serverExternalPackages: ["@prisma/adapter-pg", "pg"],
};

export default nextConfig;
