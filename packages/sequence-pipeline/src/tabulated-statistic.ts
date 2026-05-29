/**
 * Tabulated-statistic primitive — the canonical output shape for
 * `pipeline.tabulated-statistic.v1` receipts.
 *
 * The CRISPResso2 lesson re-expressed: every row carries a CI, and
 * absence is itself a row (`isNegativeSpace: true`), never a missing
 * row. The validators below are what the receipt-write boundary calls.
 */

export interface TabulatedRow {
  /** Row label (e.g. allele name, incident class). */
  readonly label: string;
  /** Integer count, ≥ 0. */
  readonly count: number;
  /** `count / totalTrials`, in [0, 1]. */
  readonly fraction: number;
  /** Lower CI bound ∈ [0, 1]; CRISPResso2 lesson: mandatory. */
  readonly ciLower: number;
  /** Upper CI bound ∈ [0, 1]; CRISPResso2 lesson: mandatory. */
  readonly ciUpper: number;
  /** True if this row represents "no event" (e.g. unmodified reference). */
  readonly isNegativeSpace: boolean;
}

export interface TabulatedStatistic {
  /** Total trials underlying the table. */
  readonly totalTrials: number;
  /** Rows, in the order the pipeline emitted them. */
  readonly rows: readonly TabulatedRow[];
  /** Method reference (e.g. `'wilson-0.95'`). */
  readonly methodRef: string;
  /** True iff the schema declares this domain has a meaningful "no event"
   *  label and therefore requires at least one `isNegativeSpace` row. */
  readonly requiresNegativeSpace: boolean;
}

/**
 * Validation for the receipt-write boundary.
 *
 * Rejects rows with `null` / non-finite CI bounds (no claim without an
 * interval), rejects bounds that do not surround the point estimate,
 * and — when `requiresNegativeSpace` is true — rejects tables that lack
 * an explicit negative-space row.
 */
export function validateTabulatedStatistic(stat: TabulatedStatistic): void {
  if (!Array.isArray(stat.rows) || stat.rows.length === 0) {
    throw new Error('tabulated-statistic: rows[] must be non-empty');
  }
  let sawNegativeSpace = false;
  for (const row of stat.rows) {
    if (!Number.isFinite(row.ciLower) || !Number.isFinite(row.ciUpper)) {
      throw new Error(`tabulated-statistic: row "${row.label}" missing CI bounds (no claim without an interval)`);
    }
    if (row.ciLower < 0 || row.ciUpper > 1 || row.ciLower > row.ciUpper) {
      throw new Error(`tabulated-statistic: row "${row.label}" CI [${row.ciLower}, ${row.ciUpper}] is malformed`);
    }
    if (row.fraction < row.ciLower - 1e-9 || row.fraction > row.ciUpper + 1e-9) {
      throw new Error(`tabulated-statistic: row "${row.label}" fraction ${row.fraction} not within CI`);
    }
    if (row.count < 0 || !Number.isInteger(row.count)) {
      throw new Error(`tabulated-statistic: row "${row.label}" count ${row.count} must be a non-negative integer`);
    }
    if (row.isNegativeSpace) sawNegativeSpace = true;
  }
  if (stat.requiresNegativeSpace && !sawNegativeSpace) {
    throw new Error('tabulated-statistic: schema requires a negative-space row but none was emitted (absence is a row)');
  }
}
