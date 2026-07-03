/**
 * Codex-Kernel — type contracts.
 *
 * Modelled on the E4-codex-kernel-governed-loop payload:
 *  - state is hashed and chained (replay contract)
 *  - every commit emits a decision receipt
 *  - validators can hard-stop the loop
 *  - the proof ledger is append-only
 */

export type ISO8601 = string;
export type Hex = string;

/** Stable JSON value type — used for state, deltas, evidence. */
export type Json =
  | null
  | boolean
  | number
  | string
  | Json[]
  | { [key: string]: Json };

/** Pipeline stage names from the Codex-Kernel payload. */
export type PipelineStage =
  | 'Signal'
  | 'Context'
  | 'Recommendation'
  | 'Simulation'
  | 'Policy'
  | 'Approval'
  | 'Execution'
  | 'Proof'
  | 'Outcome';

export type ValidatorSeverity = 'pass' | 'soft_fail' | 'hard_fail';

export interface ValidatorResult {
  name: string;
  severity: ValidatorSeverity;
  /** Human-readable summary of what was checked. */
  summary: string;
  /** Optional structured details (e.g. drift_days, threshold). */
  details?: Json;
}

export type ApprovalStatus =
  | 'not_required'
  | 'pending'
  | 'approved'
  | 'rejected';

export interface ApprovalEvent {
  approval_id: string;
  approved_by: string;
  approved_at: ISO8601;
  scope: string;
  decision: 'approved' | 'rejected';
  rationale?: string;
}

export interface DecisionReceipt {
  receipt_id: string;
  step: number;
  decision_type: string;
  summary: string;
  assumptions: string[];
  evidence: Array<{ kind: string; ref: string; mocked?: boolean }>;
  policy_version: string;
  approval_status: ApprovalStatus;
  approval_ref?: string;
  /** True if any evidence link is mocked / synthetic. */
  mocked: boolean;
  timestamp: ISO8601;
}

export type StopReason =
  | 'convergence'
  | 'budget_exhausted'
  | 'human_gate_required'
  | 'validator_hard_stop'
  | 'no_state_change_needed'
  | 'manual_stop'
  /** Ouroboros-Thesis-v3 — Δ-witness ≤ ε_Δ for W_Δ steps (adaptive-depth on only). */
  | 'adaptive_depth_converged'
  /** Ouroboros-Thesis-v3 — validator entropy ≤ ε_H for W_H steps (adaptive-depth on only). */
  | 'adaptive_depth_entropy_settled'
  | null;

export interface TraceEvent {
  ts: ISO8601;
  step: number;
  pipeline_stage: PipelineStage;
  state_prev_hash: Hex;
  observation: Json;
  proposed_delta: Json;
  validator_results: ValidatorResult[];
  decision_receipt: DecisionReceipt | null;
  state_next_hash: Hex;
  stop_reason: StopReason;
  /**
   * Optional Ouroboros-Thesis-v3 EntropyDepthAllocator verdict for this step.
   * Recorded only when `loop_policy.adaptive_depth.enabled === true`. The
   * field is additive and never affects the chain hash, so traces from
   * adaptive-disabled runs replay bit-identically to pre-v3 traces.
   */
  adaptive_depth_verdict?: {
    verdict: 'continue' | 'early_exit_converged' | 'early_exit_entropy' | 'extend';
    reason: string;
    delta_witness?: number;
    entropy?: number;
    soft_fail_rate?: number;
    extended_max_steps?: number;
  };
}

export interface ProofLedgerEntry {
  ts: ISO8601;
  step: number;
  state_hash: Hex;
  delta_hash: Hex;
  receipt_id: string;
  policy_version: string;
  approval_ref: string | null;
}

export interface Budgets {
  time_budget_ms: number;
  step_budget: number;
  retry_budget: number;
}

export interface LoopPolicy {
  max_steps: number;
  adaptive_depth: { enabled: boolean };
  entropy_regularized_exit: { enabled: boolean };
}

export interface RunSummary {
  experiment_id: string;
  status: 'ok' | 'halted' | 'error';
  steps_executed: number;
  hard_stop_failures: number;
  soft_failures: number;
  budget_used: { time_ms: number; steps: number; retries: number };
  stop_reason: StopReason;
  replay_status: 'verified' | 'failed' | 'not_run';
  final_state_hash: Hex;
  /** v3 — true when adaptive-depth was enabled for this run. */
  adaptive_depth_used?: boolean;
  /** v3 — number of times the allocator extended the step ceiling. */
  adaptive_depth_extensions?: number;
  /** v3 — final effective step ceiling (after any extensions). */
  adaptive_depth_effective_max_steps?: number;
}

/**
 * A step contributes a proposed_delta and the validators that should run on it.
 * The kernel hashes (prev_hash + delta) → next_hash, runs validators, and
 * commits or halts.
 */
export interface StepProposal<S extends Json = Json> {
  pipeline_stage: PipelineStage;
  observation: Json;
  /** Pure function: prev state → patch object merged into prev. */
  proposeDelta: (prev: S) => Json;
  /** Validators run AFTER proposed delta is computed but BEFORE commit. */
  validators: Array<(ctx: ValidationContext<S>) => ValidatorResult>;
  /** Receipt builder; if it returns null no receipt is emitted. */
  buildReceipt: (ctx: ValidationContext<S>) => Omit<
    DecisionReceipt,
    'receipt_id' | 'step' | 'timestamp'
  > | null;
  /** Approval gate; return 'not_required' to skip. */
  requireApproval?: (ctx: ValidationContext<S>) => ApprovalStatus;
}

export interface ValidationContext<S extends Json = Json> {
  step: number;
  prev_state: S;
  proposed_delta: Json;
  next_state: S;
  prev_hash: Hex;
  delta_hash: Hex;
  next_hash: Hex;
  policy_version: string;
}

export interface KernelConfig<S extends Json = Json> {
  experiment_id: string;
  initial_state: S;
  policy_version: string;
  budgets: Budgets;
  loop_policy: LoopPolicy;
  governance_enabled: boolean;
  /** A step generator yields proposals one at a time. */
  steps: Generator<StepProposal<S>, void, S>;
  /** Optional approval resolver — if a step requires approval, this is called. */
  resolveApproval?: (ctx: ValidationContext<S>) => ApprovalEvent | null;
  /** Clock injection for deterministic tests. */
  now?: () => ISO8601;
  /**
   * Optional EntropyDepthAllocator config (v3 §3.2). Only consulted when
   * `loop_policy.adaptive_depth.enabled === true`. When omitted, defaults
   * from `DEFAULT_DEPTH_ALLOCATOR_CONFIG` are used.
   */
  depth_allocator_config?: import('./depth-allocator.js').DepthAllocatorConfig;
}

export interface KernelRunResult<S extends Json = Json> {
  summary: RunSummary;
  final_state: S;
  trace: TraceEvent[];
  ledger: ProofLedgerEntry[];
  receipts: DecisionReceipt[];
  approvals: ApprovalEvent[];
}
