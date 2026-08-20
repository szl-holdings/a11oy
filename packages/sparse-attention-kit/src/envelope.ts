// SparseAttentionEnvelope — typed regime claim under which a sparse plan
// is permitted. Re-expressed from MiniMax's M1→M2 reveal: hybrid-sparse
// wins benchmarks but loses multi-hop reasoning at scale, so a sparse
// regime MUST name the envelope outside which the orchestrator escalates
// to full attention.
//
// This file is dependency-free on purpose: it must be importable from a
// browser bundle, a node worker, and an edge runtime without dragging
// zod or any other validator in. A separate `@workspace/api-spec` zod
// schema mirrors these fields at the route boundary.

import type { SparseReceiptCommon } from "./receipts.js";

export type TenantClass =
  | "operator"
  | "reviewer"
  | "ledger"
  | "control-plane"
  | "tactical-edge";

export interface SparseAttentionEnvelope {
  /** Stable identifier for the regime claim — used as parentRef in downstream receipts. */
  readonly regimeId: string;
  /** Tenant class permitted to *consume* this regime. Cross-tenant use is a Sentra fail-closed event. */
  readonly tenantClass: TenantClass;
  /** Maximum number of attention blocks the sparse plan may name. */
  readonly maxBlocks: number;
  /** Maximum reasoning-hop depth the plan claims to support without escalation. */
  readonly maxHopDepth: number;
  /**
   * Minimum agreement (∈ [0,1]) between the index branch's top-k prediction
   * and the sparse branch's actual attended block-set under which the plan
   * may execute. Below this, the contradiction-probe MUST trigger escalation.
   */
  readonly minIndexAgreement: number;
  /** Block size in tokens. Treat as policy, never hardcode. */
  readonly blockSizeTokens: number;
  /** IO bandwidth budget in bytes (HBM round-trips). FlashAttention discipline. */
  readonly ioBudgetBytes: number;
  /** Validity window in seconds — outside this, the regime must be re-admitted. */
  readonly ttlSeconds: number;
  /** Freshness nonce produced at admission. */
  readonly freshnessNonce: string;
  /** ISO-8601 UTC. */
  readonly issuedAt: string;
}

export interface SparseRegimeAdmittedReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.regime.admitted.v1";
  readonly envelope: SparseAttentionEnvelope;
}

export interface SparseRegimeRejectedReceipt extends SparseReceiptCommon {
  readonly receiptClass: "sparse.regime.rejected.v1";
  readonly proposedEnvelope: SparseAttentionEnvelope;
  readonly violatedRule:
    | "block-size-too-large"
    | "hop-depth-too-deep"
    | "index-agreement-too-low"
    | "io-budget-negative"
    | "ttl-out-of-range"
    | "tenant-not-permitted";
  readonly explanation: string;
}

export interface AdmissionPolicy {
  readonly maxBlockSizeTokens: number;
  readonly maxHopDepth: number;
  readonly minIndexAgreement: number;
  readonly maxTtlSeconds: number;
  readonly permittedTenantClasses: ReadonlyArray<TenantClass>;
}

export interface AdmitInput {
  readonly proposed: SparseAttentionEnvelope;
  readonly policy: AdmissionPolicy;
  readonly tenant: string;
  readonly issuedAt?: string;
}

export type AdmitOutput =
  | { ok: true; receipt: SparseRegimeAdmittedReceipt }
  | { ok: false; receipt: SparseRegimeRejectedReceipt };

/**
 * Pure admission: never throws, never emits — caller writes the returned
 * receipt to the ledger. Deny-by-default; the absence of any explicit
 * permit clause is treated as a rejection.
 */
export function admit(input: AdmitInput): AdmitOutput {
  const { proposed, policy, tenant } = input;
  const issuedAt = input.issuedAt ?? new Date().toISOString();

  const rejectWith = (
    rule: SparseRegimeRejectedReceipt["violatedRule"],
    explanation: string,
  ): AdmitOutput => ({
    ok: false,
    receipt: {
      receiptClass: "sparse.regime.rejected.v1",
      freshnessNonce: proposed.freshnessNonce,
      issuedAt,
      tenant,
      proposedEnvelope: proposed,
      violatedRule: rule,
      explanation,
    },
  });

  if (!policy.permittedTenantClasses.includes(proposed.tenantClass)) {
    return rejectWith(
      "tenant-not-permitted",
      `tenant class ${proposed.tenantClass} not in permitted set [${policy.permittedTenantClasses.join(", ")}]`,
    );
  }
  if (proposed.blockSizeTokens <= 0 || proposed.blockSizeTokens > policy.maxBlockSizeTokens) {
    return rejectWith(
      "block-size-too-large",
      `blockSizeTokens=${proposed.blockSizeTokens} not in (0, ${policy.maxBlockSizeTokens}]`,
    );
  }
  if (proposed.maxHopDepth <= 0 || proposed.maxHopDepth > policy.maxHopDepth) {
    return rejectWith(
      "hop-depth-too-deep",
      `maxHopDepth=${proposed.maxHopDepth} not in (0, ${policy.maxHopDepth}]`,
    );
  }
  if (proposed.minIndexAgreement < policy.minIndexAgreement || proposed.minIndexAgreement > 1) {
    return rejectWith(
      "index-agreement-too-low",
      `minIndexAgreement=${proposed.minIndexAgreement} below policy floor ${policy.minIndexAgreement}`,
    );
  }
  if (proposed.ioBudgetBytes <= 0) {
    return rejectWith("io-budget-negative", `ioBudgetBytes must be > 0, got ${proposed.ioBudgetBytes}`);
  }
  if (proposed.ttlSeconds <= 0 || proposed.ttlSeconds > policy.maxTtlSeconds) {
    return rejectWith(
      "ttl-out-of-range",
      `ttlSeconds=${proposed.ttlSeconds} not in (0, ${policy.maxTtlSeconds}]`,
    );
  }

  return {
    ok: true,
    receipt: {
      receiptClass: "sparse.regime.admitted.v1",
      freshnessNonce: proposed.freshnessNonce,
      issuedAt,
      tenant,
      envelope: proposed,
    },
  };
}
