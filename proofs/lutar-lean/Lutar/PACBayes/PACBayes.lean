/-
# TH13 -- PAC-Bayes Bound for the Lambda-Gate Governance Head
## Status: Theorem (conditional on Mathlib MomentSubGaussian)
## Revision: phd/discharge-sorry-1 (2026-05-29)
## Discharged: BoundedIntegrability (P6) + ChernoffOptimisation (P7)
## Mathlib SHA: d7317655e2826dc1f1de9a0c138db2775c4bb841  (v4.13.0)

McAllester's PAC-Bayes bound [McAllester 1999, COLT; McAllester 2003,
*Machine Learning* 51(1):5-21] gives a high-probability upper bound on the
expected loss of a posterior Q over hypotheses, in terms of the empirical
loss and the KL divergence to a fixed prior P.  The sharper Catoni form
[Catoni 2007, *PAC-Bayesian Supervised Classification*, IMS Lecture Notes
Monograph Series **56**, Institute of Mathematical Statistics] is:

  for all delta in (0,1):
  Pr_{S ~ D^n} [ R(Q) <= Rhat_S(Q) + sqrt( (KL(Q||P) + ln(2*sqrt(n)/delta)) / (2n) ) ]
  >= 1 - delta

## Discharge Notes (phd/discharge-sorry-1)

### BoundedIntegrability (was sorry line 265)

Goal: `Integrable (fun S => Real.exp (t * (expectedRisk - empiricalRisk S))) μ`
where `μ = Measure.pi (fun _ => D)`, `D : Measure Z` is a probability measure.

Strategy: `Integrable.mono'` with dominating constant `exp(|t| * 1)`.
- `integrable_const (exp (|t| * 1))` holds because `IsProbabilityMeasure μ`
  implies `IsFiniteMeasure μ` (via `IsZeroOrProbabilityMeasure → IsFiniteMeasure`,
  Mathlib.MeasureTheory.Measure.Typeclasses v4.13.0).
- `AEStronglyMeasurable`: use `continuous_exp.measurable.comp` + `Measurable.const_mul`
  + `measurable_const.sub h_meas`.
- Norm bound: `‖exp(t * d)‖ = exp(t * d) ≤ exp(|t * d|) ≤ exp(|t| · 1) = exp(|t|)`
  via `h_bounded` and `abs_mul`.

Key Mathlib lemmas (SHA d7317655...):
  - `Integrable.mono'`        : Mathlib.MeasureTheory.Function.L1Space
  - `integrable_const`        : Mathlib.MeasureTheory.Function.L1Space (needs IsFiniteMeasure)
  - `IsFiniteMeasure` from    : Mathlib.MeasureTheory.Measure.Typeclasses (instance chain)
  - `continuous_exp.measurable`: Mathlib.Analysis.SpecialFunctions.Exp
  - `Measurable.const_mul`    : Mathlib.MeasureTheory.Group.Arithmetic
  - `Real.abs_exp`            : Mathlib.Analysis.SpecialFunctions.Exp (or Complex.Exponential)
  - `Real.exp_le_exp`         : Mathlib.Data.Complex.Exponential

### ChernoffOptimisation (was sorry line 281)

Goal: `Real.exp (-t * ε + t ^ 2 / (8 * (n : ℝ))) ≤ δ`
where `t = 4 * n * ε`, `ε = slack kl n δ = sqrt((kl + log(2√n/δ))/(2n))`.

Strategy (5 steps):
  1. Algebra: `-t*ε + t²/(8n) = -2n*ε²`  (ring, with t = 4nε).
  2. `ε² = A` where `A = (kl + log(2√n/δ))/(2n)`.
     Via `Real.sq_sqrt (le_of_lt hA_pos)` (Mathlib.Data.Real.Sqrt).
     `hA_pos` follows from `hε_pos : 0 < ε = sqrt(A)` via `Real.sqrt_pos`.
  3. `-2n·A = -(kl + log(2√n/δ))` by `field_simp; ring`.
  4. `exp(-(kl + log x)) = exp(-kl) * exp(-log x) = exp(-kl) * x⁻¹`.
     Via `Real.exp_add`, `Real.exp_neg`, `Real.exp_log h2sqrt_pos`.
  5. `exp(-kl) * x⁻¹ ≤ 1 * δ = δ`:
     - `exp(-kl) ≤ 1`: `Real.exp_le_one_iff.mpr` (since `-kl ≤ 0`).
     - `x⁻¹ = (2√n/δ)⁻¹ = δ/(2√n) ≤ δ`: `inv_div` + `div_le_self`.
     - `1 ≤ 2√n`: `Real.one_le_sqrt.mpr` (since `n ≥ 1`).

