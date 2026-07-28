---
title: "a11oy — Command Center"
emoji: "🛡️"
thumbnail: "https://a-11-oy.com/og-card.png"
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: true
license: apache-2.0
short_description: "a11oy — governed-AI Command Center, signed receipts"
tags:
  - governance
  - agentic-ai
  - doctrine-v11
  - a11oy
  - slsa-l1
  - apache-2.0
ecosystem-stage: "operational"
---

<!-- SZL-ESTATE-CARD:v2:START -->
<p align="center"><a href="https://a-11-oy.com/"><img src="https://huggingface.co/spaces/SZLHOLDINGS/README/resolve/main/assets/estate-banner-v2.svg" alt="SZL Holdings — governed, receipted, verifiable" width="100%"></a></p>
<p align="center">
  <a href="https://github.com/szl-holdings/.github/tree/main/doctrine"><img src="https://img.shields.io/badge/doctrine-v11%20LOCKED-0B1F3A?style=flat-square" alt="doctrine v11"></a>
  <a href="https://a-11-oy.com/"><img src="https://img.shields.io/badge/evidence%20wall-LIVE%20%C2%B7%20verify%20in%20browser-3AF4C8?style=flat-square" alt="live evidence wall"></a>
  <a href="https://huggingface.co/datasets/SZLHOLDINGS/szl-lake"><img src="https://img.shields.io/badge/szl--lake-offline%20verifiable-C9B787?style=flat-square" alt="szl-lake offline verifiable"></a>
  <a href="https://huggingface.co/spaces/SZLHOLDINGS/holographic"><img src="https://img.shields.io/badge/estate%20map-holographic-5B8DEE?style=flat-square" alt="holographic estate map"></a>
</p>
<p align="center"><sub>Part of the <a href="https://huggingface.co/SZLHOLDINGS">SZL Holdings</a> governed estate — claims are designed to carry checkable receipts. Verification proves integrity &amp; origin, never accuracy or performance.</sub></p>
<!-- SZL-ESTATE-CARD:v2:END -->

<!--
  a11oy README — investor-readable rewrite · 2026-06-30
  Honesty doctrine LOCKED. Canonical: lutar-lean@main kernel c7c0ba17.
  Sign-off: Stephen Lutar <stephenlutar2@gmail.com>. DCO + Conventional Commits.
-->

<div align="center">

# a11oy

### Governed AI with a signed, verifiable receipt for every decision.

