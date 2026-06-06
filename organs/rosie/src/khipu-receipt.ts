// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v6
/**
 * khipu-receipt.ts — Khipu-indexed receipt DAG for governed AI decisions.
 *
 * The Inka khipu is a hierarchical knotted-cord record-keeping device whose
 * primary cord value equals the sum of pendant-cord values, and each
 * pendant value equals the sum of its sub-pendant values. The summation
 * invariant is documented in Ascher & Ascher 1981 (U. Michigan Press),
 * Urton 2003 (UT Press, pp. 41–62), Medrano & Khosla 2024 (Latin American
 * Antiquity, on ≥74% of 650 corpus khipu).
 *
 * Geometric / topological reading: the pendant–subsidiary tree is a chord
 * diagram of Vassiliev–Bar-Natan type [Bar-Natan 1995, Topology 34:423–472;
 * Vassiliev 1990, Adv. Sov. Math. 1:23–69]; the summation-cord invariant
 * supplies the 4T closure relation. The dual-attestation field follows the
 * khipu-board ceremony pattern [Hyland, Bennison & Hyland 2021, LARR,
 * DOI 10.25222/LARR.1032] which independently realises what IETF SCITT
 * formalises as a multi-receipt transparent statement
 * [draft-ietf-scitt-architecture-22, 2025].
 *
 * The Lean obligation for the summation invariant is TH11
 * `khipuReceipt_checksum_invariant` in
 * `lutar-lean/Lutar/Khipu/SummationInvariant.lean`.
 *
 * This file is part of the v15 knot-calculus graft (b1_knot_build).
 */

import { createHash } from 'node:crypto';

// ---------------------------------------------------------------------------
// Types — three-tier pendant-cord tree
// ---------------------------------------------------------------------------

/** Leaf-level decision receipt — one governance decision, one hash, one
 * scalar value. `value` is the integer-normalised governance score
 * (typically `Math.round(score * 1e6)`) to keep integer arithmetic. */
export interface DecisionReceipt {
  readonly kind: 'decision';
  readonly decisionId: string;
  readonly value: number;   // integer
  readonly hash: string;    // SHA-256 hex of (decisionId|value|payload)
  readonly payload?: Record<string, unknown>;
}

/** Pendant cord — per-organ aggregation of decisions. `pendantValue` is
 * the sum of contained decision values. */
export interface OrganReceipt {
  readonly kind: 'organ';
  readonly organId: string;
  readonly decisions: ReadonlyArray<DecisionReceipt>;
  readonly pendantValue: number;
  readonly pendantHash: string;  // SHA-256 of organId | sorted child hashes | pendantValue
}

/** Dual-attestation field. Two distinct signers, both required to render
 * the root receipt valid. Mirrors the khipu-board ceremony [Hyland 2021]
 * and the IETF SCITT multi-receipt transparent statement pattern. */
export interface DualAttestation {
  readonly signerA: string;       // signer principal identifier
  readonly signerB: string;       // must be ≠ signerA
  readonly signatureA: string;    // signature over rootHash
  readonly signatureB: string;
  readonly attestedAt: string;    // ISO-8601
}

/** Primary cord — root of the khipu receipt DAG. */
export interface KhipuRootReceipt {
  readonly kind: 'root';
  readonly receiptId: string;
  readonly organs: ReadonlyArray<OrganReceipt>;
  readonly rootValue: number;
  readonly rootHash: string;
  readonly dualAttestation?: DualAttestation;
}

// ---------------------------------------------------------------------------
// Constructors — preserve sum-of-sums invariant by construction
// ---------------------------------------------------------------------------

function sha256Hex(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

/** Build a `DecisionReceipt`. Caller supplies decisionId and integer value;
 * the hash is computed from a canonical serialization. */
export function buildDecision(
  decisionId: string,
  value: number,
  payload?: Record<string, unknown>,
): DecisionReceipt {
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(
      `buildDecision: value must be non-negative integer, got ${value}`,
    );
  }
  const canonical = JSON.stringify({
    decisionId,
    value,
    payload: payload ?? null,
  });
  return {
    kind: 'decision',
    decisionId,
    value,
    hash: sha256Hex(canonical),
    payload,
  };
}

/** Build an `OrganReceipt`. The pendant value is the sum of contained
 * decision values; the pendant hash is `SHA-256(organId | sortedChildHashes | pendantValue)`. */
