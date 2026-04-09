import Link from "next/link";
import DeviceApproveForm from "./ui";
import { getUserFromRequest } from "@/app/lib/auth";

type DevicePageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function DevicePage({ searchParams }: DevicePageProps) {
  const user = await getUserFromRequest();
  const sp = searchParams ? await searchParams : {};
  const codeRaw = sp.code;
  const initialCode =
    typeof codeRaw === "string" ? codeRaw.trim().toUpperCase() : "";

  if (!user) {
    return (
      <main className="flex-1">
        <div className="mx-auto w-full max-w-md px-6 py-14">
          <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
            <div className="text-sm text-white/70">NEXUS / DEVICE</div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight">
              Нужен вход
            </h1>
            <div className="mt-6 flex gap-3">
              <Link
                href="/auth/login"
                className="inline-flex h-11 items-center justify-center rounded-xl bg-white px-5 text-sm font-semibold text-black hover:bg-white/90"
              >
                Войти
              </Link>
              <Link
                href="/auth/register"
                className="inline-flex h-11 items-center justify-center rounded-xl border border-white/20 bg-transparent px-5 text-sm font-semibold text-white hover:bg-white/5"
              >
                Регистрация
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-md px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / DEVICE</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Привязать приложение
          </h1>
          <div className="mt-2 text-sm text-white/70">
            Введи код, который показал EXE, чтобы привязать устройство.
          </div>
          <DeviceApproveForm initialCode={initialCode} />
        </div>
      </div>
    </main>
  );
}

