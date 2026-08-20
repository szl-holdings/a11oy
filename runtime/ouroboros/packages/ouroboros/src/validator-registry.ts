/**
 * Validator registry — implementation of the v4 missing piece
 * `validators.registry` from `docs/research/ouroboros-runtime-contract.v4.json`.
 *
 * The registry is the single source of truth for every validator the
 * runtime is allowed to invoke. Validators are codified as data (id,
 * severity, rule text) so the validator gate can enumerate and report
 * them deterministically across replays. Severity governs whether a
 * failure halts, escalates, or is recorded as advisory only.
 */

export type ValidatorId =
  | 'VAL_BUDGET_ENFORCER'
  | 'VAL_NO_SILENT_MUTATION'
  | 'VAL_PROOF_REQUIRED'
  | 'VAL_RISK_ESCALATION'
  | 'VAL_APPROVAL_FOR_CRITICAL_ACTION'
  | 'VAL_SECURITY_PROOF_REQUIRED'
  | 'VAL_SOURCE_PRIORITY_REQUIRED'
  | 'VAL_MERGE_SAFETY'
  | 'VAL_CONSISTENCY_BEFORE_COMMIT';

export type ValidatorSeverity = 'error' | 'warn' | 'info';

export interface ValidatorSpec {
  readonly validatorId: ValidatorId;
  readonly severity: ValidatorSeverity;
  readonly rule: string;
}

function freeze<T extends ValidatorSpec>(v: T): T {
  return Object.freeze(v);
}

export const VALIDATOR_REGISTRY: Readonly<Record<ValidatorId, ValidatorSpec>> = Object.freeze({
  VAL_BUDGET_ENFORCER: freeze({
    validatorId: 'VAL_BUDGET_ENFORCER',
    severity: 'error',
    rule: 'No run may exceed configured token, time, or step ceilings.',
  }),
  VAL_NO_SILENT_MUTATION: freeze({
    validatorId: 'VAL_NO_SILENT_MUTATION',
    severity: 'error',
    rule: 'All material state changes must appear in append-only traces.',
  }),
  VAL_PROOF_REQUIRED: freeze({
    validatorId: 'VAL_PROOF_REQUIRED',
    severity: 'error',
    rule: 'Proof route is mandatory for proof-bound tasks.',
  }),
  VAL_RISK_ESCALATION: freeze({
    validatorId: 'VAL_RISK_ESCALATION',
    severity: 'error',
    rule: 'Runs at or above configured risk thresholds must escalate or halt.',
  }),
  VAL_APPROVAL_FOR_CRITICAL_ACTION: freeze({
    validatorId: 'VAL_APPROVAL_FOR_CRITICAL_ACTION',
    severity: 'error',
    rule: 'Critical actions require manual approval before completion.',
  }),
  VAL_SECURITY_PROOF_REQUIRED: freeze({
    validatorId: 'VAL_SECURITY_PROOF_REQUIRED',
    severity: 'error',
    rule: 'Security conclusions require supporting evidence artifacts.',
  }),
  VAL_SOURCE_PRIORITY_REQUIRED: freeze({
    validatorId: 'VAL_SOURCE_PRIORITY_REQUIRED',
    severity: 'error',
    rule: 'Data convergence runs require source precedence metadata.',
  }),
  VAL_MERGE_SAFETY: freeze({
    validatorId: 'VAL_MERGE_SAFETY',
    severity: 'error',
    rule: 'Unsafe merge actions must halt or escalate.',
  }),
  VAL_CONSISTENCY_BEFORE_COMMIT: freeze({
    validatorId: 'VAL_CONSISTENCY_BEFORE_COMMIT',
    severity: 'error',
    rule: 'Amaru cannot finalize without consistency threshold clearance.',
  }),
});

export interface ValidatorResult {
  readonly validatorId: ValidatorId;
  readonly passed: boolean;
  readonly note?: string;
}

/**
 * Summarize a batch of validator results into a halt-or-continue decision.
 * Mirrors the v4 "default_mode: hard_stop_or_escalate" policy: any
 * failed `error`-severity validator halts; lower severities are recorded
 * but do not halt.
 */
export interface ValidatorSummary {
  readonly total: number;
  readonly passed: number;
  readonly failed: readonly ValidatorResult[];
  readonly halt: boolean;
}

export function summarizeValidators(
  results: readonly ValidatorResult[],
): ValidatorSummary {
  const failed: ValidatorResult[] = [];
  let passedCount = 0;
  let halt = false;
  for (const r of results) {
    if (r.passed) {
      passedCount += 1;
      continue;
    }
    failed.push(r);
    const spec = VALIDATOR_REGISTRY[r.validatorId];
    if (spec && spec.severity === 'error') halt = true;
  }
  return Object.freeze({
    total: results.length,
    passed: passedCount,
    failed: Object.freeze([...failed]),
    halt,
  });
}
