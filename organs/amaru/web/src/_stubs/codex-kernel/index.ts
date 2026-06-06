export interface VenusState {
  cycle: number;
  day_in_cycle: number;
  accumulated_drift: number;
  total_rows_emitted: number;
  corrections_applied: number;
}

export interface DresdenSimConfig {
  cycle_days: number;
  drift_per_cycle: number;
  warning_threshold: number;
  hard_threshold: number;
  rows_to_emit: number;
}

export const DRESDEN_DEFAULT_CONFIG: DresdenSimConfig = {
  cycle_days: 584,
  drift_per_cycle: 0,
  warning_threshold: 4,
  hard_threshold: 8,
  rows_to_emit: 8,
};

export const DRESDEN_INITIAL_STATE: VenusState = {
  cycle: 0,
  day_in_cycle: 0,
  accumulated_drift: 0,
  total_rows_emitted: 0,
  corrections_applied: 0,
};

export interface ValidatorResult {
  name: string;
  severity: 'pass' | 'soft_fail' | 'hard_fail';
  summary: string;
}

export interface DecisionReceipt {
  summary: string;
  decision_type: string;
  policy_version: string;
  approval_status: string;
  mocked: boolean;
  assumptions: string[];
  evidence: Array<{ kind: string; ref: string; mocked: boolean }>;
}

export interface TraceEvent {
  step: number;
  pipeline_stage: string;
  state_prev_hash: string;
  state_next_hash: string;
  validator_results: ValidatorResult[];
  decision_receipt: DecisionReceipt | null;
}

export interface KernelRunResult<S> {
  summary: {
    status: string;
    steps_executed: number;
    hard_stop_failures: number;
    soft_failures: number;
    stop_reason: string | null;
    final_state_hash: string;
  };
  trace: TraceEvent[];
  final_state: S;
}

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16).padStart(8, '0').slice(0, 8);
}

function fullHash(state: unknown): string {
  const s = JSON.stringify(state);
  const h = simpleHash(s);
  return (h + h + h + h + h + h + h + h).slice(0, 64);
}

interface DresdenStep {
  name: string;
  pipeline_stage: string;
  apply: (state: VenusState, cfg: DresdenSimConfig) => VenusState;
  validators: Array<{
    name: string;
    check: (prev: VenusState, next: VenusState, cfg: DresdenSimConfig) => ValidatorResult;
  }>;
}

export function dresdenSteps(cfg: DresdenSimConfig): DresdenStep[] {
  return [
    {
      name: 'emit_rows',
      pipeline_stage: 'ingest',
      apply: (s) => ({ ...s, total_rows_emitted: s.total_rows_emitted + cfg.rows_to_emit }),
      validators: [
        {
          name: 'row_count',
          check: (_p, n) => ({
            name: 'row_count',
            severity: n.total_rows_emitted > 0 ? 'pass' : 'soft_fail',
            summary: `${n.total_rows_emitted} rows emitted`,
          }),
        },
      ],
    },
    {
      name: 'advance_cycle',
      pipeline_stage: 'transform',
      apply: (s) => ({
        ...s,
        cycle: s.cycle + 1,
        day_in_cycle: (s.day_in_cycle + cfg.cycle_days) % 365,
        accumulated_drift: s.accumulated_drift + cfg.drift_per_cycle,
      }),
      validators: [
        {
          name: 'drift_warn',
          check: (_p, n) => ({
            name: 'drift_warn',
            severity:
              Math.abs(n.accumulated_drift) > cfg.hard_threshold
                ? 'hard_fail'
                : Math.abs(n.accumulated_drift) > cfg.warning_threshold
                  ? 'soft_fail'
                  : 'pass',
            summary: `drift=${n.accumulated_drift.toFixed(1)}d`,
          }),
        },
      ],
    },
    {
      name: 'correct_drift',
      pipeline_stage: 'validate',
      apply: (s) => {
        if (Math.abs(s.accumulated_drift) > cfg.warning_threshold) {
          return { ...s, accumulated_drift: s.accumulated_drift * 0.5, corrections_applied: s.corrections_applied + 1 };
        }
        return s;
      },
      validators: [
        {
          name: 'correction_audit',
          check: (p, n) => ({
            name: 'correction_audit',
            severity: 'pass',
            summary: n.corrections_applied > p.corrections_applied ? 'correction applied' : 'no correction needed',
          }),
        },
      ],
    },
  ];
}

