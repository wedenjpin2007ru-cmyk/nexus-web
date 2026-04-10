import Link from "next/link";

export default function GuidePage() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-5xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-sm text-white/70">NEXUS</div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                Гайд по работе с сервисом
              </h1>
            </div>
            <Link
              href="/"
              className="inline-flex h-10 items-center justify-center rounded-lg border border-white/20 px-4 text-sm font-semibold text-white hover:bg-white/5"
            >
              На главную
            </Link>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <section className="rounded-xl border border-white/10 bg-black/30 p-4">
              <h2 className="text-lg text-white/90">Как это работает</h2>
              <p className="mt-2 text-sm text-white/75">
                Создаешь аккаунт, входишь в кабинет, активируешь промокод и
                получаешь доступ к клиенту на срок подписки.
              </p>
            </section>

            <section className="rounded-xl border border-white/10 bg-black/30 p-4">
              <h2 className="text-lg text-white/90">Поддерживаемые браузеры</h2>
              <p className="mt-2 text-sm text-white/75">
                Рекомендуем последние версии Chrome, Edge или Firefox. На
                старых версиях браузеров часть функций может работать хуже.
              </p>
            </section>

            <section className="rounded-xl border border-white/10 bg-black/30 p-4">
              <h2 className="text-lg text-white/90">Какая Windows подходит</h2>
              <p className="mt-2 text-sm text-white/75">
                Оптимально использовать Windows 10/11 x64 с актуальными
                обновлениями. Учетная запись с обычными правами подходит.
              </p>
            </section>

            <section className="rounded-xl border border-white/10 bg-black/30 p-4">
              <h2 className="text-lg text-white/90">Сложно ли запускать</h2>
              <p className="mt-2 text-sm text-white/75">
                Обычно нет: скачиваешь клиент, запускаешь и авторизуешься.
                Весь процесс обычно занимает 2-5 минут.
              </p>
            </section>
          </div>

          <section className="mt-4 rounded-xl border border-white/10 bg-black/30 p-4">
            <h2 className="text-lg text-white/90">Что нужно для старта</h2>
            <ul className="mt-2 space-y-1 text-sm text-white/75">
              <li>- Стабильный интернет.</li>
              <li>- Аккаунт на сайте.</li>
              <li>- Промокод для активации подписки.</li>
            </ul>
          </section>

          <section className="mt-4 rounded-xl border border-white/10 bg-black/30 p-4">
            <h2 className="text-lg text-white/90">Как получить промокод</h2>
            <p className="mt-2 text-sm text-white/75">
              Промокод выдает администратор или поддержка проекта. После
              получения открой кабинет и активируй код в поле ввода промо.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
