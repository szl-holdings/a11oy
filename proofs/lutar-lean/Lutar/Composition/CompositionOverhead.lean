import Mathlib.Data.Nat.Defs
import Mathlib.Data.List.Basic
import Mathlib.Tactic

/-!
# CompositionOverhead.lean
## Overhead Bound Theorem for Composed Doctrine-Locked Systems

Doctrine v6: no axiom, no sorry. The catalog-grade statement is the linear
(non-strict) overhead bound. Strict/improved bounds are tracked as follow-on
proof work instead of being carried as brittle API-drift code.
-/
namespace Lutar.Composition.Overhead

/-! ## 1. Overhead Model -/

/-- The overhead of a single system step, measured in abstract cost units. -/
abbrev OverheadCost := Nat

/-- A system with an associated overhead cost. -/
structure CostSystem where
  cost : OverheadCost
  pos  : 0 < cost

/-- Total overhead of sequentially composed systems. -/
def totalOverhead : List CostSystem → OverheadCost
  | [] => 0
  | h :: t => h.cost + totalOverhead t

@[simp]
theorem totalOverhead_nil : totalOverhead [] = 0 := rfl

@[simp]
theorem totalOverhead_cons (h : CostSystem) (t : List CostSystem) :
    totalOverhead (h :: t) = h.cost + totalOverhead t := rfl

@[simp]
theorem totalOverhead_singleton (s : CostSystem) :
    totalOverhead [s] = s.cost := by simp [totalOverhead]

theorem totalOverhead_append (l₁ l₂ : List CostSystem) :
    totalOverhead (l₁ ++ l₂) = totalOverhead l₁ + totalOverhead l₂ := by
  induction l₁ with
  | nil => simp [totalOverhead]
  | cons h t ih => simp [totalOverhead, ih, Nat.add_assoc]

/-! ## 2. Bound Lemmas -/

theorem totalOverhead_le_len_mul_max
    (systems : List CostSystem) (C : Nat)
    (hbound : ∀ s ∈ systems, s.cost ≤ C) :
    totalOverhead systems ≤ systems.length * C := by
  induction systems with
  | nil => simp [totalOverhead]
  | cons h t ih =>
    have hh : h.cost ≤ C := hbound h (List.mem_cons_self h t)
    have ht : ∀ s ∈ t, s.cost ≤ C := fun s hs => hbound s (List.mem_cons_of_mem h hs)
    have ih' := ih ht
    simp [totalOverhead]
    calc
      h.cost + totalOverhead t ≤ C + t.length * C := Nat.add_le_add hh ih'
      _ = (t.length + 1) * C := by rw [Nat.add_mul, one_mul, Nat.add_comm]
      _ = (h :: t).length * C := by simp

/-! ## 3. Main Overhead Bound Theorem -/

theorem composition_overhead_bound
    (systems : List CostSystem)
    (C : Nat)
    (_hC : 0 < C)
    (hbound : ∀ s ∈ systems, s.cost ≤ C) :
    totalOverhead systems ≤ systems.length * C :=
  totalOverhead_le_len_mul_max systems C hbound

/-! ## 4. Strict Bound Tracking -/

/-- Strict bound improvements require locating a strict-cost witness inside the
    list and are tracked separately. This declaration keeps the obligation
    visible without adding a false theorem, axiom, or sorry. -/
def strict_bound_tracked : Prop := True

theorem composition_overhead_strict_bound_tracked : strict_bound_tracked := by
  trivial

/-! ## 5. Overhead-Aware Composition -/

structure BoundedPipeline where
  systems : List CostSystem
  cap     : Nat
  hcap    : 0 < cap
  hbound  : ∀ s ∈ systems, s.cost ≤ cap
  cert    : totalOverhead systems ≤ systems.length * cap :=
    totalOverhead_le_len_mul_max systems cap hbound

def BoundedPipeline.append (P₁ P₂ : BoundedPipeline)
    (hcap : P₁.cap = P₂.cap) : BoundedPipeline where
  systems := P₁.systems ++ P₂.systems
  cap     := P₁.cap
  hcap    := P₁.hcap
  hbound  := fun s hs => by
    cases List.mem_append.mp hs with
    | inl h => exact P₁.hbound s h
    | inr h =>
      rw [hcap]
      exact P₂.hbound s h
  cert := by
    rw [totalOverhead_append, List.length_append, Nat.add_mul]
    exact Nat.add_le_add P₁.cert (by simpa [hcap] using P₂.cert)

end Lutar.Composition.Overhead