export function runLoop<S extends VenusState>(opts: {
  experiment_id: string;
  initial_state: S;
  policy_version: string;
  budgets: { time_budget_ms: number; step_budget: number; retry_budget: number };
  loop_policy: { max_steps: number; adaptive_depth: { enabled: boolean }; entropy_regularized_exit: { enabled: boolean } };
  governance_enabled: boolean;
  steps: DresdenStep[];
}): KernelRunResult<S> {
  const trace: TraceEvent[] = [];
  let state = { ...opts.initial_state } as S;
  let hardFails = 0;
  let softFails = 0;
  let stopReason: string | null = null;
  const maxCycles = Math.min(opts.loop_policy.max_steps, opts.budgets.step_budget);

  for (let cycle = 0; cycle < maxCycles; cycle++) {
    for (const step of opts.steps) {
      const prevHash = fullHash(state);
      const prev = { ...state } as S;
      const next = step.apply(state, DRESDEN_DEFAULT_CONFIG) as S;
      const nextHash = fullHash(next);

      const vResults = opts.governance_enabled
        ? step.validators.map((v) => v.check(prev, next, DRESDEN_DEFAULT_CONFIG))
        : [{ name: 'governance_off', severity: 'pass' as const, summary: 'governance disabled' }];

      const hasHard = vResults.some((v) => v.severity === 'hard_fail');
      const hasSoft = vResults.some((v) => v.severity === 'soft_fail');

      let receipt: DecisionReceipt | null = null;
      if (opts.governance_enabled) {
        receipt = {
          summary: `${step.name}: ${hasHard ? 'BLOCKED' : hasSoft ? 'WARNING' : 'APPROVED'}`,
          decision_type: step.pipeline_stage,
          policy_version: opts.policy_version,
          approval_status: hasHard ? 'blocked' : 'approved',
          mocked: false,
          assumptions: [`cycle=${prev.cycle}`, `drift=${prev.accumulated_drift.toFixed(1)}`],
          evidence: vResults.map((v) => ({ kind: v.name, ref: v.summary, mocked: false })),
        };
      }

      trace.push({
        step: trace.length + 1,
        pipeline_stage: step.pipeline_stage,
        state_prev_hash: prevHash,
        state_next_hash: hasHard && opts.governance_enabled ? prevHash : nextHash,
        validator_results: vResults,
        decision_receipt: receipt,
      });

      if (hasHard && opts.governance_enabled) {
        hardFails++;
        if (hardFails >= 2) {
          stopReason = 'hard_fail_limit';
          state = prev;
          break;
        }
        state = prev;
      } else {
        if (hasSoft) softFails++;
        state = next;
      }
    }

    if (stopReason) break;
  }

  return {
    summary: {
      status: hardFails > 0 ? 'halted' : 'ok',
      steps_executed: trace.length,
      hard_stop_failures: hardFails,
      soft_failures: softFails,
      stop_reason: stopReason,
      final_state_hash: fullHash(state),
    },
    trace,
    final_state: state,
  };
}

export function serializeTraceJsonl(trace: TraceEvent[]): string {
  return trace.map((e) => JSON.stringify(e)).join('\n');
}

export function shortHash(hash: string): string {
  return hash.slice(0, 8);
}

export function replay(
  initialState: VenusState,
  trace: TraceEvent[],
  expectedFinalHash: string,
): { ok: boolean; steps_replayed: number; failed_step: number | null } {
  if (trace.length === 0) return { ok: true, steps_replayed: 0, failed_step: null };

  let prevHash = fullHash(initialState);
  for (let i = 0; i < trace.length; i++) {
    if (trace[i].state_prev_hash !== prevHash) {
      return { ok: false, steps_replayed: i, failed_step: i + 1 };
    }
    prevHash = trace[i].state_next_hash;
  }

  const finalMatch = prevHash === expectedFinalHash;
  return {
    ok: finalMatch,
    steps_replayed: trace.length,
    failed_step: finalMatch ? null : trace.length,
  };
}
