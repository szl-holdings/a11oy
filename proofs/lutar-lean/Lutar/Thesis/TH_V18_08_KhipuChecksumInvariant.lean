/-
# TH-V18-08 — Khipu Checksum Invariant (composition of Lutar.Khipu)

Theorem: the Khipu root value equals the sum of pendant values.
Any bump (δ ≠ 0) to a leaf strictly changes the root value.
Composes Lutar.Khipu.SummationInvariant (compiled, 0 sorry).

## Lean Czar status: valid
## Proof method: exact (re-export of compiled Lutar.Khipu theorem)
## Axioms used: none
## Composes: Lutar.Khipu.SummationInvariant (compiled, v15 G7 close)
## Citations:
  - Urton (2003) Signs of the Inka Khipu UT Press pp.41-62
  - Ascher & Ascher (1981) Code of the Quipu U. Michigan Press
  - Medrano & Khosla (2024) Latin American Antiquity
-/
import Lutar.Khipu.SummationInvariant

namespace Lutar.Thesis.Khipu

open Lutar.Khipu

/-- **TH-V18-08**: pendant value is the sum of its decision values.
    Composes: Lutar.Khipu.pendantValue_def (compiled, 0 sorry). -/
theorem th_v18_08_pendant_value_is_sum (r : OrganReceipt) :
    pendantValue r = (r.decisions.map (·.value)).sum :=
  pendantValue_def r

/-- **TH-V18-08b**: root value is the sum of pendant values.
    Composes: Lutar.Khipu.rootValue_def (compiled, 0 sorry). -/
theorem th_v18_08b_root_value_is_sum (r : KhipuRootReceipt) :
    rootValue r = (r.organs.map pendantValue).sum :=
  rootValue_def r

/-- **TH-V18-08c**: empty root has zero value.
    Composes: Lutar.Khipu.rootValue_empty. -/
theorem th_v18_08c_empty_root_zero (id : String) :
    rootValue ⟨id, []⟩ = 0 :=
  rootValue_empty id

/-- **TH-V18-08d**: single-organ root has value = that organ's pendant value.
    Composes: Lutar.Khipu.rootValue_singleton. -/
theorem th_v18_08d_singleton_root (id : String) (o : OrganReceipt) :
    rootValue ⟨id, [o]⟩ = pendantValue o :=
  rootValue_singleton id o

/-- **TH-V18-08e**: a bump δ ≠ 0 at any leaf changes the root checksum.
    Composes: Lutar.Khipu.khipuReceipt_checksum_invariant (G7 close). -/
theorem th_v18_08e_bump_changes_checksum (r : KhipuRootReceipt)
    (i j δ : Nat) (hi : i < r.organs.length)
    (hj : j < (r.organs.get ⟨i, hi⟩).decisions.length)
    (hδ : δ ≠ 0) :
    rootValue (r.bumpAt i j δ) ≠ rootValue r :=
  khipuReceipt_checksum_invariant r i j δ hi hj hδ

end Lutar.Thesis.Khipu
