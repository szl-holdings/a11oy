/**
 * Operational modes registry — codifies the five operator presence modes
 * from `docs/research/ouroboros-runtime-contract.v3.json`.
 *
 * The modes interact with the risk-tier gate (see `risk-tier.ts`):
 *   - `advisory`              → no execution; recommendations only
 *   - `semi_autonomous`       → R1/R2 may execute; R3+ requires approval
 *   - `approval_gated`        → R2+ requires approval (default for prod)
 *   - `replay_audit`          → execution disabled; replay receipts only
 *   - `distillation_capture`  → execute under approval_gated rules,
 *                               additionally capture high-quality traces
 */

import type { RiskTier } from './risk-tier.js';

export type OperationalMode =
  | 'advisory'
  | 'semi_autonomous'
  | 'approval_gated'
  | 'replay_audit'
  | 'distillation_capture';

export interface OperationalModePolicy {
  readonly mode: OperationalMode;
  readonly description: string;
  readonly executionAllowed: boolean;
  /** Tiers permitted to execute autonomously (no manual approval). */
  readonly autoExecutionTiers: readonly RiskTier[];
  readonly captureDistillationTraces: boolean;
}

export const OPERATIONAL_MODES: Readonly<Record<OperationalMode, OperationalModePolicy>> =
  Object.freeze({
    advisory: Object.freeze({
      mode: 'advisory',
      description: 'Suggest only, no autonomous execution',
      executionAllowed: false,
      autoExecutionTiers: Object.freeze([] as RiskTier[]),
      captureDistillationTraces: false,
    }),
    semi_autonomous: Object.freeze({
      mode: 'semi_autonomous',
      description: 'Execute low-risk actions under validator and budget constraints',
      executionAllowed: true,
      autoExecutionTiers: Object.freeze(['R1_low', 'R2_moderate'] as RiskTier[]),
      captureDistillationTraces: false,
    }),
    approval_gated: Object.freeze({
      mode: 'approval_gated',
      description: 'Require approval before medium/high-risk actions complete',
      executionAllowed: true,
      autoExecutionTiers: Object.freeze(['R1_low'] as RiskTier[]),
      captureDistillationTraces: false,
    }),
    replay_audit: Object.freeze({
      mode: 'replay_audit',
      description: 'Replay historical traces, receipts, and golden runs',
      executionAllowed: false,
      autoExecutionTiers: Object.freeze([] as RiskTier[]),
      captureDistillationTraces: false,
    }),
    distillation_capture: Object.freeze({
      mode: 'distillation_capture',
      description: 'Capture high-quality traces for later policy or model distillation',
      executionAllowed: true,
      autoExecutionTiers: Object.freeze(['R1_low'] as RiskTier[]),
      captureDistillationTraces: true,
    }),
  });

export function isAutoExecutionAllowed(
  mode: OperationalMode,
  tier: RiskTier,
): boolean {
  const policy = OPERATIONAL_MODES[mode];
  if (!policy.executionAllowed) return false;
  return policy.autoExecutionTiers.includes(tier);
}
