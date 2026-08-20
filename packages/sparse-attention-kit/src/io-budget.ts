// IO-budget receipts — FlashAttention's IO-aware discipline re-expressed as
// a typed claim. Every sparse/full attention execution MUST name its
// ioBudgetBytes claim AND its ioConsumedBytes measurement; a sparse plan
// that saves FLOPs but inflates IO is detectable at the receipt-ledger level
// rather than at a wall-clock anomaly downstream.

import type { SparseReceiptCommon } from "./receipts.js";

export interface SparseIoBudgetReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.io.budget.v1";
  readonly regimeRef: string;
  readonly executeReceiptRef: string;
  readonly ioBudgetBytes: number;
  readonly ioConsumedBytes: number;
  readonly withinBudget: true;
}

export interface SparseIoOverrunReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.io.overrun.v1";
  readonly regimeRef: string;
  readonly executeReceiptRef: string;
  readonly ioBudgetBytes: number;
  readonly ioConsumedBytes: number;
  readonly overrunRatio: number; // consumed / budget; > 1 by definition
}

export interface RecordIoInput {
  readonly regimeRef: string;
  readonly executeReceiptRef: string;
  readonly ioBudgetBytes: number;
  readonly ioConsumedBytes: number;
  readonly tenant: string;
  readonly nonce: string;
  readonly issuedAt?: string;
}

export type RecordIoOutput =
  | { overrun: false; receipt: SparseIoBudgetReceipt }
  | { overrun: true; receipt: SparseIoOverrunReceipt };

export function recordIo(input: RecordIoInput): RecordIoOutput {
  const issuedAt = input.issuedAt ?? new Date().toISOString();
  if (input.ioConsumedBytes <= input.ioBudgetBytes) {
    return {
      overrun: false,
      receipt: {
        receiptClass: "sparse.io.budget.v1",
        freshnessNonce: input.nonce,
        issuedAt,
        tenant: input.tenant,
        parentRef: input.regimeRef,
        regimeRef: input.regimeRef,
        executeReceiptRef: input.executeReceiptRef,
        ioBudgetBytes: input.ioBudgetBytes,
        ioConsumedBytes: input.ioConsumedBytes,
        withinBudget: true,
      },
    };
  }
  return {
    overrun: true,
    receipt: {
      receiptClass: "sparse.io.overrun.v1",
      freshnessNonce: input.nonce,
      issuedAt,
      tenant: input.tenant,
      parentRef: input.regimeRef,
      regimeRef: input.regimeRef,
      executeReceiptRef: input.executeReceiptRef,
      ioBudgetBytes: input.ioBudgetBytes,
      ioConsumedBytes: input.ioConsumedBytes,
      overrunRatio: input.ioConsumedBytes / input.ioBudgetBytes,
    },
  };
}
