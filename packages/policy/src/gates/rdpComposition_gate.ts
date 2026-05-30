// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for RDPSequentialComposition (G38)
//
// Policy rationale:
//   For a pipeline of k steps each satisfying (α, εᵢ)-RDP, the sequential
//   composition is (α, Σεᵢ)-RDP (Mironov 2017, Proposition 1).
//   Converting to (ε_dp, δ)-DP: ε_dp = Σεᵢ + ln(1/δ)/(α-1).
//   The gate accepts a chained receipt only if ε_dp ≤ declared budget ceiling.
//
//   Lean theorem cited: `rdpSequentialCompositionAdditivity`
//   Lean file: Lutar/DP/RDPComposition.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Lean status: theorem (2 sorries for measure-theoretic Rényi divergence;
//                budget arithmetic predicate `rdpBudgetValid` has 0 sorries)
//   Severity: ENFORCED
//
// References:
//   Mironov (2017). "Rényi Differential Privacy."
//   IEEE CSF 2017. arXiv:1702.07476. DOI:10.1109/CSF.2017.11
//   Rényi (1961). Proc. 4th Berkeley Symposium 1, 547–561.
//   https://projecteuclid.org/euclid.bsmsp/1200512181

// ── Inline formula ─────────────────────────────────────────────────────────────
// G38: ε_total = Σᵢ εᵢ  (composition, same α)
//      ε_dp = ε_total + ln(1/δ) / (α - 1)  (conversion to (ε,δ)-DP)
//      Gate passes iff ε_dp ≤ budget_threshold.

export interface RDPCompositionGateConfig {
  /**
   * Default Rényi order α if not declared per-receipt.
   * Must be > 1. Default: 8.0 (common choice for Gaussian mechanism).
   */
  defaultAlpha?: number;
  /**
   * Default δ for RDP → DP conversion if not declared.
   * Default: 1e-5.
   */
  defaultDelta?: number;
}

export interface RDPCompositionGateOpts {
  /** Rényi order α > 1. */
  rdp_alpha: number;
  /** Per-step RDP ε values (one per sequential mechanism call). */
  rdp_epsilon_steps: number[];
  /** δ for the (ε, δ)-DP conversion. */
  dp_delta: number;
  /** Declared ε budget ceiling. */
  budget_epsilon_threshold: number;
}

export interface RDPCompositionDecision {
  allow:                    boolean;
  rationale:                string;
  formula:                  string;
  leanTheorem:              string;
  leanFile:                 string;
  leanCommitSha:            string;
  rdp_alpha:                number;
  rdp_epsilon_total:        number;
  dp_epsilon_converted:     number;
  dp_delta:                 number;
  budget_epsilon_threshold: number;
  rdp_budget_valid:         boolean;
  step_count:               number;
  dsse_extension: {
    rdp_accounting: {
      alpha:                  number;
      steps:                  number[];
      epsilon_total_rdp:      number;
      delta:                  number;
      epsilon_dp_converted:   number;
      budget_threshold:       number;
      budget_valid:           boolean;
      lean_theorem_sha:       string;
    };
  };
}

const LEAN_THEOREM = "rdpSequentialCompositionAdditivity";
const LEAN_FILE    = "Lutar/DP/RDPComposition.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const FORMULA_STR  =
  "ε_dp = Σᵢεᵢ + ln(1/δ)/(α−1)  [Mironov 2017 Prop.1+3; arXiv:1702.07476; DOI:10.1109/CSF.2017.11]";

/**
 * Compute total (α, Σεᵢ)-RDP cost from steps, then convert to (ε_dp, δ)-DP.
 * Mironov 2017 Proposition 1 (composition) and Proposition 3 (conversion).
 */
function computeRDPBudget(
  alpha: number,
  epsilonSteps: number[],
  delta: number
): { epsilon_total_rdp: number; epsilon_dp_converted: number } {
  // Composition: (α, ε₁)-RDP + (α, ε₂)-RDP = (α, ε₁+ε₂)-RDP
  const epsilon_total_rdp = epsilonSteps.reduce((s, e) => s + e, 0);
  // Conversion: (α, ε_rdp)-RDP → (ε_rdp + ln(1/δ)/(α-1), δ)-DP
  const epsilon_dp_converted = epsilon_total_rdp + Math.log(1 / delta) / (alpha - 1);
  return { epsilon_total_rdp, epsilon_dp_converted };
}

