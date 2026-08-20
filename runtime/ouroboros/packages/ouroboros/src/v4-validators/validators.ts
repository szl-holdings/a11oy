/**
 * v4 validator function implementations.
 *
 * Each validator is a pure function `(RuntimeContext) → ValidatorResult`.
 * The function realises the rule already declared in `VALIDATOR_REGISTRY`
 * (see validator-registry.ts). These are NOT axis scores for the Lutar
 * Invariant Λ — they are policy gates that produce boolean pass/fail
 * decisions and are summarised by `summarizeValidators`.
 *
 * Pass / fail semantics follow the v4 contract:
 *   - `passed: true`  → the rule is satisfied (or its precondition is absent)
 *   - `passed: false` → the rule is violated; the `note` explains why
 *
 * All severities are `error` per the registry; `summarizeValidators`
 * halts the run when any error-severity validator fails.
 */

import type { ValidatorFn, ValidatorResult, RuntimeContext } from './types.js';

/* ───────────────────────── helpers ───────────────────────── */

const TIER_RANK: Record<string, number> = Object.freeze({
  R1: 1,
  R2: 2,
  R3: 3,
  R4: 4,
});

function pass(id: string, note?: string): ValidatorResult {
  return Object.freeze({ validatorId: id, passed: true, ...(note ? { note } : {}) }) as ValidatorResult;
}

function fail(id: string, note: string): ValidatorResult {
  return Object.freeze({ validatorId: id, passed: false, note }) as ValidatorResult;
}

/* ───────────────────────── 1. VAL_BUDGET_ENFORCER ───────────────────────── */
// Rule: "No run may exceed configured token, time, or step ceilings."

export const valBudgetEnforcer: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_BUDGET_ENFORCER';
  const breaches: string[] = [];

  if (
    ctx.tokensUsed !== undefined &&
    ctx.tokenCeiling !== undefined &&
    ctx.tokensUsed > ctx.tokenCeiling
  ) {
    breaches.push(`tokens ${ctx.tokensUsed} > ceiling ${ctx.tokenCeiling}`);
  }
  if (
    ctx.stepsUsed !== undefined &&
    ctx.stepCeiling !== undefined &&
    ctx.stepsUsed > ctx.stepCeiling
  ) {
    breaches.push(`steps ${ctx.stepsUsed} > ceiling ${ctx.stepCeiling}`);
  }
  if (
    ctx.elapsedMs !== undefined &&
    ctx.timeCeilingMs !== undefined &&
    ctx.elapsedMs > ctx.timeCeilingMs
  ) {
    breaches.push(`elapsed ${ctx.elapsedMs}ms > ceiling ${ctx.timeCeilingMs}ms`);
  }

  if (breaches.length === 0) return pass(id);
  return fail(id, `budget exceeded: ${breaches.join('; ')}`);
};

/* ───────────────────────── 2. VAL_NO_SILENT_MUTATION ───────────────────────── */
// Rule: "All material state changes must appear in append-only traces."

export const valNoSilentMutation: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_NO_SILENT_MUTATION';
  const muts = ctx.mutations ?? [];
  const silent = muts.filter((m) => !m.recordedInTrace);
  if (silent.length === 0) return pass(id);
  const ids = silent.map((m) => m.id).join(', ');
  return fail(id, `mutation(s) not recorded in trace: ${ids}`);
};

/* ───────────────────────── 3. VAL_PROOF_REQUIRED ───────────────────────── */
// Rule: "Proof route is mandatory for proof-bound tasks."

export const valProofRequired: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_PROOF_REQUIRED';
  if (!ctx.proofRouteRequired) return pass(id);
  if (ctx.proofRouteResolved === true) return pass(id);
  return fail(id, 'proof route required but not resolved');
};

/* ───────────────────────── 4. VAL_RISK_ESCALATION ───────────────────────── */
// Rule: "Runs at or above configured risk thresholds must escalate or halt."

export const valRiskEscalation: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_RISK_ESCALATION';
  if (!ctx.riskTier || !ctx.riskEscalationThreshold) return pass(id);
  const tierRank = TIER_RANK[ctx.riskTier];
  const thresholdRank = TIER_RANK[ctx.riskEscalationThreshold];
  if (tierRank < thresholdRank) return pass(id);
  if (ctx.escalated === true || ctx.halted === true) return pass(id);
  return fail(
    id,
    `tier ${ctx.riskTier} ≥ threshold ${ctx.riskEscalationThreshold} but neither escalated nor halted`,
  );
};