export function buildOrgan(
  organId: string,
  decisions: ReadonlyArray<DecisionReceipt>,
): OrganReceipt {
  const pendantValue = decisions.reduce((acc, d) => acc + d.value, 0);
  const sortedHashes = [...decisions.map((d) => d.hash)].sort();
  const pendantHash = sha256Hex(
    `${organId}|${sortedHashes.join(',')}|${pendantValue}`,
  );
  return {
    kind: 'organ',
    organId,
    decisions,
    pendantValue,
    pendantHash,
  };
}

/** Build a `KhipuRootReceipt`. The root value is the sum of pendant values;
 * the root hash binds the receiptId, sorted pendant hashes, and root value. */
export function buildRoot(
  receiptId: string,
  organs: ReadonlyArray<OrganReceipt>,
  dualAttestation?: DualAttestation,
): KhipuRootReceipt {
  const rootValue = organs.reduce((acc, o) => acc + o.pendantValue, 0);
  const sortedHashes = [...organs.map((o) => o.pendantHash)].sort();
  const rootHash = sha256Hex(
    `${receiptId}|${sortedHashes.join(',')}|${rootValue}`,
  );
  return {
    kind: 'root',
    receiptId,
    organs,
    rootValue,
    rootHash,
    dualAttestation,
  };
}

// ---------------------------------------------------------------------------
// Invariant verification
// ---------------------------------------------------------------------------

/** Verify that a root's pendant values sum to its rootValue, and each
 * organ's decision values sum to its pendantValue. This is the runtime
 * counterpart to Lean TH11 `khipuReceipt_checksum_invariant`. Returns
 * `{ ok: true }` on success or `{ ok: false, reason: string }` on any
 * mismatch (with the first failing site identified). */
export function verifySumInvariant(
  root: KhipuRootReceipt,
):
  | { ok: true }
  | { ok: false; reason: string } {
  // Check each pendant's decisions sum to its pendantValue.
  for (const organ of root.organs) {
    const computed = organ.decisions.reduce((acc, d) => acc + d.value, 0);
    if (computed !== organ.pendantValue) {
      return {
        ok: false,
        reason:
          `organ "${organ.organId}" pendantValue mismatch: ` +
          `stored=${organ.pendantValue}, computed=${computed}`,
      };
    }
  }
  // Check root.rootValue equals sum of pendantValues.
  const computedRoot = root.organs.reduce((acc, o) => acc + o.pendantValue, 0);
  if (computedRoot !== root.rootValue) {
    return {
      ok: false,
      reason:
        `root "${root.receiptId}" rootValue mismatch: ` +
        `stored=${root.rootValue}, computed=${computedRoot}`,
    };
  }
  return { ok: true };
}

/** Verify dual-attestation: both signers must be present, distinct, and
 * non-empty. Signature verification is the caller's responsibility (this
 * function checks structural validity only — same scope as the Lean
 * `dual_receipt_attestation_soundness` obligation in A8 G4). */
export function verifyDualAttestation(
  root: KhipuRootReceipt,
):
  | { ok: true }
  | { ok: false; reason: string } {
  const att = root.dualAttestation;
  if (!att) {
    return { ok: false, reason: 'no dualAttestation field present' };
  }
  if (!att.signerA || !att.signerB) {
    return { ok: false, reason: 'one or both signer principals missing' };
  }
  if (att.signerA === att.signerB) {
    return {
      ok: false,
      reason: `signers must be distinct; both are "${att.signerA}"`,
    };
  }
  if (!att.signatureA || !att.signatureB) {
    return { ok: false, reason: 'one or both signatures missing' };
  }
  return { ok: true };
}

// ---------------------------------------------------------------------------
// Knot-invariant tag — connects this module to the v15 §10.2 frame.
// ---------------------------------------------------------------------------

/** Emit a knot-invariant tag for a root receipt. The tag identifies the
 * chord-diagram skeleton (pendant-cord topology) of the receipt DAG, hashed
 * together with the root value. Two receipts with the same tag are in the
 * same audit-Reidemeister equivalence class (conjecture; see
 * `lutar-lean/Lutar/Knot/ReidemeisterConjecture.lean`). */
export function knotInvariantTag(root: KhipuRootReceipt): string {
  // Skeleton = sorted list of (organId, decisionCount) pairs.
  const skeleton = [...root.organs.map((o) => `${o.organId}:${o.decisions.length}`)]
    .sort()
    .join(';');
  return sha256Hex(`knot|${skeleton}|${root.rootValue}`).slice(0, 16);
}
