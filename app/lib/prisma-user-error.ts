import { Prisma } from "@prisma/client";

/**
 * Безопасное сообщение для пользователя (без утечки внутренних деталей).
 * Возвращает null — показать общий fallback.
 */
export function prismaErrorForClient(e: unknown): string | null {
  const text = e instanceof Error ? e.message : String(e);

  if (e instanceof Prisma.PrismaClientInitializationError) {
    return (
      "Не удаётся подключиться к базе. Проверь, что у веб-сервиса в Railway задана переменная DATABASE_URL " +
      "(Reference на Postgres). Если в логах есть SSL/certificate — добавь PGSSL_NO_VERIFY=1 и перезапусти деплой."
    );
  }

  if (e instanceof Prisma.PrismaClientKnownRequestError) {
    switch (e.code) {
      case "P1000":
      case "P1001":
      case "P1017":
        return (
          "Postgres недоступен или неверный DATABASE_URL. Убедись, что строка подключения ссылается на сервис базы в том же проекте Railway."
        );
      case "P2002":
        return "Такая запись уже есть (например, email занят).";
      case "P2021":
        return null; // обрабатывается отдельно в роуте
      default:
        break;
    }
  }

  if (/certificate|SSL|TLS|self-signed|self signed|EPROTO/i.test(text)) {
    return (
      "Ошибка SSL при подключении к базе. В Variables веб-сервиса добавь PGSSL_NO_VERIFY=1 (значение 1) и сделай Redeploy."
    );
  }

  if (/ECONNREFUSED|ENOTFOUND|getaddrinfo/i.test(text)) {
    return (
      "Сеть не доходит до Postgres (хост/порт из DATABASE_URL). Проверь reference на живой сервис PostgreSQL в Railway."
    );
  }

  return null;
}
