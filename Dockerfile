# Собственный образ: Nixpacks на Railway оставался на Node 20.18, Prisma 7.7 требует 20.19+ / 22.12+.
FROM node:22-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    openssl \
  && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
# postinstall → prisma generate нужен schema до npm ci
COPY prisma ./prisma
COPY prisma.config.ts ./

RUN npm ci

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# SQLite в образе + стартовые промокоды (NEXUS7, DEMO3). На Railway повесь volume на /app/data, чтобы база не сбрасывалась.
ENV DATABASE_URL=file:/app/data/app.db
RUN mkdir -p /app/data /app/downloads \
  && npx prisma db push \
  && node prisma/seed.cjs \
  && (test -f client/dist/Nexus.exe && cp client/dist/Nexus.exe downloads/Nexus.exe || true)

ENV NODE_ENV=production

EXPOSE 3000

CMD ["node", "scripts/start-prod.cjs"]