/* ───────────────────────── 5. VAL_APPROVAL_FOR_CRITICAL_ACTION ───────────────────────── */
// Rule: "Critical actions require manual approval before completion."

export const valApprovalForCriticalAction: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_APPROVAL_FOR_CRITICAL_ACTION';
  if (!ctx.criticalAction) return pass(id);
  if (!ctx.approval) return fail(id, 'critical action with no approval snapshot');
  if (!ctx.approval.required) {
    return fail(id, 'critical action but approval.required=false (misconfiguration)');
  }
  if (!ctx.approval.granted) return fail(id, 'critical action approval not granted');
  return pass(id);
};

/* ───────────────────────── 6. VAL_SECURITY_PROOF_REQUIRED ───────────────────────── */
// Rule: "Security conclusions require supporting evidence artifacts."

export const valSecurityProofRequired: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_SECURITY_PROOF_REQUIRED';
  if (!ctx.securityConclusionPresent) return pass(id);
  const count = ctx.securityEvidenceCount ?? 0;
  if (count > 0) return pass(id);
  return fail(id, 'security conclusion with zero supporting evidence artifacts');
};

/* ───────────────────────── 7. VAL_SOURCE_PRIORITY_REQUIRED ───────────────────────── */
// Rule: "Data convergence runs require source precedence metadata."

export const valSourcePriorityRequired: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_SOURCE_PRIORITY_REQUIRED';
  if (!ctx.isDataConvergenceRun) return pass(id);
  const sources = ctx.sources ?? [];
  if (sources.length === 0) return fail(id, 'data convergence run with zero sources');
  const missing = sources.filter(
    (s) => typeof s.precedenceRank !== 'number' || !Number.isFinite(s.precedenceRank),
  );
  if (missing.length > 0) {
    return fail(
      id,
      `${missing.length} source(s) missing precedenceRank: ${missing.map((s) => s.url).join(', ')}`,
    );
  }
  return pass(id);
};

/* ───────────────────────── 8. VAL_MERGE_SAFETY ───────────────────────── */
// Rule: "Unsafe merge actions must halt or escalate."

export const valMergeSafety: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_MERGE_SAFETY';
  const actions = ctx.mergeActions ?? [];
  const unsafe = actions.filter(
    (a) => (a.destructive || a.conflictDetected) && !a.hasManualOverride,
  );
  if (unsafe.length === 0) return pass(id);
  if (ctx.escalated === true || ctx.halted === true) return pass(id);
  return fail(
    id,
    `${unsafe.length} unsafe merge action(s) without escalation or halt: ${unsafe
      .map((a) => a.id)
      .join(', ')}`,
  );
};

/* ───────────────────────── 9. VAL_CONSISTENCY_BEFORE_COMMIT ───────────────────────── */
// Rule: "Amaru cannot finalize without consistency threshold clearance."

export const valConsistencyBeforeCommit: ValidatorFn = (ctx: RuntimeContext) => {
  const id = 'VAL_CONSISTENCY_BEFORE_COMMIT';
  if (!ctx.isAmaruFinalize) return pass(id);
  const c = ctx.consistency;
  if (!c) return fail(id, 'Amaru finalize with no consistency snapshot');
  if (c.metric < c.threshold) {
    return fail(id, `consistency ${c.metric} < threshold ${c.threshold}`);
  }
  return pass(id);
};

/* ───────────────────────── registry of functions ───────────────────────── */

import type { ValidatorId } from '../validator-registry.js';

export const VALIDATOR_FNS: Readonly<Record<ValidatorId, ValidatorFn>> = Object.freeze({
  VAL_BUDGET_ENFORCER: valBudgetEnforcer,
  VAL_NO_SILENT_MUTATION: valNoSilentMutation,
  VAL_PROOF_REQUIRED: valProofRequired,
  VAL_RISK_ESCALATION: valRiskEscalation,
  VAL_APPROVAL_FOR_CRITICAL_ACTION: valApprovalForCriticalAction,
  VAL_SECURITY_PROOF_REQUIRED: valSecurityProofRequired,
  VAL_SOURCE_PRIORITY_REQUIRED: valSourcePriorityRequired,
  VAL_MERGE_SAFETY: valMergeSafety,
  VAL_CONSISTENCY_BEFORE_COMMIT: valConsistencyBeforeCommit,
});
