// SPDX-License-Identifier: Apache-2.0
// © 2026 SZL Holdings · Doctrine v12 (additive over v11 LOCKED). Yachay.
//
// szlBreaker.ts — Hystrix-style breakers for TS surfaces (a11oy Node serve, etc.)
// cockatiel: circuitBreaker (CLOSED/OPEN/HALF-OPEN) + retry (exp backoff+jitter)
//            + timeout (per-call) + fallback. Khipu receipt on every transition.
// Alternate noted by brief: @nodecg/circuitbreaker (older; we use cockatiel).
//
// ADDITIVE only: wraps calls; never alters the 13-axis Yuyay gate or LOCKED numbers.
// HONEST: receipt signature is DSSE PLACEHOLDER (Sigstore CI not wired).

import {
  circuitBreaker, ConsecutiveBreaker, retry, timeout, fallback,
  wrap, handleAll, ExponentialBackoff, TimeoutStrategy, IPolicy,
} from "cockatiel";

const SIGNATURE_PLACEHOLDER = "PLACEHOLDER — Sigstore CI not wired (Doctrine v12)";

// Reuse the live in-process Khipu DAG ingest (Wire F) if present on the Node side.
declare function ingestReceipt(receipt: Record<string, unknown>): Promise<unknown>;

async function emitDegradation(p: {
  breaker: string; flagship: string; failureMode: string;
  fallbackTier: string; state: string; traceparent?: string;
}): Promise<void> {
  const receipt = {
    schema: "szl.degradation.receipt/v1",
    event_id: `deg-${new Date().toISOString()}-${p.flagship}-${p.breaker}`,
    flagship: p.flagship, failure_mode: p.failureMode, circuit: p.breaker,
    breaker_state: p.state, fallback_tier_served: p.fallbackTier,
    detected_at: new Date().toISOString(), user_visible: true,
    traceparent: p.traceparent ?? null, doctrine: "v12",
    dsse: { sig: SIGNATURE_PLACEHOLDER, keyid: "PENDING" },
  };
  try { await ingestReceipt(receipt); }      // szl_wire equivalent on the Node side
  catch { /* local-only; never throw from the audit path */ }
}

export interface BreakerOpts {
  name: string; flagship: string; failureMode: string; fallbackTier: string;
  timeoutMs: number; retryBudget: number; failureThreshold: number;
  resetTimeoutMs: number; traceparent?: string;
}

/** Compose timeout -> retry -> circuitBreaker -> fallback into one Policy. */
export function makePolicy<T>(opts: BreakerOpts, fallbackFn: () => Promise<T>): IPolicy {
  const cb = circuitBreaker(handleAll, {
    halfOpenAfter: opts.resetTimeoutMs,
    breaker: new ConsecutiveBreaker(opts.failureThreshold),
  });
  cb.onStateChange((state) =>
    emitDegradation({ breaker: opts.name, flagship: opts.flagship,
      failureMode: opts.failureMode, fallbackTier: opts.fallbackTier,
      state: String(state), traceparent: opts.traceparent }));

  const to = timeout(opts.timeoutMs, TimeoutStrategy.Aggressive);
  const rt = retry(handleAll, {
    maxAttempts: opts.retryBudget,
    backoff: new ExponentialBackoff({ initialDelay: 1000, maxDelay: 300_000 }),
  });
  const fb = fallback(handleAll, async () => {
    await emitDegradation({ breaker: opts.name, flagship: opts.flagship,
      failureMode: opts.failureMode, fallbackTier: opts.fallbackTier,
      state: "FALLBACK", traceparent: opts.traceparent });
    return fallbackFn();
  });
  // Order matters: fallback wraps breaker wraps retry wraps timeout.
  return wrap(fb, cb, rt, to);
}

// ── Example: LLM router fallback (D2) on the Node side ────────────────────────
declare function t0CacheLookup(): Promise<string | null>;
declare function t1SmallModelIfAvailable(): Promise<string | null>;
declare function callProviderRouter(prompt: string): Promise<unknown>;

const llmPolicy = makePolicy(
  { name: "llm_router", flagship: "a11oy", failureMode: "llm_all_providers_rate_limited",
    fallbackTier: "T0/T1/honest-error", timeoutMs: 25_000, retryBudget: 0,
    failureThreshold: 5, resetTimeoutMs: 15_000 },
  async () => {
    const hit = await t0CacheLookup();
    if (hit) return { completion: hit, degraded: true, tier: "T0_cache" };
    const small = await t1SmallModelIfAvailable();
    if (small) return { completion: small, degraded: true, tier: "T1_small" };
    return { error: "all_llm_providers_rate_limited", retry_after_s: 30,
             degraded: true, honest: "No model could answer within budget." };
  },
);

export async function routeLLM(prompt: string) {
  return llmPolicy.execute(() => callProviderRouter(prompt)); // real call
}
