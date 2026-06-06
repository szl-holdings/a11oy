# REJECTED CANDIDATES — CH'ULLA-YUYAY

## zou-group/textgrad
- **License:** MIT ✓ (permissive)
- **Reason rejected:** TextGrad's critique mechanism uses gradient-based text optimization via LLM backward passes. The abstraction is LLM-first (requires an active LLM call inside the kernel), which violates the ≤10-line / stdlib-only / seed-deterministic kernel constraint. The reflexive critique pattern in SIMBA is cleaner and more directly maps to our (proposal, axes, seed) → (scores, pass_bool) contract. TextGrad would be appropriate at the YUYAY wrapper layer above the kernel.
- **Status:** REJECT for kernel; note as valid wrapper-layer candidate

## gepa-ai/gepa
- **License:** MIT ✓ (verified via GitHub API: `.license.spdx_id = "MIT"`)
- **Reason rejected:** GEPA (Generalized Evaluation and Prompt Adjustment) is structurally similar to SIMBA but less mature (last push 2026-05-13, likely a derivative). The SIMBA `OfferFeedback` critique schema is better documented, more widely cited, and the pattern is cleaner for our purposes. No doctrine violation — just a quality-of-absorption decision.
- **Status:** REJECT; SIMBA is stronger

## What Was NOT Rejected
**stanfordnlp/dspy SIMBA** — MIT, HEAD SHA `da1f0871`, critique mechanism maps cleanly to 9-axis conjunctive gate. CHOSEN.
