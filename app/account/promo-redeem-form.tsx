"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function PromoRedeemForm() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function onRedeem(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      const res = await fetch("/api/promo/redeem", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; error?: string; subscriptionEndsAt?: string }
        | null;
      if (!res.ok) {
        setError(data?.error || "Не удалось активировать");
        return;
      }
      setCode("");
      setSuccess(
        data?.subscriptionEndsAt
          ? `Готово. Доступ до ${new Date(data.subscriptionEndsAt).toLocaleString(
              "ru-RU",
            )}`
          : "Готово",
      );
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="mt-3" onSubmit={onRedeem}>
      <div className="flex gap-3">
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="h-11 flex-1 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="Введите промокод"
        />
        <button
          disabled={loading}
          className="ui-transition inline-flex h-11 items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "..." : "Активировать"}
        </button>
      </div>

      {error ? (
        <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          {success}
        </div>
      ) : null}
    </form>
  );
}

