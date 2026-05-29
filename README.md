# a11oy

[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-0B1F3A.svg?style=flat-square)](./LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276)
[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml)
[![Tests](https://github.com/szl-holdings/a11oy/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/tests.yml)
[![CodeQL](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/codeql.yml)
[![SBOM](https://github.com/szl-holdings/a11oy/actions/workflows/sbom.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/sbom.yml)
[![SLSA L1 (SBOM + DCO)](https://img.shields.io/badge/SLSA-L1_(SBOM_%2B_DCO)-0B1F3A.svg?style=flat-square)](https://slsa.dev/spec/v1.0/levels)
[![DCO](https://github.com/szl-holdings/a11oy/actions/workflows/dco.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/dco.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/a11oy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

> Vertical alignment substrate — policy, measurement, knowledge, and QEC-integrity packages for governed AI execution.  
> Doctrine v6 · DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

`a11oy` (Alloy) is the governed agentic execution fabric of SZL Holdings — the seven-layer substrate connecting live enterprise signals to human-confirmed decisions with cryptographic proof at every transition. It provides TypeScript packages for policy enforcement, signal measurement, knowledge-graph traversal, and QEC-integrity verification across all SZL domain verticals.

> [!NOTE]
> This repository ships the core fabric packages consumed by [`szl-holdings/platform`](https://github.com/szl-holdings/platform). The deployment surface for Alloy is the platform monorepo; this repo contains the standalone alignment substrate packages.
>
> **Status:** 35/35 anchor formulas wired as policy gates (5 on main; 30 in open PR #114 — merge pending review). Gate count is STAGED until PR #114 lands.

Operational map: [`docs/ECOSYSTEM.md`](docs/ECOSYSTEM.md) · Provenance contract: [`docs/PROVENANCE.md`](docs/PROVENANCE.md) · Series-A packet: [`docs/SERIES_A_DILIGENCE.md`](docs/SERIES_A_DILIGENCE.md)

---

## On Hugging Face

Live demos, dataset mirrors, and org showcase at [SZLHOLDINGS on Hugging Face](https://huggingface.co/SZLHOLDINGS):

| Surface | Artifact |
|---------|----------|
| Generated diligence mirror | [a11oy-v19-substrate](https://huggingface.co/SZLHOLDINGS/a11oy-v19-substrate) |
| Org showcase | 24 Spaces · 26 datasets · 2 models |

Hugging Face is not the canonical release source. The mirror is regenerated from tracked source with `pnpm payload:huggingface`.

---

## What is real today

All counts are grep-verifiable from this repository.

| Metric | Count | Verify |
|--------|-------|--------|
| Policy gate anchors on `main` | 5 | `find packages/policy/src/gates -name "*.ts" \| wc -l` |
| Policy gate anchors (PR #114, pending merge) | 30 | PR #114 diff |
| Anchor formulas total (Ouroboros runtime) | 35/35 | `grep -r "FORMULA" packages/ \| wc -l` |
| CI assertion tests | 35 | `packages/policy/src/gates/index.test.ts` |
| Lean proof declarations (lutar-lean) | 217 | `grep -r "^theorem\|^lemma\|^def " ../lutar-lean/Lutar/ \| wc -l` |
| Lean axioms (lutar-lean) | 12 | `grep -r "^axiom " ../lutar-lean/Lutar/ \| wc -l` |
| Lean residual sorries | 7 | `grep -r "sorry" ../lutar-lean/Lutar/ \| wc -l` |
| HF Spaces (org) | 24 | [SZLHOLDINGS HF org](https://huggingface.co/SZLHOLDINGS) |
| HF datasets (org) | 26 | [SZLHOLDINGS HF org](https://huggingface.co/SZLHOLDINGS) |
| Zenodo DOIs | 7 | [Zenodo community](https://zenodo.org/communities/szl-holdings) |

---

## Architecture

```
Enterprise signals
       │
       ▼
┌─────────────────────────────────────┐
│  a11oy layers                        │
│  L1  Policy gates (35 anchors)       │
│  L2  Measurement fiber               │
│  L3  Knowledge graph traversal       │
│  L4  QEC-integrity verification      │
│  L5  Audit receipt emission          │
│  L6  Human confirmation gate         │
│  L7  Cryptographic proof chain       │
└─────────────────────────────────────┘
       │
       ▼
Human-confirmed decision + receipt
```

---

## Quick start

```bash
pnpm install
pnpm build
pnpm test            # 35 policy-gate assertions
pnpm payload:doctrine  # doctrine v6 ban-word check
```

---

## License

Proprietary — SZL Holdings. IP transfer to Apache-2.0 pending resolution of PR #57. See [LICENSE](./LICENSE).

---

## Related repositories in the SZL substrate

The SZL Holdings org repos are organized in
[`docs/org-repo-map.md`](docs/org-repo-map.md). Use
`bash scripts/clone-org-repos.sh` to discover and clone sibling checkouts under
ignored `.repos/szl-holdings/`.

- [`a11oy`](https://github.com/szl-holdings/a11oy) — vertical alignment substrate (policy · measurement · knowledge · QEC-integrity)
- [`amaru`](https://github.com/szl-holdings/amaru) — Shor-encoded receipt minting (Cardano-anchored)
- [`rosie`](https://github.com/szl-holdings/rosie) — CSS-ingress receipt orchestration
- [`sentra`](https://github.com/szl-holdings/sentra) — Kitaev-surface drift detection on audit fibers
- [`uds-mesh`](https://github.com/szl-holdings/uds-mesh) — UDS span schemas + governance receipts
- [`lutar-lean`](https://github.com/szl-holdings/lutar-lean) — Lean 4 + Mathlib v4.13.0 proof substrate for scoped theorem/module claims
- [`ouroboros`](https://github.com/szl-holdings/ouroboros) — bounded-recursion runtime
- [`ouroboros-thesis`](https://github.com/szl-holdings/ouroboros-thesis) — DOI-pinned thesis substrate (v3 → v18)
- [`platform`](https://github.com/szl-holdings/platform) — composing monorepo (76 packages, 1,220 tests)
- [`szl-brand`](https://github.com/szl-holdings/szl-brand) — anatomy + visual doctrine (PDFs hosted in-repo)
- [`szl-cookbook`](https://github.com/szl-holdings/szl-cookbook) — governed-AI recipes
- [`agi-forecast`](https://github.com/szl-holdings/agi-forecast) — PAC-Bayes + Bekenstein governance-trajectory forecasts
- [`vsp-otel`](https://github.com/szl-holdings/vsp-otel) — OpenTelemetry exporter for Λ-axis spans
- [`vessels`](https://github.com/szl-holdings/vessels) — maritime fleet intelligence
- [`counsel`](https://github.com/szl-holdings/counsel) — legal matter command scaffold
- [`terra`](https://github.com/szl-holdings/terra) — real estate intelligence scaffold
- [`carlota-jo`](https://github.com/szl-holdings/carlota-jo) — private advisory operations scaffold
- [`szl-trust`](https://github.com/szl-holdings/szl-trust) — Public Trust Portal artifacts
- [`.github`](https://github.com/szl-holdings/.github) — organization profile and community files

Org page: [github.com/szl-holdings](https://github.com/szl-holdings) · Doctrine v6 · evidence-gated public claims · v18.0 DOI [`10.5281/zenodo.20434276`](https://doi.org/10.5281/zenodo.20434276)

---

## Security

See [SECURITY.md](./SECURITY.md) for responsible-disclosure policy.
