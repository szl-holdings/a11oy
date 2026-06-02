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
  - doctrine-v7
  - a11oy
  - execution-fabric
ecosystem-stage: "operational"
---

# a11oy — Governance Substrate

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

| `/codex-kernel` | Replay-grade governed-loop primitive (pure-TS kernel, hash-chained state + decision receipts + proof ledger + hard-stop validators + deterministic replay + Dresden-Venus emulator) |
| `/wires` | Mesh interconnects — Wire B & C LIVE, Wire D NOT YET IMPLEMENTED |
| `/evidence` | LUTAR_EVIDENCE ledger — per-claim PROVEN/SORRY/AXIOM/CONJECTURE, theorem→Lean `file:line`, ref-vector cross-ref, honest Λ-definition discrepancy |
| `/substrate` | `@szl/substrate` package surface — 6 primitives, deterministic Kahn-sort compiler (Innovation #2), 21 subpath exports |
| `/run-all` | OUROBOROS_RUN_ALL.py — live in-browser execution of all 32 module self-tests (POST `/api/a11oy/internal/run-all`) |
| `/api/a11oy/v1/honest` | "What is honest right now" disclosure (JSON) |

## What is honest right now

lutar-lean @ tag `lutar-v18.0.0` / c7c0ba17: **749 declarations · 14 unique axioms (15 raw, 1 dup) · 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.

- **Λ uniqueness is a Conjecture**, not a closed theorem — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**; Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
- **SLSA: L1 (honest)** — previously mis-claimed as L3; corrected in platform PR #235.
- **Receipts:** DSSE envelopes ship from the amaru tick endpoint today; Sigstore CI signing is **PENDING** — signatures labeled "PLACEHOLDER — signing not yet wired into CI".
- Aligned with **EU AI Act Article 12** + **NIST AI RMF (MANAGE)**.
