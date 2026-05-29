// Two-level commit — NSA's coarse/fine pair, re-expressed against
// Lutar-Lambda Λ-floor gating. The coarse step (`scoreIndex`) makes a
// `sparse.index.score.v1` claim naming eligible blocks; the fine step
// (`executeSparse`) refuses to run without a valid, fresh parent claim
// and emits `sparse.execute.v1`. The top-k commit between them is a
// budget primitive — exhausting it without escalating is a fail-closed
// event (`sparse.budget.exhausted.v1`).

import type { SparseReceiptCommon } from "./receipts.js";

export interface SparseIndexScoreReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.index.score.v1";
  readonly regimeRef: string;
  readonly eligibleBlocks: ReadonlyArray<{ blockId: number; score: number }>;
}

export interface SparseTopKCommitReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.topk.commit.v1";
  readonly regimeRef: string;
  readonly indexReceiptRef: string;
  readonly committedBlocks: ReadonlyArray<number>;
  readonly budgetK: number;
}

export interface SparseExecuteReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.execute.v1";
  readonly regimeRef: string;
  readonly commitReceiptRef: string;
  readonly attendedBlocks: ReadonlyArray<number>;
}

export interface SparseBudgetExhaustedReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.budget.exhausted.v1";
  readonly regimeRef: string;
  readonly requested: number;
  readonly available: number;
}

export interface ScoreIndexInput {
  readonly regimeRef: string;
  readonly tenant: string;
  readonly nonce: string;
  readonly candidates: ReadonlyArray<{ blockId: number; score: number }>;
  readonly issuedAt?: string;
}

export function scoreIndex(input: ScoreIndexInput): SparseIndexScoreReceipt {
  const issuedAt = input.issuedAt ?? new Date().toISOString();
  return {
    receiptClass: "sparse.index.score.v1",
    freshnessNonce: input.nonce,
    issuedAt,
    tenant: input.tenant,
    parentRef: input.regimeRef,
    regimeRef: input.regimeRef,
    eligibleBlocks: [...input.candidates].sort((a, b) => b.score - a.score),
  };
}

export interface TopKCommitInput {
  readonly regimeRef: string;
  readonly indexReceipt: SparseIndexScoreReceipt;
  readonly budgetK: number;
  readonly tenant: string;
  readonly nonce: string;
  readonly issuedAt?: string;
}

export type TopKCommitOutput =
  | { ok: true; receipt: SparseTopKCommitReceipt }
  | { ok: false; receipt: SparseBudgetExhaustedReceipt };

export function topKCommit(input: TopKCommitInput): TopKCommitOutput {
  const issuedAt = input.issuedAt ?? new Date().toISOString();
  if (input.budgetK <= 0) {
    return {
      ok: false,
      receipt: {
        receiptClass: "sparse.budget.exhausted.v1",
        freshnessNonce: input.nonce,
        issuedAt,
        tenant: input.tenant,
        parentRef: input.regimeRef,
        regimeRef: input.regimeRef,
        requested: input.budgetK,
        available: 0,
      },
    };
  }
  const top = input.indexReceipt.eligibleBlocks.slice(0, input.budgetK).map((b) => b.blockId);
  if (top.length < input.budgetK) {
    return {
      ok: false,
      receipt: {
        receiptClass: "sparse.budget.exhausted.v1",
        freshnessNonce: input.nonce,
        issuedAt,
        tenant: input.tenant,
        parentRef: input.regimeRef,
        regimeRef: input.regimeRef,
        requested: input.budgetK,
        available: top.length,
      },
    };
  }
  return {
    ok: true,
    receipt: {
      receiptClass: "sparse.topk.commit.v1",
      freshnessNonce: input.nonce,
      issuedAt,
      tenant: input.tenant,
      parentRef: input.regimeRef,
      regimeRef: input.regimeRef,
      indexReceiptRef: `${input.indexReceipt.regimeRef}:${input.indexReceipt.freshnessNonce}`,
      committedBlocks: top,
      budgetK: input.budgetK,
    },
  };
}

export interface ExecuteSparseInput {
  readonly regimeRef: string;
  readonly commitReceipt: SparseTopKCommitReceipt;
  readonly attendedBlocks: ReadonlyArray<number>;
  readonly tenant: string;
  readonly nonce: string;
  readonly issuedAt?: string;
}

export function executeSparse(input: ExecuteSparseInput): SparseExecuteReceipt {
  const issuedAt = input.issuedAt ?? new Date().toISOString();
  return {
    receiptClass: "sparse.execute.v1",
    freshnessNonce: input.nonce,
    issuedAt,
    tenant: input.tenant,
    parentRef: input.regimeRef,
    regimeRef: input.regimeRef,
    commitReceiptRef: `${input.commitReceipt.regimeRef}:${input.commitReceipt.freshnessNonce}`,
    attendedBlocks: [...input.attendedBlocks].sort((a, b) => a - b),
  };
}
