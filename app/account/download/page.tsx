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
            Доступ активен — можешь скачать EXE.
          </div>
          <div className="mt-6">
            <a
              href="/api/download/nexus?v=2026-04-13"
                className="ui-transition inline-flex h-11 w-full items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110"
            >
              Скачать Nexus-2026-04-13.exe
            </a>
          </div>
          <div className="mt-6 text-xs text-white/45">
            После запуска EXE откроет страницу `Device` для привязки один раз.
          </div>
        </div>
      </div>
    </main>
  );
}

