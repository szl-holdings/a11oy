export function riskScore(severity, likelihood, blastRadiusCost, cap) {
  const raw = severity * likelihood * blastRadiusCost;
  return cap != null ? Math.min(raw, cap) : raw;
}

export function normalizedRiskScore(severity, likelihood, blastRadiusCost, cap) {
  const effectiveCap = cap ?? 1_000_000;
  const raw = severity * likelihood * blastRadiusCost;
  return Math.min(raw, effectiveCap) / effectiveCap;
}

export function autonomyGate(normalizedRisk) {
  if (normalizedRisk < 0.2) return 'auto';
  if (normalizedRisk < 0.6) return 'approve';
  return 'multi-party';
}

export function fisherRaoDistance(p, q) {
  let sum = 0;
  for (let i = 0; i < p.length; i++) {
    sum += Math.sqrt(p[i] * q[i]);
  }
  return 2 * Math.acos(Math.min(1, sum));
}

export function bohrComplementarityFloor(sigmaA, sigmaB) {
  return sigmaA * sigmaB >= 0.25 - 1e-9;
}

export function processSignal(signal) {
  return { processed: true, signal };
}

export function runRosieLoop(options) {
  return { signals: [], iterations: 0 };
}

export const DEFAULT_DRIFT_THRESHOLDS = {
  warning: 0.05,
  critical: 0.10,
  maxHistoryLength: 100,
};

export function driftDetector(options) {
  return {
    observe(value) { return { drift: 0, status: 'stable' }; },
    reset() {},
    getHistory() { return []; },
  };
}
