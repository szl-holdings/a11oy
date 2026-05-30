# a11oy — governed agentic execution fabric

[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/a11oy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
[![License: Proprietary](https://img.shields.io/badge/License-SZL_Proprietary-0B1F3A.svg?style=flat-square)](./LICENSE)
[![Latest release](https://img.shields.io/github/v/release/szl-holdings/a11oy?sort=semver&style=flat-square)](https://github.com/szl-holdings/a11oy/releases/latest)
[![SLSA L1](https://img.shields.io/badge/SLSA-L1_honest-22c55e.svg?style=flat-square)](https://slsa.dev/spec/v1.0/levels)
[![Doctrine](https://img.shields.io/badge/Doctrine-v7-7c5cff?style=flat-square)](https://github.com/szl-holdings/.github/blob/main/DOCTRINE_V7.md)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

> The orchestrator at the center of the SZL stack — TypeScript packages for policy gates, signal measurement, knowledge-graph traversal, and QEC-integrity verification connecting enterprise signals to human-confirmed decisions with cryptographic proof at every transition.

---

## What it does

`a11oy` (Alloy) is the governed agentic execution fabric. It enforces anchor-formula policy gates, measures incoming signals, traverses a knowledge graph, and emits proof at each state transition before a decision reaches a human confirmation checkpoint. Every other Tier-1 module depends on it via `@workspace/a11oy-orchestration`.

---

## Architecture in this stack

`a11oy` **is the center** of the five-module stack. It is the orchestrator the other four modules wire into: [`sentra`](https://github.com/szl-holdings/sentra) pushes security telemetry in, [`amaru`](https://github.com/szl-holdings/amaru) mints the receipts `a11oy` emits, [`rosie`](https://github.com/szl-holdings/rosie) is the operator console over the resulting receipt DAG, and [`vessels`](https://github.com/szl-holdings/vessels) is a domain UI consuming governed decisions. All four import `@workspace/a11oy-orchestration`.

```
   sentra ─────┐                                  ┌───── rosie
 (security)    │                                  │  (operator console)
               ▼                                  │
        ┌───────────────────────────────────┐    │
        │              a11oy                 │◄───┘
        │  L1 policy gates (anchor formulas) │
        │  L2 measurement fiber              │◄──────── vessels
        │  L3 knowledge-graph traversal      │       (maritime UI)
        │  L4 QEC-integrity verification     │
        │  L5 proof ledger                   │──────►  amaru
        │  L6 human confirmation gate        │      (receipt minting)
        └───────────────────────────────────┘
```

Operational map: [`docs/ECOSYSTEM.md`](docs/ECOSYSTEM.md) · Provenance contract: [`docs/PROVENANCE.md`](docs/PROVENANCE.md)

---

## Quick demo

```bash
# Full stack (UDS):
uds run start
# Module only:
pnpm install
pnpm test                          # policy-gate assertion suite
pnpm payload:verify                # verify deploy payload integrity
```

---

## Hugging Face surfaces

| Surface | Link |
|---------|------|
| Landing | [SZLHOLDINGS/a11oy-platform](https://huggingface.co/spaces/SZLHOLDINGS/a11oy-platform) |
| Diligence mirror | [SZLHOLDINGS/a11oy-v19-substrate](https://huggingface.co/SZLHOLDINGS/a11oy-v19-substrate) |
| Org | [huggingface.co/SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) |

Hugging Face is a mirror, regenerated from tracked source with `pnpm payload:huggingface` — not the canonical release source.

---

## Receipts and provenance

State transitions emit DSSE envelopes (in-toto statement payloads). Release artifacts carry SBOMs (SPDX + CycloneDX), and the repo ships SLSA-provenance workflows. Latest-release signature search via the public Sigstore transparency log:

- Sigstore search: [search.sigstore.dev](https://search.sigstore.dev/)
- Release artifacts: [github.com/szl-holdings/a11oy/releases/latest](https://github.com/szl-holdings/a11oy/releases/latest)

---

## Verified numbers

All counts are grep-verifiable against `main`.

| Metric | Value | Verify |
|--------|-------|--------|
| Anchor-formula gate modules | 45 | `ls packages/policy/src/gates/*_gate.ts \| wc -l` |
| Substrate packages | 12 | `ls packages/ \| wc -l` |
| Lean declarations (lutar-lean) | 626 | `grep -rE '^(theorem\|lemma\|def\|abbrev\|axiom) ' lutar-lean/Lutar/ \| wc -l` |
| Lean axioms (lutar-lean) | 15 raw / 14 unique | `grep -rE '^axiom ' lutar-lean/Lutar/ \| wc -l` |
| Lean sorries (lutar-lean) | 189 (138 baseline + 51 Putnam) | `grep -rE '\bsorry\b' lutar-lean/Lutar/ \| wc -l` |
| Putnam status | 4/12 Lean-discharged [A1, A5, B4, B6] · 8/12 structure | [lutar-lean](https://github.com/szl-holdings/lutar-lean) |
| Doctrine | v7 · 15 axioms (14 unique) | [.github/DOCTRINE_V7.md](https://github.com/szl-holdings/.github/blob/main/DOCTRINE_V7.md) |
| SLSA | L1 honest (SBOM + DCO; source + build provenance documented) | [slsa.dev](https://slsa.dev/spec/v1.0/levels) |

> Gate modules present on `main`: 45 files in `packages/policy/src/gates/`. The aggregate index (`packages/policy/src/gates/index.ts`) currently re-exports a subset; remaining modules are imported directly by their consumers. Count reflects files on disk, verifiable with the command above.

---

## Warhacker 2026

Featured at Warhacker, June 16–19. A running deployment is available via [`szl-holdings/szl-uds-deployment`](https://github.com/szl-holdings/szl-uds-deployment) v0.4.0.

---

## License

`LicenseRef-SZL-Proprietary` — SZL Holdings. Apache-2.0 re-licensing pending draft PR [#57](https://github.com/szl-holdings/a11oy/pull/57). See [LICENSE](./LICENSE).

---

## Citing

See [CITATION.cff](./CITATION.cff).

```
S. P. Lutar Jr., "a11oy — Governed agentic execution fabric,"
Zenodo, DOI 10.5281/zenodo.20434276, 2026.
```

ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173) · DOI: [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

---

## Security

See [SECURITY.md](./SECURITY.md) for responsible-disclosure policy.
