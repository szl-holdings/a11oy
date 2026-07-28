/-
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-/

import Mathlib

/-!
# Lambda-AttnRes hooks

Small algebraic properties of the Wave 26 blend and rational weight closure.
These theorems do not claim training improvement or unconditional Lambda
uniqueness; Lambda remains Conjecture 1.
-/

namespace Lutar.LambdaAttnRes

def blend (lam arithmetic geometric : ℝ) : ℝ :=
  (1 - lam) * arithmetic + lam * geometric

theorem blend_zero (arithmetic geometric : ℝ) :
    blend 0 arithmetic geometric = arithmetic := by
  simp [blend]

theorem blend_one (arithmetic geometric : ℝ) :
    blend 1 arithmetic geometric = geometric := by
  simp [blend]

theorem complementary_weights_close (weight : ℚ) :
    weight + (1 - weight) = 1 := by
  ring

theorem convex_blend_bounds
    (lam arithmetic geometric : ℝ)
    (hlow : 0 ≤ lam) (hhigh : lam ≤ 1)
    (ha : 0 ≤ arithmetic) (hg : 0 ≤ geometric) :
    0 ≤ blend lam arithmetic geometric := by
  unfold blend
  have hcomp : 0 ≤ 1 - lam := sub_nonneg.mpr hhigh
  exact add_nonneg (mul_nonneg hcomp ha) (mul_nonneg hlow hg)

end Lutar.LambdaAttnRes
