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
short_description: "a11oy source — product origin a-11-oy.com, proof a11oy.net"
tags:
  - governance
  - agentic-ai
  - doctrine-v11
  - a11oy
  - slsa-l1
  - apache-2.0
ecosystem-stage: "operational"
models: [SZLHOLDINGS/SZL-Khipu-1.5B, SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent]
datasets: [SZLHOLDINGS/a11oy-verifiable-corpus, SZLHOLDINGS/szl-lake]
---

<!--
  a11oy README lead · 2026-08-29
  This repository is SOURCE for the product origin https://a-11-oy.com
  Proof lives at https://a11oy.net
  Never a11oy.com
  receipts.in ≡ receipts.out
  Canonical: lutar-lean@main kernel c7c0ba17
  Honesty doctrine LOCKED. DCO + Conventional Commits.
-->

# a11oy

This repository is the **source** for the product origin
[https://a-11-oy.com](https://a-11-oy.com).
Proof lives at [https://a11oy.net](https://a11oy.net).

`a11oy.com` is not a surface of this project.

a11oy is a governed-AI Command Center: deny-by-default policy, trust
ceiling 0.97, and a signed receipt for every decision. This tree is
that system's source. It is not the proof registry.

## Invariant

**receipts.in ≡ receipts.out**

A governed action is admitted only as a signed receipt and leaves only
as that same signed receipt. The two sides are identical. A mismatch
is a failed verification, not a display error.

| Pin | Value |
|---|---|
| Product origin | [a-11-oy.com](https://a-11-oy.com) |
| Proof registry | [a11oy.net](https://a11oy.net) |
| Source | this repository |
| Doctrine | v11 LOCKED |
| Λ | Conjecture 1 (OPEN — not a theorem) |
| Kernel | `c7c0ba17` |
| Formulas | locked-8 · never authority |
| Trust ceiling | 0.97 |
| SLSA | L1 honest · L2 build-attested · L3 roadmap |
| License | Apache-2.0 |

## Live surfaces

| Surface | URL |
|---|---|
| Console | [a-11-oy.com/console](https://a-11-oy.com/console) |
| Doctrine posture | [a-11-oy.com/api/a11oy/v1/honest](https://a-11-oy.com/api/a11oy/v1/honest) |

[a11oy-factory](https://github.com/szl-holdings/a11oy-factory) is a bind
of this source. It is not a second flagship.

Archive: [Warhacker v1.0.0](https://github.com/szl-holdings/a11oy/releases/tag/v1.0.0) is ARCHIVED.

---

<!-- LEAD END. Existing README continues from ## The proof backbone. Do not rewrite past this marker in the lead-only PR. -->

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

> The live energy ledger is in **genesis state** (chain length 0) — live and queryable, honestly empty.

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
| Signed receipts on every governed action | **LIVE** — receipts are UNSIGNED-honest unless persistent signing is enabled (`A11OY_REQUIRE_PERSISTENT_SIGNING=1`); an unsigned receipt says so and never fabricates a signature |
| 8 formulas locked-proven (Lean 4) | **LOCKED · kernel c7c0ba17** |
| Λ uniqueness | **Conjecture 1** (conditional Theorem U proven axiom-free) |
| SLSA supply chain | **L1 honest · L2 build-attested · L3 roadmap** |
| FedRAMP / ATO | **ROADMAP** |
| EXECUTION guard | **ROADMAP** |

---

## Truth gates

Round-10 payload wiring: three stdlib-first gates plus the 12-step acceptance
demo, run by the `truth-gates` workflow on every PR and push.

```bash
python3 tools/docs_lexicon_gate.py       # docs language gate: banned phrases, empty truth states
python3 tools/commercial_release_gate.py # commercial truth gate: COMMERCIAL_LEDGER + claims-ledger
python3 tools/demo_harness.py --conformance evidence/conformance/eu-ai-act-article-12.v1.yaml
```

Expected first-run exit codes: `docs_lexicon_gate.py` **1** and
`commercial_release_gate.py` **1** — those failures are intended. The lexicon
output is the Week 1 documentation fix list; the release-gate output is the 24
raise-blocking COMMERCIAL_LEDGER rows still `UNKNOWN` (the real work, per the
funding discipline). `demo_harness.py` must stay **0** (12/12 steps) on every
PR. The two observe-mode gates run `continue-on-error` until their finding
lists reach zero; flip procedure: `docs/RUNBOOK_WEEK1.md`.

Naming note (no file was overwritten): `tools/lexicon_gate.py` and
`tools/release_gate.py` already exist here as the round-5 gates, so the
round-10 gates are wired under the names above; both generations run. The
v1 Article 12 logging conformance profile lives at
`evidence/conformance/eu-ai-act-article-12.v1.yaml` because the CANON path is
occupied by an older, structurally different artifact. Fresh scaffolds are
created non-destructively with `python3 tools/szl_master_bootstrap.py --run`.

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
- [Canonical product surface](https://a-11-oy.com) · [public proof registry `a11oy.net`](https://a11oy.net)

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
