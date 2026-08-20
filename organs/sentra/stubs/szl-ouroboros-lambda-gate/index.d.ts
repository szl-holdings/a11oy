import type { Axes } from '@szl/ouroboros-types';

export interface EvaluateResult {
  lambda: number;
  pass: boolean;
  axes: Axes;
}

export function computeLambda(axes: Axes): number;
export function evaluateAxes(axes: Axes): EvaluateResult;
