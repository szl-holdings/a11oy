// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 2 — TypeScript runtime mirror of Lean theorem `SummationInvariant`
//
// Lean source:
//   szl-holdings/lutar-lean  Lutar/Khipu/SummationInvariant.lean
//   Blob SHA: a661e6b41d9f1f756f7746a83c3e5d9fbe11ba5c
//   Commit SHA (main): 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//
// Theorem statement (Lean):
//   khipuReceipt_checksum_invariant:
//     khipuReceiptTotal r = List.sum (r.organs.map pendantValue)
//   where pendantValue organ = List.sum (organ.decisions.map (·.value))
//
// Inka khipu three-tier summation invariant (TH11):
// A khipu receipt tree satisfies: primaryCord = Σ pendants; pendant_i = Σ leaves_i.
// Any tampering with a leaf value changes the root checksum — additive Merkle
// accumulator integrity enforced by arithmetic, not hash collision resistance alone.
//
// References:
//   Urton 2003, Signs of the Inka Khipu, UT Press pp.41–62
//   Ascher & Ascher 1981, Code of the Quipu, U. Michigan Press
//   Medrano & Khosla 2024, Latin American Antiquity

/** A leaf-level governance decision receipt. */
export interface DecisionReceipt {
  decisionId: string;
  /** Normalised governance score × 10^6 (integer). */
  value: number;
}

/** An organ-level (pendant) receipt: a list of decisions plus an organ tag. */
export interface OrganReceipt {
  organId: string;
  decisions: DecisionReceipt[];
}

/** A full khipu receipt: a list of organs plus a primaryCord checksum. */
export interface KhipuReceipt {
  khipuId: string;
  organs: OrganReceipt[];
  /** Pre-asserted root checksum (primaryCord). Set to sum of all leaf values. */
  primaryCord: number;
}

/** Result of summationInvariant. */
export interface SummationInvariantResult {
  /** The computed pendant values (one per organ). */
  pendantValues: number[];
  /** The computed primary cord total (sum of pendantValues). */
  computedTotal: number;
  /** Whether computedTotal === receipt.primaryCord. */
  invariantHolds: boolean;
  /** Λ-score: 1 if invariantHolds, else 0. */
  lambdaScore: number;
}

/**
 * Verify the khipu summation invariant for a receipt tree.
 *
 * Lean theorem: `khipuReceipt_checksum_invariant`
 * Lean file: Lutar/Khipu/SummationInvariant.lean
 * Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 *
 * Computes:
 *   pendantValue(organ) = Σ organ.decisions[i].value
 *   total = Σ pendantValue(organ)
 *   invariantHolds = (total === receipt.primaryCord)
 *
 * All arithmetic is integer (values are ×10^6 integers per Lean spec).
 */
export function summationInvariant(receipt: KhipuReceipt): SummationInvariantResult {
  if (!receipt.organs || !Array.isArray(receipt.organs)) {
    throw new Error("receipt.organs must be an array");
  }

  // Compute pendant values: pendantValue(organ) = Σ decisions[i].value
  const pendantValues = receipt.organs.map((organ) => {
    if (!Array.isArray(organ.decisions)) {
      throw new Error(`organ ${organ.organId} has no decisions array`);
    }
    return organ.decisions.reduce((sum, d) => {
      if (!Number.isInteger(d.value) || d.value < 0) {
        throw new Error(`decision ${d.decisionId} has invalid value ${d.value} (must be non-negative integer)`);
      }
      return sum + d.value;
    }, 0);
  });

  // Primary cord total = Σ pendantValues
  const computedTotal = pendantValues.reduce((s, v) => s + v, 0);

  // Invariant check (exact integer equality — no floating-point slack needed)
  const invariantHolds = computedTotal === receipt.primaryCord;

  return {
    pendantValues,
    computedTotal,
    invariantHolds,
    lambdaScore: invariantHolds ? 1 : 0,
  };
}

/**
 * Construct a valid KhipuReceipt from an organ list (auto-computes primaryCord).
 * Useful for building test receipts that trivially satisfy the invariant.
 */
export function buildKhipuReceipt(khipuId: string, organs: OrganReceipt[]): KhipuReceipt {
  const pendantValues = organs.map((o) => o.decisions.reduce((s, d) => s + d.value, 0));
  const primaryCord = pendantValues.reduce((s, v) => s + v, 0);
  return { khipuId, organs, primaryCord };
}
