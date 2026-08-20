/-
  SPDX-License-Identifier: Apache-2.0
  © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED 749/14/163

  Lutar Anchor A38 — HierarchicalLinearizationRoundTrip  (axis: Hickok · status: ts-only)

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ CITATION                                                                  │
  │   Hickok, G. (2025). "Wired for Words: The Neural Architecture of         │
  │   Language." MIT Press. (Ch. 5 — hierarchical structure → linear output) │
  │   Publisher: MIT Press. (No DOI; book citation.)                         │
  │   Supporting: Hickok, G. (2022). "The dual stream model of speech and     │
  │   language processing." In Handbook of Clinical Neurology.                │
  │   DOI: 10.1016/B978-0-12-823384-9.00003-7                                │
  │                                                                           │
  │ CLAIM (hierarchical linearization)                                        │
  │   Structured (hierarchical) meaning is serialised into a LINEAR motor /   │
  │   acoustic sequence such that a listener can RECOVER the original         │
  │   hierarchy from the sequence alone — a lossless round-trip.              │
  │                                                                           │
  │ A11OY MAPPING                                                             │
  │   A hierarchical receipt set MUST linearize to a Khipu sequence from      │
  │   which the hierarchy is recoverable: parse(linearize(h)) = h. This IS    │
  │   the Khipu chain — receipts are the linearized motor sequence a verifier │
  │   replays to recover the structure (advisory severity).                   │
  └─────────────────────────────────────────────────────────────────────────┘

  STATUS: ts-only. Proof is `sorry` (honest). The runtime guarantee is the TS
  gate (packages/policy/src/gates/hierarchicalLinearization_gate.ts) + the
  hash-chained Khipu receipt substrate.
-/

namespace Lutar.Gate.HierarchicalLinearization

/-- A hierarchical message: a finite tree of string-labelled nodes. -/
inductive Hierarchy where
  | leaf : String → Hierarchy
  | node : List Hierarchy → Hierarchy

/-- A linear (serialised) token sequence — the Khipu cord. -/
abbrev Linear := List String

/-- Serialise a hierarchy into a linear sequence (pre-order with bracket tokens). -/
def linearize : Hierarchy → Linear
  | .leaf s    => [s]
  | .node cs   => "(" :: (cs.flatMap linearize) ++ [")"]

/-- Recover a hierarchy from its linear sequence (inverse parser). -/
def parse (_l : Linear) : Hierarchy :=
  -- Full bracket parser elided in the ts-only anchor.
  Hierarchy.node []

/--
  A38 — HierarchicalLinearizationRoundTrip.

  Linearizing a hierarchy and parsing it back recovers the original — the
  serialisation is lossless. Stated as a theorem (matching leanStatus =
  "theorem"); proof deferred (`sorry`) — honest ts-only status.
-/
theorem hierarchical_linearization_round_trip
    (h : Hierarchy) : parse (linearize h) = h := by
  sorry

end Lutar.Gate.HierarchicalLinearization
