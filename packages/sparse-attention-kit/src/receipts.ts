// Doctrine V6 receipt classes emitted by this kit.
//
// Every receipt class in this file is on the *critical path* of a sparse-
// attention plan: a sparse plan that lacks an admission receipt cannot
// execute; a contradiction that lacks an escalation receipt is a doctrine
// violation; a router whose recent traces violate its declared envelope is
// auto-demoted at receipt-write time.
//
// Receipts are typed shapes ONLY — the emit/persist transport is owned by
// the api-server. This package never reaches out to a transport.

export const RECEIPT_CLASSES = [
  "sparse.regime.admitted.v1",
  "sparse.regime.rejected.v1",
  "sparse.regime.demoted.v1",
  "sparse.contradiction.v1",
  "sparse.escalated.v1",
  "sparse.index.score.v1",
  "sparse.topk.commit.v1",
  "sparse.execute.v1",
  "sparse.budget.exhausted.v1",
  "sparse.router.trace.v1",
  "sparse.io.budget.v1",
  "sparse.io.overrun.v1",
] as const;

export type SparseReceiptClass = (typeof RECEIPT_CLASSES)[number];

export interface SparseReceiptCommon {
  readonly receiptClass: SparseReceiptClass;
  readonly freshnessNonce: string;
  readonly issuedAt: string; // ISO 8601 UTC
  readonly parentRef?: string; // chain to upstream receipt (e.g. admission → execution)
  readonly tenant: string;
}

export function isSparseReceiptClass(s: string): s is SparseReceiptClass {
  return (RECEIPT_CLASSES as readonly string[]).includes(s);
}
