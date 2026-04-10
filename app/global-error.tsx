"use client";

import Link from "next/link";
import "./globals.css";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-black text-white font-mono">
        <main className="mx-auto w-full max-w-3xl px-6 py-14">
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
            <div className="text-sm text-white/70">NEXUS / 500</div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">
              Внутренняя ошибка
            </h1>
            <p className="mt-3 text-sm text-white/75">
              Что-то пошло не так. Попробуй перезагрузить страницу.
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={reset}
                className="ui-transition inline-flex h-11 items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110"
              >
                Повторить
              </button>
              <Link
                href="/"
                className="ui-transition inline-flex h-11 items-center justify-center rounded-xl border border-white/20 px-5 text-sm font-semibold text-white/85 hover:bg-white/5"
              >
                На главную
              </Link>
            </div>
          </div>
        </main>
      </body>
    </html>
  );
}
