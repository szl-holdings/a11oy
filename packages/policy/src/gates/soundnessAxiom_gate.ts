// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for SoundnessAxiom (A1)
//
// Policy rationale:
//   A receipt is allowed to pass only when all 9 Λ-axis scores meet or exceed
//   the conjunctive floor of 0.90. The soundness axiom guarantees: if gate_pass(r)
//   then lambda(r) >= 0.90 conjunctively. This gate enforces that claim at
//   the policy layer — rejecting any receipt that would silently under-score.
//
//   Lean axiom cited: `soundnessAxiom` (A1)
//   Lean file: Lutar/Gate/SoundnessAxiom.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if all axes >= floor → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   Thesis §4.1: soundnessAxiom — conjunctive Λ floor

export interface SoundnessAxiomGateConfig {
  /** Conjunctive floor per axis. Default: 0.90. */
  floor?: number;
}

export interface SoundnessAxiomGateOpts {
  /** Array of 9 axis scores in [0,1]. */
  axisScores: number[];
}

export interface SoundnessAxiomDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  floor:          number;
  minAxis:        number;
  failingAxes:    number[];
  lambdaScore:    number;
}

const LEAN_THEOREM = "soundnessAxiom";
const LEAN_FILE    = "Lutar/Gate/SoundnessAxiom.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_FLOOR = 0.90;
const AXIS_COUNT   = 9;

// ── Inline formula ────────────────────────────────────────────────────────────
// A1: gate_pass(r) ⟹ ∀i ∈ {0..8}: lambda_i(r) ≥ 0.90

function _geometricMean(scores: number[]): number {
  if (scores.length === 0) return 0;
  const logSum = scores.reduce((acc, s) => acc + Math.log(Math.max(s, 1e-12)), 0);
  return Math.exp(logSum / scores.length);
}

/**
 * SoundnessAxiom (A1) policy gate.
 *
 * Passes only when every axis in the 9-axis Λ-vector meets or exceeds the
 * configured conjunctive floor. This is the primary gating axiom of the
 * SZL receipt system.
 *
 * Lean axiom: `soundnessAxiom` (A1)
 * Lean file: Lutar/Gate/SoundnessAxiom.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function soundnessAxiomGate(
  config: SoundnessAxiomGateConfig = {}
): (opts: SoundnessAxiomGateOpts) => SoundnessAxiomDecision {
  const floor = config.floor ?? DEFAULT_FLOOR;
  if (!Number.isFinite(floor) || floor < 0 || floor > 1) {
    throw new Error(`SoundnessAxiomGate: floor must be in [0,1]; got ${floor}`);
  }

  return function gate(opts: SoundnessAxiomGateOpts): SoundnessAxiomDecision {
    const { axisScores } = opts;
    if (!Array.isArray(axisScores) || axisScores.length !== AXIS_COUNT) {
      throw new Error(`SoundnessAxiomGate: axisScores must be length ${AXIS_COUNT}; got ${axisScores?.length}`);
    }
    for (const s of axisScores) {
      if (!Number.isFinite(s) || s < 0 || s > 1) {
        throw new Error(`SoundnessAxiomGate: each axis score must be in [0,1]; got ${s}`);
      }
    }

    const failingAxes = axisScores.map((s, i) => ({ s, i })).filter(x => x.s < floor).map(x => x.i);
    const minAxis     = Math.min(...axisScores);
    const lambdaScore = _geometricMean(axisScores);
    const allow       = failingAxes.length === 0;

    const rationale = allow
      ? `SoundnessAxiom (A1): all ${AXIS_COUNT} axes ≥ ${floor}; min=${minAxis.toFixed(4)}, Λ=${lambdaScore.toFixed(4)}. Receipt passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `SoundnessAxiom (A1): axes [${failingAxes.join(',')}] below floor ${floor}; min=${minAxis.toFixed(4)}. Receipt denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "SoundnessAxiom", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, floor, minAxis, failingAxes, lambdaScore };
  };
}
