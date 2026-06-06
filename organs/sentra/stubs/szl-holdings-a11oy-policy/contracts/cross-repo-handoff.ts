// Local workspace type shim — cross-repo handoff contract.
//
// Type-only mirror of a11oy main
// packages/policy/src/contracts/cross_repo_handoff.ts
// (szl-holdings/a11oy @ e1a48fe). Only the input shape consumed by the
// sentra a11oy orchestration adapter is mirrored here.

export interface CrossRepoHandoffReceiptInput {
  readonly handoffId: string;
  readonly actorId: string;
  readonly sourceCommit?: string;
  readonly outcome: 'queued' | 'owner-applied' | 'target-ci-passed' | 'blocked';
  readonly upstreamPrUrl?: string;
  readonly upstreamCiUrl?: string;
  readonly details?: Record<string, unknown>;
}
