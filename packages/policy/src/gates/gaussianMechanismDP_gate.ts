// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for GaussianMechanismDP (G36)
//
// Policy rationale:
//   A DSSE receipt asserting differential privacy via the Gaussian mechanism
//   is accepted only if the declared noise scale σ_claimed satisfies the
//   calibration formula:
//     σ_claimed ≥ Δ₂f · √(2 ln(1.25/δ)) / ε
//   for the declared (ε, δ, Δ₂f) in the receipt header.
//   If σ_claimed is too small, the DP guarantee is void and the receipt is denied.
//
//   Lean theorem cited: `gaussianNoiseSufficiency`
//   Lean file: Lutar/DP/GaussianMechanism.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (2 sorries in broader measure-theoretic proof;
//                gate-level arithmetic theorem has 0 sorries)
//   Severity: ENFORCED (calibration violation is a hard deny)
//
// References:
//   Dwork & Roth (2014). Algorithmic Foundations of DP.
//   DOI: https://doi.org/10.1561/0400000042
//   Balle & Wang (2018). arXiv:1805.06530

// ── Inline formula ─────────────────────────────────────────────────────────────
// G36: σ_min = Δ₂f · √(2 · ln(1.25 / δ)) / ε
// Gate passes iff σ_claimed ≥ σ_min

export interface GaussianMechanismDPGateConfig {
  /**
   * Minimum epsilon allowed (rejects receipts with ε below this floor).
   * Default: 1e-6 (no practical floor).
   */
  minEpsilon?: number;
  /**
   * Maximum delta allowed.
   * Default: 1e-3.
   */
  maxDelta?: number;
}

export interface GaussianMechanismDPGateOpts {
  /** Declared ε privacy parameter. Must be in (0, 1). */
  dp_epsilon: number;
  /** Declared δ failure probability. Must be in (0, 1). */
  dp_delta: number;
  /** Declared ℓ₂-sensitivity of the query Δ₂f. Must be > 0. */
  l2_sensitivity: number;
  /** Asserted noise scale σ used in the Gaussian mechanism. Must be > 0. */
  sigma_claimed: number;
}

export interface GaussianMechanismDPDecision {
  allow:                 boolean;
  rationale:             string;
  formula:               string;
  leanTheorem:           string;
  leanFile:              string;
  leanCommitSha:         string;
  dp_epsilon:            number;
  dp_delta:              number;
  l2_sensitivity:        number;
  sigma_claimed:         number;
  sigma_required:        number;
  dp_calibration_valid:  boolean;
  /** DSSE receipt extension fields for in-toto payload. */
  dsse_extension: {
    dp: {
      epsilon:           number;
      delta:             number;
      l2_sensitivity:    number;
      sigma_claimed:     number;
      sigma_required:    number;
      calibration_valid: boolean;
      lean_theorem_sha:  string;
    };
  };
}

const LEAN_THEOREM  = "gaussianNoiseSufficiency";
const LEAN_FILE     = "Lutar/DP/GaussianMechanism.lean";
const LEAN_COMMIT   = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const FORMULA_STR   =
  "σ_min = Δ₂f · √(2 · ln(1.25/δ)) / ε  [Dwork-Roth 2014, §A.1; DOI:10.1561/0400000042]";

/** Compute σ_min = Δ₂f · √(2 · ln(1.25/δ)) / ε. */
function computeSigmaRequired(l2_sensitivity: number, epsilon: number, delta: number): number {
  const logTerm = Math.log(1.25 / delta);        // ln(1.25/δ) > 0 for δ < 1.25
  const sqrtTerm = Math.sqrt(2 * logTerm);        // √(2 ln(1.25/δ))
  return (l2_sensitivity * sqrtTerm) / epsilon;   // Δ₂f · √… / ε
}

/**
 * GaussianMechanismDP (G36) policy gate.
 *
 * Accepts a DSSE receipt asserting Gaussian mechanism DP only if the claimed
 * noise scale satisfies the calibration formula from Dwork-Roth 2014.
 *
 * Lean theorem: `gaussianNoiseSufficiency` (Lutar/DP/GaussianMechanism.lean)
 * Commit: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
 * References:
 *   Dwork & Roth (2014) DOI:10.1561/0400000042
 *   Balle & Wang (2018) arXiv:1805.06530
 */
