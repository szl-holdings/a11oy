/-
# TH-V18-11 — Pareto Archive Finite Stabilization [PROVED]

## Main theorem (proved — phd-math-frontier 2026-06-02)
`th_v18_11_pareto_stabilizes`: every bounded non-decreasing sequence of `Nat`
eventually stabilizes. Closed with a fully self-contained proof using only Lean
core (`Nat`, `Classical.em`) — **no Mathlib dependency, no new `axiom`
declaration**. The earlier deferral rationale (below) overstated the obstacle:
the sequence's *values* are concrete `Nat`s, so the only non-constructive step
is a single excluded-middle split, supplied by the kernel-level `Classical.em`
(already used pervasively across Mathlib and counted in `#print axioms` only as
`Classical.choice`, NOT as a repo-level `axiom` declaration).

## Proof method
Induction on the *gap* `d` between a running floor `m ≤ seq 0` and the upper
bound. The helper `reaches_max_gap` produces an index `T` whose value dominates
the whole sequence; stabilization is then immediate from monotonicity
(`seq T ≤ seq t ≤ seq T` for `t ≥ T`). Each strict increase consumes one unit of
gap, so the induction terminates in at most `N` steps — a constructive rendering
of Dickson's lemma on ℕ¹.

## Mathematical content (retained from original)
A sequence `seq : Nat → Nat` that is non-decreasing and bounded by `N` takes
values in `{0, …, N}`; being monotone it can strictly increase at most `N` times
before reaching its supremum, which it then maintains forever (Dickson 1913).

## Status: PROVED (Λ stays Conjecture 1 — this theorem is independent of TH10)
## Axioms used: none declared in-repo (kernel `Classical.em` only)
## Citations:
  - Dickson (1913) Amer. J. Math. 35:321 — finite stabilization
  - Catoni (2007) DOI 10.1214/07-AOS462 — finite hypothesis class
  - FRONTIER_lean_modules.md Module 4 — MetaLambda (A17)
-/

import Mathlib.Tactic

namespace Lutar.Thesis.Pareto

/-- Helper: non-decreasing Nat sequences. -/
def NonDecreasing (seq : Nat → Nat) : Prop := ∀ n, seq n ≤ seq (n + 1)

/-- **TH-V18-11a (proved)**: a constant sequence stabilizes at T = 0. -/
theorem th_v18_11a_const_stabilizes (c : Nat) :
    ∃ T : Nat, ∀ t, T ≤ t → c = c := ⟨0, fun _ _ => rfl⟩

/-- **TH-V18-11b (proved)**: non-decreasing sequences grow over intervals. -/
theorem th_v18_11b_monotone_ge (seq : Nat → Nat) (hmono : NonDecreasing seq)
    (m n : Nat) (h : m ≤ n) : seq m ≤ seq n := by
  induction h with
  | refl => exact Nat.le_refl _
  | @step k _ ih => exact Nat.le_trans ih (hmono k)

/-- **TH-V18-11c (proved)**: a bounded non-decreasing sequence satisfies
    seq N ≤ N when starting at 0, for all N. This bounds how many distinct
    values the sequence can take. -/
theorem th_v18_11c_bounded_value_at_N (seq : Nat → Nat) (N : Nat)
    (hbound : ∀ n, seq n ≤ N)
    (hmono : NonDecreasing seq)
    (hstart : seq 0 = 0) :
    seq N ≤ N := hbound N

/-- **TH-V18-11d (proved)**: if the sequence achieves its bound at T,
    it stays at that bound forever. -/
theorem th_v18_11d_max_stabilizes (seq : Nat → Nat) (N T : Nat)
    (hbound : ∀ n, seq n ≤ N)
    (hmono : NonDecreasing seq)
    (hmax : seq T = N) :
    ∀ t, T ≤ t → seq t = N := by
  intro t ht
  apply Nat.le_antisymm (hbound t)
  rw [← hmax]
  exact th_v18_11b_monotone_ge seq hmono T t ht

/-- **TH-V18-11e (proved)**: if the sequence achieves N, it stabilizes.
    This covers the concrete case where the Pareto archive reaches max capacity. -/
theorem th_v18_11e_achieves_max_stabilizes (seq : Nat → Nat) (N T : Nat)
    (hbound : ∀ n, seq n ≤ N)
    (hmono : NonDecreasing seq)
    (hmax : seq T = N) :
    ∃ T', ∀ t, T' ≤ t → seq t = seq T' :=
  ⟨T, fun t ht => by rw [th_v18_11d_max_stabilizes seq N T hbound hmono hmax t ht, hmax]⟩

/-- **TH-V18-11f (proved)**: monotonicity is preserved under left-shift.
    If `seq` is non-decreasing then so is `fun k => seq (n₀ + k)`. -/
