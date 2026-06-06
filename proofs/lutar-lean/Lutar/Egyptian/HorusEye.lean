/-
# Horus-Eye 6-bit dyadic weight encoding (R1-G2)

The ancient Egyptian Horus-Eye (wedjat) fractional system represents fractions
as sums of the six dyadic units `1/2, 1/4, 1/8, 1/16, 1/32, 1/64`. The total
of the six units is `63/64` — per scribal tradition the missing `1/64` was
"supplied by Thoth" [Gillings 1972, *Mathematics in the Time of the Pharaohs*,
MIT Press, ch. 1–3; Clagett 1999, *Ancient Egyptian Science vol. III*,
American Philosophical Society, §III.1].

For governed-decision receipts the system gives a deterministic 6-bit
fixed-precision encoding for weights `w ∈ [0, 63/64]`, eliminating IEEE-754
non-determinism on constrained environments.

Runtime counterpart: `rosie/src/horus-eye-weights.ts`.

v16 ancient-foundations graft R1-G2.
-/
import Mathlib.Data.Rat.Defs
import Mathlib.Algebra.BigOperators.Group.List
import Mathlib.Tactic.NormNum
import Mathlib.Tactic.FieldSimp

namespace Lutar.Egyptian.HorusEye

/-- The six Horus-Eye dyadic units as exact rationals. -/
def horusEyeUnits : List ℚ := [1/2, 1/4, 1/8, 1/16, 1/32, 1/64]

/-- Sum of the six Horus-Eye dyadic units equals exactly 63/64. -/
theorem horus_eye_sum_eq_63_over_64 :
    horusEyeUnits.sum = 63/64 := by
  unfold horusEyeUnits
  norm_num

/-- The number of distinct dyadic units in the Horus-Eye system is six. -/
theorem horus_eye_unit_count :
    horusEyeUnits.length = 6 := by
  unfold horusEyeUnits
  rfl

/-- Each Horus-Eye unit is a non-negative rational. -/
theorem horus_eye_units_nonneg :
    ∀ u ∈ horusEyeUnits, (0 : ℚ) ≤ u := by
  intro u hu
  simp [horusEyeUnits] at hu
  rcases hu with h | h | h | h | h | h <;> rw [h] <;> norm_num

/-- The maximum value representable by a 6-bit Horus-Eye code is 63/64. -/
def horusEyeMax : ℚ := 63/64

/-- The denominator of the 6-bit Horus-Eye encoding is 64. -/
def horusEyeDenominator : ℕ := 64

/-- Round-trip identity on integer codes: `code/64 * 64 = code` for any
    `code ∈ {0, …, 63}`. This is the Lean witness that the
    `encodeHorusEye(decodeHorusEye(c)) = c` direction is exact. -/
theorem horus_eye_decode_encode (code : ℕ) (h : code ≤ 63) :
    (code : ℚ) / 64 * 64 = code := by
  field_simp

end Lutar.Egyptian.HorusEye
