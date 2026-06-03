---
title: "a11oy — Governance Substrate"
emoji: "🔬"
colorFrom: indigo
colorTo: gray
sdk: docker
pinned: true
license: apache-2.0
short_description: "a11oy — policy + receipt substrate"
tags:
  - formal-verification
  - lean4
  - mathlib
  - dsse
  - governance
  - agentic-ai
  - doctrine-v11
  - a11oy
  - execution-fabric
ecosystem-stage: "operational"
---

# a11oy — Signed UDS Payload

## Lean-Verified

[![Lean-verified: composition_preserves_doctrine](https://img.shields.io/badge/Lean%204%20kernel-composition__preserves__doctrine%20%E2%9C%85-22c55e?style=flat-square&logo=github)](https://github.com/szl-holdings/lutar-lean/actions/runs/26854942475)

> ✅ **Lean-verified theorem:** `composition_preserves_doctrine` in `Lutar/Composition/TH1_Composition.lean`  
> Verified by Lake CI at commit `acd0fd46` (Mathlib v4.13.0 + Lean 4, kernel commit `c7c0ba17`).  
> Zero sorries · Full kernel check pass · [CI Run](https://github.com/szl-holdings/lutar-lean/actions/runs/26854942475)  
> This theorem proves that sequential composition of two doctrine-locked Lutar systems yields a doctrine-locked composed system — the formal foundation for the SZL governance stack.  
> Λ remains **Conjecture 1** (uniqueness TH10 is not yet fully proved). This is the first named green theorem on [lutar-lean main](https://github.com/szl-holdings/lutar-lean).

Policy substrate with HMAC-signed receipts for every gated decision.

## Prerequisites

- [Zarf](https://docs.zarf.dev/getting-started/install/) v0.38+
- [cosign](https://docs.sigstore.dev/cosign/installation/) v2.2+
- [UDS CLI](https://uds.defenseunicorns.com/docs/getting-started/) v0.14+
- OCI registry access to `ghcr.io/szl-holdings`

## Quickstart — Deploy on UDS

```bash
# 1. Pull the signed Zarf package
zarf package pull oci://ghcr.io/szl-holdings/a11oy:v0.1.11

# 2. Verify the cosign keyless signature (before deploying)
cosign verify-blob \
  --certificate-identity-regexp "https://github.com/szl-holdings/a11oy/.github/workflows/.*" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --bundle zarf-package-a11oy-amd64-v0.1.11.tar.zst.sigstore.json \
  zarf-package-a11oy-amd64-v0.1.11.tar.zst

# 3. Deploy
uds deploy oci://ghcr.io/szl-holdings/a11oy:v0.1.11
```

## Runtime demonstration

The same payload, running on Hugging Face for live demo:  
[szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space)

## Source

Every file in this repository builds the signed payload above. See `deploy/zarf.yaml`, `deploy/uds-package.yaml`, `deploy/peat-node.yaml`.

---

`/v1/policy/evaluate` · `/v1/verify` · `/v1/ledger` — one substrate, hash-chained, deny by default.

Open the full mesh: [SZLHOLDINGS/uds-demo](https://huggingface.co/spaces/SZLHOLDINGS/uds-demo)

Source: [github.com/szl-holdings/a11oy](https://github.com/szl-holdings/a11oy) · DOI: [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

Apache-2.0 · Doctrine v11 LOCKED (749/14/163) · ORCID [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)

## Live endpoints

| Path | Description |
|:-----|:------------|
| `/` | Vessels-DNA landing (preserved, commit `49ac0467`) |
| `/console/` | Operator SPA (5 working routes — health, ledger, receipt, verify, policy) |
| `/api/a11oy/healthz` | Liveness probe |
| `/api/a11oy/readyz` | Readiness probe |
| `/api/a11oy/v1/ledger` | Proof ledger (GET) |
| `/api/a11oy/v1/verify` | Chain verification (POST) |
| `/api/a11oy/v1/policy/evaluate` | Policy gate (POST) |
| `/codex-kernel` | Replay-grade governed-loop primitive |
| `/wires` | Mesh interconnects — Wire B & C LIVE, Wire D NOT YET IMPLEMENTED |
| `/evidence` | LUTAR_EVIDENCE ledger |
| `/substrate` | `@szl/substrate` package surface |
| `/api/a11oy/v1/honest` | Honesty disclosure (JSON) |

## What is honest right now

lutar-lean @ `lutar-v18.0.0` / `c7c0ba17`: **749 declarations · 14 unique axioms (15 raw, 1 dup) · 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.

- **Λ uniqueness is a Conjecture**, not a closed theorem — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**; Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
- **SLSA: L1 (honest)** — previously mis-claimed as L3; corrected in platform PR #235.
- **Receipts:** DSSE envelopes ship from the amaru tick endpoint; Sigstore CI signing is **PENDING**.
- Aligned with **EU AI Act Article 12** + **NIST AI RMF (MANAGE)**.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `cosign: no bundle found` | Wrong tag in bundle filename | Re-pull with exact tag from release assets |
| `uds deploy` hangs | UDS Core not running | `uds deploy k3d-core` first |
| `/healthz` returns 503 | Container starting | Wait 30s, retry |
| `lake build` fails | Lean cache cold | First build takes ~5 min; subsequent builds are cached |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All commits require a DCO sign-off:

```
Signed-off-by: Your Name <you@example.com>
```

Use `git commit -s` to add automatically.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability disclosure policy.

## License

Apache-2.0. See [LICENSE](LICENSE).

## Doctrine

- Doctrine v11 LOCKED 749/14/163 at kernel commit `c7c0ba17`
- Λ-aggregator: Conjecture 1 (NOT theorem)
- SLSA L1 honest
- Section 889 = exactly 5 vendors (Huawei, ZTE, Hytera, Hikvision, Dahua)

