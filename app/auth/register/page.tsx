import Link from "next/link";
import RegisterForm from "./register-form";

export default function RegisterPage() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-md px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / REGISTER</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Регистрация
          </h1>

          <RegisterForm />

          <div className="mt-6 text-sm text-white/70">
            Уже есть аккаунт?{" "}
            <Link className="text-white underline" href="/auth/login">
              Войти
            </Link>
          </div>

          <div className="mt-8 text-xs text-white/45">
            После регистрации ты попадёшь в кабинет, где можно активировать
            промокод.
          </div>
        </div>
      </div>
    </main>
  );
}

