export interface LoopStep<S> {
  state: S;
  output: number;
  deltaMagnitude: number;
  consistency: number;
  stepIndex: number;
}

export interface LoopTrace<S, O = number> {
  steps: LoopStep<S>[];
  finalState: S;
  converged: boolean;
  label: string;
}

export interface LoopConfig {
  maxSteps: number;
  convergenceThreshold: number;
  label: string;
}

export interface RunLoopOpts<S, O> {
  initialState: S;
  step: (state: S) => Promise<{ state: S; output: O }>;
  delta: (a: S, b: S) => number;
  consistency: (a: number, b: number) => number;
  config: LoopConfig;
}

export async function runLoop<S, O = number>(opts: RunLoopOpts<S, O>): Promise<LoopTrace<S, O>> {
  const steps: LoopStep<S>[] = [];
  let current = opts.initialState;
  let converged = false;

  for (let i = 0; i < opts.config.maxSteps; i++) {
    const prev = current;
    const result = await opts.step(current);
    current = result.state;
    const dm = opts.delta(prev, current);
    const cons = opts.consistency(dm, steps.length > 0 ? steps[steps.length - 1].deltaMagnitude : dm);
    steps.push({
      state: current,
      output: result.output as unknown as number,
      deltaMagnitude: dm,
      consistency: cons,
      stepIndex: i,
    });
    if (dm < opts.config.convergenceThreshold) {
      converged = true;
      break;
    }
  }

  return { steps, finalState: current, converged, label: opts.config.label };
}

export function numericConsistency(a: number, b: number): number {
  if (a === 0 && b === 0) return 1;
  return 1 - Math.abs(a - b) / Math.max(Math.abs(a), Math.abs(b), 1);
}

export function allocateDepth(opts: { recentDeltas: number[]; maxSteps: number }): {
  recommendedSteps: number;
  trajectory: string;
} {
  if (opts.recentDeltas.length === 0) {
    return { recommendedSteps: opts.maxSteps, trajectory: 'no-data' };
  }
  const trend = opts.recentDeltas.length >= 2
    ? opts.recentDeltas[0] - opts.recentDeltas[opts.recentDeltas.length - 1]
    : 0;
  if (trend > 0) {
    return { recommendedSteps: Math.max(2, Math.ceil(opts.maxSteps * 0.6)), trajectory: 'converging' };
  }
  if (trend < 0) {
    return { recommendedSteps: opts.maxSteps, trajectory: 'diverging' };
  }
  return { recommendedSteps: opts.maxSteps, trajectory: 'flat' };
}
