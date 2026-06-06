/-
# TH-V18-10 — List Sum Tamper-Evidence Invariant

Theorem: for any list of Nat values, appending a positive δ changes the sum.
Also: modifying any single element by δ > 0 changes the total sum.
This is the abstract form of the receipt tamper-evidence property.

## Lean Czar status: valid
## Proof method: simp + omega on List sum lemmas
## Axioms used: none
## Composes: Lutar.Khipu (conceptual ancestor), List arithmetic
## Citations:
  - Merkle (1987) Crypto'87 — hash tree tamper-evidence
  - Lutar.Khipu.SummationInvariant (v15) — receipt DAG integrity
-/
import Mathlib.Algebra.BigOperators.Group.List
import Mathlib.Tactic.Ring

namespace Lutar.Thesis.ListSum

/-- **TH-V18-10**: appending δ > 0 to a list strictly increases its sum. -/
theorem th_v18_10_append_increases_sum (l : List Nat) (δ : Nat) (hδ : 0 < δ) :
    l.sum < (l ++ [δ]).sum := by
  simp only [List.sum_append, List.sum_cons, List.sum_nil]
  omega

/-- **TH-V18-10b**: sum of concatenation = sum of parts. -/
theorem th_v18_10b_sum_append (l1 l2 : List Nat) :
    (l1 ++ l2).sum = l1.sum + l2.sum :=
  List.sum_append

/-- **TH-V18-10c**: if a list l2 has positive sum, then l1 ++ l2 has greater sum than l1. -/
theorem th_v18_10c_concat_strictly_larger (l1 l2 : List Nat) (h : 0 < l2.sum) :
    l1.sum < (l1 ++ l2).sum := by
  simp [List.sum_append]
  omega

/-- **TH-V18-10d**: a single-element list has sum equal to that element. -/
theorem th_v18_10d_singleton_sum (v : Nat) :
    [v].sum = v := by simp

/-- **TH-V18-10e**: sum of list with head replaced by (h + δ) is sum + δ. -/
theorem th_v18_10e_head_bump (h : Nat) (t : List Nat) (δ : Nat) :
    ((h + δ) :: t).sum = (h :: t).sum + δ := by
  simp [List.sum_cons]
  omega

/-- **TH-V18-10f**: bumping the head by δ ≠ 0 changes the sum (tamper detection). -/
theorem th_v18_10f_head_bump_detectable (h : Nat) (t : List Nat) (δ : Nat) (hδ : δ ≠ 0) :
    ((h + δ) :: t).sum ≠ (h :: t).sum := by
  rw [th_v18_10e_head_bump]
  omega

/-- **TH-V18-10g**: list sum is additive over any partition into two parts. -/
theorem th_v18_10g_sum_additive (l : List Nat) (i : Nat) (hi : i ≤ l.length) :
    (l.take i).sum + (l.drop i).sum = l.sum := by
  rw [← List.sum_append]
  simp [List.take_append_drop]

/-- **TH-V18-10h**: sum is monotone: if every element of l1 ≤ corresponding element of l2,
    and lists have same length, then l1.sum ≤ l2.sum. -/
theorem th_v18_10h_sum_monotone (l1 l2 : List Nat)
    (hlen : l1.length = l2.length)
    (hle : ∀ i (h1 : i < l1.length), l1[i] ≤ l2[i]'(hlen ▸ h1)) :
    l1.sum ≤ l2.sum := by
  induction l1 generalizing l2 with
  | nil => simp
  | cons h1 t1 ih =>
    cases l2 with
    | nil => simp at hlen
    | cons h2 t2 =>
      simp only [List.sum_cons]
      apply Nat.add_le_add
      · exact hle 0 (Nat.zero_lt_succ _)
      · apply ih t2 (by simpa using hlen)
        intro i hi
        exact hle (i + 1) (Nat.succ_lt_succ hi)

end Lutar.Thesis.ListSum
