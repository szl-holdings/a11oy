# Investor brief — SZL governed execution substrate

## Thesis

Enterprise AI needs an execution fabric, not just models. A11oy provides that
fabric: policy checks, receipts, proof-aware claim language, and deployment
payload integrity around agentic work.

## Why this matters

When a model recommends an action, high-consequence operators need to know:

- which policy constraints were checked;
- who or what approved the action;
- what payload and configuration produced the result;
- whether the record can be verified later;
- where the public claim is supported by code, tests, releases, or proofs.

A11oy turns those questions into artifacts.

## What is real now

| Layer | Current evidence |
| --- | --- |
| Runtime validation | Doctrine tests, typechecks, and builds in GitHub Actions. |
| Receipt chain | `packages/receipt-substrate` emits and verifies hash-chained operational receipts. |
| Payload integrity | `deploy/MANIFEST.json` and operational bundle checksum sidecar. |
| UDS/Zarf alignment | Operator proof-point docs and package metadata under the A11oy UDS lane. |
| Org map | 19 public repos classified in `ecosystem-readiness-report.json`. |
| Public mirror | This Hugging Face packet is generated from tracked GitHub source. |
| Market evidence | `source/docs/SERIES_A_MARKET_EVIDENCE.md` maps public governance, SBOM, provenance, and model-card expectations to concrete A11oy artifacts. |
| Live correction guardrails | `DEMO_RECEIPT_SAMPLE.jsonl` records blocked claims for Vessels `uds-v0.3.0` signed assets, inflated Putnam discharge counts, and unmerged gate totals. |

## Active ecosystem

Active/supporting repos: `a11oy`, `amaru`, `sentra`, `rosie`, `ouroboros`,
`lutar-lean`, `ouroboros-thesis`, `uds-mesh`, `vsp-otel`, `vessels`,
`agi-forecast`, `szl-trust`, `szl-brand`, `szl-cookbook`, `.github`, and
`platform`.

Excluded until funded: `counsel`, `terra`, `carlota-jo`.

## Proof posture

The proof story is strong because it is guarded. The packet does not ask the
reader to trust a slide; it points to the thesis DOI, Lean proof substrate,
runtime tests, workflow checks, and manifest artifacts. Broad proof language is
only allowed when the exact module/report is current.

## Series-A demo wedge

The clean demo path is:

1. A11oy as the governed execution hub.
2. Vessels as the active vertical wedge.
3. Sentra / Amaru / Rosie as supporting receipt, drift, and minting components.
4. UDS/Zarf packaging as the operator deployment story.
5. Hugging Face as the public diligence mirror.

## What remains gated

- **Putnam:** current investor language should say `1/12` truly discharged in
  Lean unless a current upstream proof report proves more.
- **UDS v0.3.x:** signed binary assets and GHCR package pushes remain
  owner-side release work; do not treat empty or SBOM-only releases as signed
  deployment payloads.
- **Gate totals:** this repo can cite seven live policy gate files and ten
  theorem-runtime manifest entries today; larger counts are PR/roadmap until
  merged and verified.

