/**
 * v4 validator runtime types.
 *
 * The `RuntimeContext` is the input every validator function consumes.
 * It is deliberately minimal and explicit: each field corresponds to a
 * concept already declared in the v4 codex (validator-registry.ts,
 * runtime-contract.v4.test.ts). Validators do not invent new state —
 * they observe what the runtime has decided to expose.
 *
 * All fields are optional because not every validator needs every
 * field. A validator that requires a field it does not see returns
 * `passed: false` with a `note` explaining the missing prerequisite.
 */

import type { ValidatorId, ValidatorResult } from '../validator-registry.js';

/** A single material state change that must appear in an append-only trace. */
export interface MutationRecord {
  readonly id: string;
  readonly target: string;
  readonly recordedInTrace: boolean;
}

/** Risk tier label as declared by the runtime risk-tier gate. */
export type RuntimeRiskTier = 'R1' | 'R2' | 'R3' | 'R4';

/** Runtime mode label as declared by operational-modes. */
export type RuntimeOperationalMode =
  | 'advisory'
  | 'replay_audit'
  | 'approval_gated'
  | 'semi_autonomous';

/** Approval-gate decision shape. */
export interface ApprovalSnapshot {
  readonly required: boolean;
  readonly granted: boolean;
  readonly approverId?: string;
}

/** A single source citation with its precedence rank. Lower rank = higher priority. */
export interface SourceCitation {
  readonly url: string;
  readonly precedenceRank: number;
}

/** A merge action proposed during a run. */
export interface MergeAction {
  readonly id: string;
  readonly destructive: boolean;
  readonly conflictDetected: boolean;
  readonly hasManualOverride: boolean;
}

/** Amaru consistency reading at commit time. */
export interface ConsistencySnapshot {
  readonly metric: number;
  readonly threshold: number;
}

/**
 * The full runtime context observable to validators at evaluation time.
 *
 * Every field is optional. Validators that need a field and don't see it
 * fail with a precise `note`. This keeps the validators composable
 * across very different runtime profiles (Sentra, Amaru, ad-hoc).
 */
export interface RuntimeContext {
  // VAL_BUDGET_ENFORCER inputs
  readonly tokensUsed?: number;
  readonly tokenCeiling?: number;
  readonly stepsUsed?: number;
  readonly stepCeiling?: number;
  readonly elapsedMs?: number;
  readonly timeCeilingMs?: number;

  // VAL_NO_SILENT_MUTATION inputs
  readonly mutations?: readonly MutationRecord[];

  // VAL_PROOF_REQUIRED / VAL_SECURITY_PROOF_REQUIRED inputs
  readonly proofRouteRequired?: boolean;
  readonly proofRouteResolved?: boolean;
  readonly securityConclusionPresent?: boolean;
  readonly securityEvidenceCount?: number;

  // VAL_RISK_ESCALATION inputs
  readonly riskTier?: RuntimeRiskTier;
  readonly riskEscalationThreshold?: RuntimeRiskTier;
  readonly escalated?: boolean;
  readonly halted?: boolean;

  // VAL_APPROVAL_FOR_CRITICAL_ACTION inputs
  readonly criticalAction?: boolean;
  readonly approval?: ApprovalSnapshot;

  // VAL_SOURCE_PRIORITY_REQUIRED inputs
  readonly isDataConvergenceRun?: boolean;
  readonly sources?: readonly SourceCitation[];

  // VAL_MERGE_SAFETY inputs
  readonly mergeActions?: readonly MergeAction[];

  // VAL_CONSISTENCY_BEFORE_COMMIT inputs
  readonly isAmaruFinalize?: boolean;
  readonly consistency?: ConsistencySnapshot;
}

/** A validator function. Pure, deterministic, no side effects. */
export type ValidatorFn = (ctx: RuntimeContext) => ValidatorResult;

export type { ValidatorId, ValidatorResult };
