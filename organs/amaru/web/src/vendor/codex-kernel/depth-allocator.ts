// VENDORED FROM szl-holdings/platform@653b4ba95e6ae03630a922631139481875809d0b — packages/codex-kernel/src/depth-allocator.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Codex-Kernel — EntropyDepthAllocator (Ouroboros Thesis v3, §3.2).
 *
 * Pure-function controller that decides, after each committed step, whether
 * the loop should:
 *   - `continue`               — keep iterating
 *   - `early_exit_converged`   — Δ-magnitude stayed below threshold for the
 *                                configured window
 *   - `early_exit_entropy`     — validator entropy settled to clean for the
 *                                configured window
 *   - `extend`                 — step counter is approaching the ceiling but
 *                                the soft-fail rate suggests more budget is
 *                                warranted (bounded by `hard_max_steps`)
 *
 * Determinism contract:
 *   - No clocks, no PRNG, no I/O.
 *   - All inputs are passed in `DepthAllocatorContext`.
 *   - The verdict is a deterministic function of (ctx, cfg).
 *   - Replay can re-derive every verdict bit-for-bit.
 *
 * Zero runtime dependencies (the codex-kernel package itself is zero-dep).
 */

import type { ValidatorSeverity } from './types.js';

export type DepthVerdict =
  | 'continue'
  | 'early_exit_converged'
  | 'early_exit_entropy'
  | 'extend';

/**
 * Tunable thresholds. Defaults are conservative — they prefer slightly more
 * iteration over premature exit, on the principle that a wasted step is
 * cheaper than an unsupported decision.
 */
export interface DepthAllocatorConfig {
  /** ε_Δ — normalized Hamming-witness threshold for "delta is small". */
  delta_convergence_threshold: number;
  /** W_Δ — number of consecutive steps that must satisfy ε_Δ. */
  delta_convergence_window: number;
  /** ε_H — Shannon-entropy threshold for "validators have settled". */
  entropy_threshold: number;
  /** W_H — number of consecutive clean steps required for entropy exit. */
  entropy_window: number;
  /** ρ — rolling soft-fail rate that justifies extending the budget. */
  soft_fail_extension_threshold: number;
  /** Window size (in steps) used to compute the rolling soft-fail rate. */
  soft_fail_window: number;
  /** Hard ceiling on extended step budget. The allocator never exceeds this. */
  hard_max_steps: number;
  /** How many steps remaining before extension is considered. */
  extension_horizon: number;
}

export const DEFAULT_DEPTH_ALLOCATOR_CONFIG: DepthAllocatorConfig = {
  delta_convergence_threshold: 0.05,
  delta_convergence_window: 2,
  entropy_threshold: 0.5,
  entropy_window: 2,
  soft_fail_extension_threshold: 0.5,
  soft_fail_window: 3,
  hard_max_steps: 100,
  extension_horizon: 1,
};

/** Per-step record. Owned and appended to by the kernel. */
export interface AllocatorStepRecord {
  /** Step index (1-based). */
  step: number;
  /** State hash committed by this step. Used for the Hamming witness. */
  state_hash: string;
  /** Severities of every validator that ran this step. */
  validator_severities: readonly ValidatorSeverity[];
}

export interface DepthAllocatorContext {
  /** Full history of committed steps, in order. */
  history: readonly AllocatorStepRecord[];
  /** The current step budget (may already have been extended). */
  current_max_steps: number;
}

export interface DepthAllocatorResult {
  verdict: DepthVerdict;
  /** Human-readable note for the trace. */
  reason: string;
  /** Diagnostic numbers for the trace; all optional. */
  details: {
    delta_witness?: number;
    entropy?: number;
    soft_fail_rate?: number;
    /** When `verdict === 'extend'`, the new (extended) ceiling. */
    extended_max_steps?: number;
  };
}

/**
 * Normalized state-change witness over the L-character hex chain hash.
 *
 *     d_k = Hamming(h_{k-1}, h_k) / L
 *
 * Returns a value in [0, 1]. Strings of unequal length compare over the
 * shorter length and pad the difference as a per-position mismatch (this
 * keeps the function total without hiding genuine divergence).
 */
export function deltaHammingWitness(prevHex: string, nextHex: string): number {
  const a = prevHex ?? '';
  const b = nextHex ?? '';
  const L = Math.max(a.length, b.length);
  if (L === 0) return 0;
  const common = Math.min(a.length, b.length);
  let mismatches = 0;
  for (let i = 0; i < common; i++) {
    if (a.charCodeAt(i) !== b.charCodeAt(i)) mismatches += 1;
  }
  // Length difference counts fully as mismatched positions.
  mismatches += L - common;
  return mismatches / L;
}

/**
 * Shannon entropy over the validator severity distribution at one step,
 * measured in bits. Domain is {pass, soft_fail, hard_fail}; the result is
 * in [0, log2(3)] ≈ [0, 1.585]. An empty validator list is defined as 0.
 */
