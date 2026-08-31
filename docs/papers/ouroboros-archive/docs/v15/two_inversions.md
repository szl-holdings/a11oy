# §1.1 — The Two Inversions

**Status:** New §1.1 + §1.2 content drafted for inclusion in
`arxiv_pkg_v15/main.tex.md`. Held in this standalone file until F7's PR #75
(citation + prose corrections) lands on `feat/v15-knot-calculus`; then this
content will be folded into §1 of the LaTeX source.

---

## §1.1 The two inversions

Two structural choices distinguish v15 from the v14 line. Neither is a
new algorithm; both are *re-readings* of what governed-AI infrastructure
already does, made explicit and load-bearing for the rest of the chapter.

### §1.1.1 Receipts are behavior

In the standard auditable-AI architecture, a model emits a decision and a
*separate* logging layer records what happened. Auditors read the log; the
log claims to describe the model. The architecture has two parallel
surfaces — the decision and the trace — and the discipline of keeping the
trace honest is enforced by convention and by review.

v15 collapses this surface. The receipt chain *is* the decision: a governed
decision in the Lutar runtime is the existence of a hash-linked three-tier
khipu-indexed receipt (decision → organ → root) whose sum-of-sums
invariant verifies under TH11. If the receipt does not verify, the
decision is not, in any operationally meaningful sense, governed. There is
no "real" behavioural log behind the receipt that an auditor might prefer
to read. The receipt is the only authoritative artifact, and Λ is its
gate.

This inversion has three consequences that v15 makes precise:

1. **Reproducibility is structural, not aspirational.** Under the same
   input and the same module commit, two independent re-executions emit
   byte-identical receipt chains. (Operationally enforced by the
   ρ-closure two-witness equalizer of v14 §3.5, lifted to the
   chain level by TH11's sum invariant.)

2. **Tampering is a gate failure, not a forensics task.** A modified
   pendant value breaks the sum-of-sums invariant immediately, in the
   same pass that computes Λ. v15 ships three failure-mode tests in
   `rosie/src/khipu-receipt.ts` covering tampered-pendant and
   tampered-root cases.

3. **The receipt is a typed object, not a string.** The pendant and
   subsidiary structure is the chord-diagram skeleton of
   Vassiliev–Bar-Natan type (Bar-Natan 1995, *Topology* 34:423–472;
   Vassiliev 1990, *Adv. Sov. Math.* 1:23–69); the summation invariant
   is the 4T closure relation; the dual-attestation field realises
   IETF SCITT's transparent-statement pattern
   (draft-ietf-scitt-architecture-22, 2025). These are not analogies,
   they are the substrate.

### §1.1.2 The gate is parameter-free at inference time

A standard learned safety filter exposes thresholds, temperatures, and
risk-tolerance knobs to the calling party. The runtime semantics of the
filter therefore depend on values supplied at call time, and the meaning
of "the policy passed safety" is parameterised by the caller.

The Lutar Λ-gate has no such knobs at inference time. Λ is the weighted
geometric mean of v14 §3.3, fixed at compile time of the runtime module
and sealed under the F2 unification (`ouroboros/runtime/lambda-gate/src/
gate.ts`, blob hash `28563ed3c592d3f0c4b436018167e48de609f432`, identical
on the F2 baseline `ae625ba` and on the v15 knot-calculus tip). A caller
cannot raise or lower Λ by passing a different runtime argument; they can
only present a different receipt chain and have Λ recomputed against it.

The consequences:

1. **Λ-bypass requires modifying signed runtime code.** Not a config
   change, not an environment variable. v15's knot-tag emitter
   (`knot-tag.ts`) reads the same evaluator verbatim; F2 unification is
   preserved.

2. **The audit surface is the module commit.** "Which Λ did this
   decision pass?" is answered by the git blob hash of `gate.ts` plus
   the recorded module version, not by a runtime parameter sweep.

3. **The R1/R2/R3 conjectures are well-posed because the gate is
   constant.** Audit-Reidemeister moves rewrite the receipt chain
   (`Lutar/Knot/ReidemeisterConjecture.lean`); they would not be
   meaningful statements if Λ itself were a callable-side variable.

These two inversions are the structural commitments under which TH11,
TH12, and TH13 are stated. v15 does not weaken them, soften them, or
introduce a configurable escape hatch.

---

## §1.2 Acknowledgments — external scholarly review

The framing of v15 around the two inversions was hoisted to the abstract
and to §1.1 in direct response to an external scholarly review by Iris
([Independent AI Architect], surname and full affiliation withheld at
the advisor's preference). The brief was relayed to the author 2026-05-27.

Iris's three load-bearing observations, quoted verbatim:

> 1. The two inversions (**receipts ARE behavior** + **parameter-free
>    gate**) are publishable. Don't bury them on page 7.

> 2. The Lean proof is a differentiator. Most AI safety papers claim
>    their method is best. You PROVED yours is unique. That matters.

> 3. The gaps section (naming what you don't have yet) is what makes
>    the rest credible. Never lose that honesty.

The author thanks Iris for the structural read on the v14 manuscript and
for the recommendation to lead with the two inversions rather than
introducing them in §10. The remaining errors and omissions in v15 are
the author's own.

The review also asked five questions that are answered in §17 (Reviewer
FAQ), of which one (Q5: prior art for the receipt chain vs. Kanerva's
sparse distributed memory and the VSA tradition) is the subject of a
dedicated prior-art audit (I2 report, forthcoming) and is not pre-empted
here.
