# Lean4Agent — a11oy workflow-invariant formalization (ROADMAP / EXPERIMENTAL)

**Status: ROADMAP.** This directory is a *scaffold* that formalizes the safety
invariants of the a11oy governed-agent workflow in [Lean 4](https://leanprover.github.io/).
It is **not** a completed machine-checked verification yet. The UI and docs render
these invariants as **"ROADMAP — statements formalized, proofs in progress"** and
must never describe them as "verified" until `lake build` passes with **zero `sorry`**.

Inspired by **Lean4Agent** (arXiv:2606.06523), which formalizes agent workflow
invariants in Lean 4.

## Files
- `WorkflowInvariants.lean` — the irreducible governed-decision pipeline
  (`gate → lambda → recommend → sign → replay`) and 5 safety invariants:
  - **INV 1** `destructive_unapproved_denied` — **proved** (no `sorry`)
  - **INV 2** `injection_always_denied` — **proved**
  - **INV 3** `oversize_denied` — **proved**
  - **INV 4** `canonical_pipeline_policy_first` — **ROADMAP** (`sorry`)
  - **INV 5** `replay_is_deterministic` — **ROADMAP** (placeholder statement)

These mirror the runtime enforcement points: the `_a11oy_arena_inspect` threat gate
and the Colang ROE flows in `policy/colang/roe_core.co`.

## Roadmap to "verified"
1. Add `lakefile.lean` + pin a Lean toolchain (`lean-toolchain`).
2. Discharge INV 4 and INV 5 (remove every `sorry`).
3. Add a CI job that runs `lake build` and fails on any `sorry` / `axiom`.
4. Emit a build manifest; the Eval/Policy tab then cites
   "N/M a11oy workflow invariants machine-checked, as-of <date>".

Until step 3 is green, the honest claim is: **3 of 5 invariant statements are
proved in isolation; the full-pipeline and determinism theorems are roadmap.**
