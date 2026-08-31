// Recorded router — MoBA's "record what was attended, do not prescribe what
// must be attended" discipline. The router decides per-query which blocks to
// route to; the record of those decisions IS the artifact under audit.
//
// We wrap any block-selection function (the router) so that every call emits
// `sparse.router.trace.v1`. A router whose recent traces violate its declared
// envelope is auto-demoted by the orchestrator at receipt-write time.

import type { SparseAttentionEnvelope } from "./envelope.js";
import type { SparseReceiptCommon } from "./receipts.js";

export interface SparseRouterTraceReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.router.trace.v1";
  readonly routerRef: string;
  readonly regimeRef: string;
  readonly queryId: string;
  readonly blocksSelected: ReadonlyArray<number>;
  readonly scoreDistribution: ReadonlyArray<number>;
}

export type BlockSelector = (queryId: string) => {
  blocksSelected: ReadonlyArray<number>;
  scoreDistribution: ReadonlyArray<number>;
};

export interface RecordedRouterInput {
  readonly routerRef: string;
  readonly envelope: SparseAttentionEnvelope;
  readonly select: BlockSelector;
  readonly tenant: string;
}

export interface RecordedRouter {
  readonly route: (queryId: string, nonce: string, issuedAt?: string) => {
    blocksSelected: ReadonlyArray<number>;
    trace: SparseRouterTraceReceipt;
    envelopeBreach: boolean;
  };
}

/**
 * Wrap a `BlockSelector` in a receipt emitter. `envelopeBreach` is true when
 * the router selects more than envelope.maxBlocks — the orchestrator MUST
 * treat that as a demotion trigger (NOT silently truncate).
 */
export function recordedRouter(input: RecordedRouterInput): RecordedRouter {
  return {
    route: (queryId, nonce, issuedAt) => {
      const at = issuedAt ?? new Date().toISOString();
      const { blocksSelected, scoreDistribution } = input.select(queryId);
      const breach = blocksSelected.length > input.envelope.maxBlocks;
      const trace: SparseRouterTraceReceipt = {
        receiptClass: "sparse.router.trace.v1",
        freshnessNonce: nonce,
        issuedAt: at,
        tenant: input.tenant,
        parentRef: input.envelope.regimeId,
        routerRef: input.routerRef,
        regimeRef: input.envelope.regimeId,
        queryId,
        blocksSelected: [...blocksSelected].sort((a, b) => a - b),
        scoreDistribution: [...scoreDistribution],
      };
      return { blocksSelected, trace, envelopeBreach: breach };
    },
  };
}
