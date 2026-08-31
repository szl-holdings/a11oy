/-
# Brahmi-zero AxisValue option type (R4-I2)

The Brahmi positional numeral tradition explicitly distinguishes
"no measurement" (absent place) from "measurement of zero" (marked place
holding 0). This distinction is what makes the Bakhshali manuscript
(carbon-dated 3rd–4th c. CE per Pearce et al. 2017, Bodleian Libraries) and
Brahmagupta's *Brāhmasphuṭasiddhānta* (628 CE) compositionally complete
[Plofker 2009, *Mathematics in India*, Princeton University Press, ch. 3].

For governed-decision receipts the same distinction is operationally
load-bearing: an axis that was *not evaluated* must produce a different hash
and a different Λ-aggregate than an axis that was evaluated and produced 0.

Runtime counterparts:
  - `rosie/src/axis-value-option.ts`
  - `amaru/src/axis-value-option.ts`

v16 ancient-foundations graft R4-I2.
-/

import Mathlib.Logic.Function.Basic

namespace Lutar.Brahmi

/-- An axis value distinguishes the Brahmi place-value zero from absence.
    `measured 0` is a genuine measurement that the axis produced zero;
    `absent` is the absent place. -/
inductive AxisValue
  | measured (v : Int) : AxisValue
  | absent             : AxisValue
  deriving DecidableEq, Repr

namespace AxisValue

/-- The two cases are distinguishable by `DecidableEq`. In particular,
    `measured 0 ≠ absent` — this is the Brahmi distinction. -/
theorem axis_option_distinguishes :
    measured 0 ≠ absent := by
  decide

/-- The discriminator predicate "is absent". -/
def isAbsent : AxisValue → Bool
  | absent     => true
  | measured _ => false

/-- The discriminator predicate "is measured". -/
def isMeasured : AxisValue → Bool
  | measured _ => true
  | absent     => false

/-- An AxisValue is either measured or absent — there is no third case. -/
theorem axis_dichotomy (av : AxisValue) :
    isMeasured av = true ∨ isAbsent av = true := by
  cases av <;> simp [isMeasured, isAbsent]

/-- `measured` and `absent` are mutually exclusive. -/
theorem axis_exclusive (av : AxisValue) :
    ¬ (isMeasured av = true ∧ isAbsent av = true) := by
  cases av <;> simp [isMeasured, isAbsent]

/-- Canonical serialization: `absent` becomes a distinguished string-tag
    `none`, `measured v` becomes `some v`. This is the Lean witness for the
    TypeScript `serializeAxis` function — it preserves the Brahmi
    distinction under any subsequent hash. -/
def serialize : AxisValue → Option Int
  | absent     => Option.none
  | measured v => Option.some v

theorem serialize_injective :
    Function.Injective serialize := by
  intro a b h
  cases a <;> cases b <;> simp_all [serialize]

/-- Specifically: the serialization of `measured 0` (i.e. `some 0`) is not
    equal to the serialization of `absent` (i.e. `none`). This is the
    Brahmi distinction operationalised at the serialization layer. -/
theorem serialize_measured_zero_ne_absent :
    serialize (measured 0) ≠ serialize absent := by
  simp [serialize]

end AxisValue

end Lutar.Brahmi
