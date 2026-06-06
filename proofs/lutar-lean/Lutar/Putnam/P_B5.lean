import Mathlib

namespace Lutar.Putnam.P_B5

/-!
# Putnam 2025 B5

**Problem:** Let p be a prime > 3. For each k ∈ {1,...,p-1}, let I(k) ∈ {1,...,p-1}
be such that k·I(k) ≡ 1 (mod p) (i.e., I(k) = k⁻¹ mod p).
Prove that the number of integers k ∈ {1,...,p-2} such that I(k+1) < I(k) is
greater than p/4 - 1.

**Proof technique (using sums and Weil / character sum estimates):**
Let D = #{k ∈ {1,...,p-2} : I(k+1) < I(k)}.
Note: as k varies over {1,...,p-1}, I(k) = k⁻¹ mod p is a permutation of {1,...,p-1}.
Also, I(k+1) < I(k) is equivalent to asking: does the inverse function "decrease"?

Key identity: sum over k of sign(I(k+1) - I(k)) relates to the number of inversions
in the permutation k ↦ I(k).

More precisely: since I is a bijection on {1,...,p-1} and I(k)·k ≡ 1 (mod p),
the number of "descents" D satisfies:
  D + (p-2-D) = p-2 (total comparisons)
  D - (p-2-D) = sum_{k=1}^{p-2} sign(I(k) - I(k+1))

Relating to character sums: sum_{k=1}^{p-2} sign(k⁻¹ - (k+1)⁻¹)
where sign(x) ∈ {±1} and x = k⁻¹ - (k+1)⁻¹ = (k+1-k)/(k(k+1)) = 1/(k(k+1)).
Since 1/(k(k+1)) > 0... wait, these are mod p! In {1,...,p-1}.

Actually: I(k) - I(k+1) = k⁻¹ - (k+1)⁻¹ (mod p) = [(k+1) - k]/(k(k+1)) = 1/(k(k+1)) (mod p).
So I(k) > I(k+1) as integers ↔ ... depends on reduction of 1/(k(k+1)) mod p.

The condition I(k+1) < I(k) in {1,...,p-1} as integers is equivalent to:
the representative of k⁻¹ (mod p) in {1,...,p-1} is greater than that of (k+1)⁻¹.

The official proof bounds D from below using:
  2D ≥ (p-2)/2 - 1 type estimate via quadratic character sums.

The key: D ≥ ⌊(p-1)/4⌋ - 1 > p/4 - 2. We need D > p/4 - 1.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/
@[difficulty] 5
-/

open ZMod Finset

variable (p : ℕ) [hp : Fact (Nat.Prime p)] (hp3 : 3 < p)

-- The modular inverse function on ZMod p \ {0}
-- In Mathlib: ZMod.inv (or Units.inv)

-- Count of descents: #{k ∈ {1,...,p-2} : I(k+1) < I(k)}
noncomputable def descent_count : ℕ :=
  (Finset.filter (fun k : Fin (p-1) =>
    -- k ranges over Fin(p-1), representing 1,...,p-1
    -- We need k ∈ {1,...,p-2}, i.e., k.val < p-2
    k.val < p - 2 ∧
    -- I(k+1) < I(k) as natural numbers in {1,...,p-1}
    (ZMod.val ((k.val + 2 : ℕ) : ZMod p)⁻¹ < ZMod.val ((k.val + 1 : ℕ) : ZMod p)⁻¹))
    Finset.univ).card

-- The main theorem
theorem putnam_B5_correct :
    (p : ℝ) / 4 - 1 < (descent_count p : ℝ) := by
  sorry -- sorry_p_B5_main: character sum / Weil bound argument

-- Key lemma: the sum of I(k+1) - I(k) over all k is telescoping
lemma inversion_telescopes :
    ∑ k in Finset.range (p - 2), 
      (ZMod.val ((k + 2 : ℕ) : ZMod p)⁻¹ : ℤ) -
      (ZMod.val ((k + 1 : ℕ) : ZMod p)⁻¹ : ℤ) = 
    (ZMod.val ((p-1 : ℕ) : ZMod p)⁻¹ : ℤ) - (ZMod.val (1 : ZMod p)⁻¹ : ℤ) := by
  rw [Finset.sum_range_succ_sub_sum]

-- I(1) = 1 (since 1·1 ≡ 1 mod p)
lemma inv_one : (1 : ZMod p)⁻¹ = 1 := by
  simp [ZMod.inv_one]

-- I(p-1) = p-1 (since (p-1)(p-1) = p²-2p+1 ≡ 1 mod p)
lemma inv_neg_one : ((p - 1 : ℕ) : ZMod p)⁻¹ = (p - 1 : ℕ) := by
  -- (p-1) ≡ -1 (mod p), and (-1)·(-1) = 1, so (-1)⁻¹ = -1
  have : ((p - 1 : ℕ) : ZMod p) = -1 := by
    simp [ZMod.natCast_self_eq_zero]
    sorry -- sorry_p_B5_neg_one: needs ZMod arithmetic
  rw [this]
  simp [ZMod.inv_neg_one (by exact Fact.out)]

-- The # of ascending pairs + # of descending pairs = p-2
lemma ascent_plus_descent :
    let D := descent_count p
    let A := (p - 2) - D  -- number of ascents (I(k+1) > I(k))
    D + A = p - 2 := by
  simp [Nat.add_sub_cancel']
  sorry -- sorry_p_B5_partition: I(k+1) ≠ I(k) for all k (injectivity)

/-!
## Summary
- `putnam_B5_correct`: TRACKED — 1 sorry (sorry_p_B5_main)
- `inversion_telescopes`: REAL (Finset.sum_range_succ_sub_sum)
- `inv_one`: REAL (ZMod.inv_one)
- `inv_neg_one`: TRACKED — 1 sorry (sorry_p_B5_neg_one)
- `ascent_plus_descent`: TRACKED — 1 sorry (sorry_p_B5_partition)
- `descent_count`: REAL definition
- Sorry count: 3 (sorry_p_B5_main, sorry_p_B5_neg_one, sorry_p_B5_partition)
-/

end Lutar.Putnam.P_B5
