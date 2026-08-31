/**
 * v4-validators — runnable implementations of the 9 validator rules
 * declared in `VALIDATOR_REGISTRY` (validator-registry.ts).
 *
 * Until v4, the registry was data-only: each validator had an id, a
 * severity, and a one-line rule string, but the runtime had no way to
 * compute `passed` for itself. This module closes that gap by shipping
 * pure functions for all 9 rules. The functions consume a typed
 * `RuntimeContext` and produce `ValidatorResult` records that compose
 * with the existing `summarizeValidators` halt logic.
 *
 * See `VALIDATORS.md` in this directory for the codex-aligned semantics
 * and the full mapping from rule text → function behaviour.
 */

export {
  valBudgetEnforcer,
  valNoSilentMutation,
  valProofRequired,
  valRiskEscalation,
  valApprovalForCriticalAction,
  valSecurityProofRequired,
  valSourcePriorityRequired,
  valMergeSafety,
  valConsistencyBeforeCommit,
  VALIDATOR_FNS,
} from './validators.js';

export { runValidators, V4_VALIDATOR_IDS } from './run.js';
export type { RunValidatorsResult } from './run.js';

export type {
  RuntimeContext,
  RuntimeRiskTier,
  RuntimeOperationalMode,
  ApprovalSnapshot,
  SourceCitation,
  MergeAction,
  ConsistencySnapshot,
  MutationRecord,
  ValidatorFn,
} from './types.js';
