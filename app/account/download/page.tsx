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
            Скачать клиент
          </h1>
          <p className="mt-3 text-sm text-white/70">
            Один файл — всё внутри. После установки подписки на сайте скачай EXE и
            следуй шагам ниже.
          </p>
          <div className="mt-6">
            <a
              href="/api/download/nexus?v=2026-04-11"
              className="ui-transition inline-flex h-11 w-full items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110"
            >
              Скачать Nexus-2026-04-11.exe
            </a>
          </div>
          <ol className="mt-8 list-decimal space-y-3 pl-5 text-sm text-white/65">
            <li>
              Запусти <span className="text-white/85">Nexus.exe</span> — откроется
              страница привязки устройства на этом сайте.
            </li>
            <li>
              Подтверди вход в браузере (один раз на этот ПК).
            </li>
            <li>
              Откроется панель: статус подписки (есть / нет), почта, до какой даты
              действует.
            </li>
            <li>
              В панели — <span className="text-white/85">запуск сценария</span>{" "}
              (только при активной подписке), кнопка{" "}
              <span className="text-white/85">кабинет на сайте</span> и{" "}
              <span className="text-white/85">выход</span>.
            </li>
          </ol>
          <p className="mt-6 text-xs text-white/40">
            Без подписки панель покажет, что доступа нет, и не даст ничего
            запустить — сначала активируй промокод в кабинете.
          </p>
        </div>
      </div>
    </main>
  );
}
