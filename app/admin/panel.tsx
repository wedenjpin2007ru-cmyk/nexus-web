"use client";

import { useEffect, useMemo, useState } from "react";

type AdminUser = {
  id: string;
  email: string;
  createdAt: string;
  isBanned: boolean;
  subscriptionEndsAt: string | null;
};

type AdminPromo = {
  id: string;
  code: string;
  kind: string;
  durationDays: number;
  maxRedemptions: number | null;
  redeemedCount: number;
  startsAt: string | null;
  endsAt: string | null;
  isDisabled: boolean;
  createdAt: string;
};

export default function AdminPanel() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersLoading, setUsersLoading] = useState(true);

  const [promos, setPromos] = useState<AdminPromo[]>([]);
  const [promosError, setPromosError] = useState<string | null>(null);
  const [promosLoading, setPromosLoading] = useState(true);

  const [code, setCode] = useState("");
  const [durationDays, setDurationDays] = useState(7);
  const [maxRedemptions, setMaxRedemptions] = useState<number | "">("");
  const [promoError, setPromoError] = useState<string | null>(null);
  const [promoSuccess, setPromoSuccess] = useState<string | null>(null);
  const [promoLoading, setPromoLoading] = useState(false);

  const sortedUsers = useMemo(() => users, [users]);
  const sortedPromos = useMemo(() => promos, [promos]);

  async function loadUsers() {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const res = await fetch("/api/admin/users/list", { cache: "no-store" });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; users?: AdminUser[]; error?: string }
        | null;
      if (!res.ok) {
        setUsersError(data?.error || "Не удалось загрузить пользователей");
        return;
      }
      setUsers(data?.users || []);
    } finally {
      setUsersLoading(false);
    }
  }

  async function loadPromos() {
    setPromosLoading(true);
    setPromosError(null);
    try {
      const res = await fetch("/api/admin/promo/list", { cache: "no-store" });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; promos?: AdminPromo[]; error?: string }
        | null;
      if (!res.ok) {
        setPromosError(data?.error || "Не удалось загрузить промокоды");
        return;
      }
      setPromos(data?.promos || []);
    } finally {
      setPromosLoading(false);
    }
  }

  useEffect(() => {
    void loadUsers();
    void loadPromos();
  }, []);

  async function createPromo(e: React.FormEvent) {
    e.preventDefault();
    setPromoError(null);
    setPromoSuccess(null);
    setPromoLoading(true);
    try {
      const res = await fetch("/api/admin/promo/create", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          code,
          durationDays,
          maxRedemptions: maxRedemptions === "" ? null : maxRedemptions,
        }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; error?: string; promo?: { code: string } }
        | null;
      if (!res.ok) {
        setPromoError(data?.error || "Не удалось создать промокод");
        return;
      }
      setCode("");
      setPromoSuccess(`Создано: ${data?.promo?.code || "OK"}`);
      await loadPromos();
    } finally {
      setPromoLoading(false);
    }
  }

  async function grantDays(userId: string, days: number) {
    await fetch("/api/admin/users/grant-days", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId, days }),
    });
    await loadUsers();
  }

  async function disableSubscription(userId: string) {
    await fetch("/api/admin/users/disable-subscription", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId, ban: false, clearSubscription: true }),
    });
    await loadUsers();
  }

  async function banUser(userId: string, ban: boolean) {
    await fetch("/api/admin/users/disable-subscription", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId, ban, clearSubscription: false }),
    });
    await loadUsers();
  }

  async function togglePromo(promoId: string, disabled: boolean) {
    await fetch("/api/admin/promo/toggle", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ promoId, disabled }),
    });
    await loadPromos();
  }

  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-6xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-sm text-white/70">NEXUS / ADMIN</div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight">
                Панель
              </h1>
            </div>
            <form action="/api/admin/logout" method="post">
              <button className="inline-flex h-10 items-center justify-center rounded-xl border border-white/20 bg-transparent px-4 text-sm font-semibold text-white/85 hover:bg-white/5">
                Выйти
              </button>
            </form>
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <section className="rounded-2xl border border-white/10 bg-black/30 p-6">
              <div className="text-sm text-white/70">Промокоды</div>
              <h2 className="mt-1 text-lg font-semibold">Создать промокод</h2>

              <form className="mt-4 flex flex-col gap-4" onSubmit={createPromo}>
                <label className="flex flex-col gap-2">
                  <div className="text-sm text-white/70">Code</div>
                  <input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
                    placeholder="TRIAL7"
                  />
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <label className="flex flex-col gap-2">
                    <div className="text-sm text-white/70">Дней</div>
                    <input
                      value={durationDays}
                      onChange={(e) => setDurationDays(Number(e.target.value))}
                      type="number"
                      min={1}
                      max={3650}
                      className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none focus:border-white/30"
                    />
                  </label>
                  <label className="flex flex-col gap-2">
                    <div className="text-sm text-white/70">Лимит</div>
                    <input
                      value={maxRedemptions}
                      onChange={(e) =>
                        setMaxRedemptions(
                          e.target.value === "" ? "" : Number(e.target.value),
                        )
                      }
                      type="number"
                      min={1}
                      max={1000000}
                      className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none focus:border-white/30"
                      placeholder="(опц.)"
                    />
                  </label>
                </div>

                {promoError ? (
                  <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                    {promoError}
                  </div>
                ) : null}
                {promoSuccess ? (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                    {promoSuccess}
                  </div>
                ) : null}

                <button
                  disabled={promoLoading}
                  className="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {promoLoading ? "..." : "Создать"}
                </button>
              </form>

              <div className="mt-6 flex items-center justify-between gap-4">
                <div className="text-sm text-white/70">Список промокодов</div>
                <button
                  onClick={() => void loadPromos()}
                  className="inline-flex h-9 items-center justify-center rounded-xl border border-white/20 bg-transparent px-3 text-xs font-semibold text-white/85 hover:bg-white/5"
                >
                  Обновить
                </button>
              </div>

              {promosLoading ? (
                <div className="mt-3 text-sm text-white/60">Загрузка...</div>
              ) : promosError ? (
                <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                  {promosError}
                </div>
              ) : (
                <div className="mt-3 max-h-[260px] overflow-auto rounded-xl border border-white/10">
                  <table className="w-full text-left text-xs">
                    <thead className="sticky top-0 bg-black/60 text-white/60">
                      <tr>
                        <th className="p-2">Code</th>
                        <th className="p-2">Дней</th>
                        <th className="p-2">Used</th>
                        <th className="p-2">Статус</th>
                        <th className="p-2">Действие</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedPromos.map((p) => (
                        <tr key={p.id} className="border-t border-white/10">
                          <td className="p-2 font-semibold">{p.code}</td>
                          <td className="p-2 text-white/75">{p.durationDays}</td>
                          <td className="p-2 text-white/75">
                            {p.redeemedCount}
                            {p.maxRedemptions ? `/${p.maxRedemptions}` : ""}
                          </td>
                          <td className="p-2">
                            {p.isDisabled ? (
                              <span className="rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-1 text-[10px] text-red-100">
                                DISABLED
                              </span>
                            ) : (
                              <span className="rounded-lg border border-white/15 bg-white/[0.03] px-2 py-1 text-[10px] text-white/80">
                                ENABLED
                              </span>
                            )}
                          </td>
                          <td className="p-2">
                            <button
                              onClick={() => void togglePromo(p.id, !p.isDisabled)}
                              className="inline-flex h-8 items-center justify-center rounded-xl border border-white/20 bg-transparent px-3 text-[11px] font-semibold text-white/85 hover:bg-white/5"
                            >
                              {p.isDisabled ? "Enable" : "Disable"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-white/10 bg-black/30 p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm text-white/70">Пользователи</div>
                  <h2 className="mt-1 text-lg font-semibold">Список</h2>
                </div>
                <button
                  onClick={() => void loadUsers()}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-white/20 bg-transparent px-4 text-sm font-semibold text-white/85 hover:bg-white/5"
                >
                  Обновить
                </button>
              </div>

              {usersLoading ? (
                <div className="mt-4 text-sm text-white/60">Загрузка...</div>
              ) : usersError ? (
                <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                  {usersError}
                </div>
              ) : (
                <div className="mt-4 max-h-[520px] overflow-auto rounded-xl border border-white/10">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 bg-black/60 text-xs text-white/60">
                      <tr>
                        <th className="p-3">Email</th>
                        <th className="p-3">Доступ</th>
                        <th className="p-3">Статус</th>
                        <th className="p-3">Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedUsers.map((u) => (
                        <tr
                          key={u.id}
                          className="border-t border-white/10 align-top"
                        >
                          <td className="p-3">
                            <div className="font-semibold">{u.email}</div>
                            <div className="mt-1 text-xs text-white/45">
                              {new Date(u.createdAt).toLocaleString("ru-RU")}
                            </div>
                          </td>
                          <td className="p-3 text-white/75">
                            {u.subscriptionEndsAt
                              ? new Date(u.subscriptionEndsAt).toLocaleString(
                                  "ru-RU",
                                )
                              : "—"}
                          </td>
                          <td className="p-3">
                            {u.isBanned ? (
                              <span className="rounded-lg border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs text-red-100">
                                BANNED
                              </span>
                            ) : (
                              <span className="rounded-lg border border-white/15 bg-white/[0.03] px-2 py-1 text-xs text-white/80">
                                OK
                              </span>
                            )}
                          </td>
                          <td className="p-3">
                            <div className="flex flex-wrap gap-2">
                              <button
                                onClick={() => void grantDays(u.id, 7)}
                                className="inline-flex h-9 items-center justify-center rounded-xl bg-white px-3 text-xs font-semibold text-black hover:bg-white/90"
                              >
                                +7д
                              </button>
                              <button
                                onClick={() => void grantDays(u.id, 30)}
                                className="inline-flex h-9 items-center justify-center rounded-xl border border-white/20 bg-transparent px-3 text-xs font-semibold text-white hover:bg-white/5"
                              >
                                +30д
                              </button>
                              <button
                                onClick={() => void disableSubscription(u.id)}
                                className="inline-flex h-9 items-center justify-center rounded-xl border border-white/20 bg-transparent px-3 text-xs font-semibold text-white/85 hover:bg-white/5"
                              >
                                Off
                              </button>
                              <button
                                onClick={() => void banUser(u.id, !u.isBanned)}
                                className="inline-flex h-9 items-center justify-center rounded-xl border border-white/20 bg-transparent px-3 text-xs font-semibold text-white/85 hover:bg-white/5"
                              >
                                {u.isBanned ? "Unban" : "Ban"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </div>
      </div>
    </main>
  );
}

