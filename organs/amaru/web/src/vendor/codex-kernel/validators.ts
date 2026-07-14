// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — packages/codex-kernel/src/validators.ts
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/**
 * Built-in validators for the Codex-Kernel.
 *
 * Validators are pure functions of (ValidationContext) → ValidatorResult.
 * They run AFTER the proposed delta has been computed and the next state
 * has been hashed, but BEFORE the transition is committed to the trace
 * and proof ledger.
 *
 * Severity semantics:
 *  - 'pass'      → continue
 *  - 'soft_fail' → continue but mark; consumed by adaptive depth + entropy exit
 *  - 'hard_fail' → halt the loop with stop_reason = 'validator_hard_stop'
 */

import type { Json, ValidationContext, ValidatorResult } from './types.js';

// ────────────────────────────────────────────────────────────────────────────
// stateTransitionRule
// ────────────────────────────────────────────────────────────────────────────
/**
 * Verifies the proposed delta is a non-empty plain object — i.e. that the
 * step actually proposed something. Hard-stops on silent (empty) mutations.
 */
export const stateTransitionRule = (
  ctx: ValidationContext,
): ValidatorResult => {
  const delta = ctx.proposed_delta as Record<string, unknown>;
  const isObj =
    delta !== null && typeof delta === 'object' && !Array.isArray(delta);
  const hasKeys = isObj && Object.keys(delta).length > 0;
  if (!isObj) {
    return {
      name: 'state_transition_rule',
      severity: 'hard_fail',
      summary: 'proposed_delta must be a plain object',
    };
  }
  if (!hasKeys) {
    return {
      name: 'state_transition_rule',
      severity: 'hard_fail',
      summary: 'silent mutation: proposed_delta is empty',
    };
  }
  return {
    name: 'state_transition_rule',
    severity: 'pass',
    summary: 'delta well-formed',
  };
};

// ────────────────────────────────────────────────────────────────────────────
// driftBounds
// ────────────────────────────────────────────────────────────────────────────
export interface DriftBoundsConfig<S> {
  /** Reads the drift signal off the next_state. */
  read: (next: S) => number;
  warning_threshold: number;
  hard_threshold: number;
  /** When true, a soft fail is silenced if a correction was applied this step. */
  correction_applied: (delta: Json) => boolean;
}

export function driftBounds<S extends Json>(
  cfg: DriftBoundsConfig<S>,
): (ctx: ValidationContext<S>) => ValidatorResult {
  return (ctx: ValidationContext<S>): ValidatorResult => {
    const drift = Math.abs(cfg.read(ctx.next_state));
    const corrected = cfg.correction_applied(ctx.proposed_delta);
    if (drift >= cfg.hard_threshold) {
      return {
        name: 'drift_bounds',
        severity: 'hard_fail',
        summary: `drift ${drift} exceeds hard threshold ${cfg.hard_threshold}`,
        details: { drift, threshold: cfg.hard_threshold },
      };
    }
    if (drift >= cfg.warning_threshold && !corrected) {
      return {
        name: 'drift_bounds',
        severity: 'soft_fail',
        summary: `drift ${drift} above warning ${cfg.warning_threshold}, no correction`,
        details: { drift, threshold: cfg.warning_threshold },
      };
    }
    return {
      name: 'drift_bounds',
      severity: 'pass',
      summary: `drift ${drift} within bounds`,
      details: { drift },
    };
  };
}

// ────────────────────────────────────────────────────────────────────────────
// evidenceProvenance
// ────────────────────────────────────────────────────────────────────────────
/**
 * Hard-stop if a non-trivial step would commit without a decision receipt
 * containing assumptions + evidence + policy_version. This is the EU AI Act
 * Article 12 rule expressed as code.
 *
 * Implemented as a function that the kernel calls after `buildReceipt()`;
 * if the receipt is null AND the delta is non-trivial, it hard-fails.
 */
export const evidenceProvenance = (
  ctx: ValidationContext,
  receipt: { assumptions: string[]; evidence: unknown[]; policy_version: string } | null,
): ValidatorResult => {
  if (!receipt) {
    return {
      name: 'evidence_provenance',
      severity: 'hard_fail',
      summary: 'non-trivial delta committed without decision receipt',
    };
  }
  if (!Array.isArray(receipt.assumptions)) {
    return {
      name: 'evidence_provenance',
      severity: 'hard_fail',
      summary: 'receipt missing assumptions[]',
    };
  }
  if (!Array.isArray(receipt.evidence)) {
    return {
      name: 'evidence_provenance',
      severity: 'hard_fail',
      summary: 'receipt missing evidence[]',
    };
  }
  if (!receipt.policy_version) {
    return {
      name: 'evidence_provenance',
      severity: 'hard_fail',
      summary: 'receipt missing policy_version',
    };
  }
  // Best-effort: warn if no evidence at all and not flagged as mocked.
  if (receipt.evidence.length === 0) {
    return {
      name: 'evidence_provenance',
      severity: 'soft_fail',
      summary: 'receipt has empty evidence[]',
    };
  }
  void ctx;
  return {
    name: 'evidence_provenance',
    severity: 'pass',
    summary: 'receipt complete',
  };
};

// ────────────────────────────────────────────────────────────────────────────
// humanGate
// ────────────────────────────────────────────────────────────────────────────
/**
 * Hard-stop if a step requires approval and approval is not 'approved'.
 * The kernel resolves approvals via the resolveApproval callback BEFORE
 * commit; this validator inspects the result.
 */
export const humanGate = (
  required: 'not_required' | 'pending' | 'approved' | 'rejected',
): ValidatorResult => {
  if (required === 'not_required') {
    return { name: 'human_gate', severity: 'pass', summary: 'no approval required' };
  }
  if (required === 'approved') {
    return { name: 'human_gate', severity: 'pass', summary: 'human approved' };
  }
  if (required === 'pending') {
    return {
      name: 'human_gate',
      severity: 'hard_fail',
      summary: 'approval required but not resolved',
    };
  }
  return {
    name: 'human_gate',
    severity: 'hard_fail',
    summary: 'approval rejected',
  };
};
