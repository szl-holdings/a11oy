# Warhacker mission packs

A verifiable-governance overlay for the Defense Unicorns **UDS** air-gap delivery stack,
demonstrated as a 60-minute on-stage mission pack.

- **Event:** Defense Unicorns **Warhacker 2026** — 16–19 June 2026, San Diego, CA
  ([Warhacker page](https://defenseunicorns.com/warhacker/)).
- **Output license target:** AGPL-3.0 (Warhacker default).

## The thesis

Defense Unicorns built the **delivery** primitive for the open-source air-gap future — Zarf
moves the tarballs, `uds-cli` composes them, UDS Core runs them, demonstrated end-to-end on the
F-22 OMS enclave ([Defense Unicorns, 2026-03-17](https://defenseunicorns.com/defense-unicorns-demonstrates-key-enabler-for-continuous-software-delivery-on-the-f-22/)).
The remaining gap is **verifiable governance**: a kernel-checked proof that the four-layer stack
(formal verification + agentic AI + observability + sovereign AI) composes into one
total-ordered receipt chain a reviewer can replay with cosign and Lean alone.

SZL's contribution is exactly that overlay: the `Lutar.UDSSensorReceiptChain` Lean development,
the SLSA-v1 extended-attestations chain on
[`szl-holdings/uds-mesh`](https://github.com/szl-holdings/uds-mesh), and an operator console
rendering a four-pane verification surface.

## The four-layer map

| Layer | DU / OSS today | SZL Λ-axis overlay |
|-------|----------------|--------------------|
| Formal verification | cosign + SBOM | `Lutar.UDSSensorReceiptChain` Lean kernel proof |
| Agentic AI | Lattice / Thunderforge | 13-axis Λ-gate; hard-reject on sub-floor |
| Observability | OTEL | [OTel-VSP](/anatomy/#otel-vsp) verifiable-span provenance |
| Sovereign AI | air-gap delivery | governed loop, on-prem, no external egress |

## Demo structure (7 slots × ~8.6 min)

A live `kind` cluster (`szl-mesh`) runs the workflow on `uds-cli`, pulling a
`MeshPointerManifest` and landing four cross-component SHAs (a11oy / amaru / rosie / sentra) in
**cosign-verifiable order**. The flow: opening (the gap) → live deploy → **live attestation-chain
append** → operator console → **Lean kernel-checked theorem** that the chain is total-ordered and
SHA-complete → governance gate → close. A line-5 extended-attestation is appended live on stage.

## Mission packs

The packs are built around the six Defense Unicorns engineers who built Zarf / `uds-cli` / UDS
Core — each pack maps a verified GitHub footprint to the SZL hook that lands hardest (e.g. the
supply-chain reviewer gets the live attestation append + the Lean total-order proof; the
kubectl/CLI maintainer gets the cosign-verifiable pointer manifest).

## Honest boundaries

- **Doctrine:** governance-mathematical; **no autonomous lethal action**. UDS here is
  delivery + verification + governance only.
- **License:** AGPL-3.0 on new artifacts; Apache-2.0 retained on `uds-mesh`.
