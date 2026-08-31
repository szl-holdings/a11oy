// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for EconomicGrounding (A14)
//
// Policy rationale:
//   Gate passes only if the declared action cost ≤ registered actor budget
//   at evaluation time. Required for financial services (SR 11-7 position
//   limits), insurance underwriting ceilings, and SEC Rule 17a-4 order size
//   compliance.
//
//   Lean axiom cited: `economicGrounding` (A14)
//   Lean file: Lutar/Gate/EconomicGrounding.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if cost ≤ budget → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20162352
//   INNOVATIONS.md §3 A14: economicGrounding

export interface EconomicGroundingGateConfig {
  /** Allow cost == budget exactly. Default: true. */
  allowAtBudget?: boolean;
}

export interface EconomicGroundingGateOpts {
  actionCost:     number;
  actorBudget:    number;
  actorId:        string;
  timestampMs?:   number;
}

export interface EconomicGroundingDecision {
  allow:           boolean;
  rationale:       string;
  formula:         string;
  leanTheorem:     string;
  leanFile:        string;
  leanCommitSha:   string;
  actionCost:      number;
  actorBudget:     number;
  budgetRemaining: number;
  utilizationRate: number;
  lambdaScore:     number;
}

const LEAN_THEOREM = "economicGrounding";
const LEAN_FILE    = "Lutar/Gate/EconomicGrounding.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// A14: gate_pass(r) ⟹ cost(r) ≤ B_actor(t)

/**
 * EconomicGrounding (A14) policy gate.
 *
 * Passes when the declared action cost falls within the actor's registered
 * budget. Provides the financial constraint layer required for regulated
 * verticals (SR 11-7, MiFID II, SEC Rule 17a-4).
 *
 * Lean axiom: `economicGrounding` (A14)
 * Lean file: Lutar/Gate/EconomicGrounding.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20162352
 */
export function economicGroundingGate(
  config: EconomicGroundingGateConfig = {}
): (opts: EconomicGroundingGateOpts) => EconomicGroundingDecision {
  const allowAtBudget = config.allowAtBudget ?? true;

  return function gate(opts: EconomicGroundingGateOpts): EconomicGroundingDecision {
    const { actionCost, actorBudget, actorId } = opts;
    if (!Number.isFinite(actionCost) || actionCost < 0) {
      throw new Error(`EconomicGroundingGate: actionCost must be ≥ 0; got ${actionCost}`);
    }
    if (!Number.isFinite(actorBudget) || actorBudget < 0) {
      throw new Error(`EconomicGroundingGate: actorBudget must be ≥ 0; got ${actorBudget}`);
    }
    if (!actorId) throw new Error(`EconomicGroundingGate: actorId is required`);

    const allow          = allowAtBudget ? actionCost <= actorBudget : actionCost < actorBudget;
    const budgetRemaining = Math.max(0, actorBudget - actionCost);
    const utilizationRate = actorBudget > 0 ? actionCost / actorBudget : (actionCost === 0 ? 0 : Infinity);
    const lambdaScore     = allow ? 1.0 - utilizationRate * 0.5 : 0.0;

    const rationale = allow
      ? `EconomicGrounding (A14): actor="${actorId}" cost=${actionCost} ≤ budget=${actorBudget}; remaining=${budgetRemaining}. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `EconomicGrounding (A14): actor="${actorId}" cost=${actionCost} > budget=${actorBudget} — budget exceeded. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "EconomicGrounding", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, actionCost, actorBudget, budgetRemaining, utilizationRate, lambdaScore };
  };
}