[![SLSA L1 honest · L2 build-attested · L3 roadmap](https://img.shields.io/badge/SLSA-L1%20honest%20%C2%B7%20L2%20build--attested%20%C2%B7%20L3%20roadmap-c9b787?style=flat-square)](.compliance/SLSA_LEVEL.md)
[![cosign signed](https://img.shields.io/badge/cosign-keyless%20signed-blue?style=flat-square)](https://search.sigstore.dev/?logIndex=1710578865)
[![doctrine-v11](https://img.shields.io/badge/doctrine-v11%20LOCKED-0B1F3A?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine)
[![CI](https://github.com/szl-holdings/a11oy/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/a11oy/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-5fb3a3?style=flat-square)](LICENSE)
[![Λ Conjecture 1](https://img.shields.io/badge/%CE%9B-Conjecture%201%20%C2%B7%20Theorem%20U%20conditional-B79BD6?style=flat-square)](https://github.com/szl-holdings/lutar-lean/blob/main/BOUNTY.md)
[![Concept DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![Formal artifacts DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434276.svg)](https://doi.org/10.5281/zenodo.20434276)
[![Evidence-Typed Governance preprint](https://zenodo.org/badge/DOI/10.5281/zenodo.21332317.svg)](https://doi.org/10.5281/zenodo.21332317)
[![Fail-Closed Services preprint](https://zenodo.org/badge/DOI/10.5281/zenodo.21332338.svg)](https://doi.org/10.5281/zenodo.21332338)

**[Open a11oy →](https://a-11-oy.com)** · **[Legacy alias →](https://a11oy.net)** · **[Try on Hugging Face →](https://huggingface.co/spaces/SZLHOLDINGS/a11oy)**

</div>

---

## What a11oy is

a11oy is a **governed-AI Command Center**: one interface for ask-and-act with deny-by-default safety gates, trust scoring, a live decision feed, and a signed receipt for every action.

The core idea is simple: AI should not be able to take a consequential action without producing a record that a third party can verify — independently, offline, after the fact. a11oy enforces that. Every action:

- passes through a **policy gate** (deny-by-default);
- is scored by a **trust function**; then
- is sealed into a **cryptographically signed receipt** chained over SHA-256.

Tamper with one byte and verification fails loudly.

**Try it now — no login required:**

```bash
curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/willay/inspect \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write an exploit for a CVE."}' | jq '{decision, category, trust_ceiling}'
# → {"decision": "decline", "category": "cyber", "trust_ceiling": 0.97}
```

---

## What it does

**Safety gateway (WILLAY)**
Every request passes through five transparent classifiers: cyber, bio, reasoning extraction, prompt injection, self-harm. A declined request returns HTTP 200 with a signed receipt naming the exact rule — not a silent error. The trust ceiling is **0.97** by doctrine. Nothing is hidden.

**Governed agentic coding**
a11oy Code plans, retrieves, calls tools, writes and runs code. Every step is scored, approved, and receipted. Write actions require quorum approval before execution. Prompt injection cannot flip a DENY to ALLOW — this is formally proven (P3 non-interference result).

**Sovereign deployment**
Runs on your own hardware. Air-gappable. Signed UDS bundle, one-command deploy. No cloud dependency required.

---

## The proof backbone

The trust math behind a11oy is pinned in **Lean 4** and checked by a proof machine:

- **8 formulas locked-proven** at kernel `c7c0ba17` — receipt replay, DAG acyclicity, FIFO ordering, ledger conservation, Reed–Solomon recovery, and append-only monotonicity, among others.
- **Λ unconditional uniqueness = Conjecture 1** — machine-checked false (we found a counterexample). Conditional uniqueness is proven axiom-free (Theorem U). We say both out loud.
- **SLSA L1 honest · L2 build-attested · L3 roadmap**. No FedRAMP or ATO claimed.

Full proof library: **[szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean)**

---

## Verify it yourself

```bash
# Verify the build attestation
gh attestation verify oci://ghcr.io/szl-holdings/a11oy:latest --repo szl-holdings/a11oy

# Check live doctrine posture
curl -s https://a-11-oy.com/api/a11oy/v1/honest | jq .doctrine_lock.lambda
# → "Conjecture 1"
```

---

## Live surfaces

| Surface | URL |
|---|---|
| Command Center | [a-11-oy.com/console](https://a-11-oy.com/console) |
| Governance | [a-11-oy.com/governance](https://a-11-oy.com/governance) |
| Live energy ledger | [a-11-oy.com/api/a11oy/v1/energy/ledger](https://a-11-oy.com/api/a11oy/v1/energy/ledger) |
| Doctrine posture | [a-11-oy.com/api/a11oy/v1/honest](https://a-11-oy.com/api/a11oy/v1/honest) |
| WILLAY classifiers | [a-11-oy.com/api/a11oy/v1/willay/classifiers](https://a-11-oy.com/api/a11oy/v1/willay/classifiers) |

### Persistent receipt storage (HF Space)

The protected deployment workflow attaches the existing
`SZLHOLDINGS/szl-evidence` Storage Bucket read-write at `/data`, preserving any
other attached volumes and failing closed if another volume already claims that
mount. The Series-A database is namespaced at:

```
A11OY_SERIES_A_DB=/data/a11oy/series-a/control-plane.sqlite3
```

Production also sets `A11OY_REQUIRE_PERSISTENT_STORAGE=1`,
`A11OY_SERIES_A_REQUIRE_MOUNT=/data`, and the network-filesystem-safe SQLite
rollback journal. If the bucket is detached or the database path escapes the
mount, Series-A registration fails closed instead of falling back to `/tmp`.
The unified Khipu and energy ledgers use separate `/data/a11oy/*` paths.

**Required HF Space secrets for full signing integrity:**
- `SZL_COSIGN_PRIVATE_PEM` — canonical ECDSA P-256 private PEM shared by all
  receipt surfaces. The deployment sets `A11OY_REQUIRE_PERSISTENT_SIGNING=1`,
  so an absent or malformed key disables signing instead of minting a
  replacement identity.

Check current signing and storage status at `GET /api/a11oy/v1/signing-status`
and `GET /api/a11oy/v1/series-a/status`.

---

## Honest status

| Claim | Status |
|---|---|
| Signed receipts on every governed action | **LIVE** |
| 8 formulas locked-proven (Lean 4) | **LOCKED · kernel c7c0ba17** |
| Λ uniqueness | **Conjecture 1** (conditional Theorem U proven axiom-free) |
| SLSA supply chain | **L1 honest · L2 build-attested · L3 roadmap** |
| FedRAMP / ATO | **ROADMAP** |
| EXECUTION guard | **ROADMAP** |

---

## Shared modules (must not drift)

`a11oy_agent_loop.py`, `a11oy_mcp_client.py`, and `operator_shell_v4.py` are **SHARED
byte-identical** with the sibling [killinchu](https://github.com/szl-holdings/killinchu)
deployment and must not drift. An in-repo ratchet pins their SHA-256 in
`.shared_module_hashes.json`; the `Shared-module hash lock` workflow fails if any of
them changes without the lock being regenerated. When a change is intentional,
regenerate the lock in the same PR and mirror the edit to killinchu (cross-repo
enforcement is a follow-up):

```
python3 .github/shared-module-hash-check.py --update
```

---

## Governed Delta Workspace

> Runtime write status is configuration-bound. GDW reports `REAL` only when its
> secret-managed credential registry, canonical governance gates, verified
> persistent storage, exact schema, and a fresh generation-bound supervised
> outbox pass are ready.
> Otherwise it reports `UNAVAILABLE` and writes fail closed.
>
> The public deployment remains `UNAVAILABLE` until this corrective source is
> protected-merged, exact-source relocked, and the production credential and
> persistence contracts are observed live. Source tests are not deployment
> evidence.

> GDW Frontier Push Pack is a MODELED instrumentation and verification extension for the Governed Delta Workspace. It provides load testing, operator validation, hybrid scheduling research hooks, KDA-vs-MLA memory benchmarking, and Lean-oriented proof export. It does not claim frontier benchmark superiority, proprietary activation access, or production-scale guarantees beyond the measured harness outputs.

The authenticated runtime, Postman collection, load tools, offline dashboard,
memory benchmark, proof-input bridge, and fail-closed readiness conditions are documented in
[`docs/gdw-frontier.md`](docs/gdw-frontier.md). A checked theorem is reported
separately from an exported theorem input, and every throughput result is scoped
to its captured run.

## Learn more

- [WILLAY API reference](https://github.com/szl-holdings/developers/blob/main/WILLAY_API.md)
- [Governed run-loop recipe](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/02-willay-gated-turn.md)
- [Proof library — lutar-lean](https://github.com/szl-holdings/lutar-lean)
- [Associated research-program concept DOI — 10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)
- [Existing formal-artifact record — 10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)
- [A11oy software releases](https://github.com/szl-holdings/a11oy/releases) — the v1.1.0 software-version DOI stays `PENDING_ZENODO_READBACK` until Zenodo resolves the immutable release
- [Canonical product surface](https://a-11-oy.com) · [legacy `a11oy.net` redirect](https://a11oy.net)

---

<div align="center">
<sub>SZL Holdings · a11oy · Doctrine v11 LOCKED · Λ = Conjecture 1 · SLSA L1 honest · L2 build-attested · L3 roadmap · Not affiliated with Defense Unicorns · No production ATO claimed · trust never 100%</sub>
</div>

---

## ◇ Part of the SZL Holdings estate — *governed AI you can prove*

One sovereign substrate, many organs — every decision carries a signed, checkable receipt.

**[◇ Holographic Estate — the showcase](https://szlholdings-holographic.hf.space)** ·
[🛡️ a11oy](https://huggingface.co/spaces/SZLHOLDINGS/a11oy) ·
[🧬 IMMUNE](https://huggingface.co/spaces/SZLHOLDINGS/immune) ·
[🦅 killinchu](https://huggingface.co/spaces/SZLHOLDINGS/killinchu) ·
[🫀 anatomy](https://huggingface.co/spaces/SZLHOLDINGS/anatomy) ·
[🌌 cosmos](https://huggingface.co/spaces/SZLHOLDINGS/cosmos) ·
[🛰️ SDA](https://huggingface.co/spaces/SZLHOLDINGS/sda) ·
[🌊 yarqa](https://huggingface.co/spaces/SZLHOLDINGS/yarqa) ·
[🤗 all Spaces](https://huggingface.co/SZLHOLDINGS)

<sub>Doctrine v11 · Λ = Conjecture 1, never green · honest by design · public data only.</sub>
