import type { Axes } from '@szl/ouroboros-types';

export interface EvaluationResult {
  lambda: number;
  pass: boolean;
  axes: Axes;
}

export function evaluateAxes(axes: Axes): EvaluationResult {
  const values = Object.values(axes) as number[];
  const lambda = values.reduce((sum, v) => sum + v, 0) / values.length;
  return { lambda, pass: lambda >= 0.90, axes };
}

export function computeLambda(axes: Axes): number {
  const values = Object.values(axes) as number[];
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}
