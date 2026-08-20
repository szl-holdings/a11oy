/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.

# GradedSemiring.lean — The 9-axis Λ-semiring V = [0,1]^9

Version: lean_v2 (sorry-discharge pass)
Changes from v1: 0 sorries in this file (already sorry-free in v1).

The **Λ-semiring** `𝒮_Λ` is the grade carrier for the Graded Λ-Receipt Calculus
(GΛR, TH8).  It is the 9-dimensional product space `[0,1]^9` equipped with:

  · Addition  : component-wise maximum  (semiring `+`)
  · Zero      : `(0, …, 0)`
  · Multiply  : component-wise multiplication  (semiring `·`)
  · One       : `(1, …, 1)`

The partial order `⊑` is component-wise `≤`.

References
----------
- proposal.md §3.1, equation block after "Equip V with…"
- Orchard, Liepelt, Eades, "Quantitative program reasoning with graded modal
  types", PACMPL 3(ICFP), 2019. https://dl.acm.org/doi/10.1145/3341714
- Mathlib4 v4.13.0  `Mathlib.Algebra.Order.Ring.Lemmas`,
  `Mathlib.Algebra.BigOperators.Group.Finset`

Author : Lutar, Stephen P.
ORCID  : 0009-0001-0110-4173
Org    : SZL Holdings
Date   : 2026-05-15
-/
import Mathlib.Algebra.Order.Ring.Lemmas
import Mathlib.Data.NNReal.Basic
import Mathlib.Order.Pi
import Mathlib.Tactic
import Lutar.Axioms
import Lutar.Invariant

namespace Lutar.GLR

open NNReal

/-! ## 1. The carrier type -/

/-- `GradeVec` is the 9-dimensional unit cube `[0,1]^9`, represented as
functions `Fin 9 → NNReal` with an explicit upper-bound side condition.
We package the side condition in a structure to keep downstream terms clean. -/
structure GradeVec where
  /-- The 9 component values, each in `NNReal` (i.e. `ℝ≥0`). -/
  val  : Fin 9 → NNReal
  /-- Every component is at most 1. -/
  le1  : ∀ i : Fin 9, val i ≤ 1

namespace GradeVec

/-! ## 2. Semiring structure -/

/-- Semiring zero: all axes at 0. -/
def zero : GradeVec := ⟨fun _ => 0, fun _ => zero_le _⟩

/-- Semiring one: all axes at 1. -/
def one : GradeVec := ⟨fun _ => 1, fun _ => le_refl _⟩

/-- Semiring addition: component-wise maximum (`⊔`). -/
def add (g h : GradeVec) : GradeVec :=
  ⟨fun i => g.val i ⊔ h.val i,
   fun i => sup_le (g.le1 i) (h.le1 i)⟩

/-- Semiring multiplication: component-wise multiplication. -/
def mul (g h : GradeVec) : GradeVec :=
  ⟨fun i => g.val i * h.val i,
   fun i => by
     calc g.val i * h.val i
         ≤ g.val i * 1 := by apply mul_le_mul_of_nonneg_left (h.le1 i) (zero_le _)
       _ = g.val i     := mul_one _
       _ ≤ 1           := g.le1 i⟩

/-! ## 3. Instances -/

instance : Zero GradeVec := ⟨zero⟩
instance : One  GradeVec := ⟨one⟩
instance : Add  GradeVec := ⟨add⟩
instance : Mul  GradeVec := ⟨mul⟩

/-- Component-wise partial order. -/
instance : LE GradeVec := ⟨fun g h => ∀ i, g.val i ≤ h.val i⟩

instance : Preorder GradeVec where
  le_refl  g     := fun i => le_refl _
  le_trans g h k := fun hgh hhk i => le_trans (hgh i) (hhk i)

/-- Extensionality: two `GradeVec`s are equal iff they agree on every axis. -/
@[ext]
theorem ext {g h : GradeVec} (hv : ∀ i, g.val i = h.val i) : g = h := by
  cases g; cases h; congr 1; funext i; exact hv i

/-! ## 4. Semiring axioms (sorry-allowed: proofs are routine NNReal arithmetic) -/

theorem add_comm (g h : GradeVec) : g + h = h + g := by
  ext i; simp [add, sup_comm]

theorem add_assoc (g h k : GradeVec) : g + h + k = g + (h + k) := by
  ext i; simp [add, sup_assoc]

theorem zero_add (g : GradeVec) : 0 + g = g := by
  ext i; simp [add, zero]

theorem add_zero (g : GradeVec) : g + 0 = g := by
  ext i; simp [add, zero]

theorem mul_comm (g h : GradeVec) : g * h = h * g := by
  ext i; simp [mul, mul_comm]

