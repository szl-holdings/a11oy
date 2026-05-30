// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 — a11oy policy gate for VCGTruthfulness (G37)
//
// Policy rationale:
//   In a multi-attester SZL system, payment vectors that do not match the
//   Clarke pivot formula violate the truthful-reporting dominant strategy.
//   This gate verifies that each declared payment p_i equals:
//     p_i = max_{x} Σ_{j≠i} v_j(x) − Σ_{j≠i} v_j(x*)
//   where x* is the welfare-maximising outcome.
//   A receipt with incorrect payments is denied (attester incentives not aligned).
//
//   Lean theorem cited: `vcgDominantStrategyTruth` (currently with 1 sorry
//   in argmax uniqueness; gate-level receipt validation `vcgReceiptValid_iff` is 0 sorries)
//   Lean file: Lutar/MechanismDesign/VCGTruthfulness.lean
//   Lean commit SHA: 1dca00032dfc9aa8559cc6c2e4b63192fcf52371
//   Severity: STAGED-ADVISORY until Lean sorry₁ is discharged; enforced by config.
//
// References:
//   Vickrey (1961) DOI:10.1111/j.1540-6261.1961.tb02789.x
//   Clarke (1971)  DOI:10.1007/BF01726210
//   Groves (1973)  DOI:10.2307/1914085

// ── Inline formula ─────────────────────────────────────────────────────────────
// G37: p_i = max_{x∈X} Σ_{j≠i} v_j(x) − Σ_{j≠i} v_j(x*)
// Gate passes iff all declared payments match the Clarke pivot formula.

export interface VCGTruthfulnessGateConfig {
  /**
   * Tolerance for floating-point payment comparison.
   * Default: 1e-9.
   */
  paymentTolerance?: number;
  /**
   * If false, gate is advisory (emits warning but does not block).
   * Default: false (STAGED until Lean sorry₁ discharges).
   */
  enforced?: boolean;
}

export interface AttesterValuation {
  /** Attester identifier. */
  attester_id: string;
  /** Valuation for each outcome: outcome_id → value. */
  valuations: Record<string, number>;
}

export interface VCGTruthfulnessGateOpts {
  /** Set of outcomes. */
  outcomes: string[];
  /** Valuation profile: one entry per attester. */
  attester_valuations: AttesterValuation[];
  /** Declared payment for each attester. */
  declared_payments: Record<string, number>;
}

export interface VCGTruthfulnessDecision {
  allow:                    boolean;
  is_advisory:              boolean;
  rationale:                string;
  formula:                  string;
  leanTheorem:              string;
  leanFile:                 string;
  leanCommitSha:            string;
  vcg_outcome:              string;
  vcg_social_welfare:       number;
  vcg_payments_required:    Record<string, number>;
  vcg_truthfulness_valid:   boolean;
  payment_errors:           Array<{ attester: string; declared: number; required: number }>;
  dsse_extension: {
    mechanism_design: {
      mechanism_type:            string;
      outcome_elected:           string;
      social_welfare:            number;
      attester_payments:         Record<string, number>;
      clarke_formula_verified:   boolean;
      lean_theorem_sha:          string;
    };
  };
}

const LEAN_THEOREM = "vcgDominantStrategyTruth";
const LEAN_FILE    = "Lutar/MechanismDesign/VCGTruthfulness.lean";
const LEAN_COMMIT  = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";
const FORMULA_STR  =
  "p_i = max_{x} Σ_{j≠i} v_j(x) − Σ_{j≠i} v_j(x*)  " +
  "[Vickrey 1961, Clarke 1971, Groves 1973; DOI:10.2307/1914085]";

/** Compute social welfare at outcome x under valuation profile. */
function socialWelfare(
  outcome: string,
  valuations: AttesterValuation[]
): number {
  return valuations.reduce((sum, av) => sum + (av.valuations[outcome] ?? 0), 0);
}

/** Find welfare-maximising outcome. Returns first maximum in case of tie. */
function vcgOutcome(outcomes: string[], valuations: AttesterValuation[]): string {
  if (outcomes.length === 0) throw new Error("vcgOutcome: no outcomes provided");
  let bestOutcome = outcomes[0]!;
  let bestWelfare = socialWelfare(bestOutcome, valuations);
  for (const o of outcomes.slice(1)) {
    const w = socialWelfare(o, valuations);
    if (w > bestWelfare) { bestWelfare = w; bestOutcome = o; }
  }
  return bestOutcome;
}

