// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for MadhavaBound
//
// Policy rationale:
//   A request is allowed only when the Mādhava arctan remainder bound
//   (madhavaRemainderBound) is below a configured precision threshold.
//   A high remainder bound means the truncated series is far from arctan(x),
//   indicating insufficient convergence — the governance signal is unreliable.
//
//   Lean theorem cited: `madhavaRemainderBound_nonneg`
//   Lean file: Lutar/PACBayes/MadhavaBound.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if madhavaBound(opts) ≤ threshold → policy.allow; else → policy.deny
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/PACBayes/MadhavaBound.lean
//   Runtime: szl-holdings/ouroboros agentic/formulas/madhavaBound.ts

/** Policy decision record. */
export interface PolicyDecision {
  allow:     boolean;
  rationale: string;
  formula:   string;
  leanTheorem: string;
  leanFile:  string;
  leanCommitSha: string;
  remainderBound: number;
  threshold: number;
  lambdaScore: number;
}

/** Configuration for the MadhavaBound policy gate. */
export interface MadhavaBoundGateConfig {
  /**
   * Maximum allowed remainder bound.
   * Default: 0.01 (1% precision — arctan partial sum within 1% of true value).
   */
  threshold?: number;
}

/** Inputs for the gate (mirror of MadhavaBoundOpts). */
export interface MadhavaBoundGateOpts {
  /** |x| ≤ 1 — input to the arctan series. */
  x: number;
  /** N ≥ 1 — number of terms summed. */
  N: number;
}

// ── Inline formula (mirrors ouroboros/agentic/formulas/madhavaBound.ts) ──────
// Cited: Lean `madhavaRemainderBound_nonneg` (Lutar/PACBayes/MadhavaBound.lean)
// Theorem: ∀ x N, 0 ≤ |x|^(2N+1)/(2N+1)

function _remainderBound(x: number, N: number): number {
  return Math.pow(Math.abs(x), 2 * N + 1) / (2 * N + 1);
}

function _partial(x: number, N: number): number {
  let s = 0;
  for (let n = 0; n < N; n++) s += (n % 2 === 0 ? 1 : -1) * Math.pow(x, 2*n+1) / (2*n+1);
  return s;
}

// ── Gate function ─────────────────────────────────────────────────────────────

const LEAN_THEOREM   = "madhavaRemainderBound_nonneg";
const LEAN_FILE      = "Lutar/PACBayes/MadhavaBound.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_THRESHOLD = 0.01;

/**
 * MadhavaBound policy gate.
 *
 * Allows a governance action only when the Mādhava remainder bound
 * for the given (x, N) is at or below the configured threshold.
 *
 * Lean theorem: `madhavaRemainderBound_nonneg`
 * Lean file: Lutar/PACBayes/MadhavaBound.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 *
 * @example
 *   const gate = madhavaBoundGate({ threshold: 0.001 });
 *   const decision = gate({ x: 1, N: 100 });
 *   if (decision.allow) policy.allow("series-converged");
 *   else policy.deny("series-not-converged", decision.rationale);
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

    if (!Number.isFinite(x) || Math.abs(x) > 1 + Number.EPSILON) {
      throw new Error(`MadhavaBoundGate: |x| must be ≤ 1; got ${x}`);
    }
    if (!Number.isInteger(N) || N < 1) {
      throw new Error(`MadhavaBoundGate: N must be ≥ 1; got ${N}`);
    }

    const remainderBound = _remainderBound(x, N);
    const lambdaScore    = Math.max(0, Math.min(1, 1 - remainderBound));
    const allow          = remainderBound <= threshold;

    const rationale = allow
      ? `Mādhava bound ${remainderBound.toExponential(4)} ≤ threshold ${threshold}: ` +
        `series sufficiently converged. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `Mādhava bound ${remainderBound.toExponential(4)} > threshold ${threshold}: ` +
        `series not converged — governance signal unreliable. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return {
      allow,
      rationale,
      formula:       "MadhavaBound",
      leanTheorem:   LEAN_THEOREM,
      leanFile:      LEAN_FILE,
      leanCommitSha: LEAN_COMMIT,
      remainderBound,
      threshold,
      lambdaScore,
    };
  };
}
