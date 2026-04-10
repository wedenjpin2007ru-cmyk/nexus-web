"use client";

import { useState } from "react";
import { messageFromApiResponse } from "@/app/lib/api-error-message";

export default function RegisterForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      const raw = await res.text();
      if (!res.ok) {
        setError(messageFromApiResponse(res, raw, "Ошибка регистрации"));
        return;
      }
      let ok = false;
      try {
        const data = JSON.parse(raw) as { ok?: boolean };
        ok = data?.ok === true;
      } catch {
        ok = false;
      }
      if (!ok) {
        setError("Сервер вернул неожиданный ответ после регистрации.");
        return;
      }
      window.location.assign("/account");
      return;
    } catch {
      setError(
        "Не удалось связаться с сервером. Проверь интернет или попробуй позже.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Email</div>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          autoComplete="email"
          required
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none ring-0 placeholder:text-white/30 focus:border-white/30"
          placeholder="you@example.com"
        />
      </label>

      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Пароль</div>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="new-password"
          required
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="минимум 8 символов"
        />
      </label>

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={loading}
        className="ui-transition mt-2 inline-flex h-11 items-center justify-center rounded-xl bg-[color:var(--accent)] px-5 text-sm font-semibold text-black hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Создаём..." : "Создать аккаунт"}
      </button>
    </form>
  );
}

