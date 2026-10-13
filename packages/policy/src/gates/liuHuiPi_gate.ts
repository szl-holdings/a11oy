// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for LiuHuiPi
//
// Policy rationale:
//   A geometric computation is allowed only when the float64 Liu Hui
//   polygon estimate at step k has absolute residual ≤ threshold against
//   Math.PI. That residual is a numerical check, not a proof.
//   Lean theorem sideSquared_bounds proves the real recurrence stays in
//   [0, 4]. Axiom liu_hui_pi_converges asserts only that some real limit
//   exists. It does not prove that the limit is π, and it does not prove
//   this floating-point implementation.
//
//   Lean theorem cited: `sideSquared_bounds`
//   Lean file: Lutar/Banach/LiuHuiPi.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if |float64Estimate(k) − Math.PI| ≤ threshold → policy.allow;
//   else → policy.deny. Allow does not increase mathematical authority.
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
  // Same rationalized step as runtime/ouroboros/agentic/formulas/src/liuHuiPi.ts.
  // 2 - sqrt(4 - sq) cancels in float64 and is 0 by k=27.
  let sq = 1.0;
  for (let i = 0; i < k; i++) {
    const radicand = 4 - sq;
    if (!(radicand >= 0)) {
      throw new Error(`LiuHuiPiGate: sideSquared radicand ${radicand} at step ${i}`);
    }
    sq = sq / (2 + Math.sqrt(radicand));
  }
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

    const scope =
      "Floating-point residual against Math.PI only. " +
      "Lean sideSquared_bounds is well-definedness on [0,4]. " +
      "Axiom liu_hui_pi_converges asserts some limit exists and does not identify it with π.";
    const rationale = allow
      ? `LiuHuiPi (k=${k}, ${6 * Math.pow(2, k)}-gon) |est−π| = ${absError.toExponential(4)} ≤ threshold ${threshold}: ` +
        `configured residual met. ${scope} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `LiuHuiPi (k=${k}, ${6 * Math.pow(2, k)}-gon) |est−π| = ${absError.toExponential(4)} > threshold ${threshold}: ` +
        `configured residual exceeded. ${scope} Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

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
