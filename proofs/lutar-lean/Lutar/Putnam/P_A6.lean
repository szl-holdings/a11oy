import Mathlib

namespace Lutar.Putnam.P_A6

/-!
# Putnam 2025 A6

**Problem:** Let b₀ = 0 and, for n ≥ 0, define bₙ₊₁ = 2bₙ² + bₙ + 1.
For each k ≥ 1, show that b_{2^{k+1}} − 2·b_{2^k} is divisible by 2^{2k+2} but not by 2^{2k+3}.

**NOTE on indexing:** The Putnam statement uses b_{2k+1} and b_{2k} where the subscripts
2k+1 and 2k refer to POWERS OF TWO: b_{2^{k+1}} and b_{2^k} respectively.
The original formulation with linear indexing (b_{2·k+1} - 2·b_{2·k}) is numerically
false: b₃ - 2b₂ = 37 - 8 = 29, which is odd (v₂ = 0), contradicting divisibility by 16.
With power-of-2 indexing: b₄ - 2b₂ = 2776 - 8 = 2768 = 16 · 173, confirming v₂ = 4 = 2·1+2.
The official MAA solution (Kedlaya 2025) works with c_{m,n} = b_{m+n} - b_n and
proves v₂(b_{2^k}) = k+1.

**Proof technique (2-adic valuation):**
Define c_{m,n} = b_{m+n} - b_n. The key recurrence c_{m,n+1} = c_{m,n} · d_{m,n}
where d_{m,n} = 2(b_{m+n} + b_n) + 1 ≡ 1 (mod 4).
The proof shows v₂(c_{2^k, 0}) = v₂(b_{2^k}) = k+1 by induction on k.
Then b_{2^{k+1}} - 2·b_{2^k} = c_{2^k, 2^k} (approximately), and careful valuation
tracking gives v₂ = 2k+2 exactly.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/2025s.pdf
@[source] https://kskedlaya.org/putnam-archive/2025.pdf
@[difficulty] 5
-/

-- The sequence b
def b : ℕ → ℤ
  | 0 => 0
  | (n+1) => 2 * b n ^ 2 + b n + 1

-- Compute first few values via norm_num
@[simp] lemma b_zero : b 0 = 0 := rfl
@[simp] lemma b_one : b 1 = 1 := by native_decide
@[simp] lemma b_two : b 2 = 4 := by native_decide
@[simp] lemma b_three : b 3 = 37 := by native_decide
@[simp] lemma b_four : b 4 = 2776 := by native_decide

-- Recurrence as an equation (useful for rewriting)
lemma b_succ (n : ℕ) : b (n + 1) = 2 * b n ^ 2 + b n + 1 := rfl

-- Parity: b₀ ≡ 0 (mod 2), b₁ ≡ 1 (mod 2), and the parity alternates
-- b_{n+1} = 2b_n² + b_n + 1 ≡ b_n + 1 (mod 2)
lemma b_parity (n : ℕ) : b n % 2 = n % 2 := by
  induction n with
  | zero => simp [b_zero]
  | succ n ih =>
    simp only [b_succ]
    omega

-- b_{2k} is even, b_{2k+1} is odd
lemma b_even_index (k : ℕ) : 2 ∣ b (2 * k) := by
  have h := b_parity (2 * k)
  simp only [Nat.mul_mod_right] at h
  exact Int.dvd_of_emod_eq_zero (by omega)

lemma b_odd_index (k : ℕ) : ¬ 2 ∣ b (2 * k + 1) := by
  have h := b_parity (2 * k + 1)
  simp only [Nat.add_mod, Nat.mul_mod_right, Nat.zero_add, Nat.mod_self] at h
  intro hdvd
  have := Int.emod_eq_zero_of_dvd.mpr hdvd
  omega

-- The quantity of interest: b_{2^{k+1}} - 2·b_{2^k}
-- Correct interpretation: power-of-2 indices
def d_pow (k : ℕ) : ℤ := b (2^(k+1)) - 2 * b (2^k)

-- Base case: k=1, d_pow 1 = b₄ - 2·b₂ = 2776 - 8 = 2768
lemma d_pow_one : d_pow 1 = 2768 := by
  unfold d_pow
  native_decide

-- Verify: v₂(2768) = 4 = 2·1+2
-- 2768 = 16 · 173, and 173 is odd
lemma d_pow_one_val : (16 : ℤ) ∣ d_pow 1 ∧ ¬ (32 : ℤ) ∣ d_pow 1 := by
  constructor
  · rw [d_pow_one]; norm_num
  · rw [d_pow_one]; norm_num

-- Helper: b_n ≡ n (mod 2) gives us b_{2^k} is even for k ≥ 1
lemma b_pow2_even (k : ℕ) (hk : 1 ≤ k) : (2 : ℤ) ∣ b (2^k) := by
  apply b_even_index (2^(k-1))
  congr 1
  omega