export function severityEntropyBits(
  severities: readonly ValidatorSeverity[],
): number {
  if (severities.length === 0) return 0;
  const counts: Record<ValidatorSeverity, number> = {
    pass: 0,
    soft_fail: 0,
    hard_fail: 0,
  };
  for (const s of severities) counts[s] += 1;
  const total = severities.length;
  let h = 0;
  for (const k of ['pass', 'soft_fail', 'hard_fail'] as const) {
    const p = counts[k] / total;
    if (p > 0) h += -p * Math.log2(p);
  }
  return h;
}

/**
 * Rolling soft-fail rate over the last `window` steps. Defined as
 *   (# soft_fail validator results in window) / (# validator results in window)
 * Returns 0 when the window is empty.
 */
export function rollingSoftFailRate(
  history: readonly AllocatorStepRecord[],
  window: number,
): number {
  if (history.length === 0 || window <= 0) return 0;
  const slice = history.slice(-window);
  let total = 0;
  let soft = 0;
  for (const rec of slice) {
    for (const s of rec.validator_severities) {
      total += 1;
      if (s === 'soft_fail') soft += 1;
    }
  }
  return total === 0 ? 0 : soft / total;
}

/**
 * The decision function called by the kernel after each committed step.
 *
 * Verdict precedence (first match wins):
 *   1. `early_exit_converged`  — last W_Δ Hamming witnesses ≤ ε_Δ
 *   2. `early_exit_entropy`    — last W_H steps had entropy ≤ ε_H AND zero soft fails
 *   3. `extend`                — within `extension_horizon` of the ceiling AND
 *                                soft-fail rate > ρ AND ceiling < hard_max_steps
 *   4. `continue`              — otherwise
 */
export function decideDepth(
  ctx: DepthAllocatorContext,
  cfg: DepthAllocatorConfig = DEFAULT_DEPTH_ALLOCATOR_CONFIG,
): DepthAllocatorResult {
  const h = ctx.history;
  const lastStep = h[h.length - 1];

  // Compute diagnostics regardless of which branch wins so the trace
  // always carries the same shape.
  const witnessSeries: number[] = [];
  for (let i = Math.max(1, h.length - cfg.delta_convergence_window); i < h.length; i++) {
    witnessSeries.push(deltaHammingWitness(h[i - 1]!.state_hash, h[i]!.state_hash));
  }
  const lastWitness = witnessSeries[witnessSeries.length - 1] ?? 1;
  const lastEntropy = lastStep ? severityEntropyBits(lastStep.validator_severities) : 1;
  const softFailRate = rollingSoftFailRate(h, cfg.soft_fail_window);

  // 1. delta convergence
  if (
    witnessSeries.length >= cfg.delta_convergence_window &&
    witnessSeries.every((d) => d <= cfg.delta_convergence_threshold)
  ) {
    return {
      verdict: 'early_exit_converged',
      reason: `Δ-witness ≤ ${cfg.delta_convergence_threshold} for last ${cfg.delta_convergence_window} steps (last=${lastWitness.toFixed(4)})`,
      details: {
        delta_witness: lastWitness,
        entropy: lastEntropy,
        soft_fail_rate: softFailRate,
      },
    };
  }

  // 2. entropy settled
  if (h.length >= cfg.entropy_window) {
    const tail = h.slice(-cfg.entropy_window);
    const allClean = tail.every(
      (rec) =>
        severityEntropyBits(rec.validator_severities) <= cfg.entropy_threshold &&
        !rec.validator_severities.includes('soft_fail'),
    );
    if (allClean) {
      return {
        verdict: 'early_exit_entropy',
        reason: `H ≤ ${cfg.entropy_threshold} bits and no soft-fails for last ${cfg.entropy_window} steps`,
        details: {
          delta_witness: lastWitness,
          entropy: lastEntropy,
          soft_fail_rate: softFailRate,
        },
      };
    }
  }

  // 3. extend
  const stepsRemaining = ctx.current_max_steps - h.length;
  if (
    stepsRemaining <= cfg.extension_horizon &&
    softFailRate > cfg.soft_fail_extension_threshold &&
    ctx.current_max_steps < cfg.hard_max_steps
  ) {
    const extended = Math.min(
      cfg.hard_max_steps,
      ctx.current_max_steps + cfg.delta_convergence_window + cfg.entropy_window,
    );
    return {
      verdict: 'extend',
      reason: `soft-fail rate ${softFailRate.toFixed(2)} > ${cfg.soft_fail_extension_threshold} within ${cfg.extension_horizon} of ceiling; extending to ${extended}`,
      details: {
        delta_witness: lastWitness,
        entropy: lastEntropy,
        soft_fail_rate: softFailRate,
        extended_max_steps: extended,
      },
    };
  }

  // 4. continue
  return {
    verdict: 'continue',
    reason: 'no exit condition met',
    details: {
      delta_witness: lastWitness,
      entropy: lastEntropy,
      soft_fail_rate: softFailRate,
    },
  };
}