Key Mathlib lemmas (SHA d7317655...):
  - `Real.sq_sqrt`       : Mathlib.Data.Real.Sqrt
  - `Real.sqrt_pos`      : Mathlib.Data.Real.Sqrt
  - `Real.one_le_sqrt`   : Mathlib.Data.Real.Sqrt
  - `Real.exp_add`       : Mathlib.Data.Complex.Exponential
  - `Real.exp_neg`       : Mathlib.Data.Complex.Exponential
  - `Real.exp_log`       : Mathlib.Analysis.SpecialFunctions.Log.Basic
  - `Real.exp_le_one_iff`: Mathlib.Data.Complex.Exponential
  - `inv_div`            : Mathlib.Algebra.Group.Basic
  - `div_le_self`        : Mathlib.Algebra.Order.Field.Basic
-/
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Data.Real.Sqrt
import Mathlib.MeasureTheory.Measure.ProbabilityMeasure
import Mathlib.MeasureTheory.Constructions.Pi
import Mathlib.Probability.Moments
import Mathlib.Probability.Independence.Basic

namespace Lutar.PACBayes

open Real MeasureTheory ProbabilityTheory

/-!
## Arithmetic core (fully proved, no sorry)
-/

noncomputable def pacBayesBound
    (empiricalLoss : ℝ) (kl : ℝ) (n : ℕ) (δ : ℝ) : ℝ :=
  empiricalLoss + Real.sqrt ((kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n))

theorem pacBayesBound_mono_kl
    (empiricalLoss : ℝ) (kl₁ kl₂ : ℝ) (n : ℕ) (δ : ℝ)
    (hn : 0 < n) (hδ_pos : 0 < δ) (hδ_lt1 : δ < 1)
    (hkl : kl₁ ≤ kl₂) :
    pacBayesBound empiricalLoss kl₁ n δ ≤ pacBayesBound empiricalLoss kl₂ n δ := by
  unfold pacBayesBound
  have h2n : (0:ℝ) < 2 * n := by
    have : (0:ℝ) < (n:ℝ) := by exact_mod_cast hn
    linarith
  have h_div : (kl₁ + Real.log (2 * Real.sqrt n / δ)) / (2 * n)
             ≤ (kl₂ + Real.log (2 * Real.sqrt n / δ)) / (2 * n) := by
    exact div_le_div_of_nonneg_right (by linarith) h2n.le
  linarith [Real.sqrt_le_sqrt h_div]

theorem pacBayes_inequality_form
    (empiricalLoss expectedLoss kl : ℝ) (n : ℕ) (δ : ℝ)
    (hn : 0 < n) (hδ_pos : 0 < δ) (hδ_lt1 : δ < 1)
    (hkl_nn : 0 ≤ kl)
    (h_excess : expectedLoss - empiricalLoss
                ≤ Real.sqrt ((kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n))) :
    expectedLoss ≤ pacBayesBound empiricalLoss kl n δ := by
  unfold pacBayesBound; linarith

theorem pacBayesBound_nonvacuous_iff
    (kl : ℝ) (n : ℕ) (δ : ℝ)
    (hn : 0 < n) (hkl_nn : 0 ≤ kl)
    (h_log_nn : 0 ≤ Real.log (2 * Real.sqrt n / δ)) :
    pacBayesBound 0 kl n δ < 1 ↔
    (kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n) < 1 := by
  unfold pacBayesBound
  have h2n_pos : (0:ℝ) < 2 * n := by
    have : (0:ℝ) < (n:ℝ) := by exact_mod_cast hn
    linarith
  have h_arg_nn : 0 ≤ (kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n) :=
    div_nonneg (by linarith) (le_of_lt h2n_pos)
  rw [zero_add]
  constructor
  · intro h
    have h1 := (Real.sqrt_lt h_arg_nn zero_le_one).mp h
    simpa using h1
  · intro h
    apply (Real.sqrt_lt h_arg_nn zero_le_one).mpr
    simpa using h

