import Link from "next/link";
import FloatingCard from "./components/floating-card";
import StatusIndicator from "./components/status-indicator";
import AnimatedGrid from "./components/animated-grid";

export default function Home() {
  return (
    <main className="flex-1 relative">
      <AnimatedGrid />
      <div className="mx-auto w-full max-w-4xl px-6 py-14 relative z-10">
        <FloatingCard>
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] backdrop-blur-xl p-8 shadow-2xl">
            <div className="flex flex-col gap-6">
              <div className="flex items-start justify-between gap-6">
                <div className="animate-fade-in">
                  <div className="text-sm text-white/70 tracking-widest">NEXUS</div>
                  <h1 className="mt-2 text-3xl font-semibold tracking-tight bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
                    Быстрый доступ к клиенту по подписке
                  </h1>
                </div>
                <div className="hidden text-right sm:block">
                  <StatusIndicator />
                </div>
              </div>

            <p className="max-w-2xl text-white/75 animate-fade-in-delay-1">
              Зарегистрируй аккаунт, активируй промокод и скачай клиент в
              кабинете. Весь процесс обычно занимает несколько минут.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row animate-fade-in-delay-2">
              <Link
                className="ui-transition inline-flex h-11 items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110 hover:scale-105 active:scale-95 shadow-lg hover:shadow-white/20"
                href="/auth/register"
              >
                Начать
              </Link>
              <Link
                className="ui-transition inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white hover:bg-white/5 hover:border-white/40 hover:scale-105 active:scale-95"
                href="/auth/login"
              >
                Вход
              </Link>
            </div>

            <div className="mt-2 rounded-xl border border-white/10 bg-black/30 p-4 text-sm text-white/70 animate-fade-in-delay-2 ui-transition hover:border-white/20 hover:bg-black/40">
              <div className="text-white/85 flex items-center gap-2">
                <span className="text-lg">ℹ️</span>
                Как получить доступ
              </div>
              <div className="mt-1">
                Промокод выдает администратор/поддержка. После активации код
                сразу откроет скачивание в кабинете.
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 animate-fade-in-delay-3">
              <div className="rounded-xl border border-white/10 bg-black/25 p-4 ui-transition hover:border-white/30 hover:bg-black/40 hover:scale-[1.02] cursor-default">
                <div className="text-sm font-semibold text-white/90">
                  ⚡ Стабильный доступ
                </div>
                <div className="mt-1 text-sm text-white/70">
                  Health-check и стабильный деплой на Railway.
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/25 p-4 ui-transition hover:border-white/30 hover:bg-black/40 hover:scale-[1.02] cursor-default">
                <div className="text-sm font-semibold text-white/90">
                  🚀 Быстрый старт
                </div>
                <div className="mt-1 text-sm text-white/70">
                  Регистрация, промо и загрузка клиента за пару минут.
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/25 p-4 ui-transition hover:border-white/30 hover:bg-black/40 hover:scale-[1.02] cursor-default">
                <div className="text-sm font-semibold text-white/90">
                  💬 Поддержка
                </div>
                <div className="mt-1 text-sm text-white/70">
                  Есть гайд, FAQ и канал связи для быстрых ответов.
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/25 p-4 ui-transition hover:border-white/30 hover:bg-black/40 hover:scale-[1.02] cursor-default">
                <div className="text-sm font-semibold text-white/90">
                  🔒 Безопасность
                </div>
                <div className="mt-1 text-sm text-white/70">
                  Доступ привязан к аккаунту и сроку подписки.
                </div>
              </div>
            </div>
            </div>
          </div>
        </FloatingCard>
      </div>
    </main>
  );
}
