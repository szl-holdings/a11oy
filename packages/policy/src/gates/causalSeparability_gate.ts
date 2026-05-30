// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for CausalSeparability (A11)
//
// Policy rationale:
//   Receipts from disjoint actor sets carry statistically independent entropy.
//   If two receipts share any actor IDs, they may share PRNG seeds, violating
//   the independence property required for cross-actor attribution without
//   information leakage.
//
//   Lean axiom cited: `causalSeparability` (A11)
//   Lean file: Lutar/Gate/CausalSeparability.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (ENFORCED)
//
//   Policy: if actorSetA ∩ actorSetB = ∅ → allow; else → deny
//
// References:
//   Zenodo: https://doi.org/10.5281/zenodo.20119582
//   INNOVATIONS.md §3 A11: causalSeparability

export interface CausalSeparabilityGateConfig {
  /** If true, empty sets are treated as an error. Default: true. */
  requireNonEmpty?: boolean;
}

export interface CausalSeparabilityGateOpts {
  actorSetA: string[];
  actorSetB: string[];
}

export interface CausalSeparabilityDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  sharedActors:   string[];
  disjoint:       boolean;
  lambdaScore:    number;
}

const LEAN_THEOREM = "causalSeparability";
const LEAN_FILE    = "Lutar/Gate/CausalSeparability.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// A11: actor(r) ∩ actor(r') = ∅ ⟹ receipt_hash(r) ⊥ receipt_hash(r')

/**
 * CausalSeparability (A11) policy gate.
 *
 * Checks that two actor sets are disjoint. Shared actors indicate potential
 * PRNG seed sharing, violating the independence property for cross-actor
 * receipt attribution.
 *
 * Lean axiom: `causalSeparability` (A11)
 * Lean file: Lutar/Gate/CausalSeparability.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 * Zenodo: https://doi.org/10.5281/zenodo.20119582
 */
export function causalSeparabilityGate(
  config: CausalSeparabilityGateConfig = {}
): (opts: CausalSeparabilityGateOpts) => CausalSeparabilityDecision {
  const requireNonEmpty = config.requireNonEmpty ?? true;

  return function gate(opts: CausalSeparabilityGateOpts): CausalSeparabilityDecision {
    const { actorSetA, actorSetB } = opts;
    if (requireNonEmpty && (actorSetA.length === 0 || actorSetB.length === 0)) {
      throw new Error(`CausalSeparabilityGate: both actor sets must be non-empty`);
    }

    const setA        = new Set(actorSetA);
    const sharedActors = actorSetB.filter(a => setA.has(a));
    const disjoint    = sharedActors.length === 0;
    const allow       = disjoint;
    const lambdaScore = disjoint ? 1.0 : 1.0 - sharedActors.length / Math.max(actorSetA.length, actorSetB.length);

    const rationale = allow
      ? `CausalSeparability (A11): actor sets disjoint (|A|=${actorSetA.length}, |B|=${actorSetB.length}). Independent entropy assured. Passes. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `CausalSeparability (A11): shared actors [${sharedActors.slice(0,3).join(',')}${sharedActors.length > 3 ? '…' : ''}] — sets not disjoint. Denied. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return { allow, rationale, formula: "CausalSeparability", leanTheorem: LEAN_THEOREM, leanFile: LEAN_FILE, leanCommitSha: LEAN_COMMIT, sharedActors, disjoint, lambdaScore };
  };
}
