/**
 * Wilson score interval for a binomial proportion.
 *
 * Re-expressed from CRISPResso2's allele-frequency CI columns
 * (docs/research/perception-bio-synthesis-2026.md §2). No external
 * dependency; numerical kernel is pure.
 *
 * Wilson is preferred over the Wald (normal-approximation) interval
 * because it stays inside [0, 1] for small counts and small/large
 * proportions — the exact regime where edit-call tables live.
 */

/** z critical value for a two-sided confidence level. */
const Z = {
  '0.90': 1.6448536269514722,
  '0.95': 1.959963984540054,
  '0.99': 2.5758293035489004,
} as const;

export type ConfidenceLevel = keyof typeof Z;

export interface WilsonInterval {
  /** Point estimate `successes / trials`. */
  readonly p: number;
  /** Lower bound ∈ [0, 1]. */
  readonly ciLower: number;
  /** Upper bound ∈ [0, 1]. */
  readonly ciUpper: number;
  /** Confidence level used. */
  readonly level: ConfidenceLevel;
}

/**
 * Wilson score interval. `trials` must be ≥ 0, `successes` must be in
 * `[0, trials]`. A degenerate `trials === 0` returns `[0, 1]` — the
 * widest honest interval — rather than `NaN`. This mirrors the
 * CRISPResso2 lesson that absence-of-data must not be silently
 * collapsed.
 */
export function wilsonInterval(
  successes: number,
  trials: number,
  level: ConfidenceLevel = '0.95',
): WilsonInterval {
  if (!Number.isFinite(successes) || !Number.isFinite(trials) || trials < 0 || successes < 0 || successes > trials) {
    throw new Error(`wilsonInterval: invalid inputs successes=${successes} trials=${trials}`);
  }
  if (trials === 0) {
    return { p: 0, ciLower: 0, ciUpper: 1, level };
  }
  const z = Z[level];
  const n = trials;
  const p = successes / n;
  const z2 = z * z;
  const denom = 1 + z2 / n;
  const centre = (p + z2 / (2 * n)) / denom;
  const half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom;
  return {
    p,
    ciLower: Math.max(0, centre - half),
    ciUpper: Math.min(1, centre + half),
    level,
  };
}
