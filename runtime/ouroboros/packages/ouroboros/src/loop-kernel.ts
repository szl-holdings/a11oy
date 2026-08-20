/**
 * runLoop — the Ouroboros kernel.
 *
 * Bounded recursion with measurable convergence. Caller supplies a state, a
 * step function, and a delta function. The kernel runs steps until one of:
 *   • delta drops at or below convergenceThreshold ('converged')
 *   • online consistency rises above earlyExitConsistency ('consistent')
 *   • the step function returns { abort: true } ('aborted')
 *   • we hit maxSteps ('budgetExhausted')
 *
 * Returns a typed LoopTrace. The trace is the product.
 */

import type {
  ConsistencyFn,
  DeltaFn,
  LoopConfig,
  LoopStep,
  LoopTrace,
  StepFn,
  StepResult,
} from './types.js';

const DEFAULT_MAX_STEPS = 8;
const DEFAULT_CONVERGENCE = 1e-3;
const DEFAULT_EARLY_EXIT_CONSISTENCY = 1.01; // disabled by default
const DEFAULT_SAFE_EXIT_CONSISTENCY = 0.95;

function nowMs(): number {
  // perf.now() if available, else Date.now()
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return Date.now();
}

function genId(): string {
  // Small, dependency-free stable id. Not cryptographic.
  return `loop_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export interface RunLoopArgs<S, O = unknown> {
  initialState: S;
  step: StepFn<S, O>;
  delta: DeltaFn<S>;
  /** Optional retroactive consistency scorer. */
  consistency?: ConsistencyFn<O>;
  config?: LoopConfig;
}

export async function runLoop<S, O = unknown>(
  args: RunLoopArgs<S, O>,
): Promise<LoopTrace<S, O>> {
  const {
    initialState,
    step,
    delta,
    consistency,
    config = {},
  } = args;

  const maxSteps = config.maxSteps ?? DEFAULT_MAX_STEPS;
  const convergenceThreshold = config.convergenceThreshold ?? DEFAULT_CONVERGENCE;
  // earlyExitConsistency: kept as-is (the >1 sentinel disables online exit).
  // We only enforce the lower bound to prevent negative thresholds from
  // unintentionally forcing an exit on every step.
  const rawEarlyExit = config.earlyExitConsistency ?? DEFAULT_EARLY_EXIT_CONSISTENCY;
  const earlyExitConsistency = Math.max(0, rawEarlyExit);
  // safeExitConsistency: clamped to [0, 1] — it's a similarity score.
  const rawSafeExit = config.safeExitConsistency ?? DEFAULT_SAFE_EXIT_CONSISTENCY;
  const safeExitConsistency = Math.max(0, Math.min(1, rawSafeExit));
  const id = config.id ?? genId();
  const label = config.label ?? 'ouroboros.loop';

  const steps: LoopStep<S, O>[] = [];
  let state = initialState;
  let prevOutput: O | undefined;
  let exitReason: LoopTrace<S, O>['exitReason'] = 'budgetExhausted';
  let lastOutput: O | undefined;

  const startedAt = nowMs();

  for (let i = 0; i < maxSteps; i++) {
    const stepStartedAt = nowMs();
    let result: StepResult<S, O>;
    try {
      result = await step(state, i);
    } catch (err) {
      // Surface error as an aborted exit; let caller inspect via thrown error
      // path is caller's responsibility — kernel never swallows errors.
      throw err;
    }

    if ('abort' in result && result.abort === true) {
      exitReason = 'aborted';
      break;
    }

    const next = (result as { state: S; output?: O }).state;
    const output = (result as { state: S; output?: O }).output;

    // Compare adjacent states: state (going into this step) → next.
    const deltaMagnitude = i === 0 ? 0 : Math.max(0, delta(state, next));
    const stepRecord: LoopStep<S, O> = {
      index: i,
      state: next,
      output,
      deltaMagnitude,
      durationMs: Math.max(0, nowMs() - stepStartedAt),
    };
    steps.push(stepRecord);

    state = next;

    // Online convergence check — adjacent-state delta below threshold.
    if (i > 0 && deltaMagnitude <= convergenceThreshold) {
      exitReason = 'converged';
      lastOutput = output ?? lastOutput;
      break;
    }

    // Online step-stability check — successive intermediate outputs agree.
    // This is the *online proxy* for cross-step consistency; the proper
    // intermediate-vs-final comparison happens retroactively below. Both
    // outputs must be defined (caller emits outputs) for this to fire, and
    // earlyExitConsistency must be in [0, 1] for the branch to be reachable.
    if (
      consistency &&
      output !== undefined &&
      prevOutput !== undefined &&
      i > 0 &&
      earlyExitConsistency <= 1 &&
      consistency(prevOutput, output) >= earlyExitConsistency
    ) {
      exitReason = 'consistent';
      lastOutput = output;
      break;
    }

    prevOutput = output ?? prevOutput;
    lastOutput = output ?? lastOutput;
  }

  const totalDurationMs = Math.max(0, nowMs() - startedAt);
  const finalOutput = lastOutput;

  // Retroactive cross-step consistency scoring: each intermediate output is
  // scored against the FINAL output. Earliest safe exit is the lowest step
  // index whose intermediate output already agreed with the final.
  let earliestSafeExit = -1;
  if (consistency && finalOutput !== undefined) {
    for (const s of steps) {
      const c = consistency(s.output, finalOutput);
      s.consistency = c;
      if (earliestSafeExit === -1 && c >= safeExitConsistency && s.index < steps.length - 1) {
        earliestSafeExit = s.index;
      }
    }
  }

  return {
    id,
    label,
    steps,
    finalState: state,
    finalOutput,
    exitReason,
    stepsRun: steps.length,
    maxSteps,
    earliestSafeExit,
    totalDurationMs,
  };
}