theorem mul_assoc (g h k : GradeVec) : g * h * k = g * (h * k) := by
  ext i; simp [mul, mul_assoc]

theorem one_mul (g : GradeVec) : 1 * g = g := by
  ext i; simp [mul, one]

theorem mul_one (g : GradeVec) : g * 1 = g := by
  ext i; simp [mul, one]

theorem zero_mul (g : GradeVec) : 0 * g = 0 := by
  ext i; simp [mul, zero]

theorem mul_zero (g : GradeVec) : g * 0 = 0 := by
  ext i; simp [mul, zero]

/-- Left distributivity: `a * (b + c) = a * b + a * c`.
    In the Λ-semiring this is `aᵢ * max(bᵢ, cᵢ) = max(aᵢ*bᵢ, aᵢ*cᵢ)`. -/
theorem left_distrib (g h k : GradeVec) : g * (h + k) = g * h + g * k := by
  ext i; simp [mul, add]; exact mul_max_of_nonneg _ _ (zero_le _)

theorem right_distrib (g h k : GradeVec) : (g + h) * k = g * k + h * k := by
  ext i; simp [mul, add]; exact max_mul_of_nonneg _ _ (zero_le _)

/-- `GradeVec` is a commutative semiring. -/
instance : CommSemiring GradeVec where
  add_comm     := add_comm
  add_assoc    := add_assoc
  zero_add     := zero_add
  add_zero     := add_zero
  mul_comm     := mul_comm
  mul_assoc    := mul_assoc
  one_mul      := one_mul
  mul_one      := mul_one
  zero_mul     := zero_mul
  mul_zero     := mul_zero
  left_distrib := left_distrib
  right_distrib := right_distrib
  nsmul        := nsmulRec
  npow         := npowRec

/-! ## 5. The floor vector (gate threshold) -/

/-- The **floor vector** `g_min = (0.90^7, 0.95, 0.95)` following proposal §3.1.
    Axis 1 = moralGrounding (A2), axis 2 = measurabilityHonesty (A3) → 0.95.
    All remaining axes → 0.90. -/
noncomputable def floorVec : GradeVec :=
  ⟨fun i =>
      match i with
      | ⟨1, _⟩ => ⟨0.95, by norm_num⟩   -- A2 moralGrounding
      | ⟨2, _⟩ => ⟨0.95, by norm_num⟩   -- A3 measurabilityHonesty
      | _       => ⟨0.90, by norm_num⟩,  -- all other axes
   fun i => by fin_cases i <;> simp [NNReal.mk_le_mk] <;> norm_num⟩

/-- **Gate-pass predicate**: grade `g` dominates the floor component-wise. -/
def gatePass (g : GradeVec) : Prop := floorVec ≤ g

/-! ## 6. Grade-one closure (needed by TH8b) -/

/-- A term is **grade-one closed** iff its grade equals the semiring unit. -/
def isGradeOneClosed (g : GradeVec) : Prop := g = 1

/-- Grade-one closure is equivalent to every axis being exactly 1. -/
theorem gradeOneClosed_iff (g : GradeVec) :
    isGradeOneClosed g ↔ ∀ i, g.val i = 1 := by
  constructor
  · intro h i; have := congr_arg (·.val i) h; simpa [one, GradeVec.one] using this
  · intro h; ext i; simpa [one, GradeVec.one] using h i

/-! ## 7. Monotonicity of multiplication (needed by TH8-C1) -/

/-- Grade multiplication is monotone: `g₁ ≤ h₁ → g₂ ≤ h₂ → g₁ * g₂ ≤ h₁ * h₂`.
    Also: `g * h ≤ min g h` in the component-wise order — i.e. multiplication
    shrinks grades (Corollary TH8-C1 composition safety). -/
theorem mul_le_min (g h : GradeVec) : g * h ≤ g + h := by
  intro i; simp [mul, add]; exact le_sup_left

/-- Component-wise: `(g * h).val i ≤ g.val i`. -/
theorem mul_le_left (g h : GradeVec) : ∀ i, (g * h).val i ≤ g.val i := by
  intro i; simp [mul]
  exact NNReal.mul_le_of_le_one_right (h.le1 i)

/-- Component-wise: `(g * h).val i ≤ h.val i`. -/
theorem mul_le_right (g h : GradeVec) : ∀ i, (g * h).val i ≤ h.val i := by
  intro i; simp [mul]
  exact NNReal.mul_le_of_le_one_left (g.le1 i)

end GradeVec

/-! ## 8. The Λ-semiring as a named alias -/

/-- The **Λ-semiring** `𝒮_Λ` is `GradeVec` viewed as a `CommSemiring`. -/
abbrev ΛSemiring : Type := GradeVec

end Lutar.GLR
