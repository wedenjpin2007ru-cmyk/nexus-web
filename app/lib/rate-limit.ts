type Bucket = { tokens: number; lastRefillMs: number };

const globalBuckets = globalThis as unknown as {
  __nexusRateLimit?: Map<string, Bucket>;
};

const buckets = (globalBuckets.__nexusRateLimit ??= new Map<string, Bucket>());

export function checkRateLimit(key: string, opts: { capacity: number; refillPerSec: number }) {
  const now = Date.now();
  const b = buckets.get(key) ?? { tokens: opts.capacity, lastRefillMs: now };

  const elapsedSec = Math.max(0, (now - b.lastRefillMs) / 1000);
  const refill = elapsedSec * opts.refillPerSec;
  b.tokens = Math.min(opts.capacity, b.tokens + refill);
  b.lastRefillMs = now;

  const allowed = b.tokens >= 1;
  if (allowed) b.tokens -= 1;

  buckets.set(key, b);
  return { allowed, remaining: Math.floor(b.tokens) };
}

