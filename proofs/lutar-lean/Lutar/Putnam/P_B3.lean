import Mathlib

namespace Lutar.Putnam.P_B3

/-!
# Putnam 2025 B3

**Problem:** Suppose S is a nonempty set of positive integers with the property that
if n is in S, then every positive divisor of 2025n - 15ⁿ is in S.
Must S contain all positive integers?

**Answer:** Yes, S must contain all positive integers.

**Proof technique:**
Note 2025 = 45² = 3⁴·5² and 15 = 3·5.

Key steps:
1. If 1 ∈ S, then S = ℕ₊ (since 1 | everything, wait: 1 divides every positive integer,
   so if 1 ∈ S, every positive divisor of 2025·1-15¹ = 2025-15 = 2010 is in S,
   and every divisor of 2025·n-15^n for each n ∈ S is in S.)
   Actually this doesn't immediately give everything.

2. The key is that S is closed under: n ↦ {divisors of 2025n - 15^n}.
   We need to show this closure includes all positive integers.

3. Start with some n₀ ∈ S. Show that 1 ∈ S (or show S generates all integers).

4. Note 2025n - 15^n = 15^2 · n - 15^n = 15^2(n - 15^{n-2}) when n ≥ 2?
   Actually 2025n - 15^n = 3^4·5^2·n - 3^n·5^n.

5. For n = 1: 2025·1 - 15^1 = 2010 = 2·3·5·67. So divisors of 2010 are in S.
   So {1,2,3,5,6,10,15,30,67,134,201,335,402,670,1005,2010} ⊆ S.
   In particular, 1 ∈ S. ✓

6. With 1 ∈ S: divisors of 2025·1 - 15^1 = 2010 ∈ S. Already done.

7. Now with 2 ∈ S: 2025·2 - 15^2 = 4050 - 225 = 3825 = 3^2·5^2·17 = 25·153 = 25·9·17.
   Divisors include 17. So 17 ∈ S.

8. For any prime p, we need to show p ∈ S. This requires showing p | 2025n - 15^n for
   some n already in S.

9. The official solution uses a more clever argument. With S containing all of ℤ₊ eventually.

**Full proof:** Once 1 ∈ S (which follows from any n₀ ∈ S generating a chain ending at 1),
we proceed by showing S = ℕ₊ is the unique minimal fixed point. The argument involves
showing every prime p ∈ S via number-theoretic arguments.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/
@[difficulty] 3
-/

-- The closure property
def ClosedUnderDivisors2025 (S : Set ℕ) : Prop :=
  ∀ n ∈ S, ∀ d : ℕ, d ∣ (2025 * n - 15 ^ n) → 0 < d → d ∈ S

-- Note: 2025*n - 15^n may be negative! We need to work in ℤ.
-- Actually for n=2: 2025*2 - 225 = 3825 > 0. For n=1: 2025-15=2010>0.
-- For large n: 15^n grows faster than 2025n, so 2025n - 15^n < 0.
-- When n=3: 2025*3 - 15^3 = 6075 - 3375 = 2700. Still positive.
-- When n=4: 2025*4 - 15^4 = 8100 - 50625 < 0.
-- The problem says "positive divisor of 2025n - 15^n", so we need 2025n > 15^n.
-- This holds for n ≤ 3 and n = 1,2,3 only.

-- Revisit: the problem likely means |2025n - 15^n| or takes divisors of the absolute value.
-- More likely, it means divisors of the integer 2025n - 15^n, which only makes sense
-- as a positive integer when 2025n > 15^n, i.e., for small n.

-- Restate with integers for robustness
def ClosedUnderDivisors2025' (S : Set ℕ) : Prop :=
  ∀ n ∈ S, ∀ d : ℕ, (d : ℤ) ∣ (2025 * n - 15 ^ n : ℤ) → 0 < d → d ∈ S

-- Key computation: for n=1, 2025*1 - 15^1 = 2010
lemma val_at_1 : (2025 : ℤ) * 1 - 15 ^ 1 = 2010 := by norm_num

-- 2010 = 2 * 3 * 5 * 67
lemma factored_2010 : (2010 : ℤ) = 2 * 3 * 5 * 67 := by norm_num

-- So all divisors of 2010 are in S
lemma divisors_of_2010_in_S (S : Set ℕ) (hS : ClosedUnderDivisors2025' S)
    (h1 : 1 ∈ S) : ∀ d : ℕ, d ∣ 2010 → 0 < d → d ∈ S := by
  intro d hd hpos
  apply hS 1 h1
  · exact_mod_cast hd.mul_left 1
  · exact hpos

-- In particular, 1 ∈ S (trivially: 1 | 2010)
-- The key question: does any starting set S generate 1?

-- If n₀ is the smallest element of S:
-- We need gcd({2025k - 15^k : k ∈ S, 2025k > 15^k}) = 1 or generate 1.

-- Key: gcd(2025*1 - 15, 2025*2 - 225) = gcd(2010, 3825)
-- 2010 = 2·3·5·67, 3825 = 3·5·255 = 3·5·5·51 = 3²·5²·17
-- gcd = 3·5 = 15. So gcd doesn't immediately give 1.

-- But gcd(2010, ...) will eventually give 1 once we include more n in S.

-- Main theorem
theorem putnam_B3_correct (S : Set ℕ) (hS_nonempty : S.Nonempty)
    (hS_pos : ∀ n ∈ S, 0 < n)
    (hS_closed : ClosedUnderDivisors2025' S) :
    ∀ n : ℕ, 0 < n → n ∈ S := by
  sorry -- sorry_p_B3_main: number-theoretic argument showing S = ℕ₊

-- Step 1: If S contains any n with 0 < 2025n - 15^n and gcd issues resolve to 1.
-- The official solution strategy:
-- (a) Show 1 ∈ S by finding the right combination.
-- (b) For n=1 ∈ S: get divisors of 2010 in S, including 2,3,5,67.
-- (c) For n=2 ∈ S (since 2|2010): get divisors of 3825 in S, including 17.
-- (d) For n=3 ∈ S (since 3|2010): get divisors of 2700 in S.
--     2700 = 2²·3³·5². Divisors: 4,9,25 also enter.
-- (e) Continue: eventually all primes enter S.

-- The hard part is showing every prime eventually enters S.
-- This requires: for any prime p, ∃ n ∈ S such that p | 2025n - 15^n.
-- By Fermat's little theorem (if p ∤ 15): 15^{p-1} ≡ 1 (mod p),
-- so 2025·n - 15^n ≡ 0 (mod p) when n ≡ 15^n/2025 (mod p)... complex.

-- We state the key number-theoretic lemma:
lemma all_primes_eventually_in_S (S : Set ℕ) (hS_nonempty : S.Nonempty)
    (hS_pos : ∀ n ∈ S, 0 < n)
    (hS_closed : ClosedUnderDivisors2025' S)
    (p : ℕ) (hp : Nat.Prime p) : p ∈ S := by
  sorry -- sorry_p_B3_primes: requires p-adic and Fermat argument

/-!
## Summary
- `putnam_B3_correct`: TRACKED — 1 sorry (sorry_p_B3_main)
- `all_primes_eventually_in_S`: TRACKED — 1 sorry (sorry_p_B3_primes)
- `divisors_of_2010_in_S`: partial REAL proof (exact_mod_cast)
- `val_at_1`, `factored_2010`: REAL proofs (norm_num)
- Sorry count: 2 (sorry_p_B3_main, sorry_p_B3_primes)
-/

end Lutar.Putnam.P_B3