/** Compute Clarke pivot payment for attester i. */
function clarkePayment(
  attester_id: string,
  outcomes: string[],
  valuations: AttesterValuation[],
  xStar: string
): number {
  // Valuations without attester i
  const others = valuations.filter(av => av.attester_id !== attester_id);
  // max_{x} Σ_{j≠i} v_j(x)
  const maxWelfareWithout = Math.max(
    ...outcomes.map(o => others.reduce((s, av) => s + (av.valuations[o] ?? 0), 0))
  );
  // Σ_{j≠i} v_j(x*)
  const welfareAtXStarWithout = others.reduce(
    (s, av) => s + (av.valuations[xStar] ?? 0), 0
  );
  return maxWelfareWithout - welfareAtXStarWithout;
}

/**
 * VCGTruthfulness (G37) policy gate.
 *
 * Verifies that declared attester payments match the Clarke pivot formula,
 * guaranteeing dominant-strategy truthfulness of the multi-attester mechanism.
 *
 * Lean theorem: `vcgDominantStrategyTruth` (Lutar/MechanismDesign/VCGTruthfulness.lean)
 * STAGED-ADVISORY: 1 sorry in Lean stub (argmax uniqueness). Configurable via `enforced`.
 * References: Vickrey 1961, Clarke 1971, Groves 1973.
 */
export function vcgTruthfulnessGate(
  config: VCGTruthfulnessGateConfig = {}
): (opts: VCGTruthfulnessGateOpts) => VCGTruthfulnessDecision {
  const tolerance = config.paymentTolerance ?? 1e-9;
  const enforced  = config.enforced ?? false;   // STAGED until sorry₁ discharges

  return (opts: VCGTruthfulnessGateOpts): VCGTruthfulnessDecision => {
    const { outcomes, attester_valuations, declared_payments } = opts;

    if (outcomes.length === 0) {
      throw new Error("VCGTruthfulnessGate: no outcomes provided");
    }
    if (attester_valuations.length === 0) {
      throw new Error("VCGTruthfulnessGate: no attesters provided");
    }

    // 1. Compute welfare-maximising outcome
    const xStar = vcgOutcome(outcomes, attester_valuations);
    const swAtXStar = socialWelfare(xStar, attester_valuations);

    // 2. Compute Clarke pivot payments
    const required: Record<string, number> = {};
    for (const av of attester_valuations) {
      required[av.attester_id] = clarkePayment(
        av.attester_id, outcomes, attester_valuations, xStar
      );
    }

    // 3. Compare declared payments to required
    const errors: Array<{ attester: string; declared: number; required: number }> = [];
    for (const av of attester_valuations) {
      const declared = declared_payments[av.attester_id] ?? 0;
      const req      = required[av.attester_id] ?? 0;
      if (Math.abs(declared - req) > tolerance) {
        errors.push({ attester: av.attester_id, declared, required: req });
      }
    }

    const vcg_truthfulness_valid = errors.length === 0;
    // In STAGED mode: advisory only (allow = true regardless)
    const allow = enforced ? vcg_truthfulness_valid : true;
    const is_advisory = !enforced;

    const rationale = vcg_truthfulness_valid
      ? `Lean:${LEAN_THEOREM} — VCG payments verified. Elected outcome: ${xStar}, social welfare: ${swAtXStar.toFixed(4)}.`
      : `Lean:${LEAN_THEOREM} — ${enforced ? "DENY" : "ADVISORY"}: Clarke payment mismatch for [${errors.map(e => e.attester).join(", ")}]. VCG truthfulness not verified.`;

    return {
      allow,
      is_advisory,
      rationale,
      formula: FORMULA_STR,
      leanTheorem:               LEAN_THEOREM,
      leanFile:                  LEAN_FILE,
      leanCommitSha:             LEAN_COMMIT,
      vcg_outcome:               xStar,
      vcg_social_welfare:        swAtXStar,
      vcg_payments_required:     required,
      vcg_truthfulness_valid,
      payment_errors:            errors,
      dsse_extension: {
        mechanism_design: {
          mechanism_type:            "VCG",
          outcome_elected:           xStar,
          social_welfare:            swAtXStar,
          attester_payments:         required,
          clarke_formula_verified:   vcg_truthfulness_valid,
          lean_theorem_sha:          LEAN_COMMIT,
        },
      },
    };
  };
}
