"use client";

import Link from "next/link";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / ERROR</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Что-то пошло не так
          </h1>
          <p className="mt-3 text-sm text-white/75">
            Ошибка временная. Попробуй повторить или вернуться на главную.
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
      </div>
    </main>
  );
}
