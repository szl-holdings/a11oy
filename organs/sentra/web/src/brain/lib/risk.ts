/**
 * Sentra brain risk scoring.
 *
 * Thin domain wrapper around the canonical `riskScore` from
 * `@szl-holdings/formulas` (docs/thesis/v10-canonical.md §5.2).
 *
 * Do not re-implement the severity·likelihood·value computation here —
 * if the formula needs to change, change it in `lib/formulas/src/risk.ts`
 * so every consumer (Sentra, Counsel, Terra) moves together.
 */
import { riskScore, normalizedRiskScore } from '@szl-holdings/formulas';

export interface SentraSignalRisk {
  severity: number;
  likelihood: number;
  blastRadiusCost: number;
  cap?: number;
}

/** Compound risk for a Sentra signal. */
export function sentraSignalRisk({ severity, likelihood, blastRadiusCost, cap }: SentraSignalRisk): number {
  return riskScore(severity, likelihood, blastRadiusCost, cap);
}

/**
 * Same compound risk as `sentraSignalRisk`, normalised to [0, 1] so it
 * can be fed directly into `autonomyGate()` from `@szl-holdings/formulas`.
 */
export function sentraSignalRiskNormalized({ severity, likelihood, blastRadiusCost, cap }: SentraSignalRisk): number {
  return normalizedRiskScore(severity, likelihood, blastRadiusCost, cap);
}

export { riskScore, normalizedRiskScore };
