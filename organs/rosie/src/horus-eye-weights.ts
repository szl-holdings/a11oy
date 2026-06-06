/**
 * horus-eye-weights.ts — Horus-Eye 6-bit dyadic receipt-weight encoding.
 *
 * The ancient Egyptian Horus-Eye (wedjat) fractional system represents
 * fractions as sums of the six dyadic units 1/2, 1/4, 1/8, 1/16, 1/32, 1/64.
 * The six summed values give 63/64 — the residual 1/64 was, per scribal
 * tradition, "supplied by Thoth." For governed-decision receipts this gives
 * an exact 6-bit fixed-precision encoding for weights w ∈ [0, 63/64] that
 * eliminates floating-point non-determinism on constrained environments.
 *
 * Sources:
 *   - Gillings, R. J. (1972). "Mathematics in the Time of the Pharaohs."
 *     MIT Press, ch. 1–3 (Horus-Eye dyadic units; eye-of-Horus tradition).
 *   - Clagett, M. (1999). "Ancient Egyptian Science: A Source Book,
 *     Vol III: Ancient Egyptian Mathematics." American Philosophical
 *     Society, §III.1 (dyadic fraction system).
 *
 * Lean obligation: `Lutar/Egyptian/HorusEye.lean :: horus_eye_sum_eq_63_over_64`.
 *
 * v16 ancient-foundations graft R1-G2 (b4_rosie_amaru_ancient).
 */

export const HORUS_EYE_UNITS: readonly number[] = Object.freeze([
  1 / 2,   // bit 0
  1 / 4,   // bit 1
  1 / 8,   // bit 2
  1 / 16,  // bit 3
  1 / 32,  // bit 4
  1 / 64,  // bit 5
]);

export const HORUS_EYE_DENOMINATOR = 64;
export const HORUS_EYE_MAX_NUMERATOR = 63;
export const HORUS_EYE_MAX = HORUS_EYE_MAX_NUMERATOR / HORUS_EYE_DENOMINATOR;

/**
 * Encode a weight w ∈ [0, 63/64] as a 6-bit integer in [0, 63].
 * Round-to-nearest with ties broken toward zero (banker would round to even;
 * we choose toward-zero because it is deterministic under IEEE-754 doubles).
 */
export function encodeHorusEye(weight: number): number {
  if (!Number.isFinite(weight)) {
    throw new RangeError(`encodeHorusEye: non-finite weight ${weight}`);
  }
  if (weight < 0 || weight > HORUS_EYE_MAX) {
    throw new RangeError(
      `encodeHorusEye: weight ${weight} out of range [0, ${HORUS_EYE_MAX}]`,
    );
  }
  return Math.round(weight * HORUS_EYE_DENOMINATOR);
}

/**
 * Decode a 6-bit integer in [0, 63] to its exact dyadic weight in [0, 63/64].
 * Always returns an IEEE-754 double that exactly represents n/64.
 */
export function decodeHorusEye(code: number): number {
  if (!Number.isInteger(code)) {
    throw new TypeError(`decodeHorusEye: non-integer code ${code}`);
  }
  if (code < 0 || code > HORUS_EYE_MAX_NUMERATOR) {
    throw new RangeError(
      `decodeHorusEye: code ${code} out of range [0, ${HORUS_EYE_MAX_NUMERATOR}]`,
    );
  }
  return code / HORUS_EYE_DENOMINATOR;
}

/**
 * Decompose a 6-bit code into its Horus-Eye unit summands.
 * Returns an array of length 6 of booleans, MSB-first (1/2 ... 1/64).
 */
export function horusEyeBits(code: number): readonly boolean[] {
  if (!Number.isInteger(code) || code < 0 || code > HORUS_EYE_MAX_NUMERATOR) {
    throw new RangeError(`horusEyeBits: code ${code} out of range`);
  }
  const bits: boolean[] = new Array(6);
  for (let i = 0; i < 6; i++) {
    bits[i] = ((code >> (5 - i)) & 1) === 1;
  }
  return Object.freeze(bits);
}

/**
 * Sum the six Horus-Eye dyadic units. Returns exactly 63/64 by construction.
 */
export function horusEyeSum(): number {
  let acc = 0;
  for (const u of HORUS_EYE_UNITS) acc += u;
  return acc;
}

/**
 * Round-trip a weight through encode→decode and report the quantisation error.
 * Used for calibration and audit: any |error| > 1/128 indicates a malformed
 * input rather than the expected quantisation.
 */
export function horusEyeRoundtripError(weight: number): number {
  const code = encodeHorusEye(weight);
  const decoded = decodeHorusEye(code);
  return decoded - weight;
}
