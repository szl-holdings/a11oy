const DEFAULT_CEILING = 1_000_000;

export function riskScore(severity: number, likelihood: number, blastRadiusCost: number, cap?: number): number {
  const raw = severity * likelihood * blastRadiusCost;
  return cap !== undefined ? Math.min(raw, cap) : raw;
}

export function normalizedRiskScore(severity: number, likelihood: number, blastRadiusCost: number, cap?: number): number {
  const raw = riskScore(severity, likelihood, blastRadiusCost, cap);
  const ceiling = cap ?? DEFAULT_CEILING;
  return Math.min(raw / ceiling, 1);
}

export function autonomyGate(normalizedRisk: number): 'auto' | 'approve' | 'multi-party' {
  if (normalizedRisk < 0.2) return 'auto';
  if (normalizedRisk < 0.6) return 'approve';
  return 'multi-party';
}
