# Abstract — v15 Knot Calculus for Governed-Decision Receipts

**Version:** 15.0.0-knot-calculus
**Date:** 2026-05-28
**Author:** Lutar, Stephen P., Jr. ([ORCID 0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173))
**License:** CC-BY-4.0
**Pending DOI:** 10.5281/zenodo.PENDING-v15 (concept: [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926))

---

We extend the v14 Lutar Multi-Agent Anatomy with two structural inversions
that are load-bearing for v15 and that v14 left implicit.

**Inversion 1 — receipts are the canonical record of behavior, not a
side-channel log.** In v15 the receipt-chain DAG IS the audit record: every
governed decision emits a hash-linked, three-tier khipu-indexed receipt
(decision → organ → root) that is the system's only authoritative trace of
what happened. There is no "real" log behind the receipts. This collapses
the usual gap between *the thing the system did* and *the artifact an
auditor reads* by making the receipt chain reproducible byte-for-byte under
the same input + the same module commit. Tampering, drift, or silent
re-execution are caught at the gate, not in a downstream review.

**Inversion 2 — the gate has no tunable knobs at inference time.** The
Lutar invariant Λ : [0,1]^k → [0,1] is the same weighted geometric mean
sealed in v14 §3.3 (F2 unification, commit `ae625ba`). v15 adds neither
hyper-parameter, threshold, nor architectural knob to the gate itself —
only a knot-invariant *reading* of what the gate already computes. Calling
parties cannot raise or lower Λ by passing different runtime arguments;
they can only present a different receipt chain and have Λ recomputed.

On top of these two inversions, v15 contributes (a) a three-tier
khipu-indexed receipt DAG with a runtime sum-of-sums invariant formalised
in Lean 4 as **TH11**; (b) a Λ-gate locally-invariant-domain (LID) +
DPO stability theorem **TH12** combining Pinsker's inequality with the v14
gated-QKAN-FWP Lipschitz bound; (c) a PAC-Bayes generalisation bound
**TH13** for the 9-axis governance head with closed-form arithmetic
content fully proved; and (d) three `axiom`-tagged audit-Reidemeister
rewrites (R1/R2/R3) recorded as conjectures targeting v17 closure. 31 new
runtime tests pass across rosie, a11oy, amaru, ouroboros, and
szl-cookbook. The Λ definition is unchanged from v14; no prior Lean
theorem is weakened.

---

*This standalone abstract file is the canonical short-form for v15. The
full LaTeX abstract in `arxiv_pkg_v15/main.tex.md` will be brought into
line with this text after the F7 citation-fix branch (PR #75) is merged
to `feat/v15-knot-calculus`.*
