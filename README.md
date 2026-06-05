---
title: "a11oy — Governance Substrate"
emoji: "🔬"
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
short_description: "a11oy — signed-receipt substrate; receipts.in ≡ receipts.out"
tags:
  - governance
  - agentic-ai
  - doctrine-v11
  - a11oy
  - slsa-l2
  - apache-2.0
ecosystem-stage: "operational"
---

# a11oy 🔬

> **The signed-receipt substrate. Every AI decision leaves a DSSE Khipu receipt. `receipts.in ≡ receipts.out`.**

[![SLSA L1 + L2](https://img.shields.io/badge/SLSA-L1%20%2B%20L2%20attested-2C5F2D?style=flat-square)](.compliance/SLSA_LEVEL.md)
[![cosign signed](https://img.shields.io/badge/cosign-keyless%20signed-blueviolet?style=flat-square)](https://search.sigstore.dev/?logIndex=1710578865)
[![doctrine-v11](https://img.shields.io/badge/doctrine-v11%20LOCKED-0B1F3A?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine)
[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/a11oy/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](LICENSE)

**749 declarations · 14 axioms · 163 sorries · Doctrine v11 LOCKED · kernel `c7c0ba17`**

[Live demo](#live) · [What it does](#what-it-does) · [Verify](#verify-it-yourself) · [Architecture](#architecture) · [Parity vs. leaders](#parity-vs-leaders) · [Honest status](#honest-status)

---

## Live

**HF Space (one-click, no login):** [![Open in Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Open%20in%20Spaces-a11oy-FF9D00?style=flat-square)](https://huggingface.co/spaces/SZLHOLDINGS/a11oy)

- **Primary face — the full application:** https://szlholdings-a11oy.hf.space/ (also at `/console`)
- Space URL: https://szlholdings-a11oy.hf.space
- Health: `curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest | jq .kernel_commit` → `"c7c0ba17"`
- Docs: https://docs.szlholdings.com/flagships/a11oy
- Release: [v1.0.0](https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0)

---

## The application

a11oy is a **full left-nav application** — not a landing page or a single console panel. It opens directly to the Command Center and carries the unified SZL house style (dark ground, gold `#c9b787` + teal `#5fb3a3` accents, Space Grotesk + JetBrains Mono) with a **cross-flag switcher** in the top ribbon that jumps to a11oy · sentra · amaru · rosie · killinchu in one click.

**Primary app file:** [`pages/console.html`](pages/console.html) · **served at** `/` and `/console`.

Working views in the left navigation:

| View | What it does |
|---|---|
| **Command Center** | Live operational overview — organ health, recent verdicts, receipt stream |
| **Five Superpowers** | The five orchestrated capabilities a11oy coordinates across the mesh |
| **Warhacker** | Maps the five Warhacker problems to the organ(s) that solve each, with a live signed receipt |
| **Observability** | MELT + distributed tracing where every span is a signed Khipu receipt (vs New Relic / Datadog / OTel) |
| **Wires** | The live inter-organ wires (a11oy↔sentra immune, a11oy↔rosie receipts, a11oy↔amaru cortex) |
| **Mesh** | Live cross-organ reachability — real probes, honest when an organ is unreachable |
| **Formulas** | The PURIQ formula set — **5 proved in Lean 4 {F1, F11, F12, F18, F19}**, the rest Roadmap |
| **Evidence** | Body-of-evidence export — DSSE Khipu receipts, replayable and tamper-evident |
| **LLM Router** | The governed LLM routing surface |

---

## What it does

**a11oy is the audit-fiber continuity layer for the SZL mesh.** Every AI action routes through a11oy and leaves a DSSE-enveloped Khipu receipt on a SHA-256 hash-linked Merkle DAG. The invariant is `receipts.in ≡ receipts.out`: nothing is lost between the decision and the proof.

Key capabilities:
- **Policy + receipt substrate** — `/v1/policy/evaluate`, `/v1/verify`, `/v1/ledger`: deny-by-default; every action signed
- **Honest disclosure** — `/v1/honest` reports live doctrine posture (749/14/163, Λ = Conjecture 1)
- **8 TS workspace libs** — `@szl-holdings/a11oy-knowledge`, `a11oy-policy`, `a11oy-qec-integrity`, `a11oy-receipt-substrate`, `perception-loop`, `rae1`, `sequence-pipeline`, `sparse-attention-kit`
- **DSSE Khipu receipts** — ECDSA P-256-SHA256; multi-party-witnessed; BFT quorum-capable

---

## Verify it yourself

```bash
# 1. Confirm live doctrine posture
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest | jq .kernel_commit
# => "c7c0ba17"

# 2. Verify the cosign keyless signature on the published image (SLSA L1).
#    GHCR verification shows a cosign-signed image (L1); the SLSA provenance
#    attestation (L2) verifies via `cosign verify-attestation --type slsaprovenance`
#    with strict identity. See .compliance/SLSA_LEVEL.md.
cosign verify ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
# Public Rekor entry for the image signature: log index 1710578865

# 3. Verify the SLSA L2 provenance attestation (strict identity)
cosign verify-attestation --type slsaprovenance ghcr.io/szl-holdings/a11oy:uds-v0.2.0 \
  --certificate-identity-regexp="https://github.com/szl-holdings/a11oy/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"

# 4. Deploy as part of the signed 5-organ mesh bundle
#    (organ images are L2-attested; the bundle artifact itself is not yet attested)
uds-cli bundle deploy oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0 --confirm
```

**Full guide:** [developers/VERIFY.md](https://github.com/szl-holdings/developers/blob/main/VERIFY.md)

---

## Architecture

```mermaid
graph TD
    A[Incoming action] --> PL[Policy layer\n/v1/policy/evaluate\ndeny-by-default]
    PL --> KD[Khipu DAG\nDSSE P-256 signed\nSHA-256 hash-linked]
    KD --> LDG[Ledger /v1/ledger\nreplayable, tamper-evident]
    KD --> UDS[(GHCR\nSigned OCI\ncosign-signed · SLSA L2 attested)]
    KD --> REKOR[(Rekor transparency log\nindex 1710578865)]
```

---

## Parity vs. leaders

| Capability | Palantir AIP | a11oy | Differentiator |
|---|---|---|---|
| Policy enforcement | ✅ | ✅ `/v1/policy/evaluate` | — |
| Audit trail | ✅ logs | ✅ **signed receipts** | Palantir logs are not individually verifiable cryptographic artifacts |
| Supply-chain provenance | — | ✅ **cosign-signed + SLSA L2 attested** | `cosign verify` + `cosign verify-attestation --type slsaprovenance` on every image — they don't offer this. |
| Formal math substrate | — | ✅ Lean 4 / 749 decl | Open, machine-checkable |
| Air-gap deployment | ✅ (proprietary) | ✅ **one UDS command** | Open-source, reproducible |
| Receipt multi-party witness | — | ✅ BFT quorum-capable | — |

---

## Quickstart

```bash
docker run --rm -p 7860:7860 ghcr.io/szl-holdings/a11oy:uds-v0.2.0
```

---

## Honest status

| Claim | Status |
|---|---|
| Live HF Space (HTTP 200) | ✅ |
| SLSA Build L1 + L2 | ✅ — cosign-signed image (L1), verifiable via `cosign verify`; Rekor [1710578865](https://search.sigstore.dev/?logIndex=1710578865). L2 SLSA provenance attestation verifies via `cosign verify-attestation --type slsaprovenance` (strict identity, keyless Fulcio+Rekor). See [.compliance/SLSA_LEVEL.md](.compliance/SLSA_LEVEL.md). |
| cosign keyless signed | ✅ |
| UDS bundle (`szl-uds-bundle:uds-v0.2.0`) | ✅ Real, deployable 5-organ bundle. **Note:** the bundle artifact itself is **not yet SLSA-attested** (owner-only GHCR package-write grant pending). The L2 build-provenance attestation that verifies is on the **5 organ images**, not the bundle. |
| DSSE Khipu receipts | ✅ — ECDSA P-256-SHA256 |
| Lean 749/14/163 @ `c7c0ba17` | ✅ |
| Proved PURIQ formulas | ✅ Exactly **5** — F1, F11, F12, F18, F19 (Lean 4, zero-sorry). Remaining formulas are Roadmap. |
| Λ-uniqueness | ⚠️ **Conjecture 1** (F23 open bounty) — never a theorem |
| SLSA L3 | ❌ Not claimed |
| FedRAMP / CMMC | ❌ Not claimed |

---

<sub>Doctrine v11 LOCKED · 749/14/163 · kernel `c7c0ba17` · SLSA L1 + L2 (provenance attestation verified; L3 not claimed) · Λ = Conjecture 1 · Apache-2.0 · DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)</sub>

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

