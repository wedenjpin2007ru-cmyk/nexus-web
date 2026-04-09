"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const LAST_LOGIN_EMAIL_KEY = "nexus_last_login_email";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const savedEmail = window.localStorage.getItem(LAST_LOGIN_EMAIL_KEY);
    if (savedEmail) {
      setEmail(savedEmail);
    }
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; error?: string }
        | null;
      if (!res.ok) {
        setError(data?.error || "Ошибка входа");
        return;
      }
      window.localStorage.setItem(LAST_LOGIN_EMAIL_KEY, email.trim());
      router.push("/account");
      router.refresh();
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
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="you@example.com"
        />
      </label>

      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Пароль</div>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="current-password"
          required
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
        {loading ? "Входим..." : "Войти"}
      </button>
    </form>
  );
}

