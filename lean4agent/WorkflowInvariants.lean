/-
  WorkflowInvariants.lean — ROADMAP / EXPERIMENTAL scaffold (NOT a verified proof yet)

  © 2026 Lutar, Stephen P. — SZL Holdings.  SPDX-License-Identifier: Apache-2.0

  STATUS: ROADMAP. This file formalizes the SAFETY INVARIANTS of the a11oy governed
  agent WORKFLOW in Lean 4 so they can eventually be machine-checked. It is a
  SCAFFOLD: the theorem STATEMENTS are written out and the simplest ones are proved,
  but the deeper ones are deliberately left as `sorry` and are LABELLED as such so we
  never overclaim a machine-checked guarantee we do not yet have. Inspired by
  Lean4Agent (arXiv:2606.06523) — formalizing agent workflow invariants in Lean 4.

  What this models: the irreducible core of ONE governed decision in a11oy:
      gate.evaluate → lambda.score → decision.recommend → receipt.sign → replay.verify
  and the doctrine rules the runtime enforces (Colang ROE + arena gate). The goal of
  the roadmap is: every theorem here is discharged WITHOUT `sorry`, then a CI job runs
  `lake build` and the UI cites "N/M workflow invariants machine-checked".

  HONESTY: until `lake build` passes with zero `sorry`, the UI MUST render these as
  "ROADMAP — statements formalized, proofs in progress", never as "verified".
-/

namespace A11oy.Workflow

/-- The ordered phases of one governed decision. -/
inductive Phase where
  | gate        -- policy gate evaluated the action plan
  | lambda      -- trust score (Λ, Conjecture 1) computed across axes
  | recommend   -- governed recommendation emitted
  | sign        -- decision receipt DSSE-signed (ECDSA-P256, in-image key)
  | replay      -- deterministic replay produced byte-identical root
  deriving Repr, DecidableEq

/-- A decision outcome. -/
inductive Decision where
  | allow
  | deny
  | rateLimit
  | observation
  deriving Repr, DecidableEq

/-- An action carries flags the runtime actually inspects. -/
structure Action where
  destructive        : Bool   -- matches a destructive signature
  operatorApproved   : Bool   -- operator.approve event present
  highImpact         : Bool   -- requires_approval
  injection          : Bool   -- prompt-injection signature
  payloadOverCeiling : Bool   -- exceeds 1MB DoS ceiling
  deriving Repr

/-- A workflow trace is the (ordered) list of phases that actually ran. -/
abbrev Trace := List Phase

/-- The policy gate's verdict on an action (mirrors `_a11oy_arena_inspect` +
    Colang ROE: any of these conditions ⇒ DENY). -/
def gateVerdict (a : Action) : Decision :=
  if a.injection || a.payloadOverCeiling
     || (a.destructive && ¬ a.operatorApproved)
     || (a.highImpact && ¬ a.operatorApproved)
  then Decision.deny
  else Decision.allow

/-- INVARIANT 1 (proved): a destructive action without operator approval is DENIED.
    This is the Colang `refuse_destructive_actions` flow as a theorem. -/
theorem destructive_unapproved_denied (a : Action)
    (hd : a.destructive = true) (hn : a.operatorApproved = false) :
    gateVerdict a = Decision.deny := by
  unfold gateVerdict
  simp [hd, hn]

/-- INVARIANT 2 (proved): an injection-bearing action is DENIED regardless of
    every other flag. Colang `refuse_prompt_injection`. -/
theorem injection_always_denied (a : Action) (hi : a.injection = true) :
    gateVerdict a = Decision.deny := by
  unfold gateVerdict
  simp [hi]

/-- INVARIANT 3 (proved): an oversized payload is DENIED (DoS size guard). -/
theorem oversize_denied (a : Action) (ho : a.payloadOverCeiling = true) :
    gateVerdict a = Decision.deny := by
  unfold gateVerdict
  simp [ho]

/-- "policy-before-effect": `gate` must occur strictly before `sign` in a trace. -/
def policyBeforeEffect (t : Trace) : Prop :=
  ∀ i j, t.get? i = some Phase.sign → t.get? j = some Phase.gate → j < i

/-- INVARIANT 4 (ROADMAP — `sorry`): the canonical governed-turn pipeline always
    evaluates policy before any signing/effect step. Statement is formalized; the
    proof over arbitrary well-formed traces is left for the roadmap. DO NOT claim
    this as machine-checked until the `sorry` below is removed. -/
theorem canonical_pipeline_policy_first :
    policyBeforeEffect [Phase.gate, Phase.lambda, Phase.recommend,
                        Phase.sign, Phase.replay] := by
  sorry  -- ROADMAP: discharge by `decide`/index reasoning; tracked in CI

/-- INVARIANT 5 (ROADMAP — `sorry`): determinism — replaying a trace yields a
    byte-identical receipt root. Requires modeling the receipt hash-chain; left as
    a roadmap obligation. -/
theorem replay_is_deterministic (t : Trace) :
    True := by
  trivial  -- placeholder statement only; real determinism theorem is ROADMAP

/-- Summary used by the CI/manifest extractor: which invariants are DISCHARGED. -/
def invariantStatus : List (String × Bool) :=
  [ ("destructive_unapproved_denied", true)
  , ("injection_always_denied",       true)
  , ("oversize_denied",               true)
  , ("canonical_pipeline_policy_first", false)  -- ROADMAP (sorry)
  , ("replay_is_deterministic",         false)  -- ROADMAP (placeholder)
  ]

end A11oy.Workflow
