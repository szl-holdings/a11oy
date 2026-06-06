/**
 * Evidence pack — standardized provenance bundle for high-consequence
 * outputs and replay-ready decisions. Mirrors `evidence_pack_contract`
 * from `docs/research/ouroboros-runtime-contract.v3.json`.
 *
 * An evidence pack is the minimum surface that downstream auditors,
 * regulators, or replay tooling need in order to verify a decision
 * receipt without re-running the loop.
 */

import { PROOF_ROUTES, type ProofRouteId } from './proof-route.js';
import { RISK_TIERS, type RiskTier } from './risk-tier.js';

export interface EvidencePack {
  readonly evidencePackId: string;
  readonly sourceIds: readonly string[];
  readonly locators: readonly string[];
  readonly proofRouteId: ProofRouteId;
  readonly receiptId: string;
  readonly traceId: string;
  readonly riskTier: RiskTier;
}

export interface EvidencePackInput {
  evidencePackId: string;
  sourceIds: readonly string[];
  locators: readonly string[];
  proofRouteId: ProofRouteId;
  receiptId: string;
  traceId: string;
  riskTier: RiskTier;
}

/**
 * Build a frozen evidence pack from raw inputs. Deeply freezes the result
 * so downstream consumers cannot tamper with provenance after the fact.
 */
export function buildEvidencePack(input: EvidencePackInput): EvidencePack {
  return Object.freeze({
    evidencePackId: input.evidencePackId,
    sourceIds: Object.freeze([...input.sourceIds]),
    locators: Object.freeze([...input.locators]),
    proofRouteId: input.proofRouteId,
    receiptId: input.receiptId,
    traceId: input.traceId,
    riskTier: input.riskTier,
  });
}

export type EvidencePackValidationError =
  | 'missing_evidence_pack_id'
  | 'missing_sources'
  | 'missing_locators'
  | 'missing_receipt_id'
  | 'missing_trace_id'
  | 'invalid_proof_route_id'
  | 'invalid_risk_tier';

/**
 * Validate that an evidence pack carries the minimum required provenance.
 * Returns the list of missing-field error codes; an empty list means the
 * pack is acceptable for high-consequence routing.
 *
 * Covers every required field in `evidence_pack_contract` from
 * `docs/research/ouroboros-runtime-contract.v3.json`. Runtime checks the
 * route-id and risk-tier values as well so untyped callers cannot bypass
 * the contract.
 */
export function validateEvidencePack(
  pack: EvidencePack,
): EvidencePackValidationError[] {
  const errors: EvidencePackValidationError[] = [];
  if (!pack.evidencePackId) errors.push('missing_evidence_pack_id');
  if (pack.sourceIds.length === 0) errors.push('missing_sources');
  if (pack.locators.length === 0) errors.push('missing_locators');
  if (!pack.receiptId) errors.push('missing_receipt_id');
  if (!pack.traceId) errors.push('missing_trace_id');
  // Use Object.hasOwn — the `in` operator walks the prototype chain and
  // would accept attacker-controlled values like `toString`, `constructor`,
  // or `__proto__` as valid route ids / risk tiers.
  if (!pack.proofRouteId || !Object.hasOwn(PROOF_ROUTES, pack.proofRouteId)) {
    errors.push('invalid_proof_route_id');
  }
  if (!pack.riskTier || !Object.hasOwn(RISK_TIERS, pack.riskTier)) {
    errors.push('invalid_risk_tier');
  }
  return errors;
}
