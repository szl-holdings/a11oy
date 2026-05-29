// Contradiction probe — cheap consistency check between the index branch's
// top-k predicted block-set and the sparse branch's actual attended block-set.
//
// Per the MiniMax M2 retrospective, a sparse plan that AGREES with its index
// at small scale but DIVERGES at deep multi-hop is the silent failure mode.
// The probe is therefore the gate between sparse and full attention: low
// agreement triggers `sparse.contradiction.v1` and a paired `sparse.escalated.v1`.

import type { SparseAttentionEnvelope } from "./envelope.js";
import type { SparseReceiptCommon } from "./receipts.js";

export interface SparseContradictionReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.contradiction.v1";
  readonly regimeRef: string; // SparseAttentionEnvelope.regimeId
  readonly agreement: number; // [0,1]
  readonly threshold: number; // envelope.minIndexAgreement
  readonly indexBlocks: ReadonlyArray<number>;
  readonly sparseBlocks: ReadonlyArray<number>;
}

export interface SparseEscalatedReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.escalated.v1";
  readonly regimeRef: string;
  readonly fromMode: "sparse";
  readonly toMode: "full";
  readonly reasonReceiptRef: string; // points at the contradiction receipt
}

/**
 * Jaccard agreement between two block-id sets. ∈ [0,1]. Pure; deterministic.
 */
export function jaccard(a: ReadonlyArray<number>, b: ReadonlyArray<number>): number {
  if (a.length === 0 && b.length === 0) return 1;
  const A = new Set(a);
  const B = new Set(b);
  let inter = 0;
  for (const x of A) if (B.has(x)) inter += 1;
  const union = A.size + B.size - inter;
  return union === 0 ? 1 : inter / union;
}

export interface ProbeInput {
  readonly envelope: SparseAttentionEnvelope;
  readonly indexBlocks: ReadonlyArray<number>;
  readonly sparseBlocks: ReadonlyArray<number>;
  readonly tenant: string;
  readonly nonce: string;
  readonly issuedAt?: string;
}

export type ProbeOutput =
  | { contradicted: false; agreement: number }
  | {
      contradicted: true;
      agreement: number;
      contradiction: SparseContradictionReceipt;
      escalation: SparseEscalatedReceipt;
    };

/**
 * Probe and (on contradiction) emit a paired contradiction + escalation
 * receipt. Caller is responsible for persisting the receipts and for
 * actually switching the orchestrator to full attention — this function
 * is pure and side-effect-free.
 */
export function probe(input: ProbeInput): ProbeOutput {
  const { envelope, indexBlocks, sparseBlocks, tenant, nonce } = input;
  const issuedAt = input.issuedAt ?? new Date().toISOString();
  const agreement = jaccard(indexBlocks, sparseBlocks);
  if (agreement >= envelope.minIndexAgreement) {
    return { contradicted: false, agreement };
  }
  const contradictionId = `${envelope.regimeId}:${nonce}:contradiction`;
  const contradiction: SparseContradictionReceipt = {
    receiptClass: "sparse.contradiction.v1",
    freshnessNonce: nonce,
    issuedAt,
    tenant,
    parentRef: envelope.regimeId,
    regimeRef: envelope.regimeId,
    agreement,
    threshold: envelope.minIndexAgreement,
    indexBlocks: [...indexBlocks].sort((a, b) => a - b),
    sparseBlocks: [...sparseBlocks].sort((a, b) => a - b),
  };
  const escalation: SparseEscalatedReceipt = {
    receiptClass: "sparse.escalated.v1",
    freshnessNonce: nonce,
    issuedAt,
    tenant,
    parentRef: envelope.regimeId,
    regimeRef: envelope.regimeId,
    fromMode: "sparse",
    toMode: "full",
    reasonReceiptRef: contradictionId,
  };
  return { contradicted: true, agreement, contradiction, escalation };
}
