# a11oy — doctrine-bound agent orchestrator and substrate for SZL's receipt-bus

[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/a11oy/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/a11oy)
[![License: Proprietary](https://img.shields.io/badge/License-SZL_Proprietary-0B1F3A.svg?style=flat-square)](./LICENSE)
[![Doctrine v7](https://img.shields.io/badge/Doctrine-v7-7c5cff?style=flat-square)](https://github.com/szl-holdings/.github/blob/main/doctrine/DOCTRINE_V7.md)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

> A measurable governance operator on the receipt-bus σ-algebra of agentic AI — proved in Lean 4, run sub-millisecond, packaged as a UDS-deployable bundle, and aligned with EU AI Act Article 12 + NIST AI RMF.

---

## 30-second pitch

**What is this?** `a11oy` is the substrate that orchestrates every AI action in the SZL mesh. It enforces policy gates derived from formally proved Lean 4 theorems, routes signed receipts across the mesh, and ensures no decision reaches the world without cryptographic provenance. The mesh-router is wired to `/v1/inspect` (merged PR #176), and cooperative multi-agent termination is proved via the Lynch 1996 theorem wired to Lean theorem `TH_V18_15` in the `multi_agent_terminator`.

**Why does it exist?** Every agent in the SZL mesh is an antenna. Every action emits a signed receipt the moment it happens. The substrate sees the live operational state of every AI in the system in real time, with cryptographic provenance, before any decision touches the world. `a11oy` is that substrate — the always-on, doctrine-bound orchestrator that makes "governed AI" a measurable runtime property, not a post-hoc audit claim.

**Who is it for?** Defense Unicorns integration teams who need a UDS-deployable AI orchestration layer that satisfies NIST AI RMF govern/map/measure/manage; EU AI Act Article 12 audit-log compliance teams; and Series A diligence reviewers who need verifiable proof that governance is baked in, not bolted on.

---

## Architecture — a11oy at center

```
         ┌──────────────────────────────────────────────────────┐
         │                    a11oy substrate                    │
         │  L1 policy gates (45 anchor-formula gate modules)    │
         │  L2 measurement fiber (Λ 9-axis, floor 0.90 conj.)  │
         │  L3 knowledge-graph traversal                        │
         │  L4 QEC-integrity verification                       │
         │  L5 proof ledger (DSSE-enveloped receipts)          │
         │  L6 human confirmation gate                          │
         │  mesh-router → /v1/inspect (PR #176)                │
         │  multi_agent_terminator ← TH_V18_15 (Lynch 1996)    │
         └──────────────────────────────────────────────────────┘
              ▲                    ▲                    ▲
    sentra (immune)        amaru (cortex)       rosie (console)
    /v1/inspect             /receipts           approval-router
    8-gate admission        OODA loop           mesh-health agg.
              ▲                    ▲                    ▲
         └──────────────────────────────────────────────────────┘
                              vessels
                    (cosign-signed UDS bundles)
```

Operational map: [`docs/ECOSYSTEM.md`](docs/ECOSYSTEM.md) · Provenance contract: [`docs/PROVENANCE.md`](docs/PROVENANCE.md)

---

## Quickstart

```bash
# Future-public image (pending Stephen's GHCR visibility task):
docker pull ghcr.io/szl-holdings/a11oy:latest

# Local demo via UDS bundle:
./demo.sh          # points at USB-bundle-equivalent local demo

# Full stack:
uds run start

# Module only:
pnpm install
pnpm test          # policy-gate assertion suite
pnpm payload:verify
```

---

## Receipt-bus integration — example receipt

```json
{
  "specversion": "1.0",
  "type": "szl.receipt.policy_gate.v1",
  "source": "a11oy/mesh-router",
  "organ": "a11oy",
  "gate": "anchor_formula_gate",
  "decision": "ALLOW",
  "agent_id": "urn:szl:agent:a11oy-coordinator-01",
  "signed_by": "sigstore/keyless",
  "lambda_axes": {
    "computability": 0.97,
    "moralGrounding": 0.96,
    "ontologicalGrounding": 0.94,
    "measurabilityHonesty": 0.95,
    "convergence": 0.93,
    "boundedness": 0.92,
    "completeness": 0.91,
    "consistency": 0.93,
    "auditability": 0.97
  },
  "lean_theorem": "TH_V18_15",
  "dsse_envelope": "eyJ...",
  "timestamp": "2026-05-31T10:26:00Z"
}
```

---

## Λ-9-axis governance

The Λ invariant is measured across 9 axes on every receipt. Floor is 0.90 conjunctive; `moralGrounding` and `measurabilityHonesty` require ≥ 0.95.

| Axis | Floor | Description |
|------|-------|-------------|
| `computability` | 0.90 | Halting / resource bound |
| `moralGrounding` | **0.95** | Value alignment to doctrine |
| `ontologicalGrounding` | 0.90 | Entity reference integrity |
| `measurabilityHonesty` | **0.95** | Calibrated uncertainty |
| `convergence` | 0.90 | Loop termination proof |
| `boundedness` | 0.90 | State-space containment |
| `completeness` | 0.90 | Decision coverage |
| `consistency` | 0.90 | Cross-receipt coherence |
| `auditability` | 0.90 | Receipt chain reconstructibility |

---

## Verification one-liners

```bash
# Cosign keyless verify (vessels release carries the canonical signed bundle):
cosign verify ghcr.io/szl-holdings/vessels:uds-v0.3.0 \
  --certificate-identity-regexp="github.com/szl-holdings" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# SBOM verify:
gh release download --repo szl-holdings/vessels uds-v0.3.0 --pattern "*.spdx.json"
syft attest --output spdx-json .

# Lean kernel verify (lutar-lean reproducibility bundle):
# 749 declarations / 15 raw axioms (14 unique) / 163 sorries @ HEAD c7c0ba17
# Reproducibility: .github/scripts/lean_numbers.py in szl-holdings/lutar-lean
git clone https://github.com/szl-holdings/lutar-lean && cd lutar-lean
lake build
python .github/scripts/lean_numbers.py
```

---

## Verified numbers

All counts are grep-verifiable against `main`.

| Metric | Value | Verify |
|--------|-------|--------|
| Anchor-formula gate modules | 45 | `ls packages/policy/src/gates/*_gate.ts \| wc -l` |
| Substrate packages | 12 | `ls packages/ \| wc -l` |
| Lean declarations (lutar-lean @ c7c0ba17) | **749** | `.github/scripts/lean_numbers.py` |
| Lean axioms (lutar-lean) | **15 raw / 14 unique** | `grep -rE '^axiom ' lutar-lean/Lutar/ \| wc -l` |
| Lean sorries (lutar-lean) | **163** (112 baseline + 51 Putnam) | `grep -rE '\bsorry\b' lutar-lean/Lutar/ \| wc -l` |
| Doctrine | v7 · 15 axioms (14 unique) | [DOCTRINE_V7.md](https://github.com/szl-holdings/.github/blob/main/doctrine/DOCTRINE_V7.md) |
| SLSA | L1 honest | [slsa.dev](https://slsa.dev/spec/v1.0/levels) |

> Lean build: green via `lake build` on lutar-lean `main`. Reproducibility script: `.github/scripts/lean_numbers.py`.

---

## Related

| Repo | Role |
|------|------|
| [szl-holdings/amaru](https://github.com/szl-holdings/amaru) | cognitive runtime for governed agent reasoning |
| [szl-holdings/sentra](https://github.com/szl-holdings/sentra) | policy-gated admission/egress inspection |
| [szl-holdings/rosie](https://github.com/szl-holdings/rosie) | human-in-the-loop operator surface |
| [szl-holdings/vessels](https://github.com/szl-holdings/vessels) | cosign-signed UDS deployment bundles |
| [szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean) | Lean 4 formal proofs (749 decls / 15 axioms) |
| [szl-holdings/ouroboros-thesis](https://github.com/szl-holdings/ouroboros-thesis) | Ouroboros Substrate v18.0 — DOI 10.5281/zenodo.20434276 |
| szl-holdings/platform/docs/a11oy/spec/hatun-doctrine-spec/ | Hatun Doctrine Specification (rename PR in flight via Squad B) |

---

## Citation

See [CITATION.cff](./CITATION.cff).

```
S. P. Lutar Jr., "a11oy — doctrine-bound agent orchestrator and substrate for SZL's receipt-bus,"
SZL Holdings, DOI 10.5281/zenodo.19944926, 2026.
```

ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173) · Concept DOI (always-latest): [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

---

## Trust + Security

Trust Tier 1. Vulnerabilities: [security@szlholdings.com](mailto:security@szlholdings.com) — 90-day coordinated disclosure. See [SECURITY.md](./SECURITY.md).

---

## License + Contributing

`LicenseRef-SZL-Proprietary` — SZL Holdings. Apache-2.0 re-licensing pending draft PR [#57](https://github.com/szl-holdings/a11oy/pull/57) (IP hold — do not merge until cleared). See [LICENSE](./LICENSE) and [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Hugging Face surfaces

| Surface | Link |
|---------|------|
| Landing | [SZLHOLDINGS/a11oy-platform](https://huggingface.co/spaces/SZLHOLDINGS/a11oy-platform) |
| Diligence mirror | [SZLHOLDINGS/a11oy-v19-substrate](https://huggingface.co/SZLHOLDINGS/a11oy-v19-substrate) |
| Org | [huggingface.co/SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) |

Hugging Face is a mirror regenerated from tracked source — not the canonical release source.

---

## Warhacker 2026

Featured at Warhacker, June 16–19. The publicly verifiable signed deployment artifact is the `vessels` release [uds-v0.3.0](https://github.com/szl-holdings/vessels/releases/tag/uds-v0.3.0) (cosign keyless; `.sigstore.json` + `.sha256`).
