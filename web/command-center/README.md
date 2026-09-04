# web/command-center — a11oy operator console

**Not a second flagship.** This folder is the Grok-built Command Center and public estate UI from the operator thread. It sits beside the existing Alloy Fabric view in `web/`, it does not replace it.

| Pin | Value |
| --- | --- |
| Product origin | [a-11-oy.com](https://a-11-oy.com) |
| Proof registry | [a11oy.net](https://a11oy.net) |
| Canonical source | this repository (`szl-holdings/a11oy`) |
| Runtime Space | [SZLHOLDINGS/a11oy](https://szlholdings-a11oy.hf.space) — Python docker, unchanged |
| This folder | operator console + estate UI (React / TanStack Start) |
| Doctrine | v11 LOCKED |
| Λ | Conjecture 1 — advisory, never a theorem, never 1.0 |
| Signing | UNSIGNED-honest unless a live signer probe passes |
| License | Apache-2.0 |

## Why this path

- `a-11-oy.com` stays the product apex (`a11oy_landing.html` + existing Pages).
- `a11oy.net` stays the proof / RECORD origin. Do not host this UI there.
- `SZLHOLDINGS/a11oy` stays the governed Python runtime. Do not replace that Space with this app.
- Existing `web/*.html` holograms and `web/src` stay in place. This package lives only under `web/command-center/`.

## What is here

- Public site: honesty doctrine v11, labelled figures, live probes that degrade to UNAVAILABLE.
- Command Center: mesh health, 13-axis Λ, verticals, receipt stream, locked-8 with truthful Lean refs.
- Operator tabs: Watch, Fleet, Frontiers, C2 Gate, World, Doctrine.
- Estate: Superpowers, Formulas, Evidence, Observability Λ-drift, Wires, Mesh, IMMUNE, Verify.

Every figure is labelled MEASURED, REPORTED, SAMPLE, CONJECTURE, or UNAVAILABLE. Λ uniqueness is Conjecture 1.

## What this is not

- Not a production certificate of a-11-oy.com.
- Not a Cosign / DSSE signer. Receipts in this surface are SHA-256 UNSIGNED-honest unless a separate signer probe is LIVE.
- Not SLSA L3, FedRAMP, IL5, or ATO.
- Not a replacement for the Python organ backends.

## Run locally

This package is a TanStack Start + React 19 + Tailwind v4 app. From this folder, after the source tree is complete:

```bash
npm install
npm run dev
```

Server functions probe `a-11-oy.com` and estate organs read-only. A dead probe is UNAVAILABLE, never a faked LIVE.

## Promote to the apex

Do **not** point the `a-11-oy.com` CNAME at this folder until a human operator reviews the PR and decides the Pages / runtime cutover. Until then this branch is the inspectable source of the operator console.
