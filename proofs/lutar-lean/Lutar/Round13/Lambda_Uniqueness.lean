/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 13 — Λ uniqueness: the terminal statement (HONEST)

This file states the terminal uniqueness theorem and discharges everything that is soundly
provable, while marking the one genuine remaining obligation with PRECISE dependency notation.

## What is PROVEN here (no open obligations)
* `lambda_satisfiesAxioms_round13` — Λ_k satisfies A1–A5 (re-export).
* `Factors` — the factorization predicate `Φ x = ∏ xᵢ ^ αᵢ`.
* **`lambda_unique_of_factors` — the TERMINAL CONDITIONAL THEOREM:**
  `LutarAxioms Φ → Factors Φ αs → Φ = Λ k`.  Fully proved (no open obligations) using the Round 13
  Cauchy_ND layer (`exponents_equal_inv_k_of_symm`, via A5) + the geometric-mean definition.
* `maxAgg`, and `maxAgg_ne_Lambda` — a **machine-checkable counterexample fragment**:
  `maxAgg (![4,1]) ≠ Λ 2 (![4,1])`, together with `maxAgg` satisfying A2/A3/A5, witnessing
  that the *factorization premise is essential* — A1–A5 alone do NOT force the geometric mean.

## What remains OPEN (HONEST open obligation, tied to a missing axiom)
* **`lambda_unique` (UNCONDITIONAL)** — `∀ Φ, LutarAxioms Φ → Φ = Λ k`.
  This is **FALSE** under A1–A5 as formalized: `maxAgg` (= the A4 upper bound) and `min`
  satisfy A1–A5 but are not Λ_k (see `maxAgg_ne_Lambda` and `team/lambda-closure/SORRY_AUDIT.md`
  §4). The single tagged open obligation records the dependency precisely:

      FACTORIZATION_AXIOM_GAP
      ── needs A6 (bisymmetry / associativity, Kolmogorov–Nagumo–Aczél)
      ── NOT derivable from A1–A5 (counterexample: maxAgg, min)
      ── with A6, closes mechanically via `lambda_unique_of_factors`.

  Per HONESTY-OVER-CHECKLIST we do NOT fabricate a closed proof of a false statement.
  Λ therefore stays **Conjecture 1**; the internal `Conjecture` declaration is NOT upgraded.

## DOCTRINE
- Public string `749/14/163` v11: UNTOUCHED. Organ `/honest` cards "Λ = Conjecture 1": UNTOUCHED.
- No new `axiom` tokens (axioms_unique stays 14). The A6 gap is an open obligation, never an `axiom`.
- DCO trailers on the commit; doctrine footer below.

## References
- Aczél, J. (1966). *Lectures on Functional Equations.* §5.1.
- Hardy, G.H., Littlewood, J.E., Pólya, G. (1934). *Inequalities.* §2.18.
- Kolmogorov, A.N. (1930). *Sur la notion de la moyenne.* (associativity/bisymmetry axiom.)

Signed-off-by: Λ-Closure Lead <lambda-closure@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
-/
import Lutar.Axioms
import Lutar.Invariant
import Lutar.Bound
import Lutar.Round13.CauchyND_Closure
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Algebra.BigOperators.Group.Finset

namespace Lutar.Round13

open NNReal Real BigOperators

/-! ## Λ_k satisfies A1–A5 (re-exported, no open obligations) -/

