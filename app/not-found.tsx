import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / 404</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Страница не найдена
          </h1>
          <p className="mt-3 max-w-xl text-sm text-white/75">
            Возможно, ссылка устарела или была введена с ошибкой.
          </p>
          <div className="mt-6 flex gap-3">
            <Link
              href="/"
              className="ui-transition inline-flex h-11 items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110"
            >
              Вернуться на главную
            </Link>
            <Link
              href="/guide"
              className="ui-transition inline-flex h-11 items-center justify-center rounded-xl border border-white/20 px-5 text-sm font-semibold text-white/85 hover:bg-white/5"
            >
              Открыть гайд
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