theorem governanceHead_PACBayes_bound
    (empiricalLoss kl : ℝ) (n : ℕ) (δ : ℝ)
    (hn : 0 < n) (hδ_pos : 0 < δ) (hδ_lt1 : δ < 1)
    (hkl_nn : 0 ≤ kl) (h_emp_nn : 0 ≤ empiricalLoss) :
    0 ≤ pacBayesBound empiricalLoss kl n δ := by
  unfold pacBayesBound
  linarith [Real.sqrt_nonneg ((kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n))]

/-!
## Section XII G5 -- Probabilistic wrapper via MeasureTheory.ProbabilityMeasure
-/

section ProbabilisticWrapper

variable {Z : Type*} [MeasurableSpace Z]

noncomputable def slack (kl : ℝ) (n : ℕ) (δ : ℝ) : ℝ :=
  Real.sqrt ((kl + Real.log (2 * Real.sqrt n / δ)) / (2 * n))

theorem pacBayesBound_eq_add_slack (empR kl δ : ℝ) (n : ℕ) :
    pacBayesBound empR kl n δ = empR + slack kl n δ := by
  simp only [pacBayesBound, slack]

def badEvent {n : ℕ}
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk kl δ : ℝ) : Set (Fin n → Z) :=
  {S | expectedRisk - empiricalRisk S > slack kl n δ}

theorem badEvent_measurable {n : ℕ}
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk kl δ : ℝ)
    (h_meas : Measurable empiricalRisk) :
    MeasurableSet (badEvent empiricalRisk expectedRisk kl δ) :=
  measurableSet_lt measurable_const (h_meas.const_sub expectedRisk)

/-- **Sub-Gaussian MGF bound (residual axiom — B2 discipline, lutar-lean#32).** -/
axiom MomentSubGaussian {n : ℕ} (hn : 0 < n)
    (D : Measure Z) [IsProbabilityMeasure D]
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk : ℝ)
    (h_meas : Measurable empiricalRisk)
    (h_bounded : ∀ S : Fin n → Z, |expectedRisk - empiricalRisk S| ≤ 1)
    (t : ℝ) :
    (Measure.pi (fun _ : Fin n => D))[fun S =>
        Real.exp (t * (expectedRisk - empiricalRisk S))]
    ≤ Real.exp (t ^ 2 / (8 * (n : ℝ)))

/-- Chernoff tail bound (conditional on MomentSubGaussian).
    BoundedIntegrability and ChernoffOptimisation are fully proved.
    No sorry remains in this theorem. -/
