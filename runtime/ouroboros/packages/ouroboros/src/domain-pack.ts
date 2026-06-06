/**
 * Domain pack router — implementation of the missing piece
 * `domain_pack_dispatcher` from `docs/research/ouroboros-runtime-contract.v3.json`.
 *
 * The router selects a domain pack at the start of every loop based on
 * task type, risk tier, tool affinity, proof requirements, client context,
 * and operator mode. Packs are deeply frozen and the routing function is
 * deterministic — given the same inputs, the same pack is always chosen
 * (replay-safe).
 */

import type { RiskTier } from './risk-tier.js';

export type DomainPackId =
  | 'A11oy_core'
  | 'property_ops'
  | 'finance_ops'
  | 'security_ops'
  | 'research_ops'
  | 'data_sync_ops'
  | 'medical_review'
  | 'legal_ops'
  | 'government_workflows'
  | 'creative_studio'
  // v4 ecosystem packs (replit_innovate_full_payload). Sentra_pack and
  // Amaru_pack are v4-canonical names that mirror the security_ops and
  // data_sync_ops packs respectively, with v4 ingestion-contract semantics.
  | 'Sentra_pack'
  | 'Amaru_pack';

export interface DomainPack {
  readonly packId: DomainPackId;
  readonly purpose: string;
  /** Highest tier this pack is permitted to act on without an explicit override. */
  readonly maxTierWithoutOverride: RiskTier;
  /** Whether the pack requires evidence-pack provenance on every commit. */
  readonly evidenceRequired: boolean;
}

function freeze<T extends DomainPack>(obj: T): T {
  return Object.freeze(obj);
}

export const DOMAIN_PACKS: Readonly<Record<DomainPackId, DomainPack>> = Object.freeze({
  A11oy_core: freeze({
    packId: 'A11oy_core',
    purpose: 'general agent orchestration and planner runtime',
    maxTierWithoutOverride: 'R3_high',
    evidenceRequired: false,
  }),
  property_ops: freeze({
    packId: 'property_ops',
    purpose: 'property management, maintenance, scheduling, vendor workflows',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: true,
  }),
  finance_ops: freeze({
    packId: 'finance_ops',
    purpose: 'cashflow, budget review, payment workflows, financial guardrails',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: true,
  }),
  security_ops: freeze({
    packId: 'security_ops',
    purpose: 'recursive threat modeling and access-risk workflows',
    maxTierWithoutOverride: 'R3_high',
    evidenceRequired: true,
  }),
  research_ops: freeze({
    packId: 'research_ops',
    purpose: 'claim-bound research, evidence collection, thesis and payload analysis',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: true,
  }),
  data_sync_ops: freeze({
    packId: 'data_sync_ops',
    purpose: 'convergent synchronization, merge conflicts, delta-based reconciliation',
    maxTierWithoutOverride: 'R3_high',
    evidenceRequired: true,
  }),
  medical_review: freeze({
    packId: 'medical_review',
    purpose: 'non-diagnostic bounded review with mandatory escalation gates',
    maxTierWithoutOverride: 'R1_low',
    evidenceRequired: true,
  }),
  legal_ops: freeze({
    packId: 'legal_ops',
    purpose: 'document analysis and workflow support with approval gates',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: true,
  }),
  government_workflows: freeze({
    packId: 'government_workflows',
    purpose: 'public-sector process support and structured compliance routing',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: true,
  }),
  creative_studio: freeze({
    packId: 'creative_studio',
    purpose: 'content, voice, visual planning, animation, and media workflow orchestration',
    maxTierWithoutOverride: 'R2_moderate',
    evidenceRequired: false,
  }),
  // v4 ecosystem packs (replit_innovate_full_payload).
  Sentra_pack: freeze({
    packId: 'Sentra_pack',
    purpose:
      'recursive threat modeling, security review, escalation, and security evidence workflows (v4 Sentra ingestion contract powered by A11oy_core)',
    maxTierWithoutOverride: 'R3_high',
    evidenceRequired: true,
  }),
  Amaru_pack: freeze({
    packId: 'Amaru_pack',
    purpose:
      'convergent data synchronization, merge governance, conflict reconciliation, and state consistency (v4 Amaru ingestion contract powered by A11oy_core)',
    maxTierWithoutOverride: 'R3_high',
    evidenceRequired: true,
  }),
});

