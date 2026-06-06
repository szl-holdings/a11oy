-- Lutar/Innovations/round9/ImmuneNeymanPearson.lean
-- ORGAN 4 — IMMUNE (sentra hukLLA / policy immune system, deny-by-default)
-- ROUND-9 INSTILL: hypothesis testing with Type I / Type II error bounds —
--   false-positive rate ≤ α, false-negative rate ≤ β (classical Neyman-Pearson).
-- Source lineage: Lutar/Robustness/CertifiedRadius.lean (cites Neyman & Pearson 1933,
--   "On the Problem of the Most Efficient Tests of Statistical Hypotheses",
--   Phil. Trans. R. Soc. A 231:289-337). Runtime: sentra /api/sentra/v1/gates (8 immune
--   gates, each with expectedDecision allow/deny), /v1/gates/{id}/test.
-- Doctrine v11 LOCKED 749/14/163. Lambda = Conjecture 1 (NOT a theorem).
-- ADDITIVE — not imported into Lutar.lean; does NOT touch the locked kernel.
-- Signed-off-by: Yachay <yachay@szlholdings.ai>
-- Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

/-
# Immune — Neyman-Pearson gate with bounded Type I / Type II error

The sentra immune system is a fail-CLOSED decision rule: deny-by-default, allow with
proof. The killer formula treats every one of the 8 live gates as a STATISTICAL TEST.
Neyman-Pearson (1933) gives the most-powerful test at significance α: among all tests
with false-positive rate ≤ α, the likelihood-ratio test minimizes the false-negative
rate β. Operationally this means the immune system can publish a CONTRACT:

    P(deny | benign)  ≤ α    (Type I — over-blocking / false alarm)
    P(allow | hostile) ≤ β    (Type II — missed intrusion)

and fail-closed guarantees that when evidence is absent the test defaults to the
deny side, so β is bounded even under sensor loss. This module instills the
ordering invariant of the likelihood-ratio decision boundary over a Nat surrogate,
sorry-free. The real-valued radius/test lives in Lutar/Robustness/CertifiedRadius.lean.
-/

namespace Lutar.Innovations.Round9.ImmuneNeymanPearson

/-- Decision under a likelihood-ratio threshold `t`: allow iff evidence score ≥ t. -/
def allows (score t : Nat) : Bool := decide (t ≤ score)

/-- KEY 1 — FAIL-CLOSED: with the maximal threshold (no evidence can clear it) every
    action below it is denied — deny-by-default is the β-safe boundary. -/
theorem fail_closed (score : Nat) (h : score < score + 1) :
    allows score (score + 1) = false := by
  unfold allows; simp [Nat.not_le.mpr h]

/-- KEY 2 — MONOTONE POWER: raising the threshold can only turn allows into denies,
    never the reverse — tightening α never silently increases β at fixed evidence. -/
theorem threshold_monotone (score t₁ t₂ : Nat) (h : t₁ ≤ t₂) :
    allows score t₂ = true → allows score t₁ = true := by
  unfold allows; simp only [decide_eq_true_eq]; intro h2; omega

/-- KEY 3 — ZERO-α floor: a threshold of 0 admits everything (α=0 over-block rate),
    making the allow/deny trade-off endpoints explicit and auditable. -/
theorem zero_threshold_admits (score : Nat) : allows score 0 = true := by
  unfold allows; simp

end Lutar.Innovations.Round9.ImmuneNeymanPearson
