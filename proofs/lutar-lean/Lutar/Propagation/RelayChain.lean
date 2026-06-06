/-
# R2-G5 — Qhapaq Ñan chasqui relay chain bounded latency

The Inka highway system (`Qhapaq Ñan`) carried messages via way-stations
(`tampu`) spaced ~2.5 km apart, each occupied by a runner (`chasqui`).
End-to-end latency is *additive in hop count*. If each hop's latency
is bounded by `cap`, the total latency is bounded by `chain.length · cap`.

We use this as the latency budget for receipt propagation across the
Ouroboros gateway. The Lean obligation `relay_chain_bounded_latency`
proves the linear bound by list induction.

Citation:
- Hyslop, J. (1984). *The Inka Road System.* Academic Press.
  ISBN 978-0-12-363460-3.

Status: complete proof, zero `sorry`.
-/
import Mathlib.Algebra.BigOperators.Group.List
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Linarith

namespace Lutar.Propagation.Relay

/-- A relay hop carries a non-negative per-hop latency. -/
structure RelayHop where
  latency : ℝ
  nonneg  : 0 ≤ latency

/-- A relay chain is a list of hops, ordered source → destination. -/
abbrev RelayChain := List RelayHop

/-- Total chain latency = sum of per-hop latencies. -/
def totalLatency (chain : RelayChain) : ℝ :=
  (chain.map (·.latency)).sum

/-- **R2-G5 — Linear latency bound.**

    If every hop has latency ≤ `cap`, then total ≤ |chain| · cap.
    Proof: induction on the list. -/
theorem relay_chain_bounded_latency
    (chain : RelayChain) (cap : ℝ) (hcap : 0 ≤ cap)
    (h_each : ∀ h ∈ chain, h.latency ≤ cap) :
    totalLatency chain ≤ (chain.length : ℝ) * cap := by
  induction chain with
  | nil => simp [totalLatency]
  | cons h tl ih =>
    have h_head : h.latency ≤ cap := h_each h (List.mem_cons_self _ _)
    have h_tail : ∀ x ∈ tl, x.latency ≤ cap := fun x hx =>
      h_each x (List.mem_cons_of_mem _ hx)
    have ih' := ih h_tail
    simp only [totalLatency] at ih'
    simp only [totalLatency, List.map_cons, List.sum_cons, List.length_cons,
               Nat.cast_add, Nat.cast_one, add_mul, one_mul]
    linarith

/-- Corollary: an empty chain has zero latency. -/
theorem totalLatency_nil : totalLatency ([] : RelayChain) = 0 := by
  simp [totalLatency]

/-- Corollary: total latency is non-negative. -/
theorem totalLatency_nonneg (chain : RelayChain) : 0 ≤ totalLatency chain := by
  induction chain with
  | nil => simp [totalLatency]
  | cons h tl ih =>
    simp only [totalLatency] at ih
    simp only [totalLatency, List.map_cons, List.sum_cons]
    linarith [h.nonneg]

end Lutar.Propagation.Relay
