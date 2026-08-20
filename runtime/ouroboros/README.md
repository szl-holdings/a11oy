<!-- szl-investor-header -->
<div align="center">

# ouroboros

### A runtime that keeps AI agents inside provable safety limits — every loop is bounded, witnessed, and produces a tamper-proof receipt.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/ouroboros/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/ci.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://docs.szlholdings.com) · [Quickstart](https://docs.szlholdings.com/quickstart) · [Live demo](https://szlholdings-readme.static.hf.space/) · [SZL Holdings](https://szlholdings.com)

</div>

## 💡 Why it matters

Autonomous agents can run away or skip oversight. Ouroboros guarantees each agent decision stays within a governance budget and emits a signed, replayable record connecting the policy to what actually executed.

## ▶️ Live demo

**[Open the live demo →](https://szlholdings-readme.static.hf.space/)**

[![demo screenshot](https://raw.githubusercontent.com/szl-holdings/szl-brand/main/kit/logos/png/kanchay-512.png)](https://szlholdings-readme.static.hf.space/)

<sub>_Screenshot: SZL Holdings kanchay mark — replace with a live capture of the running surface._</sub>

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/ouroboros.git
cd ouroboros
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://docs.szlholdings.com).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

<div align="center">

# ∞ ouroboros

<!-- series-a-badges (Doctrine v11) -->
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?style=flat-square&logo=dependabot&logoColor=white)](https://github.com/szl-holdings/ouroboros/security/dependabot)


**λ-gate loop**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276) [![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-a6ce39?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)
[![Doctrine](https://img.shields.io/badge/Doctrine-v11-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-L1_honest-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Hugging Face](https://huggingface.co/SZLHOLDINGS) · [Demo](https://szlholdings-readme.static.hf.space/) · [GitHub Org](https://github.com/szl-holdings)

`receipts.in ≡ receipts.out`

</div>

---
# ouroboros

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-0B1F3A.svg?style=flat-square&logo=apache&logoColor=00D4FF)](https://www.apache.org/licenses/LICENSE-2.0)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276)
[![CI](https://github.com/szl-holdings/ouroboros/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/ci.yml)
[![Tests](https://github.com/szl-holdings/ouroboros/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/tests.yml)
[![CodeQL](https://github.com/szl-holdings/ouroboros/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/codeql.yml)
[![GHAS Code Security](https://img.shields.io/badge/GHAS-Code_Security-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/ouroboros/security/code-scanning)
[![Secret Protection](https://img.shields.io/badge/GHAS-Secret_Protection-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/ouroboros/security/secret-scanning)
[![SBOM](https://github.com/szl-holdings/ouroboros/actions/workflows/sbom.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/sbom.yml)
[![SLSA L1 (SBOM + DCO)](https://img.shields.io/badge/SLSA-L1_(SBOM_%2B_DCO)-0B1F3A.svg?style=flat-square)](https://slsa.dev/spec/v1.0/levels)
[![DCO](https://github.com/szl-holdings/ouroboros/actions/workflows/dco.yml/badge.svg?branch=main)](https://github.com/szl-holdings/ouroboros/actions/workflows/dco.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/ouroboros/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/ouroboros)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)


> **NOTE:** SLSA Level 1 (source + build provenance documented). L2/L3 require Sigstore + isolated builders (roadmap).

> Bounded-loop runtime implementing the Lutar Invariant Λ — reference implementation for the Ouroboros Thesis governance framework.



> Receipt-complete bounded-loop runtime with dual-witness closure.  
> Every agent decision produces a COSE_Sign1-wrapped dual-witness receipt connecting governance policy to execution trace.

> **Thesis cross-reference:** The mathematical foundations for this repository are developed
> in the Ouroboros Thesis v18.0 (DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)).
> The thesis is published via the Zenodo DOIs above; the `ouroboros-thesis` repository has been retired and the Lean kernel lives in [`lutar-lean`](https://github.com/szl-holdings/lutar-lean).
> Concept DOI (always-latest): [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926).

## On Hugging Face

This repository's live demos, dataset mirror, and org showcase live on the [SZLHOLDINGS Hugging Face org](https://huggingface.co/SZLHOLDINGS):

| Surface | Hugging Face artifact |
|---------|---------------------|
| **Live demo** | [szl-showcase](https://huggingface.co/spaces/SZLHOLDINGS/szl-showcase) · [szl-cookbook-runner](https://huggingface.co/spaces/SZLHOLDINGS/szl-cookbook-runner) |
| **Org showcase** | [SZLHOLDINGS on Hugging Face](https://huggingface.co/SZLHOLDINGS) — 26 Spaces · 29 datasets · 2 models |

## Mathematical Foundation

The runtime enforces the Lutar Invariant: every agent decision loop terminates with a
Λ-score in \[0, 1\] satisfying the four-axiom characterisation (A1 monotone, A2 homogeneous,
A3 Egyptian-exact, A4 bounded). Λ uniqueness (TH10, `lutar_is_geomean`) is formally stated in Lean in
[szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean)
(DOI [10.5281/zenodo.20434308](https://doi.org/10.5281/zenodo.20434308)).

Every receipt payload is bounded by the GradeVec schema (9 axes × NNReal) and the
COSE_Sign1 envelope structure. Payload size is contractually constrained by the
receipt schema, not by a physical bound.

## Table of Contents

- [Mathematical Foundation](#mathematical-foundation)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [Governance Receipts](#governance-receipts)
- [How to Cite](#how-to-cite)
- [Companion Repositories](#companion-repositories)
- [License](#license)

## Repository Layout

| Path | Contents |
|------|----------|
| `src/` | Core runtime — loop scheduler, Λ-evaluator, receipt emitter |
| `runtime/` | Agentic loop infrastructure |
| `agentic/` | Agent harness and dual-witness emitters |
| `packages/` | Scoped npm packages (`@szl/ouroboros-*`) |
| `LUTAR_EVIDENCE.md` | Runtime parity evidence log (218 reference vectors) |

## Quick Start

```sh
git clone https://github.com/szl-holdings/ouroboros.git
cd ouroboros
pnpm install
pnpm test
```

> [!Note]
> Node.js ≥ 20 required. The `.nvmrc` file pins the exact version. See
> [szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) for the
> Lean 4 formal proofs that verify the core invariant properties.

## Governance Receipts

Each decision loop emits a COSE_Sign1-wrapped receipt
([RFC 9052](https://www.rfc-editor.org/rfc/rfc9052)) carrying:
- Λ score at loop exit.
- Payload-size attestation (schema-bounded GradeVec + hash).
- Dual-witness signatures.
- Shannon entropy measure of the decision code.

Receipts are anchored to SCITT transparency ledgers per
[draft-ietf-scitt-architecture-07](https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/).

## How to Cite

```bibtex
@software{ouroboros_runtime,
  author    = {Lutar, Stephen P.},
  title     = {{ouroboros --- Bounded-loop runtime implementing the Lutar Invariant}},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19944926},
  url       = {https://doi.org/10.5281/zenodo.19944926}
}
```

The `CITATION.cff` in this repository root is the authoritative citation source.

## Companion Repositories

| Repository | Role |
|-----------|------|
| Ouroboros Thesis (retired repo) | Formal thesis (v18.0, DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)) |
| [szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) | Lean 4 proofs of Λ uniqueness and bounds |
| a11oy Memory *(codename amaru, retired)* | Cardano-anchored receipt minting, consolidated into [`a11oy`](https://github.com/szl-holdings/a11oy) |
| [szl-holdings/vsp-otel](https://github.com/szl-holdings/vsp-otel) | OpenTelemetry exporter for audit fibers |

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).

Copyright 2026 SZL Holdings. ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).

---

## Related repositories in the SZL substrate

The SZL substrate repos cross-link reciprocally. This footer is maintained by GH Admin #1 (org-wide).

- [`a11oy`](https://github.com/szl-holdings/a11oy) — vertical alignment substrate (policy · measurement · knowledge · QEC-integrity)
- **a11oy Memory** *(codename amaru, retired)* — Shor-encoded receipt minting (Cardano-anchored), consolidated into a11oy
- **a11oy Operator** *(codename rosie, retired)* — CSS-ingress receipt orchestration, consolidated into a11oy
- **a11oy Sentinel** *(codename sentra, retired)* — Kitaev-surface drift detection on audit fibers, consolidated into a11oy
- [`uds-mesh`](https://github.com/szl-holdings/uds-mesh) — UDS span schemas + governance receipts
- [`lutar-lean`](https://github.com/szl-holdings/lutar-lean) — Lean 4 + Mathlib v4.13.0 kernel proofs (32 GREEN modules · 749 declarations · 163 sorries · canonical @ `c7c0ba17`)
- [`ouroboros`](https://github.com/szl-holdings/ouroboros) — bounded-recursion runtime
- Ouroboros Thesis (retired repo) — DOI-pinned thesis substrate (v3 → v18), published via Zenodo DOI
- [`platform`](https://github.com/szl-holdings/platform) — composing monorepo (76 packages, 1,220 tests)
- [`szl-brand`](https://github.com/szl-holdings/szl-brand) — anatomy + visual doctrine (PDFs hosted in-repo)
- [`szl-cookbook`](https://github.com/szl-holdings/szl-cookbook) — governed-AI recipes
- `agi-forecast` (retired) — PAC-Bayes governance-trajectory forecasts
- [`vsp-otel`](https://github.com/szl-holdings/vsp-otel) — OpenTelemetry exporter for Λ-axis spans

Org page: [github.com/szl-holdings](https://github.com/szl-holdings) · Doctrine v11 · 15 axioms (14 unique) · 749 declarations · 163 sorries · 32 GREEN modules · v18.0 DOI [`10.5281/zenodo.20434276`](https://doi.org/10.5281/zenodo.20434276)


---

## What ouroboros Is NOT

Doctrine v11 honest scoping:

- **Not a general-purpose task scheduler.** ouroboros implements bounded-recursion governance for SZL domain verticals only.
- **Not a replacement for the Lean proofs.** Runtime termination is enforced operationally; formal proof lives in `lutar-lean`.
- **Not an autonomous decision-maker.** Every cycle requires human-in-the-loop confirmation via the Covenant Policy Engine.
- **Not stable API.** v6.x is the current semver; breaking changes follow SemVer with CHANGELOG entries.


</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA L1 honest · Section 889 = 5 vendors · [SZL Holdings](https://szlholdings.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>
