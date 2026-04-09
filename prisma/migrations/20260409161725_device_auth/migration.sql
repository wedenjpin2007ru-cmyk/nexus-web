-- CreateTable
CREATE TABLE "ApiToken" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "revokedAt" DATETIME,
    "lastUsedAt" DATETIME,
    CONSTRAINT "ApiToken_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DeviceAuthRequest" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "userCode" TEXT NOT NULL,
    "tokenId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" DATETIME NOT NULL,
    "approvedAt" DATETIME,
    CONSTRAINT "DeviceAuthRequest_tokenId_fkey" FOREIGN KEY ("tokenId") REFERENCES "ApiToken" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "ApiToken_tokenHash_key" ON "ApiToken"("tokenHash");

-- CreateIndex
CREATE INDEX "ApiToken_userId_idx" ON "ApiToken"("userId");

-- CreateIndex
CREATE INDEX "ApiToken_revokedAt_idx" ON "ApiToken"("revokedAt");

-- CreateIndex
CREATE UNIQUE INDEX "DeviceAuthRequest_userCode_key" ON "DeviceAuthRequest"("userCode");

-- CreateIndex
CREATE INDEX "DeviceAuthRequest_expiresAt_idx" ON "DeviceAuthRequest"("expiresAt");