/**
 * v4 task-type → pack mapping per ouroboros-runtime-contract.v4.json.
 * The v4 payload introduces `security_review → Sentra_pack` and
 * `data_sync → Amaru_pack`. Use this map (not the v3 TASK_TO_PACK)
 * when a caller is explicitly running under the v4 ecosystem layer.
 */
export type RoutingTaskTypeV4 =
  | 'security_review'
  | 'data_sync'
  | 'property_ops'
  | 'research'
  | 'finance';

export const TASK_TO_PACK_V4: Readonly<Record<RoutingTaskTypeV4, DomainPackId>> =
  Object.freeze({
    security_review: 'Sentra_pack',
    data_sync: 'Amaru_pack',
    property_ops: 'property_ops',
    research: 'research_ops',
    finance: 'finance_ops',
  });

export type RoutingTaskType =
  | 'agent_orchestration'
  | 'property_management'
  | 'finance_operations'
  | 'security_ops'
  | 'research_and_claims'
  | 'data_sync'
  | 'client_execution'
  | 'medical_review'
  | 'legal_review'
  | 'government_workflow'
  | 'creative_workflow';

export interface RoutingInput {
  taskType: RoutingTaskType;
  riskTier?: RiskTier;
  /** Operator-supplied override (e.g. forcing an explicit pack). */
  forcedPack?: DomainPackId;
}

export const TASK_TO_PACK: Readonly<Record<RoutingTaskType, DomainPackId>> = Object.freeze({
  agent_orchestration: 'A11oy_core',
  property_management: 'property_ops',
  finance_operations: 'finance_ops',
  security_ops: 'security_ops',
  research_and_claims: 'research_ops',
  data_sync: 'data_sync_ops',
  client_execution: 'A11oy_core',
  medical_review: 'medical_review',
  legal_review: 'legal_ops',
  government_workflow: 'government_workflows',
  creative_workflow: 'creative_studio',
});

/**
 * Dispatch a task to the domain pack that should handle it. Pure function:
 * deterministic in `(taskType, riskTier, forcedPack)`.
 *
 * Routing rules:
 *  1. `forcedPack` always wins (operator override).
 *  2. Otherwise the canonical task-type → pack map is consulted.
 *  3. The chosen pack must support the requested risk tier; if the tier
 *     exceeds `maxTierWithoutOverride` without an explicit override, the
 *     return value flags `requiresOverride: true` so the caller can stop
 *     the dispatch and request approval.
 */
export interface RoutingDecision {
  pack: DomainPack;
  source: 'forced' | 'task_type_map';
  requiresOverride: boolean;
}

const TIER_ORDER: Readonly<Record<RiskTier, number>> = Object.freeze({
  R1_low: 1,
  R2_moderate: 2,
  R3_high: 3,
  R4_critical: 4,
});

export function dispatchDomainPack(input: RoutingInput): RoutingDecision {
  if (input.forcedPack) {
    const pack = DOMAIN_PACKS[input.forcedPack];
    return {
      pack,
      source: 'forced',
      requiresOverride:
        input.riskTier !== undefined &&
        TIER_ORDER[input.riskTier] > TIER_ORDER[pack.maxTierWithoutOverride],
    };
  }

  const packId = TASK_TO_PACK[input.taskType];
  const pack = DOMAIN_PACKS[packId];
  return {
    pack,
    source: 'task_type_map',
    requiresOverride:
      input.riskTier !== undefined &&
      TIER_ORDER[input.riskTier] > TIER_ORDER[pack.maxTierWithoutOverride],
  };
}
