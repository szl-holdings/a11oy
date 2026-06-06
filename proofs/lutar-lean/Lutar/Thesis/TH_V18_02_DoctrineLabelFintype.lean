/-
# TH-V18-02 — Doctrine Label Space is Finite with 4 Elements

Theorem: the doctrine label lattice {Bot, L1, L2, Top} has exactly 4 elements.
Decidable by `decide`. Basis for Shannon entropy bounds (v17 DoctrineEntropy).

## Lean Czar status: valid
## Proof method: decide (closed by kernel evaluation)
## Axioms used: none
## Composes: Lutar.Shannon.DoctrineEntropy (v17) — same 4-label lattice
## Citations:
  - Shannon (1948) BSTJ 27(3):379 — source coding theorem
  - Cover & Thomas (2006) Elements of Information Theory — Kraft bound
-/
import Mathlib.Data.Fintype.Basic
import Mathlib.Data.Fintype.Card
import Mathlib.Data.Finset.Basic

namespace Lutar.Thesis.DoctrineLabel

/-- The four-level doctrine label lattice (matches Lutar.Shannon.DoctrineEntropy). -/
inductive DoctrineLabel : Type
  | Bot | L1 | L2 | Top
  deriving DecidableEq, Repr

instance : Fintype DoctrineLabel where
  elems := {DoctrineLabel.Bot, DoctrineLabel.L1, DoctrineLabel.L2, DoctrineLabel.Top}
  complete := by intro x; cases x <;> simp

/-- **TH-V18-02**: the doctrine alphabet has exactly 4 elements. -/
theorem th_v18_02_doctrine_alphabet_size_4 :
    Fintype.card DoctrineLabel = 4 := by decide

/-- Shannon code: bijection from label to 2-bit codeword {0,1,2,3}. -/
def shannonCode : DoctrineLabel → Nat
  | .Bot => 0 | .L1 => 1 | .L2 => 2 | .Top => 3

/-- **TH-V18-02b**: Shannon code is injective (uniquely decodable). -/
theorem th_v18_02b_shannonCode_injective : Function.Injective shannonCode := by
  intro a b h
  cases a <;> cases b <;> simp_all [shannonCode]

/-- **TH-V18-02c**: Shannon decoder is left inverse to the code. -/
def shannonDecode : Nat → Option DoctrineLabel
  | 0 => some .Bot | 1 => some .L1 | 2 => some .L2 | 3 => some .Top
  | _ => none

theorem th_v18_02c_decode_left_inverse (l : DoctrineLabel) :
    shannonDecode (shannonCode l) = some l := by
  cases l <;> simp [shannonCode, shannonDecode]

/-- **TH-V18-02d**: all four labels are distinct. -/
theorem th_v18_02d_labels_distinct :
    DoctrineLabel.Bot ≠ DoctrineLabel.L1 ∧
    DoctrineLabel.Bot ≠ DoctrineLabel.L2 ∧
    DoctrineLabel.Bot ≠ DoctrineLabel.Top ∧
    DoctrineLabel.L1  ≠ DoctrineLabel.L2 ∧
    DoctrineLabel.L1  ≠ DoctrineLabel.Top ∧
    DoctrineLabel.L2  ≠ DoctrineLabel.Top := by decide

end Lutar.Thesis.DoctrineLabel
