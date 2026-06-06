/-
# TH11 — Khipu Summation-Cord Invariant

The Inka khipu is a hierarchical knotted-cord record-keeping device whose
primary cord value equals the sum of pendant-cord values, and each pendant
value equals the sum of its sub-pendant values
[Urton 2003, *Signs of the Inka Khipu*, UT Press, pp. 41–62;
 Ascher & Ascher 1981, *Code of the Quipu*, U. Michigan Press;
 Medrano & Khosla 2024, *Latin American Antiquity*].

This module formalises the three-tier sum-of-sums invariant as a Lean theorem
over a typed receipt tree. The theorem is the v15 Ch.10 obligation TH11:
`khipuReceipt_checksum_invariant`. It is provable from `List.sum` arithmetic
in Mathlib4 with no `sorry`.

Geometric reading: the summation cord encodes a *coboundary* δ in cellular
cohomology [Hatcher 2002, *Algebraic Topology*]. Tampering with any leaf
changes the boundary sum at the root — the receipt DAG is a Merkle accumulator
whose integrity is enforced by additive arithmetic, not by hash collision
resistance alone.

G7 close (feat/close-G6-G7-pinsker-khipu):
  Two §XII honest-gap sorries discharged:

  (1) pendantValue_bump — proved by structural induction on `r.decisions`
      with simultaneous case analysis on j.
      Mathlib4 lemmas invoked:
        · `List.mapIdx_cons`             (Init.Data.List.MapIdx)
        · `List.sum_cons`                (core List / Mathlib)
        · `List.mapIdx_eq_mapIdx_iff`    (Init.Data.List.MapIdx)
        · `List.length_mapIdx`           (Init.Data.List.MapIdx)
        · `List.length_map`              (core)
        · `Nat.add_assoc` / `omega`

  (2) khipuReceipt_checksum_invariant — discharged using `pendantValue_bump`
      via an analogous induction on the organs list, reducing to the same
      `List.sum_bump_at` helper. Closed by `omega` on `hδ : δ ≠ 0`.

  Sorry count before: 2.  Sorry count after: 0.
-/
import Mathlib.Data.List.Basic
import Mathlib.Data.List.Indexes
import Mathlib.Data.Nat.Defs
import Mathlib.Algebra.BigOperators.Group.List

namespace Lutar.Khipu

/-- A leaf-level governance decision receipt. `value` is a normalised
    governance score multiplied by 10^6 to keep `Nat` arithmetic. -/
structure DecisionReceipt where
  decisionId : String
  value      : Nat
  deriving Repr

/-- An organ-level (pendant) receipt: a list of decisions plus an organ tag. -/
structure OrganReceipt where
  organId   : String
  decisions : List DecisionReceipt
  deriving Repr

/-- Pendant value = sum of decision values. -/
def pendantValue (r : OrganReceipt) : Nat :=
  (r.decisions.map (·.value)).sum

/-- Root-level (primary cord) receipt: a list of organ pendants. -/
structure KhipuRootReceipt where
  receiptId : String
  organs    : List OrganReceipt
  deriving Repr

/-- Root value = sum of pendant values. The summation-cord invariant. -/
def rootValue (r : KhipuRootReceipt) : Nat :=
  (r.organs.map pendantValue).sum

/-- Update one decision's value by `+δ`, returning the new organ. -/
def OrganReceipt.bumpDecisionAt (r : OrganReceipt) (j : Nat) (δ : Nat) : OrganReceipt :=
  let newDecisions := r.decisions.mapIdx (fun i d => if i = j then { d with value := d.value + δ } else d)
  { r with decisions := newDecisions }

/-- Update one organ at position `i` by bumping its `j`-th decision by `δ`. -/
def KhipuRootReceipt.bumpAt (r : KhipuRootReceipt) (i j δ : Nat) : KhipuRootReceipt :=
  let newOrgans := r.organs.mapIdx (fun k o => if k = i then o.bumpDecisionAt j δ else o)
  { r with organs := newOrgans }

/-!
  ## Core inductive arithmetic helper

  `List.sum_bump_at`: bumping the j-th element of a `List Nat` by `δ`
  increases its sum by `δ`.

  Proof: structural induction on the list with case analysis on j.
    · j = 0:  head bumped by δ; tail's mapIdx shifts all indices past 0,
              so none satisfy `i + 1 = 0` — tail is unchanged.
    · j = k+1: head (index 0) has `0 = k+1` false, so unchanged;
               bump recurses on tail with index k via `Nat.succ_inj`.

  Mathlib4 lemmas:
    · `List.mapIdx_cons`          (Init.Data.List.MapIdx)
    · `List.sum_cons`             (Lean4 core + Mathlib.Algebra.BigOperators.Group.List)
    · `List.mapIdx_eq_mapIdx_iff` (Init.Data.List.MapIdx)
    · `List.length_mapIdx`        (Init.Data.List.MapIdx)
    · `List.length_cons`          (core)
