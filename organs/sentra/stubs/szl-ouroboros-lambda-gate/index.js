const AXIS_KEYS = [
  'moralGrounding',
  'measurabilityHonesty',
  'epistemicHumility',
  'harmAvoidance',
  'logicalCoherence',
  'citationIntegrity',
  'noveltyContribution',
  'reproducibility',
  'stakeholderAlignment',
];

const LAMBDA_THRESHOLD = 0.90;

export function computeLambda(axes) {
  let sum = 0;
  for (const key of AXIS_KEYS) {
    sum += axes[key] ?? 0;
  }
  return sum / AXIS_KEYS.length;
}

export function evaluateAxes(axes) {
  const lambda = computeLambda(axes);
  return {
    lambda,
    pass: lambda >= LAMBDA_THRESHOLD,
    axes,
  };
}
