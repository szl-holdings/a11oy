/-
================================================================================
  Allowed_Axioms.lean — the axiom allowlist for Λ-Conjecture Bounty submissions.
  SZL Holdings · Apache-2.0 · Sign: Yachay <yachay@szlholdings.dev>
  Doctrine v11 — 749 / 14 / 163 · locked_at c7c0ba17
--------------------------------------------------------------------------------
  A valid submission's proof of `Lambda.lambda_aggregator_unique` must depend on
  NO axioms beyond this allowlist. CI runs `#print axioms` on the discharged
  theorem and rejects any axiom not listed here.

  ALLOWLIST (Lean 4 core + standard Mathlib classical foundations):
    • propext            — propositional extensionality (Lean core)
    • Quot.sound         — quotient soundness (Lean core)
    • Classical.choice   — classical choice (Mathlib/Std foundation)

  Any submission that introduces a NEW `axiom`, leaves a `sorry`/`sorryAx`,
  or uses `native_decide`'s `Lean.ofReduceBool`/`Lean.trustCompiler`-style trust
  is REJECTED. `decide`, `omega`, `simp`, `ring`, etc. are fine (they elaborate to
  allowlisted foundations).
================================================================================
-/

namespace Lambda.Allowed

/-- The canonical allowed-axiom names. CI compares `#print axioms` output against
    this list (string match). Update requires a signed Doctrine bump. -/
def allowlist : List String :=
  ["propext", "Quot.sound", "Classical.choice"]

/-- Sanity: the allowlist is exactly the three classical foundations. -/
theorem allowlist_size : allowlist.length = 3 := rfl

end Lambda.Allowed
