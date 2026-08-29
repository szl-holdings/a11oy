/**
 * GovernedToolReceipt — Series A vertical slice.
 * sideEffectClass + idempotencyKey make ReplayNonMutation testable.
 * lakeSync is never synthesized to ACKNOWLEDGED without a durable ACK.
 */

export type SideEffectClass = "NONE" | "REVERSIBLE" | "IRREVERSIBLE";
export type PolicyDecision = "ALLOW" | "DENY" | "REQUIRE_APPROVAL" | "INCOMPLETE";

export type GovernedToolReceipt = {
  id: string;
  tool: string;
  actor: string;
  requestedAt: string;
  decidedAt: string;
  executedAt: string | null;
  decision: PolicyDecision;
  decisionReason: string;
  constitutionVersion: string;
  sideEffectClass: SideEffectClass;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  payloadHash: string;
  previousReceiptHash: string;
  receiptHash: string;
  signatureKind: "SOFTWARE-SIGNED" | "DSSE-LIVE" | "UNSIGNED" | "DEMO_SIGNED";
  signature: string | null;
  rollbackReference: string | null;
  obligationStatus: "NONE" | "OPEN" | "SATISFIED" | "FAILED";
  lakeSync: "LOCAL_ONLY" | "PENDING_SYNC" | "ACKNOWLEDGED" | "FAILED_SYNC";
  replayOf: string | null;
  coverage: "COMPLETE" | "INCOMPLETE";
  evidenceGaps: string[];
  /** Optional DSSE envelope when signatureKind is DSSE-LIVE. Absent here. */
  dsseEnvelope?: unknown;
};
