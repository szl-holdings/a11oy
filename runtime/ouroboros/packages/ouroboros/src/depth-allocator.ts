/**
 * EntropyDepthAllocator — Ouro's adaptive depth, generalized to system loops.
 *
 * Given a small set of "probe deltas" from the first 2-3 steps of a loop,
 * estimate how many steps this loop is likely to need, capped by the
 * caller's hard maxSteps. The allocator favours bigger budgets when the
 * delta is large or oscillating, and smaller budgets when the delta is
 * already small or monotonically shrinking.
 *
 * This is a heuristic, not a learned policy. It is the system-layer analog
 * of Ouro's entropy regularization: same goal, different signal.
 */

export interface AllocatorInput {
  /**
   * Recent delta magnitudes (most recent first), e.g. [delta_3, delta_2, delta_1].
   * 1-3 entries is typical.
   */
  recentDeltas: number[];
  /** Hard upper bound on steps. */
  maxSteps: number;
  /** Lower bound on steps. Default 1. */
  minSteps?: number;
  /**
   * Stakes multiplier in [0.5, 4]. Higher = grant more depth (e.g. during
   * a security incident). Default 1.
   */
  stakes?: number;
}

export interface AllocatorOutput {
  /** Recommended budget for the remainder of this loop. */
  recommendedSteps: number;
  /** Diagnostic: shrinking | flat | oscillating | growing | unknown. */
  trajectory: 'shrinking' | 'flat' | 'oscillating' | 'growing' | 'unknown';
  /** Diagnostic note for traces. */
  reason: string;
}

export function allocateDepth(input: AllocatorInput): AllocatorOutput {
  const minSteps = Math.max(1, input.minSteps ?? 1);
  const maxSteps = Math.max(minSteps, input.maxSteps);
  const stakes = clamp(input.stakes ?? 1, 0.5, 4);
  const deltas = input.recentDeltas.filter((d) => Number.isFinite(d));

  if (deltas.length === 0) {
    return {
      recommendedSteps: Math.round(clamp((maxSteps / 2) * stakes, minSteps, maxSteps)),
      trajectory: 'unknown',
      reason: 'no probe deltas; defaulting to half budget × stakes',
    };
  }

  const trajectory = classifyTrajectory(deltas);
  let baseFraction: number;

  switch (trajectory) {
    case 'shrinking':
      // delta is going down — already on track to converge. Modest budget.
      baseFraction = 0.35;
      break;
    case 'flat':
      // delta has stabilized but hasn't hit threshold — likely a fixed
      // point a couple of steps away. Small budget.
      baseFraction = 0.25;
      break;
    case 'oscillating':
      // delta is bouncing around — needs the most steps to settle.
      baseFraction = 0.85;
      break;
    case 'growing':
      // delta is increasing — diverging. Either needs full budget or
      // should abort. Allocator can't decide; allocate full.
      baseFraction = 1.0;
      break;
    default:
      baseFraction = 0.5;
  }

  const target = Math.round(clamp(maxSteps * baseFraction * stakes, minSteps, maxSteps));
  return {
    recommendedSteps: target,
    trajectory,
    reason: `trajectory=${trajectory}, fraction=${baseFraction.toFixed(2)}, stakes=${stakes.toFixed(2)}`,
  };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function classifyTrajectory(d: number[]): AllocatorOutput['trajectory'] {
  if (d.length < 2) return 'unknown';
  // d is most-recent-first. Reverse so we walk forward through time.
  const series = [...d].reverse();
  let downs = 0;
  let ups = 0;
  let flats = 0;
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1]!;
    const cur = series[i]!;
    const eps = Math.max(prev, cur, 1e-9) * 0.05;
    if (cur < prev - eps) downs++;
    else if (cur > prev + eps) ups++;
    else flats++;
  }
  if (downs > 0 && ups === 0 && flats === 0) return 'shrinking';
  if (ups > 0 && downs === 0 && flats === 0) return 'growing';
  if (downs > 0 && ups > 0) return 'oscillating';
  if (flats > 0 && downs === 0 && ups === 0) return 'flat';
  // mixed flats with one direction
  return downs > ups ? 'shrinking' : ups > downs ? 'growing' : 'flat';
}