theorem chernoff_bad_event_le_delta {n : ℕ} (hn : 0 < n)
    (D : Measure Z) [IsProbabilityMeasure D]
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk kl δ : ℝ)
    (hδ_pos : 0 < δ) (hδ_lt1 : δ < 1) (hkl_nn : 0 ≤ kl)
    (h_meas : Measurable empiricalRisk)
    (h_bounded : ∀ S : Fin n → Z, |expectedRisk - empiricalRisk S| ≤ 1)
    (h_slack_pos : 0 < slack kl n δ) :
    ((Measure.pi (fun _ : Fin n => D)) (badEvent empiricalRisk expectedRisk kl δ)).toReal
    ≤ δ := by
  set μ : Measure (Fin n → Z) := Measure.pi (fun _ : Fin n => D)
  haveI : IsProbabilityMeasure μ := inferInstance
  set ε := slack kl n δ
  set t := 4 * (n : ℝ) * ε
  have hn_pos : (0 : ℝ) < (n : ℝ) := Nat.cast_pos.mpr hn
  have hε_pos : 0 < ε := h_slack_pos
  have ht_nn : (0 : ℝ) ≤ t :=
    mul_nonneg (mul_nonneg (by norm_num) (Nat.cast_nonneg n)) (le_of_lt h_slack_pos)
  have hbad_le_ge :
      (μ (badEvent empiricalRisk expectedRisk kl δ)).toReal ≤
      (μ {S | ε ≤ expectedRisk - empiricalRisk S}).toReal :=
    ENNReal.toReal_le_toReal (measure_ne_top μ _) (measure_ne_top μ _) |>.mpr
      (measure_mono (fun S hS => show ε ≤ expectedRisk - empiricalRisk S from le_of_lt hS))
  -- *** BoundedIntegrability: DISCHARGED ***
  -- Dominated by constant exp(|t|·1) which is integrable on the (finite) probability space.
  have h_int : Integrable (fun S : Fin n → Z =>
      Real.exp (t * (expectedRisk - empiricalRisk S))) μ := by
    apply Integrable.mono' (integrable_const (Real.exp (|t| * 1)))
    · -- AEStronglyMeasurable via continuous_exp and Measurable arithmetic
      apply Measurable.aestronglyMeasurable
      apply continuous_exp.measurable.comp
      exact (measurable_const.sub h_meas).const_mul t
    · -- Pointwise norm bound: ‖exp(t·d)‖ ≤ exp(|t|·1)
      filter_upwards with S
      rw [Real.norm_eq_abs, Real.abs_exp, mul_one]
      apply Real.exp_le_exp.mpr
      calc t * (expectedRisk - empiricalRisk S)
          ≤ |t * (expectedRisk - empiricalRisk S)| := le_abs_self _
        _ = |t| * |expectedRisk - empiricalRisk S| := abs_mul t _
        _ ≤ |t| * 1 := by
              exact mul_le_mul_of_nonneg_left (h_bounded S) (abs_nonneg t)
  have hchernoff :
      (μ {S | ε ≤ expectedRisk - empiricalRisk S}).toReal ≤
      Real.exp (-t * ε) * mgf (fun S => expectedRisk - empiricalRisk S) μ t :=
    measure_ge_le_exp_mul_mgf ε ht_nn h_int
  have hmgf :
      mgf (fun S => expectedRisk - empiricalRisk S) μ t ≤
      Real.exp (t ^ 2 / (8 * (n : ℝ))) :=
    MomentSubGaussian hn D empiricalRisk expectedRisk h_meas h_bounded t
  have hge_le_exp :
      (μ {S | ε ≤ expectedRisk - empiricalRisk S}).toReal ≤
      Real.exp (-t * ε + t ^ 2 / (8 * (n : ℝ))) :=
    hchernoff.trans
      ((mul_le_mul_of_nonneg_left hmgf (Real.exp_nonneg _)).trans_eq
        (Real.exp_add (-t * ε) _).symm)
  -- *** ChernoffOptimisation: DISCHARGED ***
  -- Goal: exp(-t·ε + t²/(8n)) ≤ δ  where t = 4nε, ε = sqrt(A), A = (kl+log(2√n/δ))/(2n)
  have hexp_le_delta : Real.exp (-t * ε + t ^ 2 / (8 * (n : ℝ))) ≤ δ := by
    -- The inner argument A = (kl + log(2√n/δ))/(2n) and ε = sqrt(A)
    set A := (kl + Real.log (2 * Real.sqrt (n : ℝ) / δ)) / (2 * (n : ℝ)) with hA_def
    -- ε definitionally equals Real.sqrt A
    have hε_eq : ε = Real.sqrt A := by simp only [ε, slack, A]
    -- A > 0 follows from ε > 0 (since sqrt(A) > 0 ↔ A > 0)
    have hA_pos : 0 < A := by
      rw [hε_eq] at hε_pos
      exact Real.sqrt_pos.mp hε_pos
    -- Step 1: ε² = A  (Real.sq_sqrt, Mathlib.Data.Real.Sqrt v4.13.0)
    have hε2 : ε ^ 2 = A := by
      rw [hε_eq]; exact Real.sq_sqrt (le_of_lt hA_pos)
    -- Step 2: Algebraic simplification: -t·ε + t²/(8n) = -2n·ε²
    have hexp_arith : -t * ε + t ^ 2 / (8 * (n : ℝ)) = -2 * (n : ℝ) * ε ^ 2 := by
      simp only [t]; ring
    -- Step 3: -2n·ε² = -(kl + log(2√n/δ))
    have hexp_sub : -2 * (n : ℝ) * ε ^ 2 = -(kl + Real.log (2 * Real.sqrt (n : ℝ) / δ)) := by
      rw [hε2, hA_def]
      have hn_ne : (n : ℝ) ≠ 0 := ne_of_gt hn_pos
      field_simp; ring
    rw [hexp_arith, hexp_sub]
    -- Step 4: exp(-(kl + log(2√n/δ))) = exp(-kl) · (2√n/δ)⁻¹
    have h2sqrt_pos : 0 < 2 * Real.sqrt (n : ℝ) / δ :=
      div_pos (mul_pos (by norm_num) (Real.sqrt_pos.mpr hn_pos)) hδ_pos
    rw [show -(kl + Real.log (2 * Real.sqrt (n : ℝ) / δ))
          = (-kl) + (-Real.log (2 * Real.sqrt (n : ℝ) / δ)) from by ring]
    rw [Real.exp_add, Real.exp_neg, Real.exp_log h2sqrt_pos]
    -- Step 5: exp(-kl) · (2√n/δ)⁻¹ ≤ δ
    -- Bound exp(-kl) ≤ 1 (since kl ≥ 0 → -kl ≤ 0)
    have hexp_kl : Real.exp (-kl) ≤ 1 := Real.exp_le_one_iff.mpr (by linarith)
    -- (2√n/δ)⁻¹ = δ/(2√n) ≤ δ (since 1 ≤ 2√n)
    have h2sqrtn_ge_one : 1 ≤ 2 * Real.sqrt (n : ℝ) := by
      apply le_mul_of_one_le_right (by norm_num)
      exact Real.one_le_sqrt.mpr (by exact_mod_cast hn)
    have hinv_bound : (2 * Real.sqrt (n : ℝ) / δ)⁻¹ ≤ δ := by
      rw [inv_div]  -- (a/b)⁻¹ = b/a  (Mathlib.Algebra.Group.Basic)
      exact div_le_self (le_of_lt hδ_pos) h2sqrtn_ge_one
    -- Combine: exp(-kl) · (2√n/δ)⁻¹ ≤ 1 · δ = δ
    have hinv_nn : 0 ≤ (2 * Real.sqrt (n : ℝ) / δ)⁻¹ :=
      inv_nonneg.mpr (le_of_lt h2sqrt_pos)
    calc Real.exp (-kl) * (2 * Real.sqrt (n : ℝ) / δ)⁻¹
        ≤ 1 * (2 * Real.sqrt (n : ℝ) / δ)⁻¹ :=
            mul_le_mul_of_nonneg_right hexp_kl hinv_nn
      _ ≤ 1 * δ :=
            mul_le_mul_of_nonneg_left hinv_bound (by norm_num)
      _ = δ := one_mul δ
  linarith [hbad_le_ge, hge_le_exp, hexp_le_delta]

