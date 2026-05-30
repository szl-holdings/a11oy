// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for ConjunctiveGateCounterexample (T6)
//
// Policy rationale:
//   ∃ x: Λ_i(x) ≥ 0.95 for some i ∧ Λ(x) < 0.90 — a high single-axis score
//   does NOT guarantee gate pass. This gate enforces strict conjunctive logic:
//   all axes must meet the floor, regardless of how high any one axis scores.
//
//   Lean derivation cited: `conjunctiveGateCounterexample` (T6)
//   Lean file: Lutar/Gate/ConjunctiveGate.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §2 T6: conjunctive counterexample proof

export interface ConjunctiveGateCounterexampleGateConfig {
  /** Per-axis floor. Default: 0.90. */
  floor?: number;
}

export interface ConjunctiveGateCounterexampleGateOpts {
  axisScores: number[];
}

export interface ConjunctiveGateCounterexampleDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  floor:          number;
  maxAxis:        number;
  minAxis:        number;
  failingAxes:    number[];
  geometricMean:  number;
  lambdaScore:    number;
}

const LEAN_THEOREM  = "conjunctiveGateCounterexample";
const LEAN_FILE     = "Lutar/Gate/ConjunctiveGate.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_FLOOR = 0.90;

export function conjunctiveGateCounterexampleGate(
  config: ConjunctiveGateCounterexampleGateConfig = {}
): (opts: ConjunctiveGateCounterexampleGateOpts) => ConjunctiveGateCounterexampleDecision {
  const floor = config.floor ?? DEFAULT_FLOOR;

  return function gate(opts: ConjunctiveGateCounterexampleGateOpts): ConjunctiveGateCounterexampleDecision {
    const { axisScores } = opts;
    if (!Array.isArray(axisScores) || axisScores.length === 0) {
      throw new Error(`ConjunctiveGateCounterexampleGate: axisScores must be non-empty`);
    }

    const failingAxes  = axisScores.map((s, i) => ({ s, i })).filter(x => x.s < floor).map(x => x.i);
    const maxAxis      = Math.max(...axisScores);
    const minAxis      = Math.min(...axisScores);
    const logSum       = axisScores.reduce((a, s) => a + Math.log(Math.max(s, 1e-12)), 0);
    const geometricMean = Math.exp(logSum / axisScores.length);
    const allow        = failingAxes.length === 0;
    const lambdaScore  = geometricMean;

    const rationale = allow
      ? `ConjunctiveGate (T6): all axes ≥ ${floor}; GM=${geometricMean.toFixed(4)}, max=${maxAxis.toFixed(4)}. Conjunctive pass. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `ConjunctiveGate (T6): axes [${failingAxes.join(',')}] < ${floor} despite max=${maxAxis.toFixed(4)} — conjunctive logic requires ALL axes. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "ConjunctiveGateCounterexample", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, floor, maxAxis, minAxis, failingAxes, geometricMean, lambdaScore };
  };
}
