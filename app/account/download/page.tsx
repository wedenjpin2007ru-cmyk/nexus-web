import Link from "next/link";
import { getUserFromRequest } from "@/app/lib/auth";

export default async function DownloadPage() {
  const user = await getUserFromRequest();
  if (!user) {
    return (
      <main className="flex-1">
        <div className="mx-auto w-full max-w-md px-6 py-14">
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
            <div className="text-sm text-white/70">NEXUS / DOWNLOAD</div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              Нужен вход
            </h1>
            <div className="mt-6 flex gap-3">
              <Link
                href="/auth/login"
                className="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90"
              >
                Войти
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();

  if (!hasAccess) {
    return (
      <main className="flex-1">
        <div className="mx-auto w-full max-w-md px-6 py-14">
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
            <div className="text-sm text-white/70">NEXUS / DOWNLOAD</div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              Подписка закончилась
            </h1>
            <div className="mt-3 text-sm text-white/70">
              Доступ к скачиванию закрыт. Активируй промокод в кабинете.
            </div>
            <div className="mt-6">
              <Link
                href="/account"
                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white hover:bg-white/5"
              >
                В кабинет
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-md px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / DOWNLOAD</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Скачать
          </h1>
          <div className="mt-3 text-sm text-white/70">
            Доступ активен — выбери способ: готовый EXE или ZIP с запуском без
            сборки (Python + двойной клик).
          </div>
          <div className="mt-6 flex flex-col gap-3">
            <a
              href="/api/download/nexus?v=2026-04-13"
              className="ui-transition inline-flex h-11 w-full items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110"
            >
              Скачать Nexus-2026-04-13.exe
            </a>
            <a
              href="/api/download/nexus-client?v=2026-04-13"
              className="ui-transition inline-flex h-11 w-full items-center justify-center rounded-xl border border-white/25 bg-white/[0.06] px-5 text-sm font-semibold text-white hover:bg-white/10"
            >
              Скачать Nexus-client (ZIP, готовый запуск)
            </a>
          </div>
          <div className="mt-6 space-y-3 text-xs text-white/45">
            <p>
              <span className="text-white/60">EXE:</span> запусти файл — откроется
              привязка устройства один раз, дальше панель с данными подписки.
            </p>
            <p>
              <span className="text-white/60">ZIP:</span> распакуй папку, внутри
              уже прописан адрес этого сайта в{" "}
              <code className="text-white/55">app_url.txt</code>. Установи Python с{" "}
              <span className="text-white/55">python.org</span> (галочка Add to PATH)
              и дважды нажми{" "}
              <code className="text-white/55">NEXUS.vbs</code> или{" "}
              <code className="text-white/55">NEXUS.cmd</code> — откроется панель в
              браузере, без ручной настройки URL.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

