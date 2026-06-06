import Mathlib

namespace Lutar.Putnam.P_A5

/-!
# Putnam 2025 A5

**Problem:** Let n ≥ 2. For a sequence s = (s₁,...,sₙ₋₁) where each sᵢ = ±1,
let f(s) be the number of permutations (a₁,...,aₙ) of (1,2,...,n) such that
sᵢ(aᵢ₊₁ - aᵢ) > 0 for all i. For each n, determine the sequences s for which
f(s) is maximal.

**Answer:** f(s) is maximized by the "alternating" sequences:
s = (+1, -1, +1, -1, ...) and s = (-1, +1, -1, +1, ...) (and their variants).
These are the sequences with alternating signs, i.e., sᵢ · sᵢ₊₁ = -1 for all i.
The maximum value of f(s) equals the number of alternating permutations of [n],
which is the Euler number Eₙ.

**Proof technique:**
For fixed s, f(s) counts permutations where the pattern of rises/falls matches s.
The maximum is achieved by alternating sequences because: non-alternating sequences
force some consecutive rises or consecutive falls, which constrains the permutation
more than alternating sequences do. The Euler number Eₙ = |Aₙ| where Aₙ is the
set of alternating permutations, is well-known to equal the maximum of f(s) over all s.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/
@[difficulty] 4
-/

-- Sign sequence type
abbrev SignSeq (n : ℕ) := Fin (n - 1) → ({1, -1} : Set ℤ)

-- A permutation of Fin n satisfies s if all required ascents/descents hold
def satisfies_sign_seq {n : ℕ} (σ : Equiv.Perm (Fin n))
    (s : Fin (n-1) → ℤ) : Prop :=
  ∀ i : Fin (n-1),
    s i * ((σ ⟨i.val + 1, by omega⟩).val - (σ ⟨i.val, by omega⟩).val : ℤ) > 0

-- Count function f(s)
noncomputable def f {n : ℕ} (hn : 2 ≤ n) (s : Fin (n-1) → ℤ) : ℕ :=
  Fintype.card {σ : Equiv.Perm (Fin n) // satisfies_sign_seq σ s}

-- Alternating sequence: sᵢ = (-1)^i
def alt_seq_up (n : ℕ) : Fin (n-1) → ℤ :=
  fun i => if i.val % 2 = 0 then 1 else -1

def alt_seq_down (n : ℕ) : Fin (n-1) → ℤ :=
  fun i => if i.val % 2 = 0 then -1 else 1

-- Main theorem (TRACKED-PROP): f is maximized by alternating sequences
theorem putnam_A5_correct (n : ℕ) (hn : 2 ≤ n) (s : Fin (n-1) → ℤ)
    (hs : ∀ i, s i = 1 ∨ s i = -1) :
    f hn s ≤ f hn (alt_seq_up n) ∧ f hn s ≤ f hn (alt_seq_down n) := by
  sorry -- sorry_p_A5_main: requires counting alternating permutations

-- Small case verification: n=2
-- f(s) for n=2, s=(1): permutations (a₁,a₂) of {1,2} with a₂-a₁>0 → only (1,2). f=1.
-- f(s) for n=2, s=(-1): permutations with a₂-a₁<0 → only (2,1). f=1.
-- Both give 1, and E₂=1. ✓
lemma f_n2_up : f (n := 2) (by norm_num) (alt_seq_up 2) = 1 := by
  sorry -- sorry_p_A5_n2_up: explicit computation

-- For n=3, the alternating permutations of {1,2,3}:
-- (1,3,2), (2,3,1), (2,1,3)... wait:
-- alt_seq_up: s₁=1, s₂=-1, meaning a₂>a₁ and a₃<a₂ (updown).
-- Valid: (1,3,2), (2,3,1). So f=2=E₃. ✓
-- alt_seq_down: s₁=-1, s₂=1, meaning a₂<a₁ and a₃>a₂ (downup).
-- Valid: (3,1,2), (2,1,3). So f=2=E₃. ✓

-- Key fact: alternating permutations are counted by Euler numbers
-- Euler numbers: E₁=1, E₂=1, E₃=2 (wait, there are different conventions)
-- The "zigzag" or "tangent/secant numbers": T(n) where:
-- T(1)=1, T(2)=1, T(3)=2, T(4)=5, T(5)=16, ...
-- Here f(alt_seq_up, n) = T(n-1) ... depends on convention.

-- The main mathematical content: for any non-alternating s (i.e., sᵢ=sᵢ₊₁ for some i),
-- f(s) < f(alt_seq_up n). This is the strict inequality part.
lemma non_alt_strictly_smaller (n : ℕ) (hn : 3 ≤ n) (s : Fin (n-1) → ℤ)
    (hs_vals : ∀ i, s i = 1 ∨ s i = -1)
    (hs_non_alt : ∃ i : Fin (n-2), s ⟨i.val, by omega⟩ = s ⟨i.val+1, by omega⟩) :
    f (by omega) s < f (by omega) (alt_seq_up n) := by
  sorry -- sorry_p_A5_strict: requires detailed permutation counting argument

/-!
## Summary
- `putnam_A5_correct`: TRACKED — 1 sorry (sorry_p_A5_main)
- `f_n2_up`: TRACKED — 1 sorry (sorry_p_A5_n2_up)
- `non_alt_strictly_smaller`: TRACKED — 1 sorry (sorry_p_A5_strict)
- `satisfies_sign_seq`, `f`, `alt_seq_up`, `alt_seq_down`: REAL definitions
- Sorry count: 3 (sorry_p_A5_main, sorry_p_A5_n2_up, sorry_p_A5_strict)
-/

end Lutar.Putnam.P_A5
