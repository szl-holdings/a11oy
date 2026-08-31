/**
 * Operator approval gate — implementation of the missing piece
 * `operator_approval_gate` from `docs/research/ouroboros-runtime-contract.v3.json`.
 *
 * Separates the "should this need approval?" question (handled by
 * `risk-tier.ts`) from the "is approval available right now?" question
 * (handled here). Approval providers are pluggable: synchronous in-process
 * approvers for tests, async UI/CLI approvers in production.
 *
 * Pure with respect to provider — calling the gate twice with the same
 * provider returns the same recorded `ApprovalRecord`.
 */

import type { RiskTier } from './risk-tier.js';

export type ApprovalDecision = 'granted' | 'denied' | 'pending';

export interface ApprovalRequest {
  readonly receiptId: string;
  readonly tier: RiskTier;
  readonly summary: string;
  readonly proofRouteId?: string;
}

export interface ApprovalRecord {
  readonly request: ApprovalRequest;
  readonly decision: ApprovalDecision;
  readonly approverId?: string;
  readonly decidedAt?: string;
  readonly note?: string;
}

export type ApprovalProvider = (
  request: ApprovalRequest,
) => Promise<Omit<ApprovalRecord, 'request'>> | Omit<ApprovalRecord, 'request'>;

/**
 * Auto-deny provider — used in tests and as the default when no approver
 * is configured. Refusing by default is the safe failure mode for
 * approval-gated runtime modes.
 */
export const DEFAULT_DENY_PROVIDER: ApprovalProvider = (req) => ({
  decision: 'denied',
  approverId: 'system_auto_deny',
  decidedAt: new Date(0).toISOString(),
  note: `No operator approval provider configured for tier ${req.tier}`,
});

/**
 * Auto-grant provider — used ONLY in test fixtures or replay_audit mode.
 * Never wire this into production.
 */
export function makeAutoGrantProvider(approverId: string): ApprovalProvider {
  return (_req) => ({
    decision: 'granted',
    approverId,
    decidedAt: new Date(0).toISOString(),
    note: 'auto-grant test provider',
  });
}

/**
 * Run the approval gate. Returns the resulting `ApprovalRecord`. The
 * caller is responsible for persisting the record alongside the decision
 * receipt so replay can verify it.
 */
export async function requestApproval(
  request: ApprovalRequest,
  provider: ApprovalProvider = DEFAULT_DENY_PROVIDER,
): Promise<ApprovalRecord> {
  const result = await provider(request);
  return Object.freeze({ request: Object.freeze(request), ...result });
}
