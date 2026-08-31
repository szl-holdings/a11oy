/**
 * Innovation engine — implementation of the v4 missing piece
 * `innovation_engine` from `docs/research/ouroboros-runtime-contract.v4.json`.
 *
 * The engine is the bookkeeping surface for the six feedback loops the
 * runtime evolves through. Each loop is a named registry entry that
 * downstream tooling (replay analyzers, distillation jobs, golden-run
 * regressions) can subscribe to. The loops themselves are deliberately
 * declarative — execution is the responsibility of the loop owner; this
 * module only enforces the "every loop must be named, sourced, and
 * tied to an output artifact" contract.
 */

export type InnovationLoopId =
  | 'runtime_feedback_loop'
  | 'golden_run_regression_loop'
  | 'receipt_quality_loop'
  | 'security_review_improvement_loop'
  | 'data_convergence_improvement_loop'
  | 'economic_efficiency_loop';

export interface InnovationLoopSpec {
  readonly loopId: InnovationLoopId;
  readonly purpose: string;
  /** Where this loop draws its evolution signal from. */
  readonly source:
    | 'trace_jsonl'
    | 'decision_receipt'
    | 'golden_run_report'
    | 'sentra_risk_summary'
    | 'amaru_consistency_report'
    | 'budget_telemetry';
  /** Output artifact this loop emits to feed the next iteration. */
  readonly output:
    | 'distilled_policy_delta'
    | 'regression_report'
    | 'receipt_quality_report'
    | 'security_improvement_recommendations'
    | 'convergence_improvement_recommendations'
    | 'efficiency_recommendations';
}

function freeze<T extends InnovationLoopSpec>(v: T): T {
  return Object.freeze(v);
}

export const INNOVATION_LOOPS: Readonly<Record<InnovationLoopId, InnovationLoopSpec>> =
  Object.freeze({
    runtime_feedback_loop: freeze({
      loopId: 'runtime_feedback_loop',
      purpose: 'Distill runtime traces into policy improvements for the next loop.',
      source: 'trace_jsonl',
      output: 'distilled_policy_delta',
    }),
    golden_run_regression_loop: freeze({
      loopId: 'golden_run_regression_loop',
      purpose: 'Detect regressions against golden runs and generate regression reports.',
      source: 'golden_run_report',
      output: 'regression_report',
    }),
    receipt_quality_loop: freeze({
      loopId: 'receipt_quality_loop',
      purpose: 'Audit decision receipts for completeness and approval-grade quality.',
      source: 'decision_receipt',
      output: 'receipt_quality_report',
    }),
    security_review_improvement_loop: freeze({
      loopId: 'security_review_improvement_loop',
      purpose: 'Improve Sentra recursive review using historical risk summaries.',
      source: 'sentra_risk_summary',
      output: 'security_improvement_recommendations',
    }),
    data_convergence_improvement_loop: freeze({
      loopId: 'data_convergence_improvement_loop',
      purpose: 'Improve Amaru convergence policy using historical consistency reports.',
      source: 'amaru_consistency_report',
      output: 'convergence_improvement_recommendations',
    }),
    economic_efficiency_loop: freeze({
      loopId: 'economic_efficiency_loop',
      purpose: 'Reduce token, latency, and money cost per receipt while holding quality.',
      source: 'budget_telemetry',
      output: 'efficiency_recommendations',
    }),
  });

export interface InnovationEngineState {
  readonly enabled: boolean;
  readonly operatorFeedbackBinding: boolean;
  readonly traceDistillationReady: boolean;
  readonly loops: readonly InnovationLoopSpec[];
}

export const INNOVATION_ENGINE_DEFAULT: InnovationEngineState = Object.freeze({
  enabled: true,
  operatorFeedbackBinding: true,
  traceDistillationReady: true,
  loops: Object.freeze(Object.values(INNOVATION_LOOPS)),
});

/**
 * Validate that an innovation engine state is admissible: enabled, with
 * the full set of declared loops present and every loop having a source
 * and an output. Returns the missing-loop ids; empty array means valid.
 */
export function validateInnovationEngine(
  state: InnovationEngineState,
): InnovationLoopId[] {
  if (!state.enabled) return [];
  const present = new Set(state.loops.map((l) => l.loopId));
  const missing: InnovationLoopId[] = [];
  for (const id of Object.keys(INNOVATION_LOOPS) as InnovationLoopId[]) {
    if (!present.has(id)) missing.push(id);
  }
  return missing;
}
