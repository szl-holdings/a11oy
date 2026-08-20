/-
# TH-V18-01 — Agent Loop Termination (Frontier v18.0, Module 5)

Theorem: under a DPI-bounded turn budget, the Λ-gated agent state machine
reaches the `Done` state in finitely many steps.

## Proof strategy (proof-by-composition)
Direct induction on the budget `b`. Each `Running (b+1)` step reduces to
`Running b`; `Running 0` steps directly to `Done`. No axiom needed —
this is a pure structural termination argument on `Nat`.

## Lean Czar status: valid
## Proof method: induction on Nat budget
## Axioms used: none
## Originates from: FRONTIER_lean_modules.md Module 5 (AgentLoop)
## Citations:
  - Lutar.Bound (v14 PR #58, DOI 10.5281/zenodo.20424992) — DPI budget concept
  - leanprover-community/mathlib4 — Nat induction (Apache-2.0)
  - a11oy-code spec v17.1.1 — TypeScript LambdaGate reference
-/

namespace Lutar.Thesis.AgentLoop

/-- Generic n-fold function iteration. -/
def iterate {α : Type} (f : α → α) : Nat → α → α
  | 0,   x => x
  | n+1, x => iterate f n (f x)

/-- A minimal Λ-gated agent state machine.
    `Running b` means b turns of budget remain; `Done` is terminal. -/
inductive AgentState : Type where
  | Running (budget : Nat) : AgentState
  | Done                   : AgentState
  deriving DecidableEq

/-- One step of the agent loop: decrement budget or terminate. -/
def agentStep : AgentState → AgentState
  | .Running 0      => .Done
  | .Running (b+1)  => .Running b
  | .Done           => .Done

/-- **Lemma TH-V18-01a**: `Running 0` terminates in exactly 1 step. -/
theorem running_zero_step : agentStep (.Running 0) = .Done := rfl

/-- **Lemma TH-V18-01b**: `Running (b+1)` reduces budget by 1. -/
theorem running_succ_step (b : Nat) :
    agentStep (.Running (b+1)) = .Running b := rfl

/-- **Lemma TH-V18-01c**: once Done, always Done. -/
theorem done_is_fixed : agentStep .Done = .Done := rfl

/-- **Lemma TH-V18-01d**: any `Running b` terminates in b+1 steps.
    Proof: induction on b; base: Running 0 → Done in 1 step (rfl);
    step: Running (m+1) → Running m in one step, then apply IH. -/
theorem terminates_from_running (b : Nat) :
    iterate agentStep (b + 1) (.Running b) = .Done := by
  induction b with
  | zero => simp [iterate, agentStep]
  | succ m ih =>
    show iterate agentStep (m + 1) (agentStep (.Running (m + 1))) = .Done
    rw [show agentStep (.Running (m + 1)) = .Running m from rfl]
    exact ih

/-- **TH-V18-01 — Agent Loop Terminates**.
    For any initial state `s₀`, the loop reaches `Done` in finitely many steps.
    Proved by case analysis on the state constructor, then induction on budget. -/
theorem th_v18_01_terminates (s₀ : AgentState) :
    ∃ n : Nat, iterate agentStep n s₀ = .Done := by
  cases s₀ with
  | Done    => exact ⟨0, rfl⟩
  | Running b => exact ⟨b + 1, terminates_from_running b⟩

/-- **Corollary TH-V18-01e**: `Done` is the only fixed point of `agentStep`.
    Proof: match on state; for Running cases, agentStep changes the state. -/
theorem done_unique_fixed_point (s : AgentState) (h : agentStep s = s) :
    s = .Done := by
  match s with
  | .Done => rfl
  | .Running 0 => simp [agentStep] at h
  | .Running (b+1) =>
    rw [show agentStep (.Running (b+1)) = .Running b from rfl] at h
    exact absurd h (by simp)

end Lutar.Thesis.AgentLoop
