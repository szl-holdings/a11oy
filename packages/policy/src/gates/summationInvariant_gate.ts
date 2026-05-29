// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for SummationInvariant
//
// Policy rationale:
//   A receipt is allowed to advance in the governance chain only when the
//   khipu summation invariant holds: the primary cord equals the sum of all
//   pendant-cord values, and each pendant equals the sum of its leaf values.
//   A broken invariant means the receipt tree has been tampered with —
//   the additive Merkle accumulator is violated.
//
//   Lean theorem cited: `khipuReceipt_checksum_invariant`
//   Lean file: Lutar/Khipu/SummationInvariant.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
//   Policy: if summationInvariant(receipt).invariantHolds → allow; else → deny
//
// References:
//   Lean: szl-holdings/lutar-lean Lutar/Khipu/SummationInvariant.lean
//   Runtime: szl-holdings/ouroboros agentic/formulas/summationInvariant.ts
//   Urton 2003, Signs of the Inka Khipu, UT Press pp.41–62

export interface PolicyDecision {
  allow:          boolean;
  rationale:      string;
  formula:        string;
  leanTheorem:    string;
  leanFile:       string;
  leanCommitSha:  string;
  invariantHolds: boolean;
  computedTotal:  number;
  primaryCord:    number;
  delta:          number;
  lambdaScore:    number;
}

export interface DecisionReceipt {
  decisionId: string;
  value:       number;
}

export interface OrganReceipt {
  organId:   string;
  decisions: DecisionReceipt[];
}

export interface KhipuReceiptGateOpts {
  khipuId:    string;
  organs:     OrganReceipt[];
  primaryCord: number;
}

const LEAN_THEOREM = "khipuReceipt_checksum_invariant";
const LEAN_FILE    = "Lutar/Khipu/SummationInvariant.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

// ── Inline formula ────────────────────────────────────────────────────────────
// Lean: khipuReceipt_checksum_invariant:
//   khipuReceiptTotal r = List.sum (r.organs.map pendantValue)

function _checkInvariant(organs: OrganReceipt[], primaryCord: number):
  { invariantHolds: boolean; computedTotal: number; delta: number } {
  const pendantValues = organs.map((o) => o.decisions.reduce((s, d) => s + d.value, 0));
  const computedTotal = pendantValues.reduce((s, v) => s + v, 0);
  const delta = Math.abs(computedTotal - primaryCord);
  return { invariantHolds: computedTotal === primaryCord, computedTotal, delta };
}

/**
 * SummationInvariant policy gate.
 *
 * Allows receipt chain advancement only when the khipu summation invariant holds.
 * Any discrepancy (delta > 0) indicates tampering — the gate denies.
 *
 * Lean theorem: `khipuReceipt_checksum_invariant`
 * Lean file: Lutar/Khipu/SummationInvariant.lean (commit 1dca00032dfc9aa8559cc6c2e4b63192fcf52371)
 */
export function summationInvariantGate(): (opts: KhipuReceiptGateOpts) => PolicyDecision {
  return function gate(opts: KhipuReceiptGateOpts): PolicyDecision {
    const { khipuId, organs, primaryCord } = opts;

    if (!Array.isArray(organs)) {
      throw new Error(`SummationInvariantGate: organs must be an array for khipu ${khipuId}`);
    }

    const { invariantHolds, computedTotal, delta } = _checkInvariant(organs, primaryCord);
    const lambdaScore = invariantHolds ? 1 : 0;

    const rationale = invariantHolds
      ? `KhipuReceipt ${khipuId}: summation invariant holds (total=${computedTotal}). ` +
        `Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`
      : `KhipuReceipt ${khipuId}: invariant BROKEN — computedTotal=${computedTotal} ≠ primaryCord=${primaryCord} ` +
        `(delta=${delta}). Receipt tampered. Lean: ${LEAN_THEOREM} @${LEAN_COMMIT.slice(0, 12)}`;

    return {
      allow:          invariantHolds,
      rationale,
      formula:        "SummationInvariant",
      leanTheorem:    LEAN_THEOREM,
      leanFile:       LEAN_FILE,
      leanCommitSha:  LEAN_COMMIT,
      invariantHolds,
      computedTotal,
      primaryCord,
      delta,
      lambdaScore,
    };
  };
}