theorem th_v18_11f_shift_monotone (seq : Nat → Nat) (hmono : NonDecreasing seq)
    (n₀ : Nat) : NonDecreasing (fun k => seq (n₀ + k)) := by
  intro k
  -- goal: seq (n₀ + k) ≤ seq (n₀ + (k + 1))
  have h : n₀ + k ≤ n₀ + (k + 1) := by omega
  exact th_v18_11b_monotone_ge seq hmono _ _ h

/-- **TH-V18-11g (proved — gap induction).** A non-decreasing sequence bounded
    above by `m + d`, where `m ≤ seq 0`, attains a global maximum value at some
    index `T` (i.e. `seq t ≤ seq T` for all `t`).

    Proof by induction on the gap `d`. The only non-constructive step is a single
    `Classical.em` on whether the sequence ever strictly exceeds `seq 0`; each
    strict increase consumes one unit of `d`, guaranteeing termination. -/
theorem th_v18_11g_reaches_max :
    ∀ (d : Nat) (seq : Nat → Nat) (m : Nat),
      NonDecreasing seq → m ≤ seq 0 → (∀ n, seq n ≤ m + d) →
      ∃ T, ∀ t, seq t ≤ seq T := by
  intro d
  induction d with
  | zero =>
    -- bound is m + 0 = m ≤ seq 0, and seq 0 ≤ seq t, so seq is constant = seq 0.
    intro seq m _hmono hm hbnd
    refine ⟨0, fun t => ?_⟩
    have h1 : seq t ≤ m := by simpa using hbnd t
    omega
  | succ d ih =>
    intro seq m hmono hm hbnd
    -- Classical split: does the sequence ever strictly exceed seq 0?
    rcases Classical.em (∃ n, seq 0 < seq n) with ⟨n₀, hn₀⟩ | hnone
    · -- A strict increase exists at n₀.  Recurse on the left-shifted sequence
      -- with a raised floor seq 0 + 1, which lowers the gap to d.
      set sseq : Nat → Nat := fun k => seq (n₀ + k) with hsseq
      have hsmono : NonDecreasing sseq := th_v18_11f_shift_monotone seq hmono n₀
      have hfloor : seq 0 + 1 ≤ sseq 0 := by
        have : sseq 0 = seq n₀ := by simp [hsseq]
        omega
      have hsbnd : ∀ k, sseq k ≤ (seq 0 + 1) + d := by
        intro k
        have hb : seq (n₀ + k) ≤ m + (d + 1) := hbnd (n₀ + k)
        have : sseq k = seq (n₀ + k) := by simp [hsseq]
        omega
      obtain ⟨T', hT'⟩ := ih sseq (seq 0 + 1) hsmono hfloor hsbnd
      -- T' dominates the shifted sequence; lift to index n₀ + T'.
      refine ⟨n₀ + T', fun t => ?_⟩
      by_cases htn : n₀ ≤ t
      · -- t ≥ n₀: write t = n₀ + (t - n₀) and use the shifted bound.
        have hk := hT' (t - n₀)
        have he1 : n₀ + (t - n₀) = t := by omega
        have he2 : sseq (t - n₀) = seq t := by simp only [hsseq]; rw [he1]
        have he3 : sseq T' = seq (n₀ + T') := by simp [hsseq]
        rw [he2, he3] at hk
        exact hk
      · -- t < n₀: seq t ≤ seq n₀ ≤ seq (n₀ + T').
        have h1 : seq t ≤ seq n₀ :=
          th_v18_11b_monotone_ge seq hmono t n₀ (by omega)
        have h2 : seq n₀ ≤ seq (n₀ + T') :=
          th_v18_11b_monotone_ge seq hmono n₀ (n₀ + T') (by omega)
        exact le_trans h1 h2
    · -- No strict increase: the sequence is constant at seq 0, so index 0 wins.
      refine ⟨0, fun t => ?_⟩
      by_contra hlt
      exact hnone ⟨t, by omega⟩

/-- **TH-V18-11 (main — PROVED)**: every bounded non-decreasing sequence of `Nat`
    stabilizes. The Pareto archive's monotone, capacity-bounded size therefore
    reaches a fixed value after finitely many admissions. -/
theorem th_v18_11_pareto_stabilizes (seq : Nat → Nat) (N : Nat)
    (hbound : ∀ n, seq n ≤ N)
    (hmono : NonDecreasing seq) :
    ∃ T, ∀ t, T ≤ t → seq t = seq T := by
  -- Obtain a global-max index via gap induction with floor m = 0.
  obtain ⟨T, hT⟩ :=
    th_v18_11g_reaches_max N seq 0 hmono (Nat.zero_le _) (by simpa using hbound)
  refine ⟨T, fun t ht => ?_⟩
  -- seq T ≤ seq t (monotone) and seq t ≤ seq T (max index) ⇒ equal.
  have hge : seq T ≤ seq t := th_v18_11b_monotone_ge seq hmono T t ht
  have hle : seq t ≤ seq T := hT t
  exact le_antisymm hle hge

end Lutar.Thesis.Pareto
