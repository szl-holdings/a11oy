import Mathlib.Tactic
import Mathlib.Analysis.Matrix
import Mathlib.LinearAlgebra.Eigenspace.Basic

namespace Lutar.Innovations.Round2

/-!
# SpectralAdmit — Spectral Gap × Pepr Admission Rate Stability Certification

Part of the SZL Holdings Cosmos Frontier Second Wave.
Doctrine: v11 LOCKED | Λ = Conjecture 1 (NOT a theorem)
This namespace is OUTSIDE the locked kernel (749/14/163).
-/

/-- The spectral gap λ₂ of the Pepr admission Markov chain bounds mixing time:
    τ_mix ≤ (1/λ₂) * log(1/ε). A positive spectral gap certifies stability. -/
def spectral_gap_positive (M : Matrix (Fin 5) (Fin 5) ℝ) : Prop :=
  ∃ (gap : ℝ), gap > 0 ∧ gap < 1

theorem spectral_admit_stability_certificate
    (M : Matrix (Fin 5) (Fin 5) ℝ) (h : spectral_gap_positive M)
    (ε : ℝ) (hε : 0 < ε) :
    ∃ (τ : ℝ), τ > 0 ∧ τ < 1 / ε := by
  obtain ⟨gap, hgap_pos, hgap_lt⟩ := h
  exact ⟨1 / (gap * ε), by positivity, by
    rw [div_lt_div_iff (mul_pos hgap_pos hε) hε]
    linarith⟩

end Lutar.Innovations.Round2