/**
 * RDPSequentialComposition (G38) policy gate.
 *
 * Verifies that the cumulative RDP privacy budget across k sequential
 * mechanism calls, converted to (ε, δ)-DP, does not exceed the declared ceiling.
 *
 * Lean theorem: `rdpSequentialCompositionAdditivity` (Lutar/DP/RDPComposition.lean)
 * Reference: Mironov (2017) arXiv:1702.07476.
 */
export function rdpCompositionGate(
  config: RDPCompositionGateConfig = {}
): (opts: RDPCompositionGateOpts) => RDPCompositionDecision {
  const defaultAlpha = config.defaultAlpha ?? 8.0;
  const defaultDelta = config.defaultDelta ?? 1e-5;

  return (opts: RDPCompositionGateOpts): RDPCompositionDecision => {
    const {
      rdp_alpha,
      rdp_epsilon_steps,
      dp_delta,
      budget_epsilon_threshold,
    } = opts;

    // --- Input validation ---
    if (!Number.isFinite(rdp_alpha) || rdp_alpha <= 1) {
      throw new Error(`RDPCompositionGate: rdp_alpha must be > 1; got ${rdp_alpha}`);
    }
    if (!Array.isArray(rdp_epsilon_steps) || rdp_epsilon_steps.length === 0) {
      throw new Error("RDPCompositionGate: rdp_epsilon_steps must be a non-empty array");
    }
    for (const e of rdp_epsilon_steps) {
      if (!Number.isFinite(e) || e < 0) {
        throw new Error(`RDPCompositionGate: all RDP ε steps must be ≥ 0; got ${e}`);
      }
    }
    if (!Number.isFinite(dp_delta) || dp_delta <= 0 || dp_delta >= 1) {
      throw new Error(`RDPCompositionGate: dp_delta must be in (0,1); got ${dp_delta}`);
    }

    // --- Core accounting ---
    const { epsilon_total_rdp, epsilon_dp_converted } = computeRDPBudget(
      rdp_alpha, rdp_epsilon_steps, dp_delta
    );
    const rdp_budget_valid = epsilon_dp_converted <= budget_epsilon_threshold;

    const rationale = rdp_budget_valid
      ? `Lean:${LEAN_THEOREM} — RDP budget valid. ε_rdp=${epsilon_total_rdp.toFixed(6)}, ε_dp=${epsilon_dp_converted.toFixed(6)} ≤ budget=${budget_epsilon_threshold}. α=${rdp_alpha}, k=${rdp_epsilon_steps.length} steps.`
      : `Lean:${LEAN_THEOREM} — DENY: ε_dp=${epsilon_dp_converted.toFixed(6)} exceeds budget=${budget_epsilon_threshold}. (α=${rdp_alpha}, Σεᵢ=${epsilon_total_rdp.toFixed(6)}, δ=${dp_delta})`;

    return {
      allow:                    rdp_budget_valid,
      rationale,
      formula:                  FORMULA_STR,
      leanTheorem:              LEAN_THEOREM,
      leanFile:                 LEAN_FILE,
      leanCommitSha:            LEAN_COMMIT,
      rdp_alpha,
      rdp_epsilon_total:        epsilon_total_rdp,
      dp_epsilon_converted:     epsilon_dp_converted,
      dp_delta,
      budget_epsilon_threshold,
      rdp_budget_valid,
      step_count:               rdp_epsilon_steps.length,
      dsse_extension: {
        rdp_accounting: {
          alpha:                  rdp_alpha,
          steps:                  rdp_epsilon_steps,
          epsilon_total_rdp,
          delta:                  dp_delta,
          epsilon_dp_converted,
          budget_threshold:       budget_epsilon_threshold,
          budget_valid:           rdp_budget_valid,
          lean_theorem_sha:       LEAN_COMMIT,
        },
      },
    };
  };
}
