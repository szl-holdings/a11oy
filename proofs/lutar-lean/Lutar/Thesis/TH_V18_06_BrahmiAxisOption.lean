/-
# TH-V18-06 — Brahmi Axis-Option Distinction (v18 composition)

Theorems: the Brahmi positional distinction between `measured 0` and `absent`
is preserved under serialization. Extended to a full governance audit invariant:
axis measurements and non-evaluations hash to different values.

## Lean Czar status: valid
## Proof method: exact + simp (re-export + extension of compiled Lutar.Brahmi)
## Axioms used: none
## Composes: Lutar.Brahmi.AxisOption (compiled, 0 sorry, 0 axiom)
## Citations:
  - Plofker (2009) Mathematics in India — Brahmi positional notation
  - Pearce et al. (2017) Bodleian Libraries — Bakhshali manuscript dating
  - Lutar.Brahmi.AxisOption (v16 graft R4-I2)
-/
import Lutar.Brahmi.AxisOption

namespace Lutar.Thesis.Brahmi

open Lutar.Brahmi.AxisValue

/-- **TH-V18-06**: measured 0 ≠ absent (Brahmi distinction).
    Composes: Lutar.Brahmi.AxisValue.axis_option_distinguishes. -/
theorem th_v18_06_brahmi_distinction :
    measured 0 ≠ absent :=
  axis_option_distinguishes

/-- **TH-V18-06b**: any measured value differs from absent. -/
theorem th_v18_06b_measured_ne_absent (v : Int) :
    measured v ≠ absent := by
  intro h; cases h

/-- **TH-V18-06c**: two distinct measurements are distinguishable. -/
theorem th_v18_06c_measured_injective (v w : Int) (h : measured v = measured w) :
    v = w := by cases h; rfl

/-- **TH-V18-06d**: serialize is injective — the Brahmi distinction is
    preserved at the serialization layer (hash collision prevention).
    Composes: Lutar.Brahmi.AxisValue.serialize_injective. -/
theorem th_v18_06d_serialize_injective :
    Function.Injective serialize :=
  serialize_injective

/-- **TH-V18-06e**: serialized measured 0 ≠ serialized absent (hash-level).
    Composes: Lutar.Brahmi.AxisValue.serialize_measured_zero_ne_absent. -/
theorem th_v18_06e_serialize_measured_zero_ne_absent :
    serialize (measured 0) ≠ serialize absent :=
  serialize_measured_zero_ne_absent

/-- **TH-V18-06f**: either an axis is measured or it is absent (no third case).
    Uses explicit type annotation to resolve AxisValue in lake build context. -/
theorem th_v18_06f_axis_dichotomy (av : Lutar.Brahmi.AxisValue) :
    isMeasured av = true ∨ isAbsent av = true :=
  axis_dichotomy av

/-- **TH-V18-06g**: measured and absent are mutually exclusive. -/
theorem th_v18_06g_axis_exclusive (av : Lutar.Brahmi.AxisValue) :
    ¬ (isMeasured av = true ∧ isAbsent av = true) :=
  axis_exclusive av

end Lutar.Thesis.Brahmi
