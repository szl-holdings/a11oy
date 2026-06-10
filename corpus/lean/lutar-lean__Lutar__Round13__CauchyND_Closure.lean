/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 13 — Cauchy_ND closure layer (the genuinely-closable sub-lemmas)

This file discharges, as **real fully-proved theorems** (no open obligations), the three mechanically-closable
links of the Cauchy_ND uniqueness chain (see `team/lambda-closure/SORRY_AUDIT.md`):

* `monotone_additive_linear`        — Aczél 1966 Thm 5.1 / Cauchy 1821, via the **rational
                                       squeeze** (NO continuity assumed). Closes the
                                       `Uniqueness.lean` S-MAIN-1 open obligation.
* `multiplicative_monotone_isPow_pos` — multiplicative + monotone ⇒ power law on the
                                       POSITIVES, via the log/exp bridge. (`t ≠ 0` form, the
                                       one the Lutar slice actually needs.)
* the symmetric back-half (`prod_rpow_const_eq_rpow_sum`, `rpow_left_inj_one_lt`,
  `sum_alphas_eq_one`, `alphas_eq_of_symmetric`, `exponents_equal_inv_k_of_symm`) —
  pins each axis exponent to `1/k` GIVEN the factorization, using A5.

These bodies are transcribed from the team's CI-validated proofs in PR #173
(`CauchyMultMono.lean`) and PR #174 (`ExponentsSymmetric.lean`), re-homed here so Round 13
is self-contained and does not depend on unmerged branches.

## HONESTY NOTE (decisive — read SORRY_AUDIT §4)
Every lemma below that pins exponents takes the factorization `Φ x = ∏ xᵢ ^ αᵢ` as a
HYPOTHESIS. Deriving that factorization from the bare axioms A1–A5 is the load-bearing
analytic content of the n-dimensional theorem and is **NOT** provable: `Φ = max` and
`Φ = min` satisfy A1–A5 but are not the geometric mean (see
`Lutar/Round13/Lambda_Uniqueness.lean`). The honest unconditional open obligation lives there, tagged
to the missing **A6 bisymmetry/associativity axiom**. Nothing here fakes that gap.

## DOCTRINE
- Λ stays **Conjecture 1**. This file lives under `Lutar/Round13/`; it does NOT flip any
  public claim and does NOT upgrade the internal `Conjecture` declaration.
- No new `axiom` tokens are introduced (axioms_unique stays 14).
- DCO trailers on the commit; doctrine footer below.

## References
- Aczél, J. (1966). *Lectures on Functional Equations.* Academic Press. Thm 5.1.
- Cauchy, A.-L. (1821). *Cours d'analyse.* Chap. V §1.
- Hardy, G.H., Littlewood, J.E., Pólya, G. (1934). *Inequalities.* Cambridge UP. §2.18.
- Catoni, O. (2007). *PAC-Bayesian Supervised Classification.* IMS Lecture Notes 56.
- Mathlib v4.13.0: `Real.rpow_le_rpow_left_iff`, `Real.log_rpow`, `Real.exp_log`,
  `NNReal.rpow_add`, `Equiv.swap_apply_*`, `exists_rat_btwn`.

Signed-off-by: Λ-Closure Lead <lambda-closure@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
-/
import Lutar.Axioms
import Lutar.Invariant
import Mathlib.Analysis.SpecialFunctions.Pow.NNReal
import Mathlib.Analysis.SpecialFunctions.Log.Basic
import Mathlib.Analysis.SpecialFunctions.Exp
import Mathlib.Algebra.BigOperators.Fin
import Mathlib.Algebra.BigOperators.Group.Finset.Basic
import Mathlib.Algebra.BigOperators.Group.Finset.Defs
import Mathlib.Algebra.BigOperators.Group.Finset.Pi
import Mathlib.Algebra.BigOperators.Group.Finset.Powerset
import Mathlib.Algebra.BigOperators.Group.Finset.Preimage
import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Topology.Algebra.Order.Archimedean

namespace Lutar.Round13

open NNReal Real BigOperators

/-! ## Layer 1 — monotone additive ⟹ linear (rational squeeze; CLOSED VIA exists_rat_btwn) -/

