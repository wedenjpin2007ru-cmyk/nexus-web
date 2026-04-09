import Link from "next/link";
import LoginForm from "./login-form";

export default function LoginPage() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-md px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / LOGIN</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Вход</h1>

          <LoginForm />

          <div className="mt-6 text-sm text-white/70">
            Нет аккаунта?{" "}
            <Link className="text-white underline" href="/auth/register">
              Регистрация
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

