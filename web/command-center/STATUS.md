# web/command-center — source status

Measured 2026-09-11T23:02Z. Honesty doctrine v11.

This folder is the inspectable Vite/React Command Center source.
It is **not** a second flagship and does **not** replace the Python Space runtime at a-11-oy.com.

## What is operational

| Surface | URL / path | Honesty |
| --- | --- | --- |
| Product apex | https://a-11-oy.com | existing Python Space / Pages · git_sha `329fb9ac` |
| Operator console | https://a-11-oy.com/console | existing flagship · Λ advisory |
| Lean health | https://a-11-oy.com/healthz | LIVE transport · signer **ABSENT** |
| DSSE rollup | https://a-11-oy.com/api/a11oy/healthz | LIVE transport · signer **DSSE-LIVE** `9926bf69` |
| Public ledger | https://a-11-oy.com/api/a11oy/v1/ledger | LIVE transport · receipts **UNSIGNED** count 0 |
| Proof | https://a11oy.net | static RECORD |
| This package | `web/command-center/` | replica source + local receipt loop |

## Pins that stay honest

- Λ uniqueness = Conjecture 1 (not a theorem, never 1.0)
- Lean signer ABSENT and rollup DSSE-LIVE are both true. Do not flatten.
- Local receipts are SHA-256 UNSIGNED-honest
- Replica DSSE, if present, is REPLICA-SOFTWARE — not product Cosign
- Energy joules SAMPLE / UNAVAILABLE without RAPL `energy_uj`
- Killinchu public effector SIMULATED
- No FedRAMP / IL5 / ATO
- HTTP 200 / opaque fetch is reachability, not a production certificate
- Do not flip a-11-oy.com DNS onto this folder
- Do not replace Space `SZLHOLDINGS/a11oy` with this React app
