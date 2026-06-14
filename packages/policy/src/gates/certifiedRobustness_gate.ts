// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for CertifiedRobustnessRadius (G39)
//
// Policy rationale:
//   A gate decision is certifiably robust at input x if the ℓ₂ radius R
//   computed from randomized smoothing parameters satisfies R ≥ R_min_safety.
//   Formula (Cohen-Rosenfeld-Kolter 2019, Theorem 1):
//     R = (σ/2) · (Φ⁻¹(p̄_A) − Φ⁻¹(p̄_B))
//   where p̄_A is the Monte Carlo lower bound on the top-class probability
//   and p̄_B is the upper bound on the runner-up probability.
//
//   Lean theorem cited: `certifiedRobustnessRadiusBound`
//   Lean file: Lutar/Robustness/CertifiedRadius.lean
//   Lean commit SHA: b675cd84caa17080671570c153484c817f8769ac
//   Lean status: radius positivity and monotonicity are 0-sorry;
//                full N-P tightness has 2 sorries (sorry map documented).
//   Severity: ENFORCED (radius below safety floor → hard deny)
//
// Non-redundancy: adversarialRobustness_gate.ts (TH8) is a binary Λ ≥ 0.90
// check. G39 is the first quantitative radius-valued robustness gate.
//
// References:
//   Cohen, Rosenfeld & Kolter (2019). "Certified Adversarial Robustness
//   via Randomized Smoothing." ICML 2019. PMLR 97:1310-1320.
//   arXiv:1902.02918. DOI:10.48550/arXiv.1902.02918

// ── Inline formula ─────────────────────────────────────────────────────────────
// G39: R = (σ/2) · (Φ⁻¹(p̄_A) − Φ⁻¹(p̄_B))
// Gate passes iff R ≥ min_safety_radius.

export interface CertifiedRobustnessGateConfig {
  /**
   * Minimum certified radius required for allow.
   * Default: 0.0 (any positive radius passes unless overridden).
   */
  minSafetyRadius?: number;
}

export interface CertifiedRobustnessGateOpts {
  /** Gaussian smoothing noise std dev σ > 0. */
  smoothing_sigma: number;
  /** Lower confidence bound on top-class probability p̄_A ∈ (0.5, 1). */
  p_A_lower: number;
  /** Upper confidence bound on runner-up probability p̄_B ∈ [0, 0.5). */
  p_B_upper: number;
  /** Minimum safety radius to enforce (overrides config). Optional. */
  min_safety_radius?: number;
}

export interface CertifiedRobustnessDecision {
  allow:                boolean;
  rationale:            string;
  formula:              string;
  leanTheorem:          string;
  leanFile:             string;
  leanCommitSha:        string;
  smoothing_sigma:      number;
  p_A_lower:            number;
  p_B_upper:            number;
  certified_radius:     number;
  min_safety_radius:    number;
  radius_sufficient:    boolean;
  dsse_extension: {
    certified_robustness: {
      smoothing_sigma:      number;
      p_A_lower:            number;
      p_B_upper:            number;
      certified_radius:     number;
      min_safety_radius:    number;
      radius_sufficient:    boolean;
      lean_theorem_sha:     string;
    };
  };
}

const LEAN_THEOREM = "certifiedRobustnessRadiusBound";
const LEAN_FILE    = "Lutar/Robustness/CertifiedRadius.lean";
const LEAN_COMMIT  = "b675cd84caa17080671570c153484c817f8769ac";
const FORMULA_STR  =
  "R = (σ/2)·(Φ⁻¹(p̄_A)−Φ⁻¹(p̄_B))  " +
  "[Cohen, Rosenfeld & Kolter 2019 Thm.1; arXiv:1902.02918; ICML PMLR 97:1310]";

/**
 * Standard normal quantile function Φ⁻¹(p) = √2 · erfinv(2p − 1).
 * Uses the erfinv approximation for p ∈ (0, 1).
 * Reference: Abramowitz & Stegun §26.2.23 for the inverse normal CDF.
 */
