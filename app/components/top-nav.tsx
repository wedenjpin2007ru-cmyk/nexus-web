"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Главная" },
  { href: "/guide", label: "Гайд" },
  { href: "/status", label: "Status" },
  { href: "/account", label: "Кабинет" },
];

export default function TopNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-black/45 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3">
        <Link
          href="/"
          className="ui-transition text-sm font-semibold tracking-[0.22em] text-white/85 hover:text-white"
        >
          NEXUS
        </Link>

        <nav className="flex items-center gap-2">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`ui-transition inline-flex h-9 items-center justify-center rounded-lg border px-3 text-sm ${
                  active
                    ? "border-[color:var(--accent)] bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                    : "border-white/15 text-white/80 hover:border-white/30 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
          <Link
            href="/auth/login"
            className="ui-transition ml-1 inline-flex h-9 items-center justify-center rounded-lg bg-[color:var(--accent)] px-3 text-sm font-semibold text-black hover:brightness-110"
          >
            Войти
          </Link>
        </nav>
      </div>
    </header>
  );
}
