const buckets = { session: new Map(), ip: new Map(), global: new Map() };
const activeByIp = new Map();
let activeGlobal = 0;
const MAX_BUCKET_KEYS = 20_000;

function boundedInteger(name, fallback, min, max) {
  const parsed = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

export function admissionLimits() {
  return {
    windowMs: boundedInteger("IMMUNE_RATE_WINDOW_MS", 60_000, 1_000, 300_000),
    session: boundedInteger("IMMUNE_RATE_SESSION", 30, 1, 1_000),
    ip: boundedInteger("IMMUNE_RATE_IP", 60, 1, 5_000),
    global: boundedInteger("IMMUNE_RATE_GLOBAL", 300, 1, 20_000),
    ipConcurrency: boundedInteger("IMMUNE_CONCURRENCY_IP", 4, 1, 64),
    globalConcurrency: boundedInteger("IMMUNE_CONCURRENCY_GLOBAL", 16, 1, 256),
    deadlineMs: boundedInteger("IMMUNE_REQUEST_DEADLINE_MS", 5_000, 250, 60_000),
  };
}

function currentBucket(map, key, now, windowMs) {
  const prior = map.get(key);
  if (!prior || now - prior.startedAt >= windowMs) {
    const next = { startedAt: now, count: 0 };
    map.set(key, next);
    return next;
  }
  return prior;
}

function pruneBuckets(now, windowMs) {
  for (const map of Object.values(buckets)) {
    for (const [key, value] of map) if (now - value.startedAt >= windowMs) map.delete(key);
    while (map.size > MAX_BUCKET_KEYS) map.delete(map.keys().next().value);
  }
}

function rejected(scope, bucket, limit, now, windowMs) {
  const resetAt = bucket.startedAt + windowMs;
  const retrySeconds = Math.max(1, Math.ceil((resetAt - now) / 1000));
  return {
    accepted: false,
    scope,
    headers: {
      "retry-after": String(retrySeconds),
      "ratelimit-limit": String(limit),
      "ratelimit-remaining": "0",
      "ratelimit-reset": String(Math.ceil(resetAt / 1000)),
      "x-ratelimit-limit": String(limit),
      "x-ratelimit-remaining": "0",
      "x-ratelimit-reset": String(Math.ceil(resetAt / 1000)),
      "x-immune-admission-scope": scope,
    },
  };
}

export function admitRequest({ sessionId, ip, now = Date.now(), limits = admissionLimits() }) {
  pruneBuckets(now, limits.windowMs);
  const keys = { session: sessionId, ip: ip || "UNKNOWN", global: "global" };
  const scoped = [
    ["global", buckets.global, keys.global, limits.global],
    ["ip", buckets.ip, keys.ip, limits.ip],
    ["session", buckets.session, keys.session, limits.session],
  ];
  for (const [scope, map, key, limit] of scoped) {
    const bucket = currentBucket(map, key, now, limits.windowMs);
    if (bucket.count >= limit) return rejected(scope, bucket, limit, now, limits.windowMs);
  }
  if (activeGlobal >= limits.globalConcurrency) return rejected("global_concurrency", { startedAt: now }, limits.globalConcurrency, now, 1_000);
  if ((activeByIp.get(keys.ip) ?? 0) >= limits.ipConcurrency) return rejected("ip_concurrency", { startedAt: now }, limits.ipConcurrency, now, 1_000);

  for (const [, map, key] of scoped) currentBucket(map, key, now, limits.windowMs).count += 1;
  activeGlobal += 1;
  activeByIp.set(keys.ip, (activeByIp.get(keys.ip) ?? 0) + 1);
  let released = false;
  return {
    accepted: true,
    scope: "accepted",
    headers: {
      "ratelimit-limit": String(Math.min(limits.session, limits.ip, limits.global)),
      "ratelimit-remaining": String(Math.max(0, limits.session - buckets.session.get(keys.session).count)),
      "ratelimit-reset": String(Math.ceil((buckets.session.get(keys.session).startedAt + limits.windowMs) / 1000)),
      "x-immune-admission-scope": "session",
    },
    release() {
      if (released) return;
      released = true;
      activeGlobal = Math.max(0, activeGlobal - 1);
      const next = Math.max(0, (activeByIp.get(keys.ip) ?? 1) - 1);
      if (next === 0) activeByIp.delete(keys.ip); else activeByIp.set(keys.ip, next);
    },
  };
}

export class DeadlineFault extends Error {
  constructor() { super("request deadline exceeded"); this.name = "DeadlineFault"; }
}

export async function runWithDeadline(workFactory, admission, deadlineMs = admissionLimits().deadlineMs) {
  const controller = new AbortController();
  let timer;
  const work = Promise.resolve().then(() => workFactory(controller.signal)).finally(() => admission.release());
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new DeadlineFault()); }, deadlineMs);
    timer.unref?.();
  });
  try { return await Promise.race([work, timeout]); }
  finally { clearTimeout(timer); }
}

export function resetAdmissionForTest() {
  buckets.session.clear();
  buckets.ip.clear();
  buckets.global.clear();
  activeByIp.clear();
  activeGlobal = 0;
}
