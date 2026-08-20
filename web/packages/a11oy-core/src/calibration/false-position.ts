/**
 * R1-G1 — False-position (aha) gate calibration (Egyptian, ~1650 BCE)
 *
 * The Egyptian *aha* ("heap") method, recorded in the Rhind Mathematical
 * Papyrus (RMP problems 24, 25, 26, 27 — Robins & Shute 1987), solves a
 * linear equation by guessing a trial value, evaluating, and rescaling.
 * For a linear gate f(x) = m·x + c whose two measurements (x₁, y₁), (x₂, y₂)
 * are known, the input x* that yields target T is recovered exactly in one
 * step:
 *
 *     x* = x₁ + (T − y₁) · (x₂ − x₁) / (y₂ − y₁)
 *
 * This is the closed-form one-step false-position correction, exact for any
 * affine gate. We use it for one-shot calibration of any axis whose
 * pre-calibration response is known to be locally affine (governance
 * thresholds, calibration scalers, scoring-function offsets).
 *
 * Sources:
 *   - Imhausen, A. (2016), *Mathematics in Ancient Egypt: A Contextual History*,
 *     Princeton University Press, ISBN 978-0691117133, ch. 3 §3.4
 *     ("Method of False Position").
 *   - Robins, G. & Shute, C. (1987), *The Rhind Mathematical Papyrus: An
 *     Ancient Egyptian Text*, British Museum Press, ISBN 978-0714109442
 *     (RMP Problems 24–27).
 *   - Gillings, R. J. (1972), *Mathematics in the Time of the Pharaohs*,
 *     MIT Press, ISBN 978-0262570954, ch. 14.
 *
 * Lean obligation: `Lutar/Calibration/FalsePosition.lean`
 *   `false_position_correct` — proved with `ring`, no `sorry`.
 */

/** Two-point sample of an affine gate response. */
export interface AffineSample {
  /** Input value x. */
  readonly x: number;
  /** Measured output y = f(x). */
  readonly y: number;
}

/** Result of a one-step false-position correction. */
export interface FalsePositionResult {
  /** Recovered input x* such that f(x*) = target. */
  readonly xStar: number;
  /** The slope (y₂ − y₁) / (x₂ − x₁) used in the correction. */
  readonly slope: number;
  /** True iff the two samples are not degenerate (different x AND different y). */
  readonly wellPosed: boolean;
}

/**
 * Apply one-step false-position correction.
 *
 * Given two non-degenerate samples of an affine gate f(x) = m·x + c and a
 * target output T, return the exact x* with f(x*) = T.
 *
 * Pre-conditions:
 *  - `s1.x !== s2.x` (samples at distinct inputs)
 *  - `s1.y !== s2.y` (gate is non-constant on the bracket)
 *
 * Throws `RangeError` on degenerate input — degenerate inputs cannot
 * uniquely identify an affine gate; surfacing the error is required for
 * F3 failure-mode coverage rather than silently returning NaN.
 */
export function falsePosition(
  s1: AffineSample,
  s2: AffineSample,
  target: number,
): FalsePositionResult {
  const dx = s2.x - s1.x;
  const dy = s2.y - s1.y;
  if (dx === 0) {
    throw new RangeError(
      'false-position: samples at identical x — bracket is a single point',
    );
  }
  if (dy === 0) {
    throw new RangeError(
      'false-position: samples at identical y — gate is constant on bracket',
    );
  }
  const slope = dy / dx;
  const xStar = s1.x + (target - s1.y) / slope;
  return { xStar, slope, wellPosed: true };
}

/**
 * Verify a false-position result by re-evaluating the affine gate at x*.
 * Returns the residual |f(x*) − target|. For a true affine gate, this is 0
 * up to floating-point error.
 *
 * The reverification is the F3 "self-verifying" pattern: every calibration
 * step ships its own residual so a downstream consumer can decide whether
 * the affine assumption held.
 */
export function falsePositionResidual(
  s1: AffineSample,
  s2: AffineSample,
  target: number,
  xStar: number,
): number {
  const slope = (s2.y - s1.y) / (s2.x - s1.x);
  const intercept = s1.y - slope * s1.x;
  const recoveredY = slope * xStar + intercept;
  return Math.abs(recoveredY - target);
}
