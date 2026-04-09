"use client";

import { useState } from "react";

type DeviceApproveFormProps = {
  initialCode?: string;
};

export default function DeviceApproveForm({
  initialCode = "",
}: DeviceApproveFormProps) {
  const [userCode, setUserCode] = useState(initialCode.toUpperCase());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setOk(false);
    setLoading(true);
    try {
      const res = await fetch("/api/device/approve", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ userCode }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; error?: string }
        | null;
      if (!res.ok) {
        setError(data?.error || "Ошибка");
        return;
      }
      setOk(true);
      setUserCode("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="mt-6 flex flex-col gap-4" onSubmit={onSubmit}>
      <label className="flex flex-col gap-2">
        <div className="text-sm text-white/70">Код</div>
        <input
          value={userCode}
          onChange={(e) => setUserCode(e.target.value.toUpperCase())}
          className="h-11 rounded-xl border border-white/15 bg-black/40 px-4 text-white outline-none placeholder:text-white/30 focus:border-white/30"
          placeholder="XXXXXXXX"
        />
      </label>

      {error ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}
      {ok ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          Готово. Теперь вернись в EXE — он продолжит.
        </div>
      ) : null}

      <button
        disabled={loading}
        className="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "..." : "Подтвердить"}
      </button>
    </form>
  );
}

