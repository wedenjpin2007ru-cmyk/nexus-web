"use client";

import { useState } from "react";

export default function LogoutButton() {
  const [pending, setPending] = useState(false);

  async function handleLogout() {
    setPending(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
        redirect: "manual",
      });
    } finally {
      window.location.href = "/";
    }
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={pending}
      className="inline-flex h-10 items-center justify-center rounded-xl border border-white/20 bg-transparent px-4 text-sm font-semibold text-white/85 hover:bg-white/5 disabled:opacity-60"
    >
      {pending ? "Выход…" : "Выйти"}
    </button>
  );
}
