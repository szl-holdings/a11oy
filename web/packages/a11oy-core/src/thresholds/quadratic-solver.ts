/**
 * R3-G3 — BM 13901 completing-the-square solver for receipt thresholds
 *
 * The Old Babylonian tablet BM 13901 (~1800 BCE, British Museum) records
 * the closed-form solution of `x² + bx = c` as
 *
 *     x = √(c + (b/2)²) − b/2
 *
 * — the canonical *completing-the-square* construction
 * [Høyrup 2002, *Lengths, Widths, Surfaces*, Springer-Verlag, ch. 1;
 *  Robson 2008, *Mathematics in Ancient Iraq*, Princeton UP, ch. 4.1].
 *
 * We use this for one-shot root-finding when a receipt threshold satisfies
 * a quadratic stability condition (e.g. when the slack term in a PAC-Bayes
 * bound is itself defined by a quadratic in the empirical risk). The
 * formula is *exact* in real arithmetic and reduces a numerical
 * iteration to a single √.
 *
 * Sources:
 *   - Høyrup, J. (2002), *Lengths, Widths, Surfaces: A Portrait of Old
 *     Babylonian Algebra*, Springer-Verlag, ISBN 978-0387953038, ch. 1
 *     (BM 13901 problem 1).
 *   - Robson, E. (2008), *Mathematics in Ancient Iraq: A Social History*,
 *     Princeton University Press, ISBN 978-0691091822, ch. 4.1.
 *   - Neugebauer, O. (1957), *The Exact Sciences in Antiquity*, Brown
 *     University Press, ch. II.
 *
 * Lean obligation: `Lutar/Thresholds/QuadraticCompletion.lean`,
 *   `quadratic_root_correct` — proved with `Real.sq_sqrt` + `ring`.
 */

/** Input for the quadratic `x² + bx = c`, `c ≥ 0`. */
export interface QuadraticInput {
  /** Linear coefficient `b`. Sign-free. */
  readonly b: number;
  /** Constant term `c`. Must be ≥ 0 to guarantee a non-negative root. */
  readonly c: number;
}

/** Output: the non-negative root `x = √(c + (b/2)²) − b/2` and a residual. */
export interface QuadraticRoot {
  /** The Old-Babylonian root: x = √(c + (b/2)²) − b/2. */
  readonly x: number;
  /** Residual |x² + b·x − c|. Should be ~0 up to floating-point error. */
  readonly residual: number;
  /** The half-step b/2 (the "completing" offset). */
  readonly halfB: number;
  /** The discriminant √-term √(c + (b/2)²). */
  readonly sqrtTerm: number;
}

/**
 * Solve `x² + b·x = c` for the non-negative root via completing-the-square.
 *
 * Throws `RangeError` when `c + (b/2)² < 0` — in real arithmetic the
 * formula remains real iff `c ≥ −(b/2)²`. For `c ≥ 0` this is always true.
 *
 * The residual `|x² + b·x − c|` is computed alongside as the F3 self-audit
 * (every threshold solution ships its own residual).
 */
export function solveBabylonianQuadratic(input: QuadraticInput): QuadraticRoot {
  const { b, c } = input;
  const halfB = b / 2;
  const disc = c + halfB * halfB;
  if (disc < 0) {
    throw new RangeError(
      `BM-13901 solver: discriminant ${disc} < 0; no real root`,
    );
  }
  const sqrtTerm = Math.sqrt(disc);
  const x = sqrtTerm - halfB;
  const residual = Math.abs(x * x + b * x - c);
  return { x, residual, halfB, sqrtTerm };
}

/**
 * Verify a candidate root: returns the residual `|x² + b·x − c|`. Pure
 * floating-point arithmetic.
 */
export function quadraticResidual(b: number, c: number, x: number): number {
  return Math.abs(x * x + b * x - c);
}