/-- **`monotone_additive_linear`.** A monotone additive `g : ℝ → ℝ` is linear:
    `g t = g 1 * t`.  CLOSED VIA the rational-squeeze argument (no continuity).
    (Transcribed from PR #173 `CauchyMultMono.monotone_additive_linear`.) -/
theorem monotone_additive_linear
    (g : ℝ → ℝ)
    (hg_add : ∀ u v : ℝ, g (u + v) = g u + g v)
    (hg_mono : Monotone g) :
    ∀ t : ℝ, g t = g 1 * t := by
  have hg0 : g 0 = 0 := by
    have := hg_add 0 0; simp at this; linarith
  have hg_nat : ∀ n : ℕ, g n = n * g 1 := by
    intro n; induction n with
    | zero => simp [hg0]
    | succ n ih =>
        rw [show (↑(n + 1) : ℝ) = ↑n + 1 by push_cast; ring, hg_add, ih]
        push_cast; ring
  have hg_nat_mul : ∀ (n : ℕ) (x : ℝ), g (n * x) = n * g x := by
    intro n x; induction n with
    | zero => simp [hg0]
    | succ n ih =>
        rw [show (↑(n + 1) : ℝ) * x = ↑n * x + x by push_cast; ring, hg_add, ih]
        push_cast; ring
  have hg_int : ∀ n : ℤ, g n = n * g 1 := by
    intro n; rcases n with n | n
    · push_cast; exact hg_nat n
    · push_cast
      have hgneg : g (-(↑(n + 1) : ℝ)) = -(g ↑(n + 1)) := by
        have h := hg_add (↑(n + 1) : ℝ) (-(↑(n + 1) : ℝ))
        rw [add_neg_cancel, hg0] at h
        linarith
      rw [show -(↑n + 1 : ℝ) = -(↑(n + 1) : ℝ) by push_cast; ring,
          hgneg, hg_nat (n + 1)]
      push_cast; ring
  have hg_rat : ∀ q : ℚ, g (q : ℝ) = g 1 * q := by
    intro q
    have hqpos : (0 : ℝ) < q.den := by exact_mod_cast q.pos
    have key : (q.den : ℝ) * g ((q.num : ℝ) / q.den) = (q.num : ℝ) * g 1 := by
      rw [← hg_nat_mul q.den ((q.num : ℝ) / q.den), mul_div_cancel₀ _ hqpos.ne']
      exact hg_int q.num
    have hsol : g ((q.num : ℝ) / q.den) = g 1 * ((q.num : ℝ) / q.den) := by
      have h : g ((q.num : ℝ) / q.den) * (q.den : ℝ) = (q.num : ℝ) * g 1 := by
        rw [mul_comm]; exact key
      have he := (eq_div_iff hqpos.ne').mpr h
      rw [he]; ring
    rw [Rat.cast_def]
    exact hsol
  have hc_nonneg : 0 ≤ g 1 := by have := hg_mono (by norm_num : (0:ℝ) ≤ 1); rwa [hg0] at this
  intro t
  refine le_antisymm ?_ ?_
  · by_contra hlt
    push_neg at hlt
    rcases eq_or_lt_of_le hc_nonneg with hc0 | hcpos
    · obtain ⟨b, hb⟩ := exists_rat_gt t
      have hle : g t ≤ g (b : ℝ) := hg_mono (le_of_lt hb)
      rw [hg_rat b, ← hc0, zero_mul] at hle
      rw [← hc0, zero_mul] at hlt
      linarith
    · have hbnd : t < g t / g 1 := by rw [lt_div_iff₀' hcpos]; linarith [hlt]
      obtain ⟨b, hb1, hb2⟩ := exists_rat_btwn hbnd
      have hmono : g t ≤ g (b : ℝ) := hg_mono (le_of_lt hb1)
      rw [hg_rat b] at hmono
      have hcb : g 1 * (b : ℝ) < g t := (lt_div_iff₀' hcpos).mp hb2
      linarith [hmono, hcb]
  · by_contra hlt
    push_neg at hlt
    rcases eq_or_lt_of_le hc_nonneg with hc0 | hcpos
    · obtain ⟨a, ha⟩ := exists_rat_lt t
      have hle : g (a : ℝ) ≤ g t := hg_mono (le_of_lt ha)
      rw [hg_rat a, ← hc0, zero_mul] at hle
      rw [← hc0, zero_mul] at hlt
      linarith
    · have hbnd : g t / g 1 < t := by rw [div_lt_iff₀' hcpos]; linarith [hlt]
      obtain ⟨a, ha1, ha2⟩ := exists_rat_btwn hbnd
      have hmono : g (a : ℝ) ≤ g t := hg_mono (le_of_lt ha2)
      rw [hg_rat a] at hmono
      have hca : g t < g 1 * (a : ℝ) := (div_lt_iff₀' hcpos).mp ha1
      linarith [hmono, hca]

/-! ## Layer 2 — multiplicative + monotone ⟹ power law on positives -/

/-- `1 ≤ f s` for `1 ≤ s`. (PR #173 `one_le_f_of_one_le`.) -/
theorem one_le_f_of_one_le {f : NNReal → NNReal}
    (hf_mono : Monotone f) (hf_one : f 1 = 1) {s : NNReal} (hs : 1 ≤ s) :
    1 ≤ f s := by
  calc (1 : NNReal) = f 1 := hf_one.symm
    _ ≤ f s := hf_mono hs

/-- **Strict positivity on positives.** (PR #173 `f_ne_zero_of_ne_zero`.) -/
theorem f_ne_zero_of_ne_zero {f : NNReal → NNReal}
    (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
    (_hf_mono : Monotone f) (hf_one : f 1 = 1) {t : NNReal} (ht : t ≠ 0) :
    f t ≠ 0 := by
  intro hft
  have hts : t * t⁻¹ = 1 := mul_inv_cancel₀ ht
  have : f 1 = f t * f t⁻¹ := by rw [← hts, hf_mul]
  rw [hf_one, hft] at this
  simp at this

/-- **`multiplicative_monotone_isPow_pos`. SORRY-FREE.**
    Monotone multiplicative `f : ℝ≥0 → ℝ≥0` with `f 1 = 1` is a power function on the
    positives: `∃ α, ∀ t ≠ 0, f t = t ^ (α:ℝ)`.  CLOSED VIA the log/exp bridge to the
    additive Cauchy equation. (PR #173 `multiplicative_monotone_isPow_pos`.) -/
theorem multiplicative_monotone_isPow_pos {f : NNReal → NNReal}
    (hf_mul : ∀ s t : NNReal, f (s * t) = f s * f t)
    (hf_mono : Monotone f)
    (hf_one : f 1 = 1) :
    ∃ α : NNReal, ∀ t : NNReal, t ≠ 0 → f t = t ^ (α : ℝ) := by
  have hpos : ∀ x : ℝ, (0 : ℝ) < (f (Real.toNNReal (Real.exp x)) : ℝ) := by
    intro x
    have hexp_pos : (0 : NNReal) < Real.toNNReal (Real.exp x) := by
      rw [Real.toNNReal_pos]; exact Real.exp_pos x
    have hne : Real.toNNReal (Real.exp x) ≠ 0 := ne_of_gt hexp_pos
    have := f_ne_zero_of_ne_zero hf_mul hf_mono hf_one hne
    exact (NNReal.coe_pos.mpr (pos_iff_ne_zero.mpr this))
  set g : ℝ → ℝ := fun x => Real.log (f (Real.toNNReal (Real.exp x))) with hg_def
  have hg_add : ∀ u v : ℝ, g (u + v) = g u + g v := by
    intro u v
    have hexp : Real.toNNReal (Real.exp (u + v))
        = Real.toNNReal (Real.exp u) * Real.toNNReal (Real.exp v) := by
      rw [Real.exp_add, ← Real.toNNReal_mul (le_of_lt (Real.exp_pos u))]
    simp only [hg_def, hexp, hf_mul, NNReal.coe_mul]
    rw [Real.log_mul (ne_of_gt (hpos u)) (ne_of_gt (hpos v))]
  have hg_mono : Monotone g := by
    intro x y hxy
    simp only [hg_def]
    apply Real.log_le_log (hpos x)
    apply NNReal.coe_le_coe.mpr
    apply hf_mono
    exact Real.toNNReal_le_toNNReal (Real.exp_le_exp.mpr hxy)
  have hg_lin : ∀ x : ℝ, g x = g 1 * x := monotone_additive_linear g hg_add hg_mono
  set α : ℝ := g 1 with hα_def
  have hα_nonneg : 0 ≤ α := by
    have h0 : g 0 = 0 := by have := hg_add 0 0; simp at this; linarith
    have hmono01 := hg_mono (by norm_num : (0:ℝ) ≤ 1)
    rw [h0] at hmono01
    rw [hα_def]; exact hmono01
  refine ⟨⟨α, hα_nonneg⟩, ?_⟩
  intro s hs
  show f s = s ^ α
  have hsR : (0 : ℝ) < (s : ℝ) := NNReal.coe_pos.mpr (pos_iff_ne_zero.mpr hs)
  have hexp_log : Real.toNNReal (Real.exp (Real.log (s : ℝ))) = s := by
    rw [Real.exp_log hsR, Real.toNNReal_coe]
  have hg_at : g (Real.log (s : ℝ)) = Real.log (f s) := by
    simp only [hg_def, hexp_log]
  have hlin : Real.log (f s) = α * Real.log (s : ℝ) := by
    rw [← hg_at, hg_lin (Real.log (s : ℝ))]
  have hfpos : (0 : ℝ) < (f s : ℝ) := by
    have hne := f_ne_zero_of_ne_zero hf_mul hf_mono hf_one hs
    exact NNReal.coe_pos.mpr (pos_iff_ne_zero.mpr hne)
  have hrpow : Real.log (((s ^ α : NNReal)) : ℝ) = α * Real.log (s : ℝ) := by
    rw [NNReal.coe_rpow, Real.log_rpow hsR]
  have hlogeq : Real.log (f s) = Real.log (((s ^ α : NNReal)) : ℝ) := by
    rw [hlin, hrpow]
  have hcoe : ((f s : ℝ)) = (((s ^ α : NNReal)) : ℝ) := by
    have hrp_pos : (0 : ℝ) < (((s ^ α : NNReal)) : ℝ) := by
      rw [NNReal.coe_rpow]; exact Real.rpow_pos_of_pos hsR α
    have e1 := Real.exp_log hfpos
    have e2 := Real.exp_log hrp_pos
    rw [← e1, ← e2, hlogeq]
  exact NNReal.coe_injective hcoe

/-! ## Layer 3 — symmetric back-half: exponents pinned to 1/k (GIVEN the factorization) -/

/-- Symmetry / anonymity predicate (= canonical A5 `IsPermutationInvariant`, spelled
    pointwise). (PR #174 `IsSymmetric`.) -/
def IsSymmetric {k : ℕ} (Lambda_fn : Aggregator k) : Prop :=
  ∀ (σ : Equiv.Perm (Fin k)) (x : Axes k), Lambda_fn (fun i => x (σ i)) = Lambda_fn x

/-- The A5 ⇔ symmetry bridge. CLOSED VIA definitional unfolding. (PR #174.) -/
theorem isSymmetric_iff_permInvariant {k : ℕ} (Lambda_fn : Aggregator k) :
    IsSymmetric Lambda_fn ↔
      (∀ (x : Axes k) (σ : Equiv.Perm (Fin k)),
        Lambda_fn (x ∘ (σ : Fin k → Fin k)) = Lambda_fn x) := by
  constructor
  · intro h x σ; exact h σ x
  · intro h σ x; exact h x σ

/-- The canonical A5 field implies `IsSymmetric`. (NEW bridge — closes the #174
    `SYMMETRY_AXIOM_GAP` now that A5 is a `LutarAxioms` field on `main`.) -/
theorem isSymmetric_of_A5 {k : ℕ} {Lambda_fn : Aggregator k}
    (h5 : IsPermutationInvariant Lambda_fn) : IsSymmetric Lambda_fn := by
  intro σ x
  -- `IsPermutationInvariant`: ∀ x σ, Λ (x ∘ σ) = Λ x ; and `x ∘ σ = fun i => x (σ i)`.
  exact h5 x σ

/-- `∏ i, c ^ (f i) = c ^ (∑ i, f i)` for a fixed nonzero base. CLOSED VIA `NNReal.rpow_add`.
    (PR #174 `prod_rpow_const_eq_rpow_sum`.) -/
theorem prod_rpow_const_eq_rpow_sum {ι : Type*} (s : Finset ι) {c : NNReal}
    (hc : c ≠ 0) (f : ι → ℝ) :
    (∏ i ∈ s, c ^ (f i)) = c ^ (∑ i ∈ s, f i) := by
  classical
  induction s using Finset.induction_on with
  | empty => simp
  | @insert a t ha ih =>
      rw [Finset.prod_insert ha, Finset.sum_insert ha, ih, NNReal.rpow_add hc]

/-- For a fixed base `c > 1`, `a ↦ c ^ a` is injective in the real exponent.
    CLOSED VIA `Real.rpow_le_rpow_left_iff`. (PR #174 `rpow_left_inj_one_lt`.) -/
theorem rpow_left_inj_one_lt {c : NNReal} (hc : 1 < c) {a b : ℝ}
    (h : c ^ a = c ^ b) : a = b := by
  have hcoe : (c : ℝ) ^ a = (c : ℝ) ^ b := by
    have := congrArg (fun t : NNReal => (t : ℝ)) h
    simpa only [NNReal.coe_rpow] using this
  have hc' : (1 : ℝ) < (c : ℝ) := by exact_mod_cast hc
  have hle : a ≤ b := (Real.rpow_le_rpow_left_iff hc').mp (le_of_eq hcoe)
  have hge : b ≤ a := (Real.rpow_le_rpow_left_iff hc').mp (le_of_eq hcoe.symm)
  exact le_antisymm hle hge

/-- **`sum_alphas_eq_one`** (UNCONDITIONAL given the factorization). CLOSED VIA A3 + the
    rpow-collapse. (PR #174.) -/
theorem sum_alphas_eq_one {k : ℕ}
    (Lambda_fn : Aggregator k)
    (hL : LutarAxioms Lambda_fn)
    (alphas : Fin k → NNReal)
    (h_factor : ∀ x : Axes k, Lambda_fn x = ∏ i, (x i) ^ (alphas i : ℝ)) :
    (∑ i, (alphas i : ℝ)) = 1 := by
  set c : NNReal := 2 with hc_def
  have hc0 : c ≠ 0 := by rw [hc_def]; norm_num
  have hdiag : Lambda_fn (fun _ => c) = c := hL.A3.A3_normalize c
  have hfac : Lambda_fn (fun _ => c) = ∏ i, c ^ (alphas i : ℝ) := h_factor (fun _ => c)
  have hkey : c = ∏ i, c ^ (alphas i : ℝ) := by rw [← hfac, hdiag]
  have hcollapse : (∏ i, c ^ (alphas i : ℝ)) = c ^ (∑ i, (alphas i : ℝ)) :=
    prod_rpow_const_eq_rpow_sum (Finset.univ) hc0 (fun i => (alphas i : ℝ))
  have heq : c ^ (1 : ℝ) = c ^ (∑ i, (alphas i : ℝ)) := by
    rw [NNReal.rpow_one, ← hcollapse, ← hkey]
  have h1c : (1 : NNReal) < c := by rw [hc_def]; norm_num
  exact (rpow_left_inj_one_lt h1c heq).symm

/-- **`alphas_eq_of_symmetric`** — symmetry forces equal exponents. CLOSED VIA `Equiv.swap`.
    (PR #174.) -/
theorem alphas_eq_of_symmetric {k : ℕ}
    (Lambda_fn : Aggregator k)
    (hsym : IsSymmetric Lambda_fn)
    (alphas : Fin k → NNReal)
    (h_factor : ∀ x : Axes k, Lambda_fn x = ∏ i, (x i) ^ (alphas i : ℝ)) :
    ∀ i j, alphas i = alphas j := by
  classical
  intro i j
  set c : NNReal := 2 with hc_def
  have hc1 : (1 : NNReal) < c := by rw [hc_def]; norm_num
  set e : Fin k → Axes k := (fun m => fun n => if n = m then c else 1) with he_def
  have hcollapse : ∀ m, (∏ n, (e m n) ^ (alphas n : ℝ)) = c ^ (alphas m : ℝ) := by
    intro m
    rw [Finset.prod_eq_single m]
    · rw [he_def]; simp
    · intro n _ hn
      rw [he_def]; simp only [if_neg hn, NNReal.one_rpow]
    · intro hm
      exact absurd (Finset.mem_univ m) hm
  have hswap : (fun n => e i ((Equiv.swap i j) n)) = e j := by
    funext n
    rw [he_def]
    show (if (Equiv.swap i j) n = i then c else 1) = (if n = j then c else 1)
    have hiff : ((Equiv.swap i j) n = i) ↔ (n = j) := by
      constructor
      · intro h
        have h2 := congrArg (Equiv.swap i j) h
        rwa [Equiv.swap_apply_self, Equiv.swap_apply_left] at h2
      · intro h; subst h; simp [Equiv.swap_apply_right]
    by_cases hnj : n = j
    · rw [if_pos (hiff.mpr hnj), if_pos hnj]
    · rw [if_neg (fun h => hnj (hiff.mp h)), if_neg hnj]
  have hsym_eq : Lambda_fn (fun n => e i ((Equiv.swap i j) n)) = Lambda_fn (e i) :=
    hsym (Equiv.swap i j) (e i)
  rw [hswap] at hsym_eq
  have hfi : Lambda_fn (e i) = c ^ (alphas i : ℝ) := by
    rw [h_factor (e i), hcollapse i]
  have hfj : Lambda_fn (e j) = c ^ (alphas j : ℝ) := by
    rw [h_factor (e j), hcollapse j]
  have : c ^ (alphas j : ℝ) = c ^ (alphas i : ℝ) := by
    rw [← hfj, ← hfi]; exact hsym_eq
  have hreal : (alphas j : ℝ) = (alphas i : ℝ) := rpow_left_inj_one_lt hc1 this
  exact (NNReal.coe_injective hreal).symm

/-- **`exponents_equal_inv_k_of_symm`** — every exponent is `1/k`, GIVEN symmetry + A3 +
    factorization. CLOSED VIA `sum_alphas_eq_one` + `alphas_eq_of_symmetric`. (PR #174.) -/
theorem exponents_equal_inv_k_of_symm {k : ℕ} (hk : 0 < k)
    (Lambda_fn : Aggregator k)
    (hL : LutarAxioms Lambda_fn)
    (hsym : IsSymmetric Lambda_fn)
    (alphas : Fin k → NNReal)
    (h_factor : ∀ x : Axes k, Lambda_fn x = ∏ i, (x i) ^ (alphas i : ℝ)) :
    ∀ i, alphas i = (1 / k : NNReal) := by
  have hk' : (0 : ℝ) < (k : ℝ) := by exact_mod_cast hk
  have hkne : (k : ℝ) ≠ 0 := ne_of_gt hk'
  have hall : ∀ i j, alphas i = alphas j :=
    alphas_eq_of_symmetric Lambda_fn hsym alphas h_factor
  have hsum : (∑ i, (alphas i : ℝ)) = 1 :=
    sum_alphas_eq_one Lambda_fn hL alphas h_factor
  intro i
  set i0 : Fin k := ⟨0, hk⟩
  have hconst : ∀ j, (alphas j : ℝ) = (alphas i0 : ℝ) := by
    intro j; exact_mod_cast (hall j i0)
  have hsum2 : (∑ _j : Fin k, (alphas i0 : ℝ)) = 1 := by
    rw [← hsum]; exact (Finset.sum_congr rfl (fun j _ => (hconst j).symm))
  rw [Finset.sum_const, Finset.card_univ, Fintype.card_fin, nsmul_eq_mul] at hsum2
  have hi0_val : (alphas i0 : ℝ) = 1 / (k : ℝ) := by
    rw [eq_div_iff hkne, mul_comm]
    exact hsum2
  have hi_val : (alphas i : ℝ) = 1 / (k : ℝ) := by
    rw [show (alphas i : ℝ) = (alphas i0 : ℝ) from by exact_mod_cast (hall i i0)]
    exact hi0_val
  have hcoe : (alphas i : ℝ) = ((1 / k : NNReal) : ℝ) := by
    rw [hi_val, NNReal.coe_div, NNReal.coe_one, NNReal.coe_natCast]
  exact NNReal.coe_injective hcoe

end Lutar.Round13

/-
## HONEST SORRY LEDGER (this file)
ZERO open obligations. Every theorem above is fully discharged.
The remaining (genuine) gap — deriving the factorization `Φ x = ∏ xᵢ^αᵢ` from A1–A5 — is
documented and tagged in `Lutar/Round13/Lambda_Uniqueness.lean`, where the `max`/`min`
counterexamples prove A1–A5 are insufficient and the unconditional uniqueness obligation is
tied to a missing A6 bisymmetry axiom.

No new `axiom` tokens. axioms_unique stays 14.

Signed-off-by: Λ-Closure Lead <lambda-closure@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
-/
