import Link from "next/link";
import { getUserFromRequest } from "@/app/lib/auth";
import PromoRedeemForm from "./promo-redeem-form";

function formatDate(dt: Date) {
  return new Intl.DateTimeFormat("ru-RU", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(dt);
}

export default async function AccountPage() {
  const user = await getUserFromRequest();
  if (!user) {
    return (
      <main className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 py-14">
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
            <div className="text-sm text-white/70">NEXUS / ACCOUNT</div>
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
              <Link
                href="/auth/register"
                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white hover:bg-white/5"
              >
                Регистрация
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const hasAccess =
    user.subscriptionEndsAt && user.subscriptionEndsAt.getTime() > Date.now();

  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-3xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-sm text-white/70">NEXUS / ACCOUNT</div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight">
                Аккаунт
              </h1>
              <div className="mt-2 text-sm text-white/70">{user.email}</div>
            </div>
            <form action="/api/auth/logout" method="post">
              <button className="inline-flex h-10 items-center justify-center rounded-xl border border-white/20 bg-transparent px-4 text-sm font-semibold text-white/85 hover:bg-white/5">
                Выйти
              </button>
            </form>
          </div>

          <div className="mt-8 grid gap-4">
            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/70">Статус подписки</div>
              <div className="mt-1 text-lg font-semibold">
                {hasAccess ? "ACTIVE" : "INACTIVE"}
              </div>
              <div className="mt-1 text-sm text-white/70">
                {user.subscriptionEndsAt
                  ? `до ${formatDate(user.subscriptionEndsAt)}`
                  : "нет данных"}
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/70">Промокод</div>
              <PromoRedeemForm />
            </div>

            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/70">Скачивание</div>
              <div className="mt-2 text-sm text-white/70">
                {hasAccess
                  ? "Подписка активна. Можно скачать клиент."
                  : "Сначала активируй подписку, чтобы открыть скачивание."}
              </div>
              <div className="mt-4">
                <Link
                  href={hasAccess ? "/account/download" : "/account"}
                  className={`inline-flex h-11 items-center justify-center rounded-xl px-5 text-sm font-semibold ${
                    hasAccess
                      ? "bg-white text-black hover:bg-white/90"
                      : "cursor-not-allowed border border-white/20 bg-transparent text-white/50"
                  }`}
                  aria-disabled={!hasAccess}
                >
                  {hasAccess ? "Открыть скачивание" : "Скачивание недоступно"}
                </Link>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-sm text-white/70">Купить</div>
              <div className="mt-2 text-sm text-white/70">
                Оплата пока отключена. Доступ выдаётся промокодом или вручную.
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

