// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for MadhavaBound
//
// The allow decision compares the classical first-omitted-term expression
// |x|^(2N+1)/(2N+1) with an absolute threshold in log space.
// That comparison is not a kernel-checked arctan specialization and is not a
// float64 truncation-error bound.
//
//   Lean theorem cited: `madhavaRemainderBound_nonneg` (nonnegativity only)
//   Lean file: Lutar/PACBayes/MadhavaBound.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/PACBayes/MadhavaBound.lean
//   Runtime: runtime/ouroboros/agentic/formulas/src/madhavaBound.ts

/** Policy decision record. */
export interface PolicyDecision {
  allow:     boolean;
  rationale: string;
  formula:   string;
  leanTheorem: string;
  leanFile:  string;
  leanCommitSha: string;
  remainderBound: number;
  remainderBoundState: "FINITE" | "SUBNORMAL_OR_UNDERFLOW";
  threshold: number;
  /** Null when the reported remainder flushed below the normal float range. */
  lambdaScore: number | null;
  accuracyClaim: "NOT_ASSERTED";
  leanScope: "nonnegativity_only";
  floatTruncationError: "NOT_BOUNDED";
  comparison: "log_space_first_omitted_term";
}

/** Configuration for the MadhavaBound policy gate. */
export interface MadhavaBoundGateConfig {
  /**
   * Absolute threshold for the classical first-omitted-term expression.
   * Default: 0.01. This is not a relative-accuracy or arctan-error claim.
   */
  threshold?: number;
}

/** Inputs for the gate (mirror of MadhavaBoundOpts). */
export interface MadhavaBoundGateOpts {
  /** |x| ≤ 1 — input to the classical series expression. */
  x: number;
  /** Integer N in 1..10000 — truncation index. */
  N: number;
}

const MADHAVA_MAX_TERMS = 10_000;
const FLOAT_MIN_NORMAL_LOG = Math.log(2.2250738585072014e-308);
const LEAN_THEOREM   = "madhavaRemainderBound_nonneg";
const LEAN_FILE      = "Lutar/PACBayes/MadhavaBound.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_THRESHOLD = 0.01;

function logBound(absX: number, n: number): number {
  if (absX === 0) return Number.NEGATIVE_INFINITY;
  if (absX === 1) return -Math.log(2 * n + 1);
  return (2 * n + 1) * Math.log(absX) - Math.log(2 * n + 1);
}

function remainderOf(absX: number, n: number): { value: number; state: PolicyDecision["remainderBoundState"] } {
  const logValue = logBound(absX, n);
  if (absX === 0) return { value: 0, state: "FINITE" };
  if (absX === 1) return { value: 1 / (2 * n + 1), state: "FINITE" };
  if (logValue < FLOAT_MIN_NORMAL_LOG) return { value: 0, state: "SUBNORMAL_OR_UNDERFLOW" };
  const value = Math.exp(logValue);
  if (value === 0 || !Number.isFinite(value)) return { value: 0, state: "SUBNORMAL_OR_UNDERFLOW" };
  return { value, state: "FINITE" };
}

function withinThreshold(absX: number, n: number, threshold: number): boolean {
  const logThreshold = Math.log(threshold);
  if (!Number.isFinite(logThreshold)) return false;
  return logBound(absX, n) <= logThreshold;
}

/**
 * MadhavaBound policy gate.
 *
 * Allows only when the classical first-omitted-term expression is at or below
 * the configured absolute threshold. Lean `madhavaRemainderBound_nonneg` is
 * nonnegativity only and is not cited as an arctan or float64 error proof.
 */
export function madhavaBoundGate(
  config: MadhavaBoundGateConfig = {}
): (opts: MadhavaBoundGateOpts) => PolicyDecision {
  const threshold = config.threshold ?? DEFAULT_THRESHOLD;
  if (!Number.isFinite(threshold) || threshold <= 0) {
    throw new Error(`MadhavaBoundGate: threshold must be > 0; got ${threshold}`);
  }

  return function gate(opts: MadhavaBoundGateOpts): PolicyDecision {
    const { x, N } = opts;

    if (typeof x !== "number" || !Number.isFinite(x) || Math.abs(x) > 1 + Number.EPSILON) {
      throw new Error(`MadhavaBoundGate: |x| must be ≤ 1; got ${x}`);
    }
    if (!Number.isInteger(N) || N < 1 || N > MADHAVA_MAX_TERMS) {
      throw new Error(`MadhavaBoundGate: N must be ≥ 1 and ≤ ${MADHAVA_MAX_TERMS}; got ${N}`);
    }

    const absX = Math.abs(x);
    const remainder = remainderOf(absX, N);
    const allow = withinThreshold(absX, N, threshold);
    const lambdaScore = remainder.state === "FINITE"
      ? Math.max(0, Math.min(1, 1 - remainder.value))
      : null;
    const leanPin = LEAN_COMMIT.slice(0, 12);
    const rationale = allow
      ? `Madhava first-omitted-term bound state=${remainder.state} is within absolute threshold ${threshold}. ` +
        `This is not a kernel-checked arctan error and not a float64 error bound. ` +
        `Lean: ${LEAN_THEOREM} is nonnegativity only @${leanPin}`
      : `Madhava first-omitted-term bound state=${remainder.state} exceeds absolute threshold ${threshold}, ` +
        `or the threshold is outside log-space comparison. ` +
        `Lean: ${LEAN_THEOREM} is nonnegativity only @${leanPin}`;

    return {
      allow,
      rationale,
      formula:       "MadhavaBound",
      leanTheorem:   LEAN_THEOREM,
      leanFile:      LEAN_FILE,
      leanCommitSha: LEAN_COMMIT,
      remainderBound: remainder.value,
      remainderBoundState: remainder.state,
      threshold,
      lambdaScore,
      accuracyClaim: "NOT_ASSERTED",
      leanScope: "nonnegativity_only",
      floatTruncationError: "NOT_BOUNDED",
      comparison: "log_space_first_omitted_term",
    };
  };
}
