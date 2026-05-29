// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LiuHuiPi
//
// Policy rationale:
//   A geometric computation is allowed only when the Liu Hui polygon
//   approximation of π at step k achieves an absolute error ≤ threshold.
//   The Lean theorem proves sideSquared ∈ [0,4] (well-definedness), and
//   the monotone convergence guarantees piEstimate < π. The gate enforces
//   that sufficient polygon sides have been computed before the approximation
//   is trusted in a governance computation.
//
//   Lean theorem cited: `sideSquared_bounds`
//   Lean file: Lutar/Banach/LiuHuiPi.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if |liuHuiPi(k) − π| ≤ threshold → policy.allow; else → policy.deny
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/Banach/LiuHuiPi.lean
//   Runtime: szl-holdings/ouroboros agentic/formulas/liuHuiPi.ts

export interface PolicyDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  piEstimate:    number;
  absError:      number;
  threshold:     number;
  lambdaScore:   number;
}

export interface LiuHuiPiGateConfig {
  /**
   * Maximum allowed |piEstimate − π|.
   * Default: 1e-4 (requires k ≥ 8 for convergence).
   */
  threshold?: number;
}

export interface LiuHuiPiGateOpts {
  k: number;
}

const LEAN_THEOREM   = "sideSquared_bounds";
const LEAN_FILE      = "Lutar/Banach/LiuHuiPi.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_THRESH = 1e-4;

// ── Inline formula ────────────────────────────────────────────────────────────
// Lean: sideSquared_bounds ensures sq ∈ [0,4] for all steps

function _liuHuiPi(k: number): { piEstimate: number; absError: number } {
  let sq = 1.0;
  for (let i = 0; i < k; i++) sq = 2 - Math.sqrt(4 - sq);
  const sideCount = 6 * Math.pow(2, k);
  const piEstimate = (sideCount * Math.sqrt(sq)) / 2;
  return { piEstimate, absError: Math.abs(piEstimate - Math.PI) };
}

/**
 * LiuHuiPi policy gate.
 *
 * Allows geometric governance actions only when the Liu Hui π approximation
 * at step k achieves absolute error ≤ threshold.
 *
 * Lean theorem: `sideSquared_bounds`
 * Lean file: Lutar/Banach/LiuHuiPi.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
export function liuHuiPiGate(
  config: LiuHuiPiGateConfig = {}
): (opts: LiuHuiPiGateOpts) => PolicyDecision {
  const threshold = config.threshold ?? DEFAULT_THRESH;
  if (!Number.isFinite(threshold) || threshold < 0) {
    throw new Error(`LiuHuiPiGate: threshold must be ≥ 0; got ${threshold}`);
  }

  return function gate(opts: LiuHuiPiGateOpts): PolicyDecision {
    const { k } = opts;
    if (!Number.isInteger(k) || k < 0 || k > 50) {
      throw new Error(`LiuHuiPiGate: k must be in [0,50]; got ${k}`);
    }

    const { piEstimate, absError } = _liuHuiPi(k);
    const lambdaScore = Math.max(0, 1 - absError / Math.PI);
    const allow = absError <= threshold;

    const rationale = allow
      ? `LiuHuiPi (k=${k}, ${6 * Math.pow(2, k)}-gon) |est−π| = ${absError.toExponential(4)} ≤ threshold ${threshold}: ` +
        `π approximation sufficiently accurate. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `LiuHuiPi (k=${k}, ${6 * Math.pow(2, k)}-gon) |est−π| = ${absError.toExponential(4)} > threshold ${threshold}: ` +
        `π approximation not yet converged. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return {
      allow,
      rationale,
      formula:       "LiuHuiPi",
      leanTheorem:   LEAN_THEOREM,
      leanFile:      LEAN_FILE,
      leanCommitSha: LEAN_COMMIT,
      piEstimate,
      absError,
      threshold,
      lambdaScore,
    };
  };
}
