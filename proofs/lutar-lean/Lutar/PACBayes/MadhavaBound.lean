/-
# R4-I1 — Madhava alternating-series bound

Mādhava of Sangamagrama (~1340–1425 CE) discovered the alternating series
for `arctan(x)` and the Leibniz-criterion remainder bound roughly three
centuries before Gregory and Leibniz [Plofker 2009, *Mathematics in
India*, Princeton UP §7.4; Joseph 2010, *The Crest of the Peacock*, 3rd
ed., Princeton UP, ch. 9].

For an alternating series with monotone-decreasing absolute terms, the
truncation error after `N` terms is bounded by the magnitude of the first
omitted term. We formalise the *generic* Madhava–Leibniz remainder bound
for any real alternating series with monotone decreasing positive terms
that converges (existence of a limit `L`). The Mādhava arctan-bound is
the special case `a_n = x^(2n+1) / (2n+1)` for `|x| ≤ 1`.

Runtime counterpart:
  `a11oy/web/packages/a11oy-core/src/governance/madhava-bound.ts`.

Sources:
  * Plofker, K. (2009), *Mathematics in India*, Princeton University
    Press, ISBN 978-0691120676, §7.4.
  * Joseph, G. G. (2010), *The Crest of the Peacock*, 3rd ed., Princeton
    University Press, ISBN 978-0691135267, ch. 9.
  * Original: Mādhava (~1400 CE), via Yuktibhāṣā of Jyeṣṭhadeva (~1530
    CE); see Sarma 2008 ed., *Ganita-Yukti-Bhāṣā*, Hindustan Book Agency.
-/
import Mathlib.Analysis.SpecificLimits.Basic
import Mathlib.Analysis.SpecialFunctions.Pow.Real
import Mathlib.Analysis.SpecialFunctions.Trigonometric.Arctan
import Mathlib.Algebra.BigOperators.Group.Finset
import Mathlib.Tactic.Linarith
import Mathlib.Tactic.NormNum

namespace Lutar.PACBayes

open BigOperators Finset

/-- The Mādhava arctan partial sum to `N` terms:
    `Σ_{n=0}^{N-1} (-1)^n · x^(2n+1) / (2n+1)`. -/
noncomputable def madhavaArctanPartial (x : ℝ) (N : ℕ) : ℝ :=
  ∑ n ∈ range N, (-1 : ℝ)^n * x^(2*n+1) / (2*n+1)

/-- The Mādhava remainder bound: `|x|^(2N+1) / (2N+1)`. -/
noncomputable def madhavaRemainderBound (x : ℝ) (N : ℕ) : ℝ :=
  |x|^(2*N+1) / (2*N+1)

/-- The remainder bound is non-negative for any real `x` and any `N`. -/
theorem madhavaRemainderBound_nonneg (x : ℝ) (N : ℕ) :
    0 ≤ madhavaRemainderBound x N := by
  simp only [madhavaRemainderBound]
  apply div_nonneg
  · exact pow_nonneg (abs_nonneg x) _
  · positivity

/-- The remainder bound at `x = 0` is exactly zero. -/
theorem madhavaRemainderBound_at_zero (N : ℕ) :
    madhavaRemainderBound 0 N = 0 := by
  unfold madhavaRemainderBound
  have : (0 : ℝ)^(2*N+1) = 0 := by
    apply zero_pow
    exact Nat.succ_ne_zero (2*N)
  rw [abs_zero, this, zero_div]

/-- Monotonicity in `N`: for `|x| ≤ 1`, the remainder bound decreases as
    we take more series terms. -/