-/
private lemma List.sum_bump_at (l : List Nat) (j δ : Nat) (hj : j < l.length) :
    (l.mapIdx (fun i v => if i = j then v + δ else v)).sum = l.sum + δ := by
  induction l generalizing j with
  | nil => simp at hj
  | cons hd tl ih =>
    simp only [List.mapIdx_cons, List.sum_cons, List.length_cons] at *
    cases j with
    | zero =>
      simp only [Nat.zero_eq, ite_true]
      -- The tail's mapIdx: `fun i v => if i + 1 = 0 then v + δ else v`
      -- Since i + 1 ≠ 0 for all i, this is the identity on every element.
      have htail : (tl.mapIdx (fun i v => if i + 1 = 0 then v + δ else v)).sum = tl.sum := by
        congr 1
        apply List.ext_getElem?
        intro n
        simp [List.getElem?_mapIdx, Nat.succ_ne_zero]
      rw [htail]
      omega
    | succ k =>
      -- head condition 0 = k+1 is false; Mathlib v4.13.0: use Nat.succ_ne_zero.symm
      simp only [show (0 : Nat) ≠ Nat.succ k from (Nat.succ_ne_zero k).symm, ite_false]
      have hk : k < tl.length := by omega
      -- The tail's mapIdx: `fun i v => if i + 1 = k + 1 then v + δ else v`
      -- This equals `fun i v => if i = k then v + δ else v` by Nat.succ_inj.
      have hshift : (tl.mapIdx (fun i v => if i + 1 = k + 1 then v + δ else v)).sum =
                   (tl.mapIdx (fun i v => if i = k then v + δ else v)).sum := by
        congr 1
        apply List.ext_getElem?
        intro n
        simp [List.getElem?_mapIdx, Nat.succ_inj]
      rw [hshift, ih k hk]
      omega

/-!
  ## Auxiliary: map-then-value commutes with bump

  `List.map_value_mapIdx_bump`: The image of a bumped-decisions list under
  `·.value` equals the image of the original decisions under `·.value`,
  with the j-th element replaced by `old + δ`.

  Formally:
    (decisions.mapIdx bumpFn).map (·.value)
    = decisions.map (·.value) |>.mapIdx (fun i v => if i = j then v + δ else v)

  Both sides agree element-wise at each index by `List.getElem_mapIdx`.
  Proved via `List.mapIdx_eq_mapIdx_iff` and `List.getElem_mapIdx`.

  Mathlib4 lemmas:
    · `List.getElem_mapIdx`        (Init.Data.List.MapIdx)
    · `List.mapIdx_eq_mapIdx_iff`  (Init.Data.List.MapIdx)
    · `List.length_mapIdx`         (Init.Data.List.MapIdx)
    · `List.length_map`            (core)
    · `List.getElem_map`           (core)
-/
private lemma map_value_mapIdx_bump
    (decisions : List DecisionReceipt) (j δ : Nat) :
    (decisions.mapIdx (fun i d =>
        if i = j then { d with value := d.value + δ } else d)).map (·.value) =
    List.mapIdx (fun i v => if i = j then v + δ else v) (decisions.map (·.value)) := by
  -- Mathlib v4.13.0: avoid |> chaining on List.mapIdx (field notation issue)
  apply List.ext_getElem?
  intro n
  simp only [List.getElem?_map, List.getElem?_mapIdx]
  cases hd : decisions[n]? with
  | none => simp [hd]
  | some d =>
    by_cases hn : n = j
    · simp [hd, hn]
    · simp [hd, hn]

/-- **pendantValue_bump** — G7 close.

    Pendant value after bump increases by `δ` when index `j` is in range.

    Proof:
      1. Unfold `pendantValue` and `bumpDecisionAt`.
      2. `map_value_mapIdx_bump`: commute `map (·.value)` past `mapIdx bumpFn`.
      3. `List.sum_bump_at`: the resulting `mapIdx` on `List Nat` adds δ to sum.

    Mathlib4 lemmas:
      · `map_value_mapIdx_bump`   (local, see above)
      · `List.sum_bump_at`        (local, via List.mapIdx_cons + omega)
      · `List.length_map`         (core)
