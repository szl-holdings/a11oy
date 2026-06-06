# A15 Status — Persistent Homology

**Doctrine v6** | Last updated: 2024-12

## Overview

A15 formalises the Lutar topology layer using persistent homology. The primary
object is the H₀ Betti number (connected component count) as a function of the
Rips filtration parameter Λ (note: Λ-uniqueness is Conjecture 1 — NOT a theorem). All Lean 4 + Mathlib lemmas target:

## Per-Theorem Status Table

| # | Theorem / Lemma | File | Status | Method | References |
|---|----------------|------|--------|--------|-----------|
| PH1 | `componentCount_antitone` | `PersistentHomologyChain.lean` | ✅ PROVED | `Fintype.card_le_of_injective` | ELZ 2002 §3 |
| PH2 | `h0_at_lambda_threshold` | `PersistentHomologyChain.lean` | ✅ PROVED | `Fintype.card_le_of_injective` | ELZ 2002 §3 (h0-at-Λ-threshold; references an ELZ proposition, NOT the Λ-uniqueness Conjecture) |
| PH3 | `h0_euler_bound` | `PersistentHomologyChain.lean` | ✅ PROVED | `omega` | Euler formula |
| PH4 | `h0_zero_threshold_isolated` | `PersistentHomologyChain.lean` | ✅ PROVED | `ext` + `linarith` | isolation at Λ=0 |
| PH5 | `persistence_nonneg` | `PersistentHomologyChain.lean` | ✅ PROVED | `linarith` | birth ≤ death |
| PH6 | `h0_persistence_pairs_count` | `PersistentHomologyChain.lean` | ✅ PROVED | `omega` | n-1 merges + 1 essential |
| PH7 | `FiltrationMono` | `PersistentHomologyChain.lean` | ✅ PROVED | `le_trans` | RipsGraph monotonicity |

## Summary

- **Total theorems proved**: 7
- **Axioms introduced**: 0
- **Sorry count**: 0
- **Lean 4 + Mathlib components**: `SimpleGraph`, `ConnectedComponent`, `Fintype.card`,
  `Finset.card`, `SimpleGraph.Reachable`, `SimpleGraph.edgeFinset`
- **Proof methods**: `Fintype.card_le_of_injective`, `le_trans`, `omega`, `linarith`, `ext`, `simp`

## References

1. Edelsbrunner, H., Letscher, D., & Zomorodian, A. (2002).
   "Topological Persistence and Simplification".
   *Discrete & Computational Geometry*, **28**(4), 511–533.
   DOI: **10.1007/s00454-002-2885-2**

## Doctrine v6 Compliance

The A15 module uses only combinatorial graph theory (`SimpleGraph` in Mathlib)
and real-valued distances. No differential geometry or algebraic topology
abstractions beyond what Mathlib provides are assumed. The H₀ count is directly
computable via `Fintype.card (G.ConnectedComponent)`. No Bekenstein-bound
arguments are used.
