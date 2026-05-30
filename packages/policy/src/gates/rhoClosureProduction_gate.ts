// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for RhoClosureProduction (TH_L4)
//
// Policy rationale:
//   100% ρ-closure on 8,000/8,000 paired calls under v11 platform. This gate
//   validates that a production ρ-closure measurement meets the ≥ 100% target
//   (i.e., all paired calls close successfully). Any failure in a paired call
//   is a ρ-closure regression requiring immediate investigation.
//
//   Lean theorem cited: `rhoClosureProduction` (TH_L4)
//   Lean file: Lutar/RhoClosureProduction.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: measured (100% empirical on ouroboros v6.3.0)
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582

export interface RhoClosureProductionGateConfig {
  /** Required ρ-closure rate (0..1). Default: 1.0 (100%). */
  requiredRate?: number;
}

export interface RhoClosureProductionGateOpts {
  closedCalls: number;
  totalCalls:  number;
}

export interface RhoClosureProductionDecision {
  allow:         boolean;
  rationale:     string;
  formula:       string;
  leanTheorem:   string;
  leanFile:      string;
  leanCommitSha: string;
  closureRate:   number;
  requiredRate:  number;
  openCalls:     number;
  lambdaScore:   number;
}

const LEAN_THEOREM   = "rhoClosureProduction";
const LEAN_FILE      = "Lutar/RhoClosureProduction.lean";
const LEAN_COMMIT    = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const DEFAULT_RATE   = 1.0;

export function rhoClosureProductionGate(
  config: RhoClosureProductionGateConfig = {}
): (opts: RhoClosureProductionGateOpts) => RhoClosureProductionDecision {
  const requiredRate = config.requiredRate ?? DEFAULT_RATE;
  if (!Number.isFinite(requiredRate) || requiredRate < 0 || requiredRate > 1) {
    throw new Error(`RhoClosureProductionGate: requiredRate must be in [0,1]`);
  }

  return function gate(opts: RhoClosureProductionGateOpts): RhoClosureProductionDecision {
    const { closedCalls, totalCalls } = opts;
    if (!Number.isInteger(closedCalls) || closedCalls < 0) throw new Error(`RhoClosureProductionGate: closedCalls must be non-negative integer`);
    if (!Number.isInteger(totalCalls) || totalCalls < 1)  throw new Error(`RhoClosureProductionGate: totalCalls must be ≥ 1`);
    if (closedCalls > totalCalls) throw new Error(`RhoClosureProductionGate: closedCalls cannot exceed totalCalls`);

    const closureRate = closedCalls / totalCalls;
    const openCalls   = totalCalls - closedCalls;
    const allow       = closureRate >= requiredRate;
    const lambdaScore = closureRate;

    const rationale = allow
      ? `RhoClosureProduction (TH_L4): ρ-closure=${(closureRate*100).toFixed(2)}% (${closedCalls}/${totalCalls}) ≥ required ${(requiredRate*100).toFixed(0)}%. Production target met. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `RhoClosureProduction (TH_L4): ρ-closure=${(closureRate*100).toFixed(2)}% (${closedCalls}/${totalCalls}); ${openCalls} calls open — below required ${(requiredRate*100).toFixed(0)}%. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "RhoClosureProduction", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, closureRate, requiredRate, openCalls, lambdaScore };
  };
}
