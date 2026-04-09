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

# Не задавай здесь DATABASE_URL=file:... и не запускай prisma db push в слое сборки:
# схема Prisma = postgresql, file: даёт P1013. Живой Postgres на этапе build обычно недоступен.
# Синхронизация БД: Railway preDeploy → node scripts/prisma-sync.cjs и при старте → start-prod.cjs.
RUN mkdir -p /app/downloads \
  && (test -f client/dist/Nexus.exe && cp client/dist/Nexus.exe downloads/Nexus.exe || true)

ENV NODE_ENV=production

EXPOSE 3000

CMD ["node", "scripts/start-prod.cjs"]