theorem lambda_satisfiesAxioms_round13 {k : ℕ} (hk : 0 < k) :
    LutarAxioms (Λ k) :=
  { A1 := by
      intro x y hxy
      simp only [Λ, hk.ne', dite_false]
      apply NNReal.rpow_le_rpow
      · exact Finset.prod_le_prod (fun i _ => zero_le _) (fun i _ => hxy i)
      · positivity
    A2 := by
      intro c x
      simp only [Λ, hk.ne', dite_false]
      have : (Finset.univ : Finset (Fin k)).prod (fun i => c * x i) =
             c ^ k * (Finset.univ : Finset (Fin k)).prod x := by
        rw [Finset.prod_mul_distrib, Finset.prod_const, Finset.card_fin]
      rw [this, NNReal.mul_rpow]
      congr 1
      rw [← NNReal.rpow_natCast c k, ← NNReal.rpow_mul]
      simp [hk.ne']
    A3 := { k_pos := hk, A3_normalize := a3_normalize_proof k hk }
    A4 := fun x => Λ_le_max hk x
    A5 := fun x σ => by
      simp only [Λ_def hk]
      congr 1
      exact Equiv.prod_comp σ x }

/-! ## The factorization predicate -/

/-- `Φ` factors as a weighted product with real exponents `αs`. This is the load-bearing
    analytic content that A1–A5 do NOT supply (see `maxAgg_ne_Lambda`). -/
def Factors {k : ℕ} (Φ : Aggregator k) (αs : Fin k → NNReal) : Prop :=
  ∀ x : Axes k, Φ x = ∏ i, (x i) ^ (αs i : ℝ)

/-! ## TERMINAL CONDITIONAL THEOREM (no open obligations) -/

/-- **`lambda_unique_of_factors`.** Any A1–A5 aggregator that *factors* equals `Λ k`.

    This is the maximal honestly-true uniqueness statement: GIVEN the factorization
    `Φ x = ∏ xᵢ^αᵢ`, the axioms pin every exponent to `1/k` (via A5 through the Round 13
    `exponents_equal_inv_k_of_symm`), and `∏ xᵢ^(1/k) = (∏ xᵢ)^(1/k) = Λ k x`.
    CLOSED VIA: `exponents_equal_inv_k_of_symm`, `isSymmetric_of_A5`,
    `prod_rpow_const_eq_rpow_sum`-style collapse, `Λ_def`. -/
theorem lambda_unique_of_factors {k : ℕ} (hk : 0 < k)
    (Φ : Aggregator k) (hL : LutarAxioms Φ)
    (αs : Fin k → NNReal) (hfac : Factors Φ αs) :
    Φ = Λ k := by
  -- symmetry from A5
  have hsym : IsSymmetric Φ := isSymmetric_of_A5 hL.A5
  -- every exponent is 1/k
  have hα : ∀ i, αs i = (1 / k : NNReal) :=
    exponents_equal_inv_k_of_symm hk Φ hL hsym αs hfac
  funext x
  -- rewrite Φ x via the factorization, then collapse the constant exponents
  rw [hfac x, Λ_def hk]
  -- ∏ i, (x i) ^ (αs i : ℝ) = ∏ i, (x i) ^ ((1/k : NNReal) : ℝ)
  have hstep : (∏ i, (x i) ^ (αs i : ℝ))
      = ∏ i, (x i) ^ (((1 / k : NNReal) : ℝ)) := by
    apply Finset.prod_congr rfl
    intro i _
    rw [hα i]
  rw [hstep]
  -- ∏ i, (x i) ^ r  =  (∏ i, x i) ^ r   for a common real exponent r
  set r : ℝ := ((1 / k : NNReal) : ℝ) with hr
  have hprodrpow : (∏ i, (x i) ^ r) = ((∏ i, x i)) ^ r := by
    classical
    induction (Finset.univ : Finset (Fin k)) using Finset.induction_on with
    | empty => simp
    | @insert a t ha ih =>
        rw [Finset.prod_insert ha, Finset.prod_insert ha, ih, ← NNReal.mul_rpow]
  -- but the product over univ in `Λ_def` is `Finset.univ.prod x`; align indices
  have hxprod : (∏ i, (x i) ^ r) = ((Finset.univ : Finset (Fin k)).prod x) ^ r := by
    simpa using hprodrpow
  -- finally identify r = 1/k as reals
  have hrk : r = (1 : ℝ) / (k : ℝ) := by
    rw [hr, NNReal.coe_div, NNReal.coe_one, NNReal.coe_natCast]
  rw [hxprod, hrk]

/-! ## Counterexample fragment — A1–A5 do NOT force Λ (witness of insufficiency)

We exhibit the max-aggregator on `k = 2` and prove (i) it disagrees with `Λ 2` on `(4,1)`,
and (ii) it satisfies the *algebraic* axioms A2/A3/A5 (A1/A4 hold by `sup'` monotonicity and
`A4 = ≤ max` reflexivity — see SORRY_AUDIT §4). This is the machine-checkable record that the
`Factors` premise in `lambda_unique_of_factors` is ESSENTIAL: dropping it makes the statement
false. -/

/-- The 2-axis max aggregator `maxAgg x = x 0 ⊔ x 1` (= the A4 upper bound `univ.sup'`). -/
noncomputable def maxAgg : Aggregator 2 := fun x => x 0 ⊔ x 1

/-- `maxAgg` is permutation-invariant (A5). CLOSED VIA `sup_comm` on the swap. -/
theorem maxAgg_A5 : IsPermutationInvariant maxAgg := by
  intro x σ
  simp only [maxAgg, Function.comp]
  -- goal: x (σ 0) ⊔ x (σ 1) = x 0 ⊔ x 1.  A permutation of `Fin 2` either fixes or swaps the
  -- two indices; in both cases the unordered pair {σ 0, σ 1} = {0, 1}, so the sup is unchanged.
  -- σ 0 ≠ σ 1 (injective); on Fin 2 this forces {σ 0, σ 1} = {0,1}.
  have h01 : σ 0 ≠ σ 1 := fun h => by simpa using σ.injective h
  have hpair : (σ 0 = 0 ∧ σ 1 = 1) ∨ (σ 0 = 1 ∧ σ 1 = 0) := by
    -- decide over the (≤2)² possible value pairs using their `.val` in `{0,1}`.
    have v0 := (σ 0).isLt; have v1 := (σ 1).isLt
    have hne : (σ 0).val ≠ (σ 1).val := fun h => h01 (Fin.ext h)
    have : (σ 0).val = 0 ∧ (σ 1).val = 1 ∨ (σ 0).val = 1 ∧ (σ 1).val = 0 := by omega
    rcases this with ⟨a, b⟩ | ⟨a, b⟩
    · exact Or.inl ⟨Fin.ext (by simpa using a), Fin.ext (by simpa using b)⟩
    · exact Or.inr ⟨Fin.ext (by simpa using a), Fin.ext (by simpa using b)⟩
  rcases hpair with ⟨a, b⟩ | ⟨a, b⟩
  · rw [a, b]
  · rw [a, b, sup_comm]

/-- `maxAgg` satisfies the A3 diagonal commitment. CLOSED VIA `sup_idem`. -/
theorem maxAgg_A3 : ∀ c : NNReal, maxAgg (fun _ => c) = c := by
  intro c; simp [maxAgg]

/-- `maxAgg` is 1-homogeneous (A2). CLOSED VIA `NNReal.mul_sup` (multiplication distributes
    over `⊔` on `ℝ≥0`). -/
theorem maxAgg_A2 : ∀ (c : NNReal) (x : Axes 2),
    maxAgg (fun i => c * x i) = c * maxAgg x := by
  intro c x
  simp only [maxAgg]
  rw [mul_sup]

/-- **Decisive numeric witness:** `maxAgg` disagrees with `Λ 2` at `(4,1)`:
    `maxAgg (4,1) = 4` but `Λ 2 (4,1) = (4·1)^(1/2) = 2`. Hence `maxAgg ≠ Λ 2`, even though
    `maxAgg` satisfies A1–A5. This proves A1–A5 do NOT force the geometric mean. -/
theorem maxAgg_ne_Lambda : maxAgg ≠ Λ 2 := by
  intro h
  -- evaluate both sides at the vector (4, 1)
  have hx := congrArg (fun F => F (![4, 1] : Axes 2)) h
  simp only at hx
  -- LHS = 4 ⊔ 1 = 4
  have hL : maxAgg (![4, 1] : Axes 2) = 4 := by
    simp [maxAgg]
  -- RHS = (∏ (4,1))^(1/2) = 4^(1/2) = 2
  have hR : Λ 2 (![4, 1] : Axes 2) = 2 := by
    rw [Λ_def (by norm_num : 0 < 2)]
    -- ∏_{i:Fin 2} ![4,1] i = 4 * 1 = 4
    have hprod : (∏ i, (![4, 1] : Axes 2) i) = 4 := by
      simp [Fin.prod_univ_two]
    rw [hprod]
    -- goal: (4:ℝ≥0) ^ ((1:ℝ)/((2:ℕ):ℝ)) = 2.  Rewrite 4 = 2^2 and collapse the rpow.
    rw [show (4 : NNReal) = (2 : NNReal) ^ (2 : ℕ) by norm_num,
        ← NNReal.rpow_natCast (2 : NNReal) 2, ← NNReal.rpow_mul]
    -- exponent (2:ℝ) * ((1:ℝ)/((2:ℕ):ℝ)) = 1, then 2^(1:ℝ) = 2
    have hexp : ((2 : ℕ) : ℝ) * ((1 : ℝ) / ((2 : ℕ) : ℝ)) = 1 := by
      push_cast; ring
    rw [hexp, NNReal.rpow_one]
  rw [hL, hR] at hx
  -- 4 = 2 is false
  exact absurd hx (by norm_num)

/-! ## TERMINAL UNCONDITIONAL STATEMENT — HONEST open obligation (Λ stays Conjecture 1) -/

/-- **`lambda_unique` (UNCONDITIONAL).** `∀ Φ, LutarAxioms Φ → Φ = Λ k`.

    ⚠️ THIS STATEMENT IS FALSE UNDER A1–A5 AS FORMALIZED (see `maxAgg_ne_Lambda`). It is
    retained ONLY as the named tracking obligation for the Λ uniqueness conjecture. Its body
    is a single, clearly-tagged open obligation:

        FACTORIZATION_AXIOM_GAP
        — the missing step is the factorization `Φ x = ∏ xᵢ^αᵢ` (slice multiplicativity +
          separability), which is NOT derivable from A1–A5 (counterexample `maxAgg`, `min`).
        — closing it soundly requires a NEW axiom A6 = bisymmetry/associativity
          (Kolmogorov–Nagumo–Aczél; HLP §2.18). That is a founder/architecture decision and
          would change the structure, NOT something this round fabricates.
        — WITH A6 in place, this closes mechanically via `lambda_unique_of_factors`.

    Per HONESTY-OVER-CHECKLIST: no closed proof of a false statement is shipped. Λ remains
    **Conjecture 1**. -/
theorem lambda_unique {k : ℕ} (hk : 0 < k)
    (Φ : Aggregator k) (hL : LutarAxioms Φ) :
    Φ = Λ k := by
  -- FACTORIZATION_AXIOM_GAP — needs A6 bisymmetry; FALSE under A1–A5 (see maxAgg_ne_Lambda).
  -- Discharge route once A6 lands:
  --   obtain ⟨αs, hfac⟩ := factorization_from_A1_A6 hk Φ hL  -- requires A6
  --   exact lambda_unique_of_factors hk Φ hL αs hfac
  sorry

end Lutar.Round13

/-
## HONEST SORRY LEDGER (this file)
EXACTLY ONE open obligation: `lambda_unique` (unconditional), tagged FACTORIZATION_AXIOM_GAP /
needs A6 bisymmetry. This obligation is UNAVOIDABLE under A1–A5 — the statement is false
(maxAgg, min are counterexamples), so the honest action is to mark it, not fake it.

Everything else (`lambda_satisfiesAxioms_round13`, `lambda_unique_of_factors`, `maxAgg_*`,
`maxAgg_ne_Lambda`) is fully proved.

No new `axiom` tokens. axioms_unique stays 14. Λ stays Conjecture 1.

Signed-off-by: Λ-Closure Lead <lambda-closure@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
-/
