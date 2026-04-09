/**
 * Клиентский IP за reverse proxy (Railway, Cloudflare, nginx и т.д.).
 * Без заголовков возвращает null — нельзя подставлять один общий ключ (ломает лимиты).
 */
export function getClientIp(req: Request): string | null {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) {
    const first = xff.split(",")[0]?.trim();
    if (first) return first;
  }
  for (const name of [
    "x-real-ip",
    "cf-connecting-ip",
    "true-client-ip",
    "fastly-client-ip",
  ] as const) {
    const v = req.headers.get(name)?.trim();
    if (v) return v;
  }
  return null;
}
