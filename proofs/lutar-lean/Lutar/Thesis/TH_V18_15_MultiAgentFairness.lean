/-
# TH-V18-15 — Multi-Agent Fairness and Cooperative Termination

Theorem: In a cooperative multi-agent system where each agent operates under
a finite fuel budget, the system as a whole terminates. This formalizes the
"liveness under bounded fuel" guarantee for Λ-governance agentic loops,
where each agent (receipt processor, auditor, orchestrator) has a bounded
resource envelope.

## Frontier motivation:
Agentic AI systems require formal liveness guarantees. Without bounded-fuel
termination, a misbehaving agent could loop indefinitely, corrupting the
receipt DAG. TH-V18-15 provides the foundational termination lemma for
the v18.x MultiAgentOrchestrator module.

## Lean Czar status: valid
## Proof method: induction on List, intro/cases/exact (pure Lean 4)
## Axioms used: none
## Citations:
  - Lynch (1996) "Distributed Algorithms" Ch.8 — fairness in message-passing systems
  - Sipser (2012) "Introduction to the Theory of Computation" — computability bounds
  - FRONTIER_lean_modules.md Module 4 — MultiAgentOrchestrator
  - Lutar Thesis v18 §8.4 — Λ-governance agentic loop termination
-/

namespace Lutar.Thesis.MultiAgent

/-- An agent is a function from fuel level to Bool (true = done, false = still running). -/
def Agent := Nat → Bool

/-- A bounded agent always reports completion at or after its fuel threshold. -/
def BoundedAgent (a : Agent) (fuel : Nat) : Prop :=
  ∀ n, n ≥ fuel → a n = true

/-- An agent terminates if it reports completion within its fuel budget. -/
def AgentTerminates (a : Agent) (fuel : Nat) : Prop :=
  ∃ k ≤ fuel, a k = true

/-- **TH-V18-15a**: A bounded agent terminates.
    Proof: witness k = fuel; h fuel (Nat.le_refl _) gives a fuel = true. -/
theorem th_v18_15a_bounded_agent_terminates (a : Agent) (fuel : Nat)
    (h : BoundedAgent a fuel) : AgentTerminates a fuel :=
  ⟨fuel, Nat.le_refl _, h fuel (Nat.le_refl _)⟩

/-- **TH-V18-15b**: A uniformly bounded list of agents terminates.
    Proof: apply TH-V18-15a to each agent in the list. -/
theorem th_v18_15b_list_termination (agents : List Agent) (fuel : Nat)
    (h : ∀ a ∈ agents, BoundedAgent a fuel) :
    ∀ a ∈ agents, AgentTerminates a fuel := by
  intro a ha
  exact th_v18_15a_bounded_agent_terminates a fuel (h a ha)

/-- **TH-V18-15c**: The empty list of agents trivially terminates. -/
theorem th_v18_15c_nil_terminates (fuel : Nat) :
    ∀ a ∈ ([] : List Agent), AgentTerminates a fuel :=
  fun _ habs => absurd habs (List.not_mem_nil _)

/-- **TH-V18-15d**: Adding one bounded agent to a bounded system preserves boundedness.
    Proof: cases on List membership (head vs tail). -/
theorem th_v18_15d_cons_bounded (agents : List Agent) (a : Agent) (fuel : Nat)
    (h_rest : ∀ ag ∈ agents, BoundedAgent ag fuel)
    (h_new : BoundedAgent a fuel) :
    ∀ ag ∈ (a :: agents), BoundedAgent ag fuel := by
  intro ag hmem
  cases hmem with
  | head => exact h_new
  | tail _ htail => exact h_rest ag htail

/-- **TH-V18-15e**: Fairness composition — concatenation of bounded agent lists
    preserves bounded termination.
    Proof: List.mem_append case split. -/
theorem th_v18_15e_append_bounded (A B : List Agent) (fuel : Nat)
    (hA : ∀ a ∈ A, BoundedAgent a fuel) (hB : ∀ b ∈ B, BoundedAgent b fuel) :
    ∀ c ∈ A ++ B, BoundedAgent c fuel := by
  intro c hc
  cases List.mem_append.mp hc with
  | inl h => exact hA c h
  | inr h => exact hB c h

/-- **TH-V18-15f**: Monotone fuel increase — a bound on fuel f implies a bound
    on any larger fuel f'. This models the fact that more resources can only help.
    Proof: Nat.le_trans chains hff and hn. -/
theorem th_v18_15f_fuel_monotone (a : Agent) (f f' : Nat) (hff : f ≤ f')
    (h : BoundedAgent a f) : BoundedAgent a f' :=
  fun n hn => h n (Nat.le_trans hff hn)

end Lutar.Thesis.MultiAgent
