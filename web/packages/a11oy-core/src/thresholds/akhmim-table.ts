/**
 * R1-G4 — Self-verifying threshold tables in the Akhmim/RMP tradition
 *
 * The Akhmim Wooden Tablet (Cairo Egyptian Museum CG 25367/25368, ~2000 BCE)
 * computes 1-by-n divisions for n ∈ {3, 5, 7, 10, 11, 13} as unit-fraction
 * sums and *verifies them in place* by reconstructing 1 from the parts
 * [Vymazalová 2002, *Archiv Orientální* 70(1):27–42]. The Rhind Mathematical
 * Papyrus (RMP, ~1650 BCE) contains the 2/n table for n odd, 3 ≤ n ≤ 101 —
 * the canonical Egyptian fraction decompositions [Imhausen 2016 ch. 4;
 * Robins-Shute 1987, plates 1–4]. We package both lineages as a single
 * **self-verifying threshold table** for a11oy governance thresholds:
 * every entry stores its Egyptian-fraction decomposition AND a runtime
 * verifier that recovers the original ratio from the parts.
 *
 * Use case: governance threshold values θ_i ∈ Q with rational denominators
 * benefit from a verifiable decomposition into unit fractions because each
 * piece is independently bounded ([0,1/2], [0,1/3], etc.). This is the
 * classical "additive bound proof" pattern: instead of trusting a single
 * floating-point θ, ship the decomposition and verify in place.
 *
 * Sources:
 *   - Vymazalová, H. (2002), "The Wooden Tablets from Cairo: The Use of the
 *     Grain Unit ḤḲȜ.T in Ancient Egypt", *Archiv Orientální* 70(1):27–42.
 *   - Imhausen, A. (2016), *Mathematics in Ancient Egypt*, Princeton UP,
 *     ISBN 978-0691117133, ch. 4 (the 2/n table).
 *   - Robins, G. & Shute, C. (1987), *The Rhind Mathematical Papyrus*,
 *     British Museum Press, plates 1–4 (RMP recto, 2/n table for odd
 *     n ∈ {3..101}).
 *   - Gillings, R. J. (1972), *Mathematics in the Time of the Pharaohs*,
 *     MIT Press, ch. 5 (2/n decompositions enumerated).
 *
 * Lean obligation: `Lutar/Egyptian/AkhmimTable.lean`,
 *   `akhmim_2n_correct` — proved by `decide` over the finite table.
 */

/** A unit-fraction decomposition: ratio = Σ 1/dᵢ. */
export interface UnitFractionDecomposition {
  /** The denominators dᵢ; the sum is Σ 1/dᵢ. */
  readonly parts: readonly number[];
  /** Original ratio numerator (for `2/n`, this is 2). */
  readonly num: number;
  /** Original ratio denominator (for `2/n`, this is n). */
  readonly den: number;
}

/**
 * The RMP 2/n table for odd n ∈ {3, 5, ..., 101}. Decompositions match
 * the canonical readings in Gillings 1972 and Imhausen 2016 (the RMP itself
 * does not write the table identically for every n; we use the Gillings
 * normalisation, which is exact in lowest form).
 */
export const RMP_TWO_OVER_N: ReadonlyMap<number, readonly number[]> = new Map([
  [3, [2, 6]],
  [5, [3, 15]],
  [7, [4, 28]],
  [9, [6, 18]],
  [11, [6, 66]],
  [13, [8, 52, 104]],
  [15, [10, 30]],
  [17, [12, 51, 68]],
  [19, [12, 76, 114]],
  [21, [14, 42]],
  [23, [12, 276]],
  [25, [15, 75]],
  [27, [18, 54]],
  [29, [24, 58, 174, 232]],
  [31, [20, 124, 155]],
  [33, [22, 66]],
  [35, [30, 42]],
  [37, [24, 111, 296]],
  [39, [26, 78]],
  [41, [24, 246, 328]],
  [43, [42, 86, 129, 301]],
  [45, [30, 90]],
  [47, [30, 141, 470]],
  [49, [28, 196]],
  [51, [34, 102]],
  [53, [30, 318, 795]],
  [55, [30, 330]],
  [57, [38, 114]],
  [59, [36, 236, 531]],
  [61, [40, 244, 488, 610]],
  [63, [42, 126]],
  [65, [39, 195]],
  [67, [40, 335, 536]],
  [69, [46, 138]],
  [71, [40, 568, 710]],
  [73, [60, 219, 292, 365]],
  [75, [50, 150]],
  [77, [44, 308]],
  [79, [60, 237, 316, 790]],
  [81, [54, 162]],
  [83, [60, 332, 415, 498]],
  [85, [51, 255]],
  [87, [58, 174]],
  [89, [60, 356, 534, 890]],
  [91, [70, 130]],
  [93, [62, 186]],
  [95, [60, 380, 570]],
  [97, [56, 679, 776]],
  [99, [66, 198]],
  [101, [101, 202, 303, 606]],
]);

/**
 * Verify a unit-fraction decomposition: returns
 * `{ok: true}` when Σ 1/dᵢ equals num/den exactly in rationals,
 * `{ok: false, reason}` otherwise.
 *
 * Integer-arithmetic verification: rather than sum 1/d in floating point,
 * we compute `Σ (∏ dⱼ / dᵢ) = num · (∏ dⱼ / den)` over integers, which is
 * exact for the entire RMP table.
 */
export function verifyUnitFractionDecomposition(
  d: UnitFractionDecomposition,
): { ok: true } | { ok: false; reason: string } {
  if (d.parts.length === 0) return { ok: false, reason: 'empty decomposition' };
  if (d.den === 0) return { ok: false, reason: 'zero denominator' };
  for (const p of d.parts) {
    if (!Number.isInteger(p) || p <= 0) {
      return { ok: false, reason: `non-positive-integer part ${p}` };
    }
  }
  // Σ 1/dᵢ = num/den  ⇔  den · (Σ ∏_{j≠i} dⱼ) = num · ∏ dⱼ
  // Use BigInt to avoid floating-point or i32 overflow on long tables.
  const parts = d.parts.map((p) => BigInt(p));
  const prod = parts.reduce((a, b) => a * b, 1n);
  let lhs = 0n;
  for (let i = 0; i < parts.length; i++) {
    let term = 1n;
    for (let j = 0; j < parts.length; j++) {
      if (j !== i) term *= parts[j]!;
    }
    lhs += term;
  }
  const lhsScaled = BigInt(d.den) * lhs;
  const rhsScaled = BigInt(d.num) * prod;
  if (lhsScaled === rhsScaled) return { ok: true };
  return {
    ok: false,
    reason: `sum mismatch: den·Σ=${lhsScaled} vs num·∏=${rhsScaled}`,
  };
}

/**
 * Look up the RMP 2/n decomposition. Returns `undefined` if n is even or
 * out of range; throws no exception — the caller is expected to handle
 * the absence.
 */
export function lookupTwoOverN(
  n: number,
): UnitFractionDecomposition | undefined {
  const parts = RMP_TWO_OVER_N.get(n);
  if (!parts) return undefined;
  return { parts, num: 2, den: n };
}

/**
 * Self-verifying lookup: returns the decomposition together with the
 * verification result. The F3 failure-mode pattern — every table entry
 * carries its own audit.
 */
export function selfVerifyingLookup(
  n: number,
):
  | { found: true; decomposition: UnitFractionDecomposition; verified: boolean }
  | { found: false } {
  const decomposition = lookupTwoOverN(n);
  if (!decomposition) return { found: false };
  const result = verifyUnitFractionDecomposition(decomposition);
  return { found: true, decomposition, verified: result.ok };
}
