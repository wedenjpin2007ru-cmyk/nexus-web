export default function Loading() {
  return (
    <main className="flex-1">
      <div className="mx-auto w-full max-w-4xl px-6 py-14">
        <div className="animate-pulse rounded-2xl border border-white/10 bg-white/[0.03] p-8">
          <div className="h-4 w-24 rounded bg-white/10" />
          <div className="mt-4 h-8 w-72 rounded bg-white/10" />
          <div className="mt-6 h-4 w-full max-w-2xl rounded bg-white/10" />
          <div className="mt-2 h-4 w-full max-w-xl rounded bg-white/10" />
          <div className="mt-8 flex gap-3">
            <div className="h-11 w-28 rounded-xl bg-white/10" />
            <div className="h-11 w-24 rounded-xl bg-white/10" />
          </div>
        </div>
      </div>
    </main>
  );
}
