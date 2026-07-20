// VENDORED FROM szl-holdings/platform@c11291e09702c86f3f8995fffcae6167155c7240 — packages/codex-kernel/src/receipts.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Decision receipts — the human-readable, replayable record of why a step
 * committed. Each receipt is keyed by `receipt_id` and indexed in the
 * proof ledger.
 */

import type { DecisionReceipt, ISO8601 } from './types.js';

export interface ReceiptIdSeed {
  experiment_id: string;
  step: number;
}

/** Deterministic id: e.g. "rcpt-E4-0007". */
export function buildReceiptId(seed: ReceiptIdSeed): string {
  return `rcpt-${seed.experiment_id}-${String(seed.step).padStart(4, '0')}`;
}

/** Detect whether any evidence entry was marked as mocked / synthetic. */
export function isMocked(
  evidence: ReadonlyArray<{ mocked?: boolean }>,
): boolean {
  return evidence.some((e) => e.mocked === true);
}

/**
 * Build a fully-formed DecisionReceipt from the partial returned by a
 * StepProposal.buildReceipt callback. Adds receipt_id, step, timestamp.
 */
export function finalizeReceipt(
  partial: Omit<DecisionReceipt, 'receipt_id' | 'step' | 'timestamp'>,
  ctx: { experiment_id: string; step: number; now: ISO8601 },
): DecisionReceipt {
  return {
    ...partial,
    receipt_id: buildReceiptId({ experiment_id: ctx.experiment_id, step: ctx.step }),
    step: ctx.step,
    timestamp: ctx.now,
    mocked: partial.mocked ?? isMocked(partial.evidence),
  };
}