export function gaussianMechanismDPGate(
  config: GaussianMechanismDPGateConfig = {}
): (opts: GaussianMechanismDPGateOpts) => GaussianMechanismDPDecision {
  const minEpsilon = config.minEpsilon ?? 1e-6;
  const maxDelta   = config.maxDelta   ?? 1e-3;

  return (opts: GaussianMechanismDPGateOpts): GaussianMechanismDPDecision => {
    const { dp_epsilon, dp_delta, l2_sensitivity, sigma_claimed } = opts;

    // --- Input validation ---
    if (!Number.isFinite(dp_epsilon) || dp_epsilon <= 0 || dp_epsilon >= 1) {
      throw new Error(`GaussianMechanismDPGate: dp_epsilon must be in (0,1); got ${dp_epsilon}`);
    }
    if (!Number.isFinite(dp_delta) || dp_delta <= 0 || dp_delta >= 1) {
      throw new Error(`GaussianMechanismDPGate: dp_delta must be in (0,1); got ${dp_delta}`);
    }
    if (!Number.isFinite(l2_sensitivity) || l2_sensitivity <= 0) {
      throw new Error(`GaussianMechanismDPGate: l2_sensitivity must be > 0; got ${l2_sensitivity}`);
    }
    if (!Number.isFinite(sigma_claimed) || sigma_claimed <= 0) {
      throw new Error(`GaussianMechanismDPGate: sigma_claimed must be > 0; got ${sigma_claimed}`);
    }

    // --- Config bound checks ---
    if (dp_epsilon < minEpsilon) {
      return deny(opts, 0,
        `dp_epsilon ${dp_epsilon} below configured minEpsilon ${minEpsilon}`);
    }
    if (dp_delta > maxDelta) {
      return deny(opts, 0,
        `dp_delta ${dp_delta} exceeds configured maxDelta ${maxDelta}`);
    }

    // --- Core calibration check ---
    const sigma_required = computeSigmaRequired(l2_sensitivity, dp_epsilon, dp_delta);
    const dp_calibration_valid = sigma_claimed >= sigma_required;

    const allow = dp_calibration_valid;
    const rationale = allow
      ? `Lean:${LEAN_THEOREM} — σ_claimed (${sigma_claimed.toFixed(4)}) ≥ σ_required (${sigma_required.toFixed(4)}). Gaussian mechanism (ε=${dp_epsilon}, δ=${dp_delta}) calibration satisfied.`
      : `Lean:${LEAN_THEOREM} — DENY: σ_claimed (${sigma_claimed.toFixed(4)}) < σ_required (${sigma_required.toFixed(4)}). DP guarantee void for (ε=${dp_epsilon}, δ=${dp_delta}).`;

    return {
      allow,
      rationale,
      formula: FORMULA_STR,
      leanTheorem:          LEAN_THEOREM,
      leanFile:             LEAN_FILE,
      leanCommitSha:        LEAN_COMMIT,
      dp_epsilon,
      dp_delta,
      l2_sensitivity,
      sigma_claimed,
      sigma_required,
      dp_calibration_valid,
      dsse_extension: {
        dp: {
          epsilon:           dp_epsilon,
          delta:             dp_delta,
          l2_sensitivity,
          sigma_claimed,
          sigma_required,
          calibration_valid: dp_calibration_valid,
          lean_theorem_sha:  LEAN_COMMIT,  // gate uses commit SHA; CI replaces with file hash
        },
      },
    };
  };
}

/** Helper: build a deny decision. */
function deny(
  opts: GaussianMechanismDPGateOpts,
  sigma_required: number,
  reason: string
): GaussianMechanismDPDecision {
  return {
    allow: false,
    rationale: `Lean:${LEAN_THEOREM} — DENY: ${reason}`,
    formula: FORMULA_STR,
    leanTheorem:          LEAN_THEOREM,
    leanFile:             LEAN_FILE,
    leanCommitSha:        LEAN_COMMIT,
    dp_epsilon:           opts.dp_epsilon,
    dp_delta:             opts.dp_delta,
    l2_sensitivity:       opts.l2_sensitivity,
    sigma_claimed:        opts.sigma_claimed,
    sigma_required,
    dp_calibration_valid: false,
    dsse_extension: {
      dp: {
        epsilon:           opts.dp_epsilon,
        delta:             opts.dp_delta,
        l2_sensitivity:    opts.l2_sensitivity,
        sigma_claimed:     opts.sigma_claimed,
        sigma_required,
        calibration_valid: false,
        lean_theorem_sha:  LEAN_COMMIT,
      },
    },
  };
}
