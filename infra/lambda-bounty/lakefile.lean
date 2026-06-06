import Lake
open Lake DSL

-- SZL Holdings — Λ-Conjecture Bounty · Apache-2.0 · Yachay <yachay@szlholdings.dev>
-- Doctrine v11 — 749 / 14 / 163 · locked_at c7c0ba17
package «lambda-bounty» where
  -- Lean 4 + Mathlib. A submission discharges Lambda.lambda_aggregator_unique
  -- using only the allowlisted axioms (Lambda/Allowed_Axioms.lean).

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.13.0"

@[default_target]
lean_lib «Lambda» where
  -- Library root: Lambda/ (Lambda.lean + Allowed_Axioms.lean + submissions)
