/**
 * GRAFT 2 — Kochen–Specker 18-Vector Contextuality Witness
 *
 * Source: Cabello, A., Estebaranz, J. M., & García-Alcaine, G. (1996).
 * "Bell-Kochen-Specker theorem: A proof with 18 vectors."
 * Physics Letters A 212(4), 183–187. arXiv:quant-ph/9706009.
 *
 * The 18-vector / 9-context construction shows that no non-contextual
 * hidden-variable model can reproduce all the quantum predictions on a
 * 4-dimensional Hilbert space. We use it as a contextuality witness for
 * the a11oy policy head: if the rolling sequence of governance answers
 * is consistent with a non-contextual hidden-variable assignment, the
 * witness flags BOHR-ANOMALOUS — the policy head has collapsed into a
 * classical deterministic rule and is no longer providing the dual-
 * framed (Bohr-complementary) reasoning it claims to provide.
 *
 * The 18 vectors and 9 four-element contexts below are the canonical
 * Cabello-Estebaranz-García-Alcaine construction.
 */

/* eslint-disable @typescript-eslint/no-magic-numbers -- coordinates of
   canonical 18-vector basis from Cabello et al. (1996) Table 1. */
export const KS18_VECTORS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0, 0, 0, 1], [0, 0, 1, 0], [1, -1, 0, 0], [1, 1, 0, 0],
  [0, 0, 1, 1], [0, 0, 1, -1], [1, -1, 1, -1], [1, -1, -1, 1],
  [1, 1, -1, 1], [-1, 1, 1, 1], [1, 1, 1, -1], [1, 0, -1, 0],
  [0, 1, 0, -1], [1, 0, 1, 0], [1, 1, -1, -1], [1, 1, 1, 1],
  [1, 0, 0, 1], [0, 1, -1, 0],
];

/** Nine four-element mutually-orthogonal contexts (indices into KS18_VECTORS). */
export const KS18_CONTEXTS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0, 1, 2, 3],
  [3, 4, 5, 6],
  [5, 6, 7, 8],
  [7, 8, 9, 10],
  [9, 10, 11, 12],
  [11, 12, 13, 14],
  [13, 14, 15, 16],
  [15, 16, 17, 0],
  [17, 0, 1, 2],
];

export type KSAssignment = Map<number, 0 | 1>;

export type KSWitnessResult =
  | { contextual: true; reason: 'NO_NON_CONTEXTUAL_MODEL_FITS_OBSERVATIONS' }
  | { contextual: false; reason: 'BOHR_ANOMALOUS_NON_CONTEXTUAL_FIT_EXISTS'; example: KSAssignment };

/**
 * Search for a 0/1 assignment over the 18 vectors such that every
 * context sums to 1. Cabello et al. (1996) prove this is impossible —
 * therefore any time `search` *succeeds* in finding such an assignment
 * over our observed yes/no policy answers, our policy answers are
 * compressible to a non-contextual hidden-variable model and we have
 * collapsed.
 */
export function evaluate(observed: ReadonlyMap<number, 0 | 1>): KSWitnessResult {
  // Try to extend `observed` to a full 18-vector assignment satisfying
  // every context. Depth-first over unfilled vectors.
  const assignment: Map<number, 0 | 1> = new Map(observed);
  const order = Array.from({ length: 18 }, (_, i) => i).filter((i) => !assignment.has(i));

  const ok = (): boolean => {
    for (const ctx of KS18_CONTEXTS) {
      let s = 0;
      let unknown = false;
      for (const idx of ctx) {
        const v = assignment.get(idx);
        if (v === undefined) {
          unknown = true;
          break;
        }
        s += v;
      }
      if (!unknown && s !== 1) return false;
    }
    return true;
  };

  function dfs(i: number): boolean {
    if (i === order.length) return ok();
    const idx = order[i];
    for (const v of [0, 1] as const) {
      assignment.set(idx, v);
      if (ok() && dfs(i + 1)) return true;
    }
    assignment.delete(idx);
    return false;
  }

  const found = dfs(0);
  return found
    ? { contextual: false, reason: 'BOHR_ANOMALOUS_NON_CONTEXTUAL_FIT_EXISTS', example: assignment }
    : { contextual: true, reason: 'NO_NON_CONTEXTUAL_MODEL_FITS_OBSERVATIONS' };
}

export const KochenSpecker18Witness = { evaluate, KS18_VECTORS, KS18_CONTEXTS } as const;
