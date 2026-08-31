// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for FalsePosition
//
// Policy rationale:
//   A calibration action is allowed only when the false-position correction
//   yields an xStar that, when evaluated on the reconstructed affine gate,
//   recovers the target T to within the configured residual tolerance.
//   This enforces the Lean theorem: f(xStar) = T exactly for affine gates;
//   a non-trivial residual indicates numerical degeneration.
//
//   Lean theorem cited: `false_position_correct`
//   Lean file: Lutar/Calibration/FalsePosition.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if |f(xStar) − T| ≤ tolerance → policy.allow; else → policy.deny
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/Calibration/FalsePosition.lean
//   Runtime: szl-holdings/ouroboros agentic/formulas/falsePosition.ts

export interface PolicyDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  xStar:         number;
  residual:      number;
  tolerance:     number;
  lambdaScore:   number;
}

export interface FalsePositionGateConfig {
  /**
   * Maximum allowed |f(xStar) − T|.
   * Default: 1e-8 (floating-point near-exact recovery).
   */
  tolerance?: number;
}

export interface FalsePositionGateOpts {
  x1: number; y1: number;
  x2: number; y2: number;
  T: number;
}

const LEAN_THEOREM = "false_position_correct";
const LEAN_FILE    = "Lutar/Calibration/FalsePosition.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_TOL  = 1e-8;

// ── Inline formula ────────────────────────────────────────────────────────────
// Lean: false_position_correct (m c x₁ x₂ T : ℝ) (hm : m≠0) (hx : x₁≠x₂) : f(x*) = T

function _falsePosition(x1: number, y1: number, x2: number, y2: number, T: number):
  { xStar: number; residual: number } {
  for (const [name, value] of Object.entries({ x1, y1, x2, y2, T })) {
    if (!Number.isFinite(value)) {
      throw new Error(`FalsePositionGate: ${name} must be finite; got ${value}`);
    }
  }
  if (Math.abs(x2 - x1) < Number.EPSILON * Math.max(Math.abs(x1), Math.abs(x2), 1)) {
    throw new Error("FalsePositionGate: degenerate samples (x₁ = x₂)");
  }
  const dy = y2 - y1;
  if (Math.abs(dy) < Number.EPSILON * Math.max(Math.abs(y1), Math.abs(y2), 1)) {
    throw new Error("FalsePositionGate: degenerate samples (y₁ = y₂)");
  }
  const xStar = x1 + ((T - y1) * (x2 - x1)) / dy;
  const m = dy / (x2 - x1);
  const c = y1 - m * x1;
  const residual = Math.abs(m * xStar + c - T);
  return { xStar, residual };
}

/**
 * FalsePosition policy gate.
 *
 * Allows calibration actions when the false-position correction recovers
 * the target T with residual ≤ tolerance.
 *
 * Lean theorem: `false_position_correct`
 * Lean file: Lutar/Calibration/FalsePosition.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
export function falsePositionGate(
  config: FalsePositionGateConfig = {}
): (opts: FalsePositionGateOpts) => PolicyDecision {
  const tolerance = config.tolerance ?? DEFAULT_TOL;
  if (!Number.isFinite(tolerance) || tolerance < 0) {
    throw new Error(`FalsePositionGate: tolerance must be ≥ 0; got ${tolerance}`);
  }

  return function gate(opts: FalsePositionGateOpts): PolicyDecision {
    const { x1, y1, x2, y2, T } = opts;
    const { xStar, residual } = _falsePosition(x1, y1, x2, y2, T);
    const lambdaScore = Math.max(0, 1 - residual / (1 + Math.abs(T)));
    const allow = residual <= tolerance;

    const rationale = allow
      ? `FalsePosition residual |f(x*)−T| = ${residual.toExponential(4)} ≤ tol ${tolerance}: ` +
        `calibration target recovered exactly. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `FalsePosition residual |f(x*)−T| = ${residual.toExponential(4)} > tol ${tolerance}: ` +
        `calibration degenerate — deny update. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return {
      allow,
      rationale,
      formula:       "FalsePosition",
      leanTheorem:   LEAN_THEOREM,
      leanFile:      LEAN_FILE,
      leanCommitSha: LEAN_COMMIT,
      xStar,
      residual,
      tolerance,
      lambdaScore,
    };
  };
}