-- The d recurrence (wrong linear indexing): kept for reference
-- d(k+1) = b_{2k+3} - 2b_{2k+2}
lemma d_recurrence_linear (k : ℕ) :
    b (2*k+3) - 2 * b (2*k+2) =
    2 * b (2*k+2) ^ 2 + b (2*k+2) + 1 -
    2 * (2 * b (2*k+1) ^ 2 + b (2*k+1) + 1) := by
  simp only [b_succ]
  ring

-- Base case: d(0) in linear indexing = b₁ - 2b₀ = 1 - 0 = 1
lemma d_linear_zero : b 1 - 2 * b 0 = 1 := by simp

-- CORRECTED MAIN THEOREM using power-of-2 indexing
-- Partial discharge: base case k=1 fully proved; full induction annotated with route.
theorem putnam_A6_correct_pow (k : ℕ) (hk : 1 ≤ k) :
    -- 2^{2k+2} divides b_{2^{k+1}} - 2·b_{2^k}
    (2 : ℤ) ^ (2*k+2) ∣ d_pow k ∧
    -- but 2^{2k+3} does not
    ¬ (2 : ℤ) ^ (2*k+3) ∣ d_pow k := by
  -- DISCHARGE_ROUTE: Full proof by induction on k.
  -- Base case k=1: d_pow_one_val above establishes 2^4 | 2768 and 2^5 ∤ 2768.
  -- Inductive step: Uses the Lifting-the-Exponent Lemma (LTE) for p=2:
  --   Mathlib.NumberTheory.LucasPrimality or Mathlib.RingTheory.Valuation.Basic
  -- The key recurrence in the official solution (Kedlaya 2025s):
  --   c_{2k,0} = b_{2k} satisfies v₂(b_{2^k}) = k+1
  --   Then b_{2^{k+1}} - 2·b_{2^k} = f_{2^k}(b_{2^k}) - 2·b_{2^k}
  --   where f(x) = 2x²+x+1.
  --   Since b_{2^k} = 2^{k+1}·m (m odd), f(b_{2^k}) - 2·b_{2^k} = 2b_{2^k}²- b_{2^k}+1
  --   This gives v₂ = 2(k+1)+... The exact valuation 2k+2 follows from
  --   Mathlib.NumberTheory.Padics.PadicNorm or multiplicity.Finset.
  -- DISCHARGE_ROUTE: need Mathlib.NumberTheory.Multiplicity + LTE for p=2
  --   Specifically: multiplicity.Int.two_pow_dvd_mul lemma family
  sorry -- sorry_p_A6_pow_induction: full LTE-based induction; base case k=1 proved above

-- The original theorem statement (with linear indexing) is FALSE:
-- b_{2k+1} - 2*b_{2k} is always odd for k ≥ 1 (since b_{2k+1} is odd, 2*b_{2k} is even).
-- We document this as a FALSE theorem with explanation.
theorem putnam_A6_original_statement_is_false :
    ¬ ∀ k : ℕ, 1 ≤ k → (2 : ℤ) ^ (2*k+2) ∣ (b (2*k+1) - 2 * b (2*k)) := by
  intro h
  -- Instantiate at k=1: need 16 | b 3 - 2 * b 2 = 37 - 8 = 29
  have h1 := h 1 (by norm_num)
  -- b(3) - 2*b(2) = 37 - 8 = 29
  simp only [b_succ, b_zero] at h1
  norm_num at h1

/-!
## Summary
- `putnam_A6_correct_pow`: PARTIAL DISCHARGE — 1 sorry remains (sorry_p_A6_pow_induction)
  - Base case k=1 is proved by `d_pow_one_val` (norm_num/native_decide).
  - Full induction deferred.
  - DISCHARGE_ROUTE: need Mathlib.NumberTheory.Multiplicity (LTE for p=2)
    Specifically: `multiplicity.Int.pow_sub_pow` or `padicValInt.pow`
- `putnam_A6_original_statement_is_false`: FULLY PROVED — the linear-indexed theorem
  as originally stated is false; proved by norm_num at k=1.
- `d_pow_one_val`: FULLY PROVED — base case 2^4 | 2768 ∧ 2^5 ∤ 2768.
- `b_parity`, `b_even_index`, `b_odd_index`: FULLY PROVED.
- Sorry count: 1 (sorry_p_A6_pow_induction, was 1 before but now correctly stated)
- Net improvement: theorem statement corrected from false to true; base case proved.
- Prior art: Numina-Lean-Agent (arXiv:2601.14027) has 12/12 fully discharged.
-/

end Lutar.Putnam.P_A6
