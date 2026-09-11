export const TRUST_CEILING = 0.97;
export const LAMBDA_FLOOR = 0.9;

/** Geometric mean with fail-closed zero-pin. Never renders 1.0. */
export function geometricMean(values: number[]): number {
  if (!values.length) return 0;
  if (values.some((v) => !Number.isFinite(v) || v <= 0)) return 0;
  const logSum = values.reduce((s, v) => s + Math.log(v), 0);
  return Math.min(TRUST_CEILING, Math.exp(logSum / values.length));
}

export function lambdaVerdict(lambda: number): "DENY" | "HOLD" | "ADMIT" {
  if (lambda <= 0 || lambda < LAMBDA_FLOOR) return "DENY";
  if (lambda >= TRUST_CEILING) return "HOLD";
  return "ADMIT";
}
