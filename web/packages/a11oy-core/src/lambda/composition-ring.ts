/**
 * R4-I3 — Brahmagupta–Fibonacci 2-square composition identity
 *
 * Brahmagupta (598–668 CE), in the *Brāhmasphuṭasiddhānta* (628 CE),
 * recorded the two-square multiplication identity
 *
 *     (a² + b²)(c² + d²) = (ac − bd)² + (ad + bc)²
 *
 * — independently rediscovered by Fibonacci (Leonardo of Pisa) in the
 * *Liber Quadratorum* (1225 CE) [Plofker 2009, *Mathematics in India*,
 * Princeton UP §5; Sigler 1987 trans., *Fibonacci's Liber Quadratorum*,
 * Academic Press]. The identity is the statement that the sum-of-squares
 * norm `N(a, b) = a² + b²` is *multiplicative* under the bilinear product
 *
 *     (a, b) · (c, d) := (ac − bd, ad + bc)
 *
 * — equivalently, that the Gaussian integers ℤ[i] are a multiplicative
 * monoid under complex multiplication with absolute-value-squared norm.
 *
 * **Use in the a11oy Λ-category.** The composability requirement on
 * the Λ-gate (TH4: a Λ-morphism is the composition of two morphisms
 * iff both certificate-norms multiply to the composite norm) reduces,
 * for 2-component certificates, to the Brahmagupta–Fibonacci identity.
 * This file implements the bilinear product and ships a numeric check
 * of the norm-multiplicativity property.
 *
 * Sources:
 *   - Brahmagupta (628 CE), *Brāhmasphuṭasiddhānta*, ch. 18 (kuṭṭaka).
 *   - Fibonacci, Leonardo (1225 CE), *Liber Quadratorum*; trans.
 *     Sigler, L. E. (1987), *Fibonacci's Liber Quadratorum*, Academic
 *     Press, ISBN 978-0126431308.
 *   - Plofker, K. (2009), *Mathematics in India*, Princeton UP,
 *     ISBN 978-0691120676, §5.
 *   - Dickson, L. E. (1919), *History of the Theory of Numbers*, vol.
 *     II, Carnegie Institution of Washington, ch. VI.
 *
 * Lean obligation: `Lutar/Lambda/CompositionRing.lean`,
 *   `brahmagupta_fibonacci_identity` — proved by `ring`.
 */

/** A 2-vector certificate `(a, b)` with sum-of-squares norm `a² + b²`. */
export interface TwoVector {
  readonly a: number;
  readonly b: number;
}

/** Sum-of-squares norm: `N(a, b) = a² + b²`. */
export function squareNorm(v: TwoVector): number {
  return v.a * v.a + v.b * v.b;
}

/**
 * Brahmagupta–Fibonacci bilinear product:
 *
 *     (a, b) · (c, d) := (ac − bd, ad + bc).
 *
 * The norm of the product equals the product of the norms — this is
 * the Λ-composability identity at certificate-arity 2.
 */
export function bfProduct(u: TwoVector, v: TwoVector): TwoVector {
  return {
    a: u.a * v.a - u.b * v.b,
    b: u.a * v.b + u.b * v.a,
  };
}

/**
 * Residual of the Brahmagupta–Fibonacci identity at a single 4-tuple:
 *
 *     residual(a, b, c, d) = |(a² + b²)(c² + d²) − ((ac−bd)² + (ad+bc)²)|.
 *
 * Should be exactly 0 in real arithmetic and within floating-point
 * round-off for finite inputs. Pure floating-point, no allocations.
 */
export function bfResidual(u: TwoVector, v: TwoVector): number {
  const lhs = squareNorm(u) * squareNorm(v);
  const rhs = squareNorm(bfProduct(u, v));
  return Math.abs(lhs - rhs);
}

/** Λ-composability result: the composed certificate plus its audit. */
export interface LambdaCompositionResult {
  /** The composed 2-vector certificate `(ac − bd, ad + bc)`. */
  readonly composed: TwoVector;
  /** Norm of the composed certificate. */
  readonly composedNorm: number;
  /** Product of input norms `N(u) · N(v)`. */
  readonly productOfNorms: number;
  /** Residual `|composedNorm − productOfNorms|`; should be ~0. */
  readonly residual: number;
}

/**
 * Compose two Λ-certificates as 2-vectors, returning the composed
 * certificate together with the F3 self-audit (residual of the
 * Brahmagupta–Fibonacci identity).
 */
export function composeLambdaCertificates(
  u: TwoVector,
  v: TwoVector,
): LambdaCompositionResult {
  const composed = bfProduct(u, v);
  const composedNorm = squareNorm(composed);
  const productOfNorms = squareNorm(u) * squareNorm(v);
  return {
    composed,
    composedNorm,
    productOfNorms,
    residual: Math.abs(composedNorm - productOfNorms),
  };
}
