---
title: A11oy Orbital Compute Tier (MODELED Roadmap)
emoji: 🛰️
colorFrom: indigo
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
tags:
  - governance
  - provenance
  - energy
  - orbital
  - roadmap
  - szl-holdings
---

# A11oy — Orbital Compute Tier (MODELED Roadmap)

> **MODELED — Orbital Roadmap (no on-orbit hardware yet).**
> SZL operates a **REAL ground GPU fabric** today. Every orbital node, link, and
> joule shown here is a **MODELED design artifact** — not reachable, never serving
> a real job. This Space is a *forward design* showcase, not a deployed system.
> Λ = Conjecture 1 (OPEN); sovereign = false on this path. Doctrine v11 LOCKED.

This is a **public, login-free static showcase** that mirrors the live
[`a11oy.net/orbital`](https://a11oy.net/orbital) surface: SZL's governed
energy-receipt + signed-provenance moat, extended to space compute as a roadmap
design.

## What it shows

- A MODELED LEO/MEO/GEO constellation (6 LEO edge + 3 MEO + 2 GEO nodes, OISL
  inter-satellite links + ground-space downlinks to the REAL ground fabric),
  rendered client-side with three.js r160 (MIT, **vendored — 0 runtime CDN**).
- A **governed-receipt overlay**: each MODELED orbital job shows a MODELED energy
  figure derived from the **REAL ground-measured J/token coefficient** (the only
  `MEASURED` value), plus a **would-be signed governed-energy-receipt** — the SZL
  moat applied to space compute. The receipt is explicitly a MODELED would-be
  artifact, never presented as a real signature.

## Honesty (doctrine v11, non-negotiable)

- The entire surface carries a persistent, unmissable `MODELED — Orbital Roadmap`
  banner. It can never be mistaken for live telemetry.
- No orbital node / joule / receipt is fabricated. Nodes are `modeled:true` /
  `reachable:false`; `reachable` is REAL-PROBE-ONLY and the topology reports 0
  reachable nodes by construction.
- A MODELED orbital joule is **never** relabeled `MEASURED`. Only the ground
  J/token coefficient is `MEASURED`.

## Data source

The page fetches the **live** MODELED endpoints from the canonical box first:

- `https://szlholdings-a11oy.hf.space/api/a11oy/v1/orbital/topology`
- `https://szlholdings-a11oy.hf.space/api/a11oy/v1/orbital/projection`

If those are unreachable from this Space, it degrades to the **baked SAMPLE**
JSON under [`./data/`](./data) — clearly labeled `SAMPLE` in the UI and captured
2026-06-16. It never fabricates data: honest BLOCKED beats fake green.

## The unified SZL showcase

| Surface | Link | Status |
| --- | --- | --- |
| Live orbital surface (canonical) | <https://a11oy.net/orbital> | REAL page · MODELED data |
| a11oy application Space | <https://huggingface.co/spaces/SZLHOLDINGS/a11oy> | LIVE app |
| GitHub canonical source | <https://github.com/szl-holdings/a11oy#orbital-frontier-showcase> | source of truth |
| UDS signed mesh bundle | `oci://ghcr.io/szl-holdings/szl-uds-bundle` | cosign-signed, Rekor-anchored |

**Canonical rule:** GitHub releases, CI, manifests, checksums, and provenance are
canonical; Hugging Face is a generated discovery and showcase mirror.

---

© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Apache-2.0
