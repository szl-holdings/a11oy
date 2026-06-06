// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v6
/**
 * axis-value-option.ts — Brahmi-zero AxisValue option type for receipts.
 *
 * The Brahmi positional numeral tradition explicitly distinguishes
 * "no measurement" (the absent place) from "measurement of zero" (the
 * marked place holding 0). This distinction is the load-bearing semantic
 * device that the Bakhshali manuscript (carbon-dated 3rd–4th c. CE per
 * Pearce et al. 2017) and the Brāhmasphuṭasiddhānta (Brahmagupta 628 CE)
 * use to make decimal arithmetic compositional.
 *
 * For governed-decision receipts the same distinction matters: an axis
 * that was *not evaluated* must not be confused with an axis whose
 * evaluation produced the value 0. Hashing, dual-attestation, and
 * Λ-aggregation all behave differently on the two cases.
 *
 * Sources:
 *   - Plofker, K. (2009). "Mathematics in India." Princeton University
 *     Press, ch. 3 (Brahmi positional notation; place-value zero).
 *   - Pearce, J., du Sautoy, M., et al. (2017). "Bakhshali manuscript
 *     dated to 3rd–4th c. CE." Bodleian Libraries / University of
 *     Oxford. https://www.bodleian.ox.ac.uk/news/2017/sep-14
 *   - Brahmagupta (628 CE). "Brāhmasphuṭasiddhānta" §18 (kuṭṭaka
 *     algorithm; explicit zero semantics).
 *
 * Lean obligation: `Lutar/Brahmi/AxisOption.lean :: axis_option_distinguishes`.
 *
 * v16 ancient-foundations graft R4-I2 (b4_rosie_amaru_ancient).
 */

export type AxisValue =
  | { readonly kind: 'measured'; readonly v: number }
  | { readonly kind: 'absent' };

export const AXIS_ABSENT: AxisValue = Object.freeze({ kind: 'absent' });

export function measuredAxis(v: number): AxisValue {
  if (!Number.isFinite(v)) {
    throw new RangeError(`measuredAxis: non-finite value ${v}`);
  }
  return Object.freeze({ kind: 'measured', v });
}

export function isAbsent(av: AxisValue): boolean {
  return av.kind === 'absent';
}

export function isMeasured(av: AxisValue): av is { kind: 'measured'; v: number } {
  return av.kind === 'measured';
}

/**
 * Hash-stable serialization. The two cases produce *different* byte strings:
 *   absent      → "A"
 *   measured(v) → "M:" + v.toString()
 * This guarantees that `hash(absent) !== hash(measured(0))`, which is the
 * Brahmi distinction proper.
 */
export function serializeAxis(av: AxisValue): string {
  if (av.kind === 'absent') return 'A';
  return `M:${av.v}`;
}

/**
 * Parse the canonical serialization back to an AxisValue. Inverse of
 * `serializeAxis` on the canonical range.
 */
export function parseAxis(s: string): AxisValue {
  if (s === 'A') return AXIS_ABSENT;
  if (s.startsWith('M:')) {
    const v = Number(s.slice(2));
    if (!Number.isFinite(v)) {
      throw new RangeError(`parseAxis: non-finite value in "${s}"`);
    }
    return measuredAxis(v);
  }
  throw new SyntaxError(`parseAxis: malformed axis value "${s}"`);
}

/**
 * Two AxisValues are equal iff they are both absent, or both measured with
 * the same numeric value (`Object.is` for NaN/-0 stability — though the
 * constructors reject non-finite values, this remains the principled choice).
 */
export function axisEqual(a: AxisValue, b: AxisValue): boolean {
  if (a.kind === 'absent' && b.kind === 'absent') return true;
  if (a.kind === 'measured' && b.kind === 'measured') {
    return Object.is(a.v, b.v);
  }
  return false;
}

/**
 * Λ-aggregation over a vector of AxisValues: absent axes are *skipped*
 * (do not lower the geometric mean), measured-zero axes propagate to a
 * geomean of 0. This is the Brahmi distinction in operational form.
 *
 * Returns the geometric mean of measured axes, or null if every axis is
 * absent (no signal at all).
 */
export function lambdaGeomeanOption(axes: readonly AxisValue[]): number | null {
  const measured: number[] = [];
  for (const a of axes) {
    if (a.kind === 'measured') measured.push(a.v);
  }
  if (measured.length === 0) return null;
  // Geometric mean via log-domain to avoid underflow on long chains.
  // If any v ≤ 0, the geometric mean is 0 by convention.
  for (const v of measured) {
    if (v <= 0) return 0;
  }
  let logSum = 0;
  for (const v of measured) logSum += Math.log(v);
  return Math.exp(logSum / measured.length);
}