function normalQuantile(p: number): number {
  if (p <= 0 || p >= 1) throw new RangeError(`normalQuantile: p must be in (0,1); got ${p}`);
  // Rational approximation of Φ⁻¹ (Beasley-Springer-Moro algorithm, relative error < 2.3e-9)
  const a = [
    -3.969683028665376e+01,  2.209460984245205e+02,
    -2.759285104469687e+02,  1.383577518672690e+02,
    -3.066479806614716e+01,  2.506628277459239e+00,
  ];
  const b = [
    -5.447609879822406e+01,  1.615858368580409e+02,
    -1.556989798598866e+02,  6.680131188771972e+01,
    -1.328068155288572e+01,
  ];
  const c = [
    -7.784894002430293e-03, -3.223964580411365e-01,
    -2.400758277161838e+00, -2.549732539343734e+00,
     4.374664141464968e+00,  2.938163982698783e+00,
  ];
  const d = [
     7.784695709041462e-03,  3.224671290700398e-01,
     2.445134137142996e+00,  3.754408661907416e+00,
  ];
  const p_low = 0.02425;
  const p_high = 1 - p_low;
  let q: number;
  if (p < p_low) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0]! * q + c[1]!) * q + c[2]!) * q + c[3]!) * q + c[4]!) * q + c[5]!) /
           ((((d[0]! * q + d[1]!) * q + d[2]!) * q + d[3]!) * q + 1);
  } else if (p <= p_high) {
    q = p - 0.5;
    const r = q * q;
    return (((((a[0]! * r + a[1]!) * r + a[2]!) * r + a[3]!) * r + a[4]!) * r + a[5]!) * q /
           (((((b[0]! * r + b[1]!) * r + b[2]!) * r + b[3]!) * r + b[4]!) * r + 1);
  } else {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return -(((((c[0]! * q + c[1]!) * q + c[2]!) * q + c[3]!) * q + c[4]!) * q + c[5]!) /
             ((((d[0]! * q + d[1]!) * q + d[2]!) * q + d[3]!) * q + 1);
  }
}

/** Compute certified ℓ₂ radius from Cohen-Rosenfeld-Kolter 2019 Theorem 1. */
function computeCertifiedRadius(sigma: number, pA: number, pB: number): number {
  return (sigma / 2) * (normalQuantile(pA) - normalQuantile(pB));
}

/**
 * CertifiedRobustnessRadius (G39) policy gate.
 *
 * Verifies that the certified ℓ₂ robustness radius R derived from randomized
 * smoothing parameters meets the configured safety floor R_min.
 *
 * Lean theorem: `certifiedRobustnessRadiusBound` (Lutar/Robustness/CertifiedRadius.lean)
 * Reference: Cohen, Rosenfeld & Kolter (2019) arXiv:1902.02918.
 */
export function certifiedRobustnessGate(
  config: CertifiedRobustnessGateConfig = {}
): (opts: CertifiedRobustnessGateOpts) => CertifiedRobustnessDecision {
  const configMinRadius = config.minSafetyRadius ?? 0.0;

  return (opts: CertifiedRobustnessGateOpts): CertifiedRobustnessDecision => {
    const { smoothing_sigma, p_A_lower, p_B_upper } = opts;
    const min_safety_radius = opts.min_safety_radius ?? configMinRadius;

    // --- Input validation ---
    if (!Number.isFinite(smoothing_sigma) || smoothing_sigma <= 0) {
      throw new Error(`CertifiedRobustnessGate: smoothing_sigma must be > 0; got ${smoothing_sigma}`);
    }
    if (p_A_lower <= 0.5 || p_A_lower >= 1) {
      throw new Error(`CertifiedRobustnessGate: p_A_lower must be in (0.5,1); got ${p_A_lower}`);
    }
    if (p_B_upper < 0 || p_B_upper >= 0.5) {
      throw new Error(`CertifiedRobustnessGate: p_B_upper must be in [0,0.5); got ${p_B_upper}`);
    }
    if (p_B_upper >= p_A_lower) {
      throw new Error(`CertifiedRobustnessGate: p_A_lower must exceed p_B_upper`);
    }

    // --- Core computation ---
    const certified_radius = computeCertifiedRadius(smoothing_sigma, p_A_lower, p_B_upper);
    const radius_sufficient = certified_radius >= min_safety_radius;

    const rationale = radius_sufficient
      ? `Lean:${LEAN_THEOREM} — R=${certified_radius.toFixed(4)} ≥ R_min=${min_safety_radius}. Certified ℓ₂-robust at σ=${smoothing_sigma}, p̄_A=${p_A_lower}, p̄_B=${p_B_upper}.`
      : `Lean:${LEAN_THEOREM} — DENY: R=${certified_radius.toFixed(4)} < R_min=${min_safety_radius}. Certified radius insufficient.`;

    return {
      allow:             radius_sufficient,
      rationale,
      formula:           FORMULA_STR,
      leanTheorem:       LEAN_THEOREM,
      leanFile:          LEAN_FILE,
      leanCommitSha:     LEAN_COMMIT,
      smoothing_sigma,
      p_A_lower,
      p_B_upper,
      certified_radius,
      min_safety_radius,
      radius_sufficient,
      dsse_extension: {
        certified_robustness: {
          smoothing_sigma,
          p_A_lower,
          p_B_upper,
          certified_radius,
          min_safety_radius,
          radius_sufficient,
          lean_theorem_sha: LEAN_COMMIT,
        },
      },
    };
  };
}
