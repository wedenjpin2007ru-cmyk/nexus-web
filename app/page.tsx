import Link from "next/link";

export default function Home() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-4xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="flex flex-col gap-6">
            <div className="flex items-start justify-between gap-6">
              <div>
                <div className="text-sm text-white/70">NEXUS</div>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                  Доступ к скрипту по подписке
                </h1>
              </div>
              <div className="hidden text-right text-sm text-white/60 sm:block">
                <div>status: online</div>
                <div>mode: mono</div>
              </div>
            </div>

            <p className="max-w-2xl text-white/75">
              Зарегистрируйся, зайди в аккаунт и активируй промокод — получишь
              доступ на время действия подписки (например, 7 дней trial).
            </p>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                className="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90"
                href="/auth/register"
              >
                Регистрация
              </Link>
              <Link
                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white hover:bg-white/5"
                href="/auth/login"
              >
                Вход
              </Link>
              <Link
                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white/80 hover:bg-white/5"
                href="/account"
              >
                Кабинет
              </Link>
            </div>

            <div className="mt-2 rounded-xl border border-white/10 bg-black/30 p-4 text-sm text-white/70">
              <div className="text-white/85">Подсказка</div>
              <div className="mt-1">
                Если промокода нет — в кабинете будет заглушка “оплата скоро /
                связаться с админом”.
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/35 p-4 text-sm text-white/75">
              <div className="text-base text-white/90">Краткий гайд</div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                  <div className="text-white/90">Как это работает</div>
                  <p className="mt-1 text-white/70">
                    Регистрируешь аккаунт, заходишь в кабинет, активируешь
                    промокод и получаешь доступ к загрузке клиента на срок
                    подписки.
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                  <div className="text-white/90">Браузеры</div>
                  <p className="mt-1 text-white/70">
                    Рекомендуем Chrome, Edge или Firefox последних версий.
                    Safari и мобильные браузеры могут работать нестабильно.
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                  <div className="text-white/90">Windows</div>
                  <p className="mt-1 text-white/70">
                    Оптимально: Windows 10/11 x64 с обновлениями и обычными
                    правами пользователя.
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/30 p-3">
                  <div className="text-white/90">Насколько сложно запустить</div>
                  <p className="mt-1 text-white/70">
                    Обычно легко: скачать клиент, запустить файл и авторизоваться.
                    В среднем занимает 2-5 минут.
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/30 p-3 sm:col-span-2">
                  <div className="text-white/90">Что нужно и как получить промо</div>
                  <p className="mt-1 text-white/70">
                    Нужны интернет, рабочий аккаунт и промокод. Промокод
                    выдаёт администратор/поддержка проекта; после получения
                    активируй его в кабинете в поле ввода промо.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-10 text-xs text-white/50">
          © {new Date().getFullYear()} Nexus
        </footer>
      </div>
    </main>
  );
}
