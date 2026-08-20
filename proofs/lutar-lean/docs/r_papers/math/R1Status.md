# R1 Status — Composable Doctrine-Locked Systems

**Doctrine v6** | Last updated: 2024-12

## Per-Theorem Status Table

| # | Theorem / Lemma | File | Status | Method | Notes |
|---|----------------|------|--------|--------|-------|
| TH1 | `composition_preserves_doctrine` | `TH1_Composition.lean` | ✅ PROVED | `constructor` + struct fields | Main theorem; no sorry, no axiom |
| TH1.C | `composeList_doctrine_locked` | `TH1_Composition.lean` | ✅ PROVED | induction on list | Iterated composition corollary |
| TH1.M | `doctrine_monotone_threshold` | `TH1_Composition.lean` | ✅ PROVED | `le_trans` | Threshold strengthening |
| OV1 | `composition_overhead_bound` | `CompositionOverhead.lean` | ✅ PROVED | `foldl` induction | O(N·C) overhead bound |
| OV2 | `totalOverhead_append` | `CompositionOverhead.lean` | ✅ PROVED | `foldl_append` + omega | Additivity of overhead |
| OV3 | `composition_overhead_strict_bound` | `CompositionOverhead.lean` | ✅ PROVED | List split + linarith | Strict bound with slack system |
| AR1 | `robustness_preserved_by_composition` | `AdversarialRobustness.lean` | ✅ PROVED | `robustness_composes` | Main robustness theorem |
| AR2 | `adversary_budget_bounded` | `AdversarialRobustness.lean` | ✅ PROVED | `hS₁`, `hS₂` chaining | Adversary cannot exceed ε₂ |
| T1 | `test1_bot_le_l1` | `R1Tests.lean` | ✅ `decide` | kernel reduction | Bot ≤ L1 |
| T2 | `test2_l2_not_le_l1` | `R1Tests.lean` | ✅ `decide` | kernel reduction | Downgrade rejected |
| T3 | `test3_doctrine_predicate_exact` | `R1Tests.lean` | ✅ `decide` | kernel reduction | Exact threshold match |
| T4 | `test4_compose_labels` | `R1Tests.lean` | ✅ `rfl` | definitional eq | Composed label correctness |
| T5 | `test5_composition_preserves_doctrine_concrete` | `R1Tests.lean` | ✅ `decide` | kernel reduction | Concrete TH1 instance |

## Summary

- **Total theorems proved**: 13
- **Axioms introduced**: 0
- **Sorry count**: 0
- **Proof methods**: `decide`, `rfl`, `constructor`, `induction`, `calc`, `omega`, `linarith`
- **Mathlib dependencies**: `Data.Finset.Basic`, `Data.List.Basic`, `Order.BoundedOrder`, `Algebra.Order.Ring`, `Analysis.SpecialFunctions`, `Topology.MetricSpace`

## Doctrine v6 Compliance

All theorems operate within the Doctrine v6 label lattice `{Bot, L1, L2, Top}`.
The `noDowngrade` invariant is enforced structurally in `LutarSystem`, ensuring
doctrine-locking cannot be violated by composition. The `Compatible` predicate
gatekeeps composition, preventing information downgrade at system interfaces.
