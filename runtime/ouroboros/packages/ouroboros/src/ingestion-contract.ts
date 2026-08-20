/**
 * Ingestion contracts — implementation of the v4 missing piece
 * `ingestion_contracts` from `docs/research/ouroboros-runtime-contract.v4.json`.
 *
 * Sentra (security review) and Amaru (data convergence) ingest through
 * the shared A11oy_core runtime. This module provides the canonical,
 * frozen contract for each: which ingest types are accepted, the loop
 * profile they run under, the validator IDs that must pass, and the
 * required output artifacts they must emit before halt is allowed.
 *
 * Pure module: no I/O, no clock dependency.
 */

import type { ValidatorId } from './validator-registry.js';

export type IngestionTarget = 'Sentra' | 'Amaru';

export type SentraIngestType =
  | 'alerts'
  | 'logs'
  | 'security_events'
  | 'threat_hypotheses'
  | 'attack_paths'
  | 'access_reviews';

export type AmaruIngestType =
  | 'records'
  | 'deltas'
  | 'conflicts'
  | 'schema_variants'
  | 'sync_jobs'
  | 'merge_candidates';

export type LoopProfile =
  | 'security_recursive_review'
  | 'convergent_data_runtime';

export type RequiredOutput =
  | 'trace'
  | 'decision_receipt'
  | 'risk_summary'
  | 'evidence_pack'
  | 'consistency_report'
  | 'delta_log';

export interface IngestionContract {
  readonly target: IngestionTarget;
  readonly poweredBy: 'A11oy_core';
  readonly ingestTypes: readonly string[];
  readonly loopProfile: LoopProfile;
  readonly requiredValidators: readonly ValidatorId[];
  readonly requiredOutputs: readonly RequiredOutput[];
}

function freeze<T extends IngestionContract>(c: T): T {
  return Object.freeze({
    ...c,
    ingestTypes: Object.freeze([...c.ingestTypes]),
    requiredValidators: Object.freeze([...c.requiredValidators]),
    requiredOutputs: Object.freeze([...c.requiredOutputs]),
  });
}

export const INGESTION_CONTRACTS: Readonly<Record<IngestionTarget, IngestionContract>> =
  Object.freeze({
    Sentra: freeze({
      target: 'Sentra',
      poweredBy: 'A11oy_core',
      ingestTypes: [
        'alerts',
        'logs',
        'security_events',
        'threat_hypotheses',
        'attack_paths',
        'access_reviews',
      ] as readonly SentraIngestType[],
      loopProfile: 'security_recursive_review',
      requiredValidators: [
        'VAL_RISK_ESCALATION',
        'VAL_SECURITY_PROOF_REQUIRED',
        'VAL_APPROVAL_FOR_CRITICAL_ACTION',
      ],
      requiredOutputs: ['trace', 'decision_receipt', 'risk_summary', 'evidence_pack'],
    }),
    Amaru: freeze({
      target: 'Amaru',
      poweredBy: 'A11oy_core',
      ingestTypes: [
        'records',
        'deltas',
        'conflicts',
        'schema_variants',
        'sync_jobs',
        'merge_candidates',
      ] as readonly AmaruIngestType[],
      loopProfile: 'convergent_data_runtime',
      requiredValidators: [
        'VAL_SOURCE_PRIORITY_REQUIRED',
        'VAL_MERGE_SAFETY',
        'VAL_CONSISTENCY_BEFORE_COMMIT',
      ],
      requiredOutputs: ['trace', 'decision_receipt', 'consistency_report', 'delta_log'],
    }),
  });

export type IngestionValidationError =
  | 'unknown_target'
  | 'unsupported_ingest_type'
  | 'missing_required_output'
  | 'missing_required_validator';

/**
 * Validate that a proposed ingest payload is admissible under its target's
 * contract. Returns the list of error codes; an empty list means the
 * payload is acceptable.
 *
 * Pure: deterministic in `(target, ingestType, presentOutputs, passedValidators)`.
 */
export function validateIngestion(input: {
  target: string;
  ingestType: string;
  presentOutputs: ReadonlySet<RequiredOutput>;
  passedValidators: ReadonlySet<ValidatorId>;
}): IngestionValidationError[] {
  const errors: IngestionValidationError[] = [];
  if (!Object.hasOwn(INGESTION_CONTRACTS, input.target)) {
    errors.push('unknown_target');
    return errors;
  }
  const contract = INGESTION_CONTRACTS[input.target as IngestionTarget];
  if (!contract.ingestTypes.includes(input.ingestType)) {
    errors.push('unsupported_ingest_type');
  }
  for (const out of contract.requiredOutputs) {
    if (!input.presentOutputs.has(out)) errors.push('missing_required_output');
  }
  for (const v of contract.requiredValidators) {
    if (!input.passedValidators.has(v)) errors.push('missing_required_validator');
  }
  return errors;
}
