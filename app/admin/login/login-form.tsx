"use client";

import { messageFromApiResponse } from "@/app/lib/api-error-message";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function AdminLoginForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });
      const raw = await res.text();
      if (!res.ok) {
        setError(messageFromApiResponse(res, raw, "Ошибка входа"));
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
        setError("Сервер вернул неожиданный ответ.");
        return;
      }
      router.push("/admin");
      router.refresh();
    } catch {
      setError("Не удалось связаться с сервером.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Логин</div>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="username"
          autoComplete="username"
        />
      </label>

      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Пароль</div>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="current-password"
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="••••••••"
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
        className="mt-2 inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "..." : "Войти"}
      </button>
    </form>
  );
}

