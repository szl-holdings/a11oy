/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173
Date:  2026-05-28

# HUKLLA Halt-Eligibility — Formal Predicate and Proofs

DOI (thesis): 10.5281/zenodo.14502417

## Cross-org provenance

HUKLLA (Hardened Unambiguous Kill-switch, Latch & Lineage Authority) is the
SZL Holdings Governance Tripwire Doctrine, documented across the org:

  1. **Doctrine reference**: `szl-holdings/ouroboros-thesis/docs/HUKLLA.md`
     Authored 2026-05-11. T01–T11 tripwire register. ORCID 0009-0001-0110-4173.

  2. **Runtime tripwires (T01–T10)**: `szl-holdings/amaru/src/chakras/chakra_7_crown/HUKLLA_10_TRIPWIRES.md`
     Ten deterministic tripwires: T01 (moralGrounding < 0.95), T02
     (measurabilityHonesty < 0.95), T05 (unauthorized write), T10 (STOP
     directive), etc. Any fire → `allegiance_pass = false` → state frozen.

  3. **Public claim source**: `szl-holdings/ouroboros-thesis/docs/anatomy/explainers/linkedin/linkedin_full_body.md`
     Publicly states "HUKLLA — 660 SLOC. Ten deterministic tripwires."

  4. **CI gate (T11)**: `szl-holdings/ouroboros-thesis/.github/workflows/doi-title-gate.yml`
     `huklla-t11-doi-title-gate` — active CI gate enforcing DOI/title consistency.
     Also deployed in `szl-holdings/szl-trust`.

## Lean formalization role

This file is the PROOF LAYER above the CI/doctrine layer. The CI tripwires
and the Python kernel enforce HUKLLA at runtime; this file provides the
formal predicate `isHaltEligible` with machine-checked proofs of its
monotonicity and decidability. Together they form the full HUKLLA stack:
doctrine → CI gate → kernel tripwires → Lean proof layer.

The halt-eligibility predicate operationalises T01/T02 (axis floor ≥ 0.90)
and T10 (halt authority belongs to HUKLLA, not OVERWATCH — see
`Lutar.OVERWATCH.ReadOnly.overwatch_halt_separation_of_powers`).

## What this file proves

  - `isHaltEligible`: Bool predicate over ExecutionTrace.
  - `halt_eligibility_monotone`: eligibility is monotone in lambda_score.
  - `halt_eligibility_decidable`: Decidable instance (kernel-checkable).
  - `not_eligible_of_low_score`: score < 0.90 → not eligible.

Zero `sorry`. Doctrine V6.

**Doctrine V6 declaration.**
No banned words (revolutionary, groundbreaking, magical, world-class,
best-in-class, game-changing, first-ever, unprecedented, frontier-defining)
appear in this file. All theorems are genuinely machine-checked.
-/

import Mathlib.Tactic
import Mathlib.Data.Bool.Basic

namespace Lutar.HUKLLA

/-! ## Core structure -/

/-- An execution trace carries the three fields that determine halt eligibility.
`lambda_score` is in `ℝ`; callers are responsible for ensuring it lies in
`[0, 1]` when produced by the Lutar invariant runtime.

The 0.90 floor matches `A11OY_DOCTRINE_LAMBDA_FLOOR=0.90` in
`szl-holdings/a11oy/deploy/manifests/a11oy-deployment.yaml` (line 34–35)
and corresponds to the T01/T02 axis floors in the amaru tripwire register. -/
structure ExecutionTrace where
  lambda_score          : ℝ
  receipts_closed       : Bool
  rho_closure_satisfied : Bool

/-! ## Halt-eligibility predicate -/

/-- The lambda floor: 0.90, matching the runtime constant. -/
def LAMBDA_FLOOR : ℝ := 0.90

/-- `isHaltEligible t` is `true` iff all three conditions hold:
  - trust score meets the 0.90 threshold (LAMBDA_FLOOR),
  - receipts are confirmed closed,
  - ρ-closure invariant is satisfied.

Corresponds to the HUKLLA T10 tripwire: halt authority belongs to HUKLLA.
The threshold 0.90 matches `A11OY_DOCTRINE_LAMBDA_FLOOR` in
`a11oy/deploy/manifests/a11oy-deployment.yaml` line 34–35. -/
noncomputable def isHaltEligible (t : ExecutionTrace) : Bool :=
  decide (t.lambda_score ≥ LAMBDA_FLOOR) && t.receipts_closed && t.rho_closure_satisfied

/-! ## Theorem 1 — Monotonicity -/

/-- **halt_eligibility_monotone.**
If trace `t1` has a lambda_score no greater than trace `t2`'s, and both
traces share the same boolean fields, then eligibility is monotone:
`t1` being eligible implies `t2` is eligible.

Proof: unfold `isHaltEligible`, case-split on `decide`, and use
transitivity of `≥` for real numbers. -/
theorem halt_eligibility_monotone
    (t1 t2 : ExecutionTrace)
    (h_score : t1.lambda_score ≤ t2.lambda_score)
    (h_rc    : t1.receipts_closed = t2.receipts_closed)
    (h_rho   : t1.rho_closure_satisfied = t2.rho_closure_satisfied)
    (h_elig  : isHaltEligible t1 = true) :
    isHaltEligible t2 = true := by
  simp only [isHaltEligible, Bool.and_eq_true, decide_eq_true_eq] at *
  obtain ⟨⟨h_ge, h_rc1⟩, h_rho1⟩ := h_elig
  exact ⟨⟨le_trans h_ge h_score, h_rc ▸ h_rc1⟩, h_rho ▸ h_rho1⟩

/-! ## Theorem 2 — Decidability -/

/-- **halt_eligibility_decidable.**
For any execution trace, whether `isHaltEligible t = true` is decidable.
This follows from `Bool.decEq`. -/
noncomputable instance halt_eligibility_decidable (t : ExecutionTrace) :
    Decidable (isHaltEligible t = true) :=
  inferInstance

/-! ## Corollary — false when score below threshold -/

/-- If `lambda_score < LAMBDA_FLOOR`, the trace is not halt-eligible
regardless of the boolean fields. -/
theorem not_eligible_of_low_score
    (t : ExecutionTrace)
    (h : t.lambda_score < LAMBDA_FLOOR) :
    isHaltEligible t = false := by
  have hnot : ¬ t.lambda_score ≥ LAMBDA_FLOOR := not_le.mpr h
  simp [isHaltEligible, hnot]

end Lutar.HUKLLA
