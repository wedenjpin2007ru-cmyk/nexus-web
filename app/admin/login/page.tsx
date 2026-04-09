import AdminLoginForm from "./login-form";

export default function AdminLoginPage() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-md px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="text-sm text-white/70">NEXUS / ADMIN</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            Вход в админку
          </h1>
          <AdminLoginForm />
        </div>
      </div>
    </main>
  );
}

