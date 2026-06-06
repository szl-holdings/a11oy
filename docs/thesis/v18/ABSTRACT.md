# Abstract

**The Ouroboros Substrate: a Governance-Mathematical Foundation for Verifiable Agentic AI**

Stephen P. Lutar (ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)) — SZL Holdings

---

We present the Ouroboros Substrate (SZL Holdings, versions 14 through 18), a
formally verified execution environment for agentic AI in which every
governance invariant is machine-checked by the Lean 4 kernel against
Mathlib v4.13.0. The central mathematical object is the Lambda-axis score, a
nine-dimensional product-of-receipts governance scalar bounded by axiom system
A1–A15. Axioms A1–A4 (monotonicity, positive homogeneity, Egyptian-fraction
normalisation, max bound) characterise Lambda uniquely, proved in
`Lutar/Axioms.lean` and `Lutar/Bound.lean` ([DOI 10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308)).
Axiom A15 (SHA-256 collision resistance) is a cryptographic open problem under
NIST FIPS 180-4, not derivable from Mathlib, and is labelled as such.

The v18.0 thesis ([206 pages, DOI 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276))
contains 72 named theorem environments and 4 corollaries across eight chapters.
Of the 31 theorems in Chapter 2 and 16 in Chapter 6, the Lean Czar audit
(Chapter 7) certifies: 17 lake-verified with no `sorry` and no new axiom;
22 skeleton-pending with honest `sorry` markers; 1 open-problem-axiomatic (SBOM
Lambda-chain total order, conditional on A15); and 1 pure metatheorem (Lean
kernel soundness). The TH-V18 catalogue (16 stubs, TH-V18-01 through TH-V18-16)
builds clean under `lake build Lutar.Thesis` with 13 axiom declarations and
8 in-code `sorry` tactics, each enumerable by `grep` at the chapter-bind tag
2026-05-28 ([DOI 10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308)).

The [32-module runtime](https://github.com/szl-holdings/ouroboros) executes
934+ inline assertions (exit code 0) and emits SCITT-compatible, SHA-256-chained
receipts at every agent action. An OpenTelemetry SEMCONV extension surfaces
Lambda scores as first-class indexed telemetry. Domain grafts span seven
observability vendors (Splunk, Datadog, Dynatrace, New Relic, Better Stack,
Honeycomb, Grafana), four cybersecurity platforms (Palantir, Palo Alto Networks,
CrowdStrike, Fortinet), graph neural networks (PyTorch Geometric v2.7), sparse
self-attention (rasbt DSA), agentic IDE governance (Cursor + Claude Opus 4.8),
and sovereign-AI provenance (IQT Labs). Governance is enforced by Doctrine v6:
a machine-checked ban on marketing superlatives applied at CI time.

All code, proofs, and data publicly archived via Zenodo DOIs [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926), [10.5281/zenodo.20424992](https://doi.org/10.5281/zenodo.20424992), [10.5281/zenodo.20424995](https://doi.org/10.5281/zenodo.20424995), [10.5281/zenodo.20424996](https://doi.org/10.5281/zenodo.20424996), [10.5281/zenodo.20431181](https://doi.org/10.5281/zenodo.20431181), [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276), [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308).

---

**Keywords:** agentic AI governance, Lambda-axis calculus, Lean 4, Mathlib v4.13.0,
dual-witness receipts, Schur concavity, PAC-Bayes bounds, Doctrine v6,
SCITT receipt chain, sovereign AI, NIST FIPS 180-4, OpenTelemetry.
