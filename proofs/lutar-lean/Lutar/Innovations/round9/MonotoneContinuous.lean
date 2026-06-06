/-
# Lutar/Innovations/round9/MonotoneContinuous.lean

## Step 3 of the Cauchy_ND uniqueness chain — the monotonicity → continuity bridge

The multiplicative Cauchy functional equation `f (s * t) = f s * f t` has wildly
discontinuous (Hamel-basis) solutions in general.  Monotonicity is the regularity
hypothesis that rules them out, so that the downstream
`multiplicative_monotone_isPow` (PhD Functional Analysis sibling) can force
`f t = t ^ α`.

### HONESTY NOTE — the *verbatim* PROOF_SPEC target is FALSE.

The task asked for:

    monotone_multiplicative_continuous {f : NNReal → NNReal}
      (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
      (hf_mono : Monotone f) :
      Continuous f
  (binder keyword elided so the corpus counter does not mistake this prose for a
   real declaration).

This statement is **false**, with an explicit counterexample (formalised below as
`monotone_multiplicative_not_continuous_everywhere`):

    f x := if x = 0 then 0 else 1

* `hf_mul` ✓ — NNReal has no zero divisors, so `s*t = 0 ↔ s = 0 ∨ t = 0`;
  both sides of the equation are `0` in that case and `1` otherwise.
* `hf_mono` ✓ — `f 0 = 0 ≤ 1 = f x` for `x ≠ 0`, constant `1` thereafter.
* `Continuous f` ✗ — `f` jumps from `0` to `1` at `0`
  (`lim_{x→0⁺} f x = 1 ≠ 0 = f 0`).

So the discontinuity at the single point `0` is genuinely *not* excluded by
multiplicativity + monotonicity.  (Note this `f` is NOT an `rpow`: `t ↦ t ^ (0:ℝ)`
is the constant `1`, since `NNReal` uses `0 ^ 0 = 1`.)

### What IS true, and what the Cauchy argument actually needs.

The rpow characterisation `f t = t ^ α` only constrains `f` on `t > 0`
(the value at `0` is pinned separately, by the A2 homogeneity / A3 normalisation
axioms of the parent proof, NOT by continuity).  We therefore prove the strongest
TRUE statements:

* `monotone_multiplicative_continuousAt_of_pos` :
      `b ≠ 0 → ContinuousAt f b`               -- continuity at every positive point
* `monotone_multiplicative_continuousAt_one` :
      `ContinuousAt f 1`                         -- the bootstrap anchor
* `monotone_multiplicative_continuousOn_Ioi` :
      `ContinuousOn f (Set.Ioi 0)`              -- continuity on the positive ray

These hand the Functional Analysis sibling everything it needs:
`multiplicative_monotone_isPow` derives `f t = t ^ α` for `t > 0` from continuity on
the positive ray (its log/exp bridge only ever evaluates `f` at `exp x > 0`).

### Proof architecture (fully discharged; no proof-deferred holes, no new `axiom`)

1. Degenerate branch `f 1 = 0`:  multiplicativity collapses `f` to the constant `0`,
   which is continuous.
2. Main branch `f 1 = 1`:
   a. `Monotone.countable_not_continuousAt` (Mathlib, needs `SecondCountableTopology`,
      which `ℝ≥0` has): the set of discontinuity points is countable.
   b. `ℝ≥0` is uncountable (we prove `¬ Countable ℝ≥0` via the injection
      `r ↦ Real.toNNReal (Real.exp r)` and `Cardinal.not_countable_real`), so a
      continuity point `a ≠ 0` exists.
   c. Transport along the homeomorphism `x ↦ c * x` (`Homeomorph.mulLeft₀`, valid since
      `ℝ≥0` is a `GroupWithZero` with continuous `*`):  with `c = b * a⁻¹` we have
      `c * a = b` and `f ∘ (c * ·) = fun x => f c * f x`, so continuity of `f` at `a`
      transports to continuity at `b` for every `b ≠ 0`.

### DOCTRINE
- Λ stays **Conjecture 1**.  This file proves only a Step-3 supporting bridge and lives
  in `Lutar/Innovations/round9/`, OUTSIDE the LOCKED 749/14/163 kernel.
- No new `axiom`s; every obligation is discharged (no proof-deferred holes).
- The false verbatim target is recorded as a refuted statement, not silently dropped.

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
-/
import Mathlib.Topology.Order.LeftRightLim
import Mathlib.Topology.Algebra.GroupWithZero
import Mathlib.Topology.Instances.NNReal
import Mathlib.Data.Real.Cardinality

namespace Lutar.Innovations.Round9.MonotoneContinuous

open Set Filter Topology

/-! ### `ℝ≥0` is uncountable -/

/-- `ℝ≥0` is uncountable: the map `r ↦ Real.toNNReal (Real.exp r)` is an injection
    of `ℝ` (which is uncountable, `Cardinal.not_countable_real`) into `ℝ≥0`. -/
theorem not_countable_nnreal : ¬ Countable NNReal := by
  intro hcnt
  -- The injection ℝ ↪ ℝ≥0.
  have hinj : Function.Injective (fun r : ℝ => Real.toNNReal (Real.exp r)) := by
    intro a b hab
    have : Real.exp a = Real.exp b := by
      have h1 : (0 : ℝ) ≤ Real.exp a := (Real.exp_pos a).le
      have h2 : (0 : ℝ) ≤ Real.exp b := (Real.exp_pos b).le
      have := congrArg (fun x : NNReal => (x : ℝ)) hab
      simpa [Real.coe_toNNReal _ h1, Real.coe_toNNReal _ h2] using this
    exact Real.exp_injective this
  -- An injection into a countable type makes the source countable.
  have : Countable ℝ := hinj.countable
  exact Cardinal.not_countable_real (Set.countable_univ_iff.2 this)

/-! ### The refuted verbatim target -/

/-- **The PROOF_SPEC target is false.**  There is a monotone, multiplicative
    `f : ℝ≥0 → ℝ≥0` that is NOT continuous (it jumps at `0`).  This justifies
    proving the positive-ray statements below instead of `Continuous f`. -/
theorem monotone_multiplicative_not_continuous_everywhere :
    ∃ f : NNReal → NNReal,
      (∀ s t : NNReal, f (s * t) = f s * f t) ∧ Monotone f ∧ ¬ Continuous f := by
  refine ⟨fun x => if x = 0 then 0 else 1, ?_, ?_, ?_⟩
  · -- multiplicativity
    intro s t
    by_cases hs : s = 0
    · subst hs; simp
    · by_cases ht : t = 0
      · subst ht; simp
      · have hst : s * t ≠ 0 := mul_ne_zero hs ht
        simp [hs, ht, hst]
  · -- monotonicity
    intro x y hxy
    by_cases hx : x = 0
    · subst hx; simp
    · have hy : y ≠ 0 := by
        rintro rfl
        exact hx (le_antisymm hxy (zero_le _))
      simp [hx, hy]
  · -- discontinuity at 0
    intro hcont
    have hca : ContinuousAt (fun x : NNReal => if x = 0 then (0:NNReal) else 1) 0 :=
      hcont.continuousAt
    -- The right-hand neighbourhood of 0 in ℝ≥0 maps to the constant `1`, but `f 0 = 0`.
    have h0 : (fun x : NNReal => if x = 0 then (0:NNReal) else 1) 0 = 0 := by simp
    -- Use the filter `𝓝[>] 0`, which is nontrivial (NoMaxOrder ⇒ NeBot), to derive a contradiction.
    have htend : Filter.Tendsto
        (fun x : NNReal => if x = 0 then (0:NNReal) else 1) (𝓝[>] 0) (𝓝 (0:NNReal)) := by
      have := hca.continuousWithinAt (s := Ioi 0)
      simpa [h0] using this.tendsto
    -- On `Ioi 0` the function is constantly `1`, so the limit must be `1`.
    have hev : (fun x : NNReal => if x = 0 then (0:NNReal) else 1)
        =ᶠ[𝓝[>] 0] (fun _ => (1:NNReal)) := by
      filter_upwards [self_mem_nhdsWithin] with x hx
      have : x ≠ 0 := ne_of_gt hx
      simp [this]
    have hconst : Filter.Tendsto
        (fun x : NNReal => if x = 0 then (0:NNReal) else 1) (𝓝[>] 0) (𝓝 (1:NNReal)) :=
      (Filter.Tendsto.congr' hev.symm tendsto_const_nhds)
    have := tendsto_nhds_unique htend hconst
    exact (by norm_num : (0:NNReal) ≠ 1) this

/-! ### The true bridge: continuity at every positive point -/

variable {f : NNReal → NNReal}

/-- **Continuity at every positive point.**  A monotone multiplicative
    `f : ℝ≥0 → ℝ≥0` is continuous at every `b ≠ 0`. -/
theorem monotone_multiplicative_continuousAt_of_pos
    (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
    (hf_mono : Monotone f) {b : NNReal} (hb : b ≠ 0) :
    ContinuousAt f b := by
  -- Degenerate case f 1 = 0 ⟹ f ≡ 0.
  by_cases h1 : f 1 = 0
  · have hconst : ∀ x : NNReal, f x = 0 := by
      intro x
      have := hf_mul x 1
      simpa [h1] using this
    have : f = fun _ => (0 : NNReal) := funext hconst
    rw [this]; exact continuousAt_const
  -- Main case.  First obtain a continuity point a ≠ 0.
  · -- The discontinuity set is countable.
    have hcount : (Set.Countable {x : NNReal | ¬ ContinuousAt f x}) :=
      hf_mono.countable_not_continuousAt
    -- If every continuity point were 0, then {x ≠ 0} ⊆ discontinuity set,
    -- forcing ℝ≥0 countable — contradiction.
    have hexists : ∃ a : NNReal, a ≠ 0 ∧ ContinuousAt f a := by
      by_contra hno
      push_neg at hno
      -- hno : ∀ a, a ≠ 0 → ¬ ContinuousAt f a
      have hsub : {x : NNReal | x ≠ 0} ⊆ {x : NNReal | ¬ ContinuousAt f x} := by
        intro x hx; exact hno x hx
      have hne_count : (Set.Countable {x : NNReal | x ≠ 0}) := hcount.mono hsub
      -- Then univ = {0} ∪ {x ≠ 0} is countable, so ℝ≥0 is countable.
      have huniv : (Set.univ : Set NNReal).Countable := by
        have h0 : (Set.univ : Set NNReal) = {(0:NNReal)} ∪ {x : NNReal | x ≠ 0} := by
          ext x; by_cases hx : x = 0 <;> simp [hx]
        rw [h0]
        exact (Set.countable_singleton _).union hne_count
      exact not_countable_nnreal (Set.countable_univ_iff.1 huniv)
    obtain ⟨a, ha0, hca⟩ := hexists
    -- Transport continuity from a to b via the homeomorphism x ↦ c * x, c = b * a⁻¹.
    have hc0 : b * a⁻¹ ≠ 0 := mul_ne_zero hb (inv_ne_zero ha0)
    -- `c * a = b`.
    have hca_eq : (b * a⁻¹) * a = b := inv_mul_cancel_right₀ ha0 b
    -- `f c * f (·)` is continuous at `a`  (product of a constant and `f`).
    have hca' : ContinuousAt (fun x => f (b * a⁻¹) * f x) a := continuousAt_const.mul hca
    -- This equals `f ∘ (mulLeft₀ c)` pointwise, by multiplicativity.
    have hcomp : (f ∘ (Homeomorph.mulLeft₀ (b * a⁻¹) hc0)) = fun x => f (b * a⁻¹) * f x := by
      funext x
      simp only [Function.comp_apply, Homeomorph.coe_mulLeft₀]
      exact hf_mul (b * a⁻¹) x
    have hcomp_cont : ContinuousAt (f ∘ (Homeomorph.mulLeft₀ (b * a⁻¹) hc0)) a := by
      rw [hcomp]; exact hca'
    -- Transport across the homeomorphism: ContinuousAt (f ∘ h) a ↔ ContinuousAt f (h a).
    have hbcont : ContinuousAt f ((Homeomorph.mulLeft₀ (b * a⁻¹) hc0) a) :=
      ((Homeomorph.mulLeft₀ (b * a⁻¹) hc0).comp_continuousAt_iff' f a).1 hcomp_cont
    -- `h a = c * a = b`.
    have : (Homeomorph.mulLeft₀ (b * a⁻¹) hc0) a = b := by
      simp only [Homeomorph.coe_mulLeft₀]; exact hca_eq
    rwa [this] at hbcont

/-- **Continuity at `1`** — the bootstrap anchor used by the Cauchy lemma. -/
theorem monotone_multiplicative_continuousAt_one
    (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
    (hf_mono : Monotone f) :
    ContinuousAt f 1 :=
  monotone_multiplicative_continuousAt_of_pos hf_mul hf_mono (one_ne_zero)

/-- **Continuity on the positive ray** `(0, ∞)` — the regularity the
    `multiplicative_monotone_isPow` bridge consumes (its log/exp change of
    variables only ever evaluates `f` at strictly positive arguments). -/
theorem monotone_multiplicative_continuousOn_Ioi
    (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
    (hf_mono : Monotone f) :
    ContinuousOn f (Set.Ioi 0) := by
  intro x hx
  have hx0 : x ≠ 0 := ne_of_gt hx
  exact (monotone_multiplicative_continuousAt_of_pos hf_mul hf_mono hx0).continuousWithinAt

end Lutar.Innovations.Round9.MonotoneContinuous
