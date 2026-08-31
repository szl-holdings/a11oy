import Mathlib

namespace Lutar.Putnam.P_B4

/-!
# Putnam 2025 B4

**Problem:** For n ≥ 2, let A = [aᵢⱼ] be an n×n matrix of nonneg integers such that:
(a) aᵢⱼ = 0 when i+j ≤ n;
(b) aᵢ₊₁,ⱼ ∈ {aᵢⱼ, aᵢⱼ+1} when 1≤i≤n-1, 1≤j≤n;
(c) aᵢ,ⱼ₊₁ ∈ {aᵢⱼ, aᵢⱼ+1} when 1≤i≤n, 1≤j≤n-1.
Let S = sum of entries of A, and N = number of nonzero entries of A.
Prove that S ≤ (n+2)N/3.

**Proof technique:**
The matrix entries live in the "upper-right triangle" (where i+j > n).
Condition (a) says the lower-left triangle is 0.
Conditions (b),(c) say the matrix is "weakly increasing" as we move down or right,
increasing by at most 1 per step.

Key observation: each nonzero entry aᵢⱼ satisfies aᵢⱼ ≤ min(i+j-n, ...).
Actually: the maximum entry aᵢⱼ is at most min(i-1, j-1, i+j-n) by the step conditions
(since we start from 0 at i+j=n+1 and can increase by at most 1 per step).

More precisely: aᵢⱼ can reach (i,j) from the boundary i+j=n+1 (where aᵢⱼ ∈ {0,1}).
The maximum number of steps from any boundary point to (i,j) bounds aᵢⱼ.

The bound S ≤ (n+2)N/3:
Each nonzero entry in row i, col j has i+j > n.
aᵢⱼ ≤ (number of steps from 0-boundary) ≤ i+j-n-1+1 = i+j-n ... but this gives
loose bound.

The tight argument: define a "dual" counting. Each unit of value contributes 1 to S,
and corresponds to a step increase at some position. Each step increase at (i,j)
(from row i to row i+1, or col j to col j+1) affects at most 3 nonzero positions
"downstream" (weighted argument). Hence S ≤ (n+2)N/3.

@[source] https://maa.org/wp-content/uploads/2026/02/2025OfficialSolutions.pdf
@[source] https://kskedlaya.org/putnam-archive/
@[difficulty] 4
-/

-- Model: 1-indexed matrix of size n×n
-- We use Fin n → Fin n → ℕ with shifted indexing

/-- The condition on the matrix -/
structure PutnamMatrix (n : ℕ) (hn : 2 ≤ n) where
  -- entries
  a : Fin n → Fin n → ℕ
  -- (a) zero below anti-diagonal
  zero_below : ∀ i j : Fin n, i.val + j.val + 2 ≤ n → a i j = 0
  -- (b) row increments by at most 1
  row_inc : ∀ i j : Fin n, ∀ hi : i.val + 1 < n,
    a ⟨i.val + 1, hi⟩ j = a i j ∨ a ⟨i.val + 1, hi⟩ j = a i j + 1
  -- (c) col increments by at most 1
  col_inc : ∀ i j : Fin n, ∀ hj : j.val + 1 < n,
    a i ⟨j.val + 1, hj⟩ = a i j ∨ a i ⟨j.val + 1, hj⟩ = a i j + 1

/-- Sum of all entries -/
def S_total {n : ℕ} {hn : 2 ≤ n} (M : PutnamMatrix n hn) : ℕ :=
  ∑ i : Fin n, ∑ j : Fin n, M.a i j

/-- Number of nonzero entries -/
def N_count {n : ℕ} {hn : 2 ≤ n} (M : PutnamMatrix n hn) : ℕ :=
  (Finset.univ.filter (fun p : Fin n × Fin n => M.a p.1 p.2 ≠ 0)).card

-- Key lemma: each entry is bounded by the distance from the zero boundary
lemma entry_bound {n : ℕ} {hn : 2 ≤ n} (M : PutnamMatrix n hn)
    (i j : Fin n) (hij : i.val + j.val + 2 > n) :
    M.a i j ≤ i.val + j.val + 2 - n := by
  sorry -- sorry_p_B4_entry_bound: induction on distance from anti-diagonal

-- Main theorem: S ≤ (n+2)*N/3
theorem putnam_B4_correct {n : ℕ} (hn : 2 ≤ n) (M : PutnamMatrix n hn) :
    3 * S_total M ≤ (n + 2) * N_count M := by
  sorry -- sorry_p_B4_main: weighted counting argument

-- Small case: n=2
-- The matrix is 2×2: positions (1,1),(1,2),(2,1),(2,2) [1-indexed]
-- (a) zeros when i+j ≤ 2: a(1,1)=0. So a(1,2), a(2,1), a(2,2) are potentially nonzero.
-- (b) row increment: a(2,j) ∈ {a(1,j), a(1,j)+1}
-- (c) col increment: a(i,2) ∈ {a(i,1), a(i,1)+1}
-- Fin 2 uses 0-indexed, so i+j+2≤2 iff i+j≤0 iff i=j=0.
-- So a(0,0)=0. a(0,1), a(1,0), a(1,1) can be nonzero.
-- Maximum entries: a(0,1) ≤ 1, a(1,0) ≤ 1, a(1,1) ≤ 2.
-- Maximum S: 0+1+1+2=4. N=3. (n+2)*N/3 = 4*3/3 = 4. So S ≤ 4. ✓

lemma n2_base_case (M : PutnamMatrix 2 (by norm_num)) :
    3 * S_total M ≤ 4 * N_count M := by
  sorry -- sorry_p_B4_n2: explicit computation for n=2

/-!
## Summary
- `putnam_B4_correct`: TRACKED — 1 sorry (sorry_p_B4_main)
- `entry_bound`: TRACKED — 1 sorry (sorry_p_B4_entry_bound)
- `n2_base_case`: TRACKED — 1 sorry (sorry_p_B4_n2)
- `PutnamMatrix`, `S_total`, `N_count`: REAL definitions
- Sorry count: 3 (sorry_p_B4_main, sorry_p_B4_entry_bound, sorry_p_B4_n2)
-/

end Lutar.Putnam.P_B4