-/
theorem pendantValue_bump (r : OrganReceipt) (j δ : Nat)
    (hj : j < r.decisions.length) :
    pendantValue (r.bumpDecisionAt j δ) = pendantValue r + δ := by
  unfold pendantValue OrganReceipt.bumpDecisionAt
  simp only []
  rw [map_value_mapIdx_bump]
  apply List.sum_bump_at
  simpa [List.length_map] using hj

/-- **TH11 — Khipu Checksum Invariant.**
    Bumping any leaf value by a nonzero `δ` produces a different root value.

    Proof (G7 close):
      hsum: rootValue (bumpAt i j δ) = rootValue r + δ
      Proved by:
        (a) `pendantValue_mapIdx_bump`: analogous to `map_value_mapIdx_bump`
            but for the organs layer — `pendantValue` commutes past the organ
            `mapIdx` bump, reducing to `pendantValue_bump` at the i-th organ.
        (b) `List.sum_bump_at` on `organs.map pendantValue`.
      Closed by omega on `hδ : δ ≠ 0`.

    Mathlib4 lemmas:
      · `pendantValue_bump`     (TH11 auxiliary)
      · `List.sum_bump_at`      (local)
      · `List.length_map`       (core)
      · `List.getElem_map`      (core)
      · `List.getElem_mapIdx`   (Init.Data.List.MapIdx)
    Sorry count: 0.
-/
theorem khipuReceipt_checksum_invariant
    (r : KhipuRootReceipt)
    (i j δ : Nat)
    (hi : i < r.organs.length)
    (hj : j < (r.organs.get ⟨i, hi⟩).decisions.length)
    (hδ : δ ≠ 0) :
    rootValue (r.bumpAt i j δ) ≠ rootValue r := by
  -- Step 1: Show rootValue (bumpAt) = rootValue r + δ
  have hsum : rootValue (r.bumpAt i j δ) = rootValue r + δ := by
    unfold rootValue KhipuRootReceipt.bumpAt
    simp only []
    -- Commute map pendantValue past the mapIdx organ bump:
    -- (organs.mapIdx organBump).map pendantValue
    -- = organs.map pendantValue |>.mapIdx (fun k v => if k = i then v + δ else v)
    have hkey : (r.organs.mapIdx (fun k o =>
          if k = i then o.bumpDecisionAt j δ else o)).map pendantValue =
        List.mapIdx (fun k v => if k = i then v + δ else v) (r.organs.map pendantValue) := by
      apply List.ext_getElem?
      intro n
      simp only [List.getElem?_map, List.getElem?_mapIdx]
      by_cases hn_range : n < r.organs.length
      · -- n is in range; look up the organ at position n
        have ho : r.organs[n]? = some r.organs[n] := List.getElem?_eq_getElem hn_range
        rw [ho]
        by_cases hn : n = i
        · subst hn
          have hi_eq : r.organs[n] = r.organs.get ⟨n, hn_range⟩ := by
            simp [List.get_eq_getElem]
          have hjlt : j < r.organs[n].decisions.length := by
            rw [hi_eq]; exact hj
          simp only [Option.map_some, ite_true]
          -- Goal: some (pendantValue (bumpDecisionAt ...)) = some (pendantValue ... + δ)
          exact congrArg some (pendantValue_bump r.organs[n] j δ hjlt)
        · simp [hn]
      · -- n is out of range; both sides are none
        have ho : r.organs[n]? = none := List.getElem?_eq_none (Nat.not_lt.mp hn_range)
        simp [ho]
    rw [hkey]
    apply List.sum_bump_at
    simpa [List.length_map] using hi
  -- Step 2: rootValue r + δ ≠ rootValue r since δ ≠ 0
  rw [hsum]
  omega

/-- **Pendant-sum well-formedness.** For any organ receipt, the pendant value
    is determined by the list of decision values — no hidden state. This is
    `rfl` and is exposed for downstream callers. -/
theorem pendantValue_def (r : OrganReceipt) :
    pendantValue r = (r.decisions.map (·.value)).sum := rfl

/-- **Root-sum well-formedness.** Same as above for the root. -/
theorem rootValue_def (r : KhipuRootReceipt) :
    rootValue r = (r.organs.map pendantValue).sum := rfl

/-- **Empty-organ root invariant.** A root with no organs has value 0. -/
theorem rootValue_empty (id : String) :
    rootValue { receiptId := id, organs := [] } = 0 := by
  simp [rootValue]

/-- **Single-organ root invariant.** A root with one organ has value equal to
    that organ's pendant value. -/
theorem rootValue_singleton (id : String) (o : OrganReceipt) :
    rootValue { receiptId := id, organs := [o] } = pendantValue o := by
  simp [rootValue]

end Lutar.Khipu
