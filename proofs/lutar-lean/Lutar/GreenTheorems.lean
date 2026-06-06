/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Lutar — Green Theorems Index (Λ aggregator)

A discoverable, single-file index of the **fully-discharged, Lake-verified**
theorems about the Lutar Invariant `Λ k` (the weighted geometric mean with
Egyptian unit-fraction weights `1/k`).

Every declaration in this file is completely proved — there is no
proof-deferred placeholder anywhere in its dependency chain. Each entry simply
*names* and re-exports a theorem that is already machine-checked in
`Lutar/Invariant.lean`, `Lutar/Bound.lean`, and `Lutar/Uniqueness.lean`, so that
a reviewer (or the UDS Fleet Registry) can point at one file and one canonical
name.

## Verified by Lake CI

The flagship green theorem is `Lutar.green_lambda_satisfies_lutar_axioms`:

    theorem green_lambda_satisfies_lutar_axioms {k : ℕ} (hk : 0 < k) :
        LutarAxioms (Λ k)

It states that the concrete Lutar Invariant `Λ k` satisfies all four Lutar
axioms (A1 monotone, A2 1-homogeneous, A3 Egyptian-exact diagonal commitment,
A4 bounded-by-max). Its proof is the fully-discharged `lambda_satisfiesAxioms`
assembly, whose four components are each kernel-checked:

  * A1 — `lambda_isMonotone`        (Finset.prod_le_prod + NNReal.rpow_le_rpow)
  * A2 — `lambda_isHomogeneous`     (Finset.prod_mul_distrib + NNReal.mul_rpow)
  * A3 — `lambda_isEgyptianExact`   (a3_normalize_proof, Invariant.lean)
  * A4 — `lambda_isBounded`         (Λ_le_max, Bound.lean)

## Scope note (Doctrine v11 LOCKED 749/14/163)

This index introduces **no new axioms** and **no new proof placeholders** — it
only assigns public, citable names to already-discharged facts. `Λ` remains
Conjecture 1; the full uniqueness theorem (TH10 / `lutar_unique`) still carries
the documented CAUCHY_ND residual in `Lutar/Uniqueness.lean` and is *not*
re-exported here.
-/
import Lutar.Axioms
import Lutar.Invariant
import Lutar.Bound
import Lutar.Uniqueness

namespace Lutar

open NNReal

/-- **GREEN — Λ satisfies all four Lutar axioms (flagship index entry).**

    The Lutar Invariant `Λ k` (geometric mean with unit-fraction weights)
    satisfies A1 (monotone), A2 (1-homogeneous), A3 (Egyptian-exact diagonal
    commitment), and A4 (bounded by the max axis). Fully discharged,
    Lake-verified.

    This is the canonical named green theorem about the Λ aggregator. Its proof
    is the already-discharged `lambda_satisfiesAxioms`. -/
theorem green_lambda_satisfies_lutar_axioms {k : ℕ} (hk : 0 < k) :
    LutarAxioms (Λ k) :=
  lambda_satisfiesAxioms hk

/-- **GREEN — Λ is monotone (A1).** Increasing any axis cannot decrease `Λ k`.
    Re-export of the fully-discharged `lambda_isMonotone`. -/
theorem green_lambda_monotone {k : ℕ} (hk : 0 < k) :
    IsMonotone (Λ k) :=
  lambda_isMonotone hk

/-- **GREEN — Λ is 1-homogeneous (A2).** Scaling every axis by `c` scales the
    output by `c`. Re-export of the fully-discharged `lambda_isHomogeneous`. -/
theorem green_lambda_homogeneous {k : ℕ} (hk : 0 < k) :
    IsHomogeneous (Λ k) :=
  lambda_isHomogeneous hk

/-- **GREEN — Λ is bounded above by the max axis (A4).** A passing `Λ k` value
    never exceeds the best axis. Re-export of the fully-discharged `Λ_le_max`. -/
theorem green_lambda_le_max {k : ℕ} (hk : 0 < k) (x : Axes k) :
    Λ k x ≤ Finset.univ.sup' ⟨⟨0, hk⟩, Finset.mem_univ _⟩ x :=
  Λ_le_max hk x

end Lutar