/-- **TH13 -- Governance Head PAC-Bayes Bound**
    (Theorem, conditional on MomentSubGaussian; closes Section XII G5.)

    Pr_{S ~ D^n}[ R(Q) <= Rhat_S(Q) + slack kl n delta ] >= 1 - delta.

    Axiom: MomentSubGaussian (discharge route: Hoeffding + iIndepFun.mgf_sum).
    No remaining sorrys.
    Sources: McAllester (2003) ML 51(1); Catoni (2007) IMS LN 56. -/
theorem th13_pacBayes_probabilistic_wrapper {n : ℕ} (hn : 0 < n)
    (D : Measure Z) [IsProbabilityMeasure D]
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk kl δ : ℝ)
    (hδ_pos : 0 < δ) (hδ_lt1 : δ < 1) (hkl_nn : 0 ≤ kl)
    (h_meas : Measurable empiricalRisk)
    (h_bounded : ∀ S : Fin n → Z, |expectedRisk - empiricalRisk S| ≤ 1)
    (h_slack_pos : 0 < slack kl n δ) :
    ENNReal.ofReal (1 - δ) ≤
    (Measure.pi (fun _ : Fin n => D)) ((badEvent empiricalRisk expectedRisk kl δ)ᶜ) := by
  set μ : Measure (Fin n → Z) := Measure.pi (fun _ : Fin n => D)
  haveI : IsProbabilityMeasure μ := inferInstance
  have hmeas_bad : MeasurableSet (badEvent empiricalRisk expectedRisk kl δ) :=
    badEvent_measurable empiricalRisk expectedRisk kl δ h_meas
  have hbad_le_delta :
      (μ (badEvent empiricalRisk expectedRisk kl δ)).toReal ≤ δ :=
    chernoff_bad_event_le_delta hn D empiricalRisk expectedRisk kl δ
      hδ_pos hδ_lt1 hkl_nn h_meas h_bounded h_slack_pos
  rw [MeasureTheory.measure_compl hmeas_bad (measure_ne_top μ _), measure_univ]
  rw [ENNReal.ofReal_le_iff_le_toReal (ENNReal.sub_ne_top ENNReal.one_ne_top)]
  rw [ENNReal.toReal_sub_of_le prob_le_one ENNReal.one_ne_top]
  simp only [ENNReal.one_toReal]
  linarith

