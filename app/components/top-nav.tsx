import Link from "next/link";
import { getUserFromRequest } from "@/app/lib/auth";

const navItems = [
  { href: "/", label: "Главная" },
  { href: "/guide#faq", label: "FAQ" },
  { href: "/guide#support", label: "Контакты поддержки" },
  { href: "/account", label: "Кабинет" },
];

export default async function TopNav() {
  const user = await getUserFromRequest();

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
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="ui-transition inline-flex h-9 items-center justify-center rounded-lg border border-white/15 px-3 text-sm text-white/80 hover:border-white/30 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
          {!user ? (
            <Link
              href="/auth/login"
              className="ui-transition ml-1 inline-flex h-9 items-center justify-center rounded-lg bg-[color:var(--accent)] px-3 text-sm font-semibold text-black hover:brightness-110"
            >
              Войти
            </Link>
          ) : null}
        </nav>
      </div>
    </header>
  );
}
