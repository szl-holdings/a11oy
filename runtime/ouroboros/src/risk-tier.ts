/**
 * Risk-tier escalation gate — implementation of the missing piece
 * `risk_tier_escalation_gate` from `docs/research/ouroboros-runtime-contract.v2.json`.
 *
 * Tiers mirror the payload contract:
 *   R1_low       — informational; receipt required, no manual approval
 *   R2_moderate  — operational with limited consequence; receipt required
 *   R3_high      — high-consequence system actions; manual approval required
 *   R4_critical  — security/financial/medical/legal consequence; force escalation
 *
 * The gate is purely functional. The runtime calls `evaluateRiskTier` before
 * each step transition; the returned `RiskTierDecision` tells the kernel
 * whether to continue, halt for approval, or force-escalate out of band.
 */

export type RiskTier = 'R1_low' | 'R2_moderate' | 'R3_high' | 'R4_critical';

export interface RiskTierPolicy {
  readonly tier: RiskTier;
  readonly description: string;
  readonly requiresManualApproval: boolean;
  readonly receiptRequired: boolean;
  readonly forceEscalation: boolean;
}

export const RISK_TIERS: Readonly<Record<RiskTier, RiskTierPolicy>> = Object.freeze({
  R1_low: Object.freeze({
    tier: 'R1_low',
    description: 'Low-risk informational tasks',
    requiresManualApproval: false,
    receiptRequired: true,
    forceEscalation: false,
  }),
  R2_moderate: Object.freeze({
    tier: 'R2_moderate',
    description: 'Operational tasks with limited consequence',
    requiresManualApproval: false,
    receiptRequired: true,
    forceEscalation: false,
  }),
  R3_high: Object.freeze({
    tier: 'R3_high',
    description: 'High-consequence system actions or regulated recommendations',
    requiresManualApproval: true,
    receiptRequired: true,
    forceEscalation: false,
  }),
  R4_critical: Object.freeze({
    tier: 'R4_critical',
    description:
      'Critical actions with security, financial, medical, or legal consequence',
    requiresManualApproval: true,
    receiptRequired: true,
    forceEscalation: true,
  }),
});

export type RiskTierDecision =
  | { gate: 'continue'; tier: RiskTier; reason: string }
  | { gate: 'await_approval'; tier: RiskTier; reason: string }
  | { gate: 'force_escalate'; tier: RiskTier; reason: string };

export interface RiskTierContext {
  tier: RiskTier;
  approvalGranted?: boolean;
  approverId?: string;
  operatorMode?:
    | 'advisory'
    | 'semi_autonomous'
    | 'approval_gated'
    | 'replay_audit';
}

/**
 * Decide whether the current step is allowed to proceed under the configured
 * risk tier. The decision is deterministic in `(tier, approvalGranted,
 * operatorMode)` so it is fully replayable in audit mode.
 */
export function evaluateRiskTier(ctx: RiskTierContext): RiskTierDecision {
  const policy = RISK_TIERS[ctx.tier];

  if (policy.forceEscalation) {
    return {
      gate: 'force_escalate',
      tier: ctx.tier,
      reason: `Tier ${ctx.tier} force-escalates per Ouroboros contract`,
    };
  }

  if (ctx.operatorMode === 'replay_audit') {
    return {
      gate: 'continue',
      tier: ctx.tier,
      reason: 'replay_audit mode bypasses approval; receipts already exist',
    };
  }

  if (ctx.operatorMode === 'advisory') {
    return {
      gate: 'continue',
      tier: ctx.tier,
      reason: 'advisory mode emits recommendations only; no execution',
    };
  }

  if (policy.requiresManualApproval && ctx.approvalGranted !== true) {
    return {
      gate: 'await_approval',
      tier: ctx.tier,
      reason: `Tier ${ctx.tier} requires manual approval before continuation`,
    };
  }

  return {
    gate: 'continue',
    tier: ctx.tier,
    reason: 'Risk-tier policy permits continuation',
  };
}
