import Link from "next/link";

export const dynamic = "force-dynamic";

function fmtUptime(totalSec: number) {
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${h}h ${m}m ${s}s`;
}

export default async function StatusPage() {
  const health = {
    ok: true,
    uptimeSec: Math.floor(process.uptime()),
    now: new Date().toISOString(),
  };
  const deploySha =
    process.env.RAILWAY_GIT_COMMIT_SHA ||
    process.env.VERCEL_GIT_COMMIT_SHA ||
    "unknown";
  const deployAt = process.env.RAILWAY_DEPLOYMENT_ID || "unknown";

  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-4xl px-6 py-14">
        <div className="rounded-2xl border border-white/15 bg-white/[0.03] p-8">
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="text-sm text-white/70">NEXUS / STATUS</div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                Состояние сервиса
              </h1>
            </div>
            <span
              className={`inline-flex h-9 items-center rounded-full border px-4 text-sm ${
                health?.ok
                  ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200"
                  : "border-amber-400/40 bg-amber-400/10 text-amber-200"
              }`}
            >
              {health?.ok ? "ONLINE" : "DEGRADED"}
            </span>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-xs text-white/60">API Health</div>
              <div className="mt-1 text-lg font-semibold text-white/90">
                {health?.ok ? "ok" : "check required"}
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-xs text-white/60">Uptime</div>
              <div className="mt-1 text-lg font-semibold text-white/90">
                {typeof health?.uptimeSec === "number"
                  ? fmtUptime(health.uptimeSec)
                  : "unknown"}
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-xs text-white/60">Last API Time</div>
              <div className="mt-1 text-sm text-white/85">
                {health?.now
                  ? new Date(health.now).toLocaleString("ru-RU")
                  : "unknown"}
              </div>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="text-xs text-white/60">Deploy</div>
              <div className="mt-1 text-sm text-white/85">
                <div>sha: {deploySha.slice(0, 8)}</div>
                <div>id: {deployAt}</div>
              </div>
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <Link
              href="/api/health"
              className="ui-transition inline-flex h-10 items-center justify-center rounded-lg border border-white/20 px-4 text-sm text-white/85 hover:bg-white/5"
            >
              Открыть API Health
            </Link>
            <Link
              href="/"
              className="ui-transition inline-flex h-10 items-center justify-center rounded-lg border border-white/20 px-4 text-sm text-white/85 hover:bg-white/5"
            >
              На главную
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