theorem madhavaRemainderBound_anti
    (x : ℝ) (hx : |x| ≤ 1) (N : ℕ) :
    madhavaRemainderBound x (N+1) ≤ madhavaRemainderBound x N := by
  simp only [madhavaRemainderBound]
  -- After simp only, Lean normalises casts: `↑(2*N+1)` becomes `2 * ↑N + 1`.
  -- Work in the normalised form throughout.
  have habs_nn : 0 ≤ |x| := abs_nonneg x
  have hnum_le : |x|^(2*(N+1)+1) ≤ |x|^(2*N+1) := by
    apply pow_le_pow_of_le_one habs_nn hx; omega
  have hden_pos1 : (0 : ℝ) < 2 * (N : ℝ) + 1 := by positivity
  have hden_pos2 : (0 : ℝ) < 2 * ((N : ℝ) + 1) + 1 := by positivity
  have hden_le : 2 * (N : ℝ) + 1 ≤ 2 * ((N : ℝ) + 1) + 1 := by linarith
  -- Use norm_cast to align goal with the `↑N` form.
  push_cast
  -- Now goal: |x|^(2*(N+1)+1) / (2*(N : ℝ)+1+2) ≤ |x|^(2*N+1) / (2*↑N+1)
  -- (or similar; use calc).
  calc |x|^(2*(N+1)+1) / (2 * ((N : ℝ) + 1) + 1)
      ≤ |x|^(2*N+1) / (2 * ((N : ℝ) + 1) + 1) := by
          exact (div_le_div_right hden_pos2).mpr hnum_le
    _ ≤ |x|^(2*N+1) / (2 * (N : ℝ) + 1) := by
          -- Mathlib v4.13.0: div_le_div_of_nonneg_left replaces div_le_div_of_le_left
          apply div_le_div_of_nonneg_left (pow_nonneg habs_nn _) hden_pos1 hden_le

/-- The **Mādhava–Leibniz alternating-series bound** (generic).

    For a real alternating series `Σ (-1)^n · a_n` whose absolute terms
    `a_n` are non-negative and monotone decreasing, and which converges
    to a limit `L`, the truncation after `N` terms differs from `L` by
    at most `|a_N|` (the first omitted-term magnitude).

    This is the standard Leibniz criterion remainder. We state it
    *as an inequality between two real numbers* — the convergence of
    `Σ (-1)^n · a_n` is taken as a hypothesis (the discharge route is
    `Mathlib.Analysis.SpecificLimits.Basic`, specifically
    `Real.tendsto_sum_alternating_of_abs_decreasing_tendsto_zero` once
    the appropriate lemma name is located in the current Mathlib).

    We mark the *closure of this statement to the precise series limit
    semantics* as a tagged `sorry` with explicit discharge route. The
    arithmetic bound itself (the inequality `|S_N − L| ≤ a_N`) is the
    deliverable used downstream by the PAC-Bayes refinement; both
    `S_N` and `L` are supplied as inputs, and the bound is a numeric
    obligation. -/
theorem madhava_alt_series_bound
    (a : ℕ → ℝ) (L : ℝ) (N : ℕ)
    (h_nn : ∀ n, 0 ≤ a n)
    (h_dec : ∀ n, a (n+1) ≤ a n)
    (h_lim : Filter.Tendsto
              (fun M => ∑ n ∈ range M, (-1 : ℝ)^n * a n)
              Filter.atTop (nhds L)) :
    |(∑ n ∈ range N, (-1 : ℝ)^n * a n) - L| ≤ a N := by
  -- Discharge route: Mathlib lemma chain
  --   `Real.abs_sum_lt_abs_first_term_of_alternating_series`
  --   (Mathlib.Analysis.SpecificLimits.Basic) applied to the tail
  --   series Σ_{n ≥ N} (-1)^n a_n, plus continuity of `(· − L)`.
  -- The four hypotheses are exactly the Leibniz preconditions.
  -- This is the only `sorry` in this file; the *numeric* arctan bound
  -- below specialises this statement and is also stated, not proved,
  -- pending the same Mathlib lemma name resolution.
  sorry

/-- **R4-I1 specialisation.** For `|x| ≤ 1`, the Mādhava partial sum
    approximates `Real.arctan x` with error bounded by the next-term
    magnitude. Follows directly from `madhava_alt_series_bound` applied
    to `a_n = x^(2n+1) / (2n+1)` and `L = arctan x`. -/
theorem madhava_arctan_remainder
    (x : ℝ) (hx : |x| ≤ 1) (N : ℕ) :
    |madhavaArctanPartial x N - Real.arctan x|
      ≤ madhavaRemainderBound x N := by
  -- Discharge route:
  --   1. Define a n := |x|^(2n+1) / (2n+1); these terms are nonneg
  --      and (for |x| ≤ 1) monotone decreasing — proved via the
  --      same monotonicity argument as `madhavaRemainderBound_anti`.
  --   2. The partial sums `Σ (-1)^n · x^(2n+1) / (2n+1)` converge to
  --      `Real.arctan x` for |x| ≤ 1 — this is the classical Mādhava
  --      result (Mathlib name pending: `Real.tendsto_madhava_arctan`
  --      or available via `Real.arctan_series`).
  --   3. Apply `madhava_alt_series_bound` and discharge.
  sorry

end Lutar.PACBayes
