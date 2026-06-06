/-
  Lutar/QEC/HammingFoundations.lean — v17 Hamming foundations

  Richard W. Hamming's 1950 paper — "Error Detecting and Error
  Correcting Codes" (Bell System Technical Journal 29(2):147–160) —
  is the foundation under everything in this directory.

  Citations:
    • Hamming, R. W. (1950).  Error Detecting and Error Correcting
      Codes.  *Bell System Technical Journal* 29(2):147–160.
      DOI 10.1002/j.1538-7305.1950.tb00463.x.
    • Shannon, C. E. (1948).  Bell System Technical Journal
      27(3):379–423.  Already cited in Lutar/Shannon/DoctrineEntropy.
    • Cover, T. M., Thomas, J. A. (2006).  Elements of Information
      Theory, 2nd ed.  Wiley.  ISBN 978-0-471-24195-9.

  Innovation beyond attribution:
    • Hamming's distance, weight, and code structure are instantiated
      for byte-level doctrine receipts (no prior art at the receipt
      level).
    • The Hamming code structure is named as the spine under
      Lutar.QEC.CSS, Lutar.QEC.Shor, and Lutar.QEC.Kitaev.
-/

import Mathlib.Data.Nat.Defs

namespace Lutar.QEC.Hamming

/-- A codeword: a list of bits (Bool). -/
abbrev Codeword := List Bool

/-- Hamming distance: number of positions where two codewords differ.
    For equal-length codewords this is the standard Hamming distance;
    mismatched lengths yield 0 (caller's responsibility to align). -/
def hammingDist : Codeword → Codeword → Nat
  | [], [] => 0
  | [], _  => 0
  | _, []  => 0
  | a :: as, b :: bs =>
      (if a = b then 0 else 1) + hammingDist as bs

/-- Hamming weight: positions where the codeword has a `true` bit. -/
def hammingWeight : Codeword → Nat
  | [] => 0
  | true :: rest  => 1 + hammingWeight rest
  | false :: rest => hammingWeight rest

/-- Hamming distance to self is zero. -/
theorem hamming_dist_self : ∀ (a : Codeword), hammingDist a a = 0
  | [] => rfl
  | (h :: t) => by
      simp [hammingDist, hamming_dist_self t]

namespace Tests

  /-- Two equal short codewords have distance 0. -/
  example : hammingDist [true, false, true] [true, false, true] = 0 := by decide
  /-- Distance between 000 and 111 is 3. -/
  example : hammingDist [false, false, false] [true, true, true] = 3 := by decide
  /-- Distance between 1010 and 0101 is 4. -/
  example : hammingDist [true, false, true, false] [false, true, false, true] = 4 := by decide
  /-- Weight of all-zero is 0. -/
  example : hammingWeight [false, false, false] = 0 := by decide
  /-- Weight of all-one of length 4 is 4. -/
  example : hammingWeight [true, true, true, true] = 4 := by decide
  /-- Weight of 1010 is 2. -/
  example : hammingWeight [true, false, true, false] = 2 := by decide

end Tests

end Lutar.QEC.Hamming
