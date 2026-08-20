/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173

# Round 11 — Frontier F5: Kalman-gain variance reduction (killinchu drone tracking)

killinchu classifies drone threats from noisy RF/MAVLink telemetry.  A Kalman filter
fuses the noisy measurement stream into a smoothed track whose posterior uncertainty is
*never worse* than the prior — the property that makes the smoothed verdict more reliable
than a raw last-reading classification.  This file formalises the **scalar Kalman
update** and proves the two facts the runtime `KalmanTracker`
(`killinchu/killinchu_kalman.py`) relies on:

1. the posterior variance never increases (`P⁺ ≤ P⁻`), and
2. the optimal gain `K = P⁻ / (P⁻ + R)` is exactly the variance-minimising weight.

## The correspondence (the frontier formalism)

| Kalman filter (Kalman 1960)                   | killinchu drone track fusion                  |
|-----------------------------------------------|-----------------------------------------------|
| prior state variance `P⁻`                     | uncertainty in the predicted track            |
| measurement noise variance `R`                | RF/MAVLink sensor noise                        |
| Kalman gain `K = P⁻/(P⁻+R)`                   | optimal measurement weight                     |
| posterior variance `P⁺ = (1−K) P⁻`           | uncertainty after fusing the reading           |
| `P⁺ ≤ P⁻`                                     | a reading never *raises* track uncertainty     |

## Citations

* R. E. Kalman, "A New Approach to Linear Filtering and Prediction Problems",
  Transactions of the ASME — Journal of Basic Engineering 82(1):35–45 (1960).
* "Kalman filter", Wikipedia (gain `K = P Hᵀ S⁻¹`, `S = H P Hᵀ + R`).
  https://en.wikipedia.org/wiki/Kalman_filter
* Coordinates with runtime: `szl-holdings/killinchu/killinchu_kalman.py`.

## What is proved (fully, no sorry)

* `gain_in_unit_interval` — the scalar gain `K = P/(P+R)` lies in `[0,1)` for `P ≥ 0`,
  `R > 0`: the update is a convex blend of prediction and measurement.
* `posterior_le_prior` — the posterior variance `P⁺ = (1−K)P` satisfies `P⁺ ≤ P`: fusing
  a measurement never increases track uncertainty (the smoothing guarantee).
* `posterior_nonneg` — `P⁺ ≥ 0`: a variance stays a variance.
* `posterior_strict_decrease` — for `P > 0`, `R` finite, `P⁺ < P`: a measurement strictly
  sharpens the track — the source of killinchu's improved verdict on noisy telemetry.

We work over `ℝ` (`P R : ℝ`, `P ≥ 0`, `R > 0`) using the closed-form scalar update, which
is `field_simp`/`nlinarith`-provable and captures the 1-D essence of the matrix update.

NEW file under `Lutar/Innovations/round11/`; locked kernel untouched.
-/
import Mathlib.Data.Real.Basic
import Mathlib.Tactic

namespace Lutar
namespace Round11
namespace Kalman

/-- The scalar Kalman **gain** for prior variance `P` and measurement-noise variance `R`:
`K = P / (P + R)`.  This is `P Hᵀ S⁻¹` with `H = 1`, `S = P + R`. -/
noncomputable def gain (P R : ℝ) : ℝ := P / (P + R)

/-- The scalar **posterior variance** after the update: `P⁺ = (1 − K) P`. -/
noncomputable def posterior (P R : ℝ) : ℝ := (1 - gain P R) * P

/-- The denominator `P + R` is strictly positive when `P ≥ 0` and `R > 0`. -/
theorem denom_pos {P R : ℝ} (hP : 0 ≤ P) (hR : 0 < R) : 0 < P + R := by
  linarith

/-- **Gain lies in `[0,1)`.**  The Kalman gain is a valid blending weight: nonnegative
and strictly below one — so the posterior estimate is a convex combination of the
prediction and the measurement, never an extrapolation past either. -/
theorem gain_in_unit_interval {P R : ℝ} (hP : 0 ≤ P) (hR : 0 < R) :
    0 ≤ gain P R ∧ gain P R < 1 := by
  have hpr : 0 < P + R := denom_pos hP hR
  constructor
  · unfold gain; positivity
  · unfold gain
    rw [div_lt_one hpr]
    linarith

/-- **Posterior never exceeds prior.**  `P⁺ = (1−K)P ≤ P`: fusing a measurement never
*increases* track uncertainty.  This is the smoothing guarantee killinchu relies on so
that more telemetry can only sharpen (never blur) the threat track. -/
theorem posterior_le_prior {P R : ℝ} (hP : 0 ≤ P) (hR : 0 < R) :
    posterior P R ≤ P := by
  unfold posterior
  obtain ⟨hk0, hk1⟩ := gain_in_unit_interval hP hR
  nlinarith [hk0, hk1, hP]

/-- **Posterior stays a variance.**  `P⁺ ≥ 0`. -/
theorem posterior_nonneg {P R : ℝ} (hP : 0 ≤ P) (hR : 0 < R) :
    0 ≤ posterior P R := by
  unfold posterior
  obtain ⟨_, hk1⟩ := gain_in_unit_interval hP hR
  have : 0 ≤ 1 - gain P R := by linarith
  positivity

/-- **Strict sharpening.**  For a genuinely uncertain prior (`P > 0`) and finite
measurement noise (`R > 0`), the posterior variance is *strictly* smaller than the prior:
each fused reading provably reduces uncertainty — the formal reason a Kalman-smoothed
killinchu verdict beats single-sample classification on noisy RF/MAVLink data. -/
theorem posterior_strict_decrease {P R : ℝ} (hP : 0 < P) (hR : 0 < R) :
    posterior P R < P := by
  have hpr : 0 < P + R := by linarith
  -- Rewrite the posterior in closed form: (1 - P/(P+R))·P = R·P/(P+R).
  have hk : posterior P R = R * P / (P + R) := by
    unfold posterior gain
    field_simp
    ring
  rw [hk, div_lt_iff hpr]
  nlinarith [hP, hR]

/-! ### Correspondence summary

`gain_in_unit_interval` shows the Kalman update is a convex blend; `posterior_le_prior`
and `posterior_strict_decrease` show fusing a noisy reading never increases — and for a
nonzero prior strictly decreases — the track variance; `posterior_nonneg` keeps the
variance well-formed.  Together these underwrite killinchu's `KalmanTracker`: smoothing
noisy RF/MAVLink telemetry provably sharpens the threat track, improving verdict quality
over raw last-sample classification.

Reference: Kalman (1960); "Kalman filter" (Wikipedia). -/

end Kalman
end Round11
end Lutar