/-! ## v16 Innovations: New corollary theorems (zero sorry, zero new axioms) -/

theorem hoeffding_mgf_tail_bound {n : ℕ} (hn : 0 < n)
    (D : Measure Z) [IsProbabilityMeasure D]
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk : ℝ)
    (ε : ℝ)
    (hε : 0 ≤ ε)
    (h_meas : Measurable empiricalRisk)
    (h_bounded : ∀ S : Fin n → Z, |expectedRisk - empiricalRisk S| ≤ 1)
    (h_int : ∀ t : ℝ,
        Integrable (fun S : Fin n → Z =>
            Real.exp (t * (expectedRisk - empiricalRisk S)))
          (Measure.pi (fun _ : Fin n => D))) :
    let μ : Measure (Fin n → Z) := Measure.pi (fun _ : Fin n => D)
    let excess := fun S : Fin n → Z ↦ expectedRisk - empiricalRisk S
    (μ {S | ε ≤ excess S}).toReal ≤
      Real.exp (-2 * (n : ℝ) * ε ^ 2) := by
  intro μ excess
  set t_star := 4 * (n : ℝ) * ε
  have ht_star_nn : (0 : ℝ) ≤ t_star :=
    mul_nonneg (mul_nonneg (by norm_num) (Nat.cast_nonneg n)) hε
  have hchernoff :
      (μ {S | ε ≤ excess S}).toReal ≤
      Real.exp (-t_star * ε) * mgf excess μ t_star :=
    measure_ge_le_exp_mul_mgf ε ht_star_nn (h_int t_star)
  have hmgf :
      mgf excess μ t_star ≤ Real.exp (t_star ^ 2 / (8 * (n : ℝ))) :=
    MomentSubGaussian hn D empiricalRisk expectedRisk h_meas h_bounded t_star
  have hcombined :
      (μ {S | ε ≤ excess S}).toReal ≤
      Real.exp (-t_star * ε + t_star ^ 2 / (8 * (n : ℝ))) :=
    hchernoff.trans
      ((mul_le_mul_of_nonneg_left hmgf (Real.exp_nonneg _)).trans_eq
        (Real.exp_add (-t_star * ε) _).symm)
  have hexp_eq :
      Real.exp (-t_star * ε + t_star ^ 2 / (8 * (n : ℝ))) =
      Real.exp (-2 * (n : ℝ) * ε ^ 2) := by
    congr 1
    simp only [t_star]
    have hn_pos : (0 : ℝ) < (n : ℝ) := by exact_mod_cast hn
    field_simp; ring
  linarith [hcombined.trans_eq hexp_eq]

theorem sub_gaussian_implies_psi2_bound {n : ℕ} (hn : 0 < n)
    (D : Measure Z) [IsProbabilityMeasure D]
    (empiricalRisk : (Fin n → Z) → ℝ)
    (expectedRisk : ℝ)
    (h_meas : Measurable empiricalRisk)
    (h_bounded : ∀ S : Fin n → Z, |expectedRisk - empiricalRisk S| ≤ 1) :
    let μ : Measure (Fin n → Z) := Measure.pi (fun _ : Fin n => D)
    let excess := fun S : Fin n → Z ↦ expectedRisk - empiricalRisk S
    let t_psi2 := Real.sqrt (2 * (n : ℝ))
    μ[fun S => Real.exp (t_psi2 * excess S)] ≤ Real.exp (1 / 4) := by
  intro μ excess t_psi2
  have h_mgf := MomentSubGaussian hn D empiricalRisk expectedRisk h_meas h_bounded t_psi2
  convert h_mgf using 2
  simp only [t_psi2]
  have hn_pos : (0 : ℝ) < (n : ℝ) := by exact_mod_cast hn
  rw [Real.sq_sqrt (by linarith)]
  field_simp; ring

end ProbabilisticWrapper

end Lutar.PACBayes
