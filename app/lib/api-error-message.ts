/** Разбор тела ответа API для показа в формах (клиентский код). */
export function messageFromApiResponse(
  res: Response,
  rawBody: string,
  fallbackLabel: string,
): string {
  try {
    const data = JSON.parse(rawBody) as { error?: unknown };
    if (typeof data?.error === "string" && data.error.trim()) {
      return data.error.trim();
    }
  } catch {
    /* не JSON */
  }
  const t = rawBody.trim();
  if (t.length > 0 && !t.startsWith("<")) {
    return t.length > 400 ? `${t.slice(0, 400)}…` : t;
  }
  return `${fallbackLabel} (HTTP ${res.status})`;
}
