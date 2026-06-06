/-
# TH-V18-07 — Feynman Citation Chain Integrity

Theorems about the Feynman → SZL citation lineage chain.
The chain has exactly 4 steps, all citations nonempty, and the first step
is the Feynman 1949 paper. Composes Lutar.Feynman.FeynmanLineage.

## Lean Czar status: valid
## Proof method: exact + decide (compose Lutar.Feynman.FeynmanLineage)
## Axioms used: none
## Composes: Lutar.Feynman.FeynmanLineage (compiled, 0 sorry, 0 axiom)
## Citations:
  - Feynman (1949) DOI 10.1103/PhysRev.76.769
  - Witten (1989) DOI 10.1007/BF01217730
  - Bar-Natan (1995) DOI 10.1016/0040-9383(95)93237-2
  - Kontsevich (1993) MR 1237836
-/
import Lutar.Feynman.FeynmanLineage

namespace Lutar.Thesis.Feynman

open Lutar.Feynman.Lineage

/-- **TH-V18-07**: the Feynman → SZL citation chain has exactly 4 steps.
    Composes: Lutar.Feynman.Lineage.chain_length (compiled). -/
theorem th_v18_07_chain_length_4 :
    feynmanToSZLChain.length = 4 :=
  chain_length

/-- **TH-V18-07b**: every step in the chain has a nonempty citation.
    Composes: Lutar.Feynman.Lineage.chain_citations_nonempty (compiled). -/
theorem th_v18_07b_all_citations_nonempty :
    ∀ step ∈ feynmanToSZLChain, step.citation ≠ "" :=
  chain_citations_nonempty

/-- **TH-V18-07c**: the chain is nonempty (at least one citation step).
    Follows from chain_length = 4 > 0. -/
theorem th_v18_07c_chain_nonempty :
    feynmanToSZLChain ≠ [] := by
  intro h
  have := chain_length
  rw [h] at this
  exact absurd this (by decide)

/-- **TH-V18-07d**: the first author_year is "Feynman 1949b". -/
theorem th_v18_07d_first_step_feynman :
    feynmanToSZLChain[0]?.map (·.author_year) = some "Feynman 1949b" := by decide

/-- **TH-V18-07e**: the last step is the SZL Knot Calculus. -/
theorem th_v18_07e_last_step_szl :
    feynmanToSZLChain[3]?.map (·.author_year) = some "SZL Knot Calculus (v15/v16)" := by decide

end Lutar.Thesis.Feynman
