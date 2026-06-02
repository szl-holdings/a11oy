/-
  SPDX-License-Identifier: Apache-2.0
  © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED 749/14/163

  Lutar Anchor A36 — DualStreamRoutingAxiom  (axis: Hickok · status: ts-only)

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ CITATION                                                                  │
  │   Hickok, G. & Poeppel, D. (2007). "The cortical organization of speech  │
  │   processing." Nature Reviews Neuroscience 8, 393–402.                    │
  │   DOI: 10.1038/nrn2113   https://doi.org/10.1038/nrn2113                  │
  │                                                                           │
  │ CLAIM (the dual-stream model)                                             │
  │   Speech processing is organised into two largely segregated cortical    │
  │   streams: a DORSAL stream (sensorimotor / action — mapping sound onto    │
  │   articulatory representations) and a VENTRAL stream (meaning /           │
  │   comprehension — mapping sound onto conceptual representations).         │
  │                                                                           │
  │ A11OY MAPPING                                                             │
  │   Every Amaru tick MUST route through EXACTLY ONE of {dorsal, ventral}:   │
  │   never both, never neither. Dorsal = action/repetition (imperatives);   │
  │   ventral = meaning/comprehension (questions/explanations). A request     │
  │   the rule-based classifier cannot disambiguate is marked `dual` and      │
  │   the gate FAILS — A36 says exactly one stream.                           │
  └─────────────────────────────────────────────────────────────────────────┘

  STATUS: ts-only. This Lean anchor is the formal statement of the runtime
  TypeScript gate (packages/policy/src/gates/dualStreamRouting_gate.ts). The
  proof is `sorry` (honest) — the operational guarantee is provided by the
  TS gate + the dual-stream router middleware, not yet by a closed Lean proof.
-/

namespace Lutar.Gate.DualStreamRouting

/-- The two cortical processing streams of the Hickok–Poeppel dual-stream model. -/
inductive Stream where
  | dorsal   -- action / sensorimotor (repetition, imperatives)
  | ventral  -- meaning / comprehension (questions, explanations)
  deriving DecidableEq, Repr

/-- An Amaru routing decision for a single tick. -/
structure Tick where
  stream : Stream

/-- Exclusive-or over the two routing predicates: a tick is dorsal XOR ventral. -/
def routesExactlyOne (t : Tick) : Prop :=
  (t.stream = Stream.dorsal) ≠ (t.stream = Stream.ventral)

/--
  A36 — DualStreamRoutingAxiom.

  Every tick routes through exactly one of {dorsal, ventral} — never both,
  never neither. This is stated as an `axiom` (the Hickok–Poeppel architecture
  is taken as a modelling primitive, matching leanStatus = "axiom").
-/
axiom dual_stream_routing_axiom : ∀ (t : Tick), routesExactlyOne t

/--
  Soundness companion (theorem form, ts-only): a tick that the classifier could
  resolve to a single stream satisfies the exactly-one routing property.
  Proof deferred (`sorry`) — honest ts-only status; the runtime guarantee is the
  TS gate + router middleware.
-/
theorem dual_stream_routing_sound (t : Tick) : routesExactlyOne t := by
  sorry

end Lutar.Gate.DualStreamRouting
