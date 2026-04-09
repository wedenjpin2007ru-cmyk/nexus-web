-- CreateTable
CREATE TABLE "IpRegistration" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ip" TEXT NOT NULL,
    "day" TEXT NOT NULL,
    "count" INTEGER NOT NULL DEFAULT 0,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE INDEX "IpRegistration_ip_idx" ON "IpRegistration"("ip");

-- CreateIndex
CREATE UNIQUE INDEX "IpRegistration_ip_day_key" ON "IpRegistration"("ip", "day");
