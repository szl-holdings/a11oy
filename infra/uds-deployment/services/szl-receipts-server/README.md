# szl-receipts-server

OCI image source for the SZL governance-receipts server. Built from this
directory's `Dockerfile`; deployed by `charts/szl-receipts`.

This replaces the prior approach of mounting `server.py` from a Helm ConfigMap
onto a stock `python:3.12-slim` (PhD Systems Scope 6).

## What it does

- `POST /receipt` — accepts a receipt body, signs it with **Ed25519** over the
  **canonical DSSE PAE**, appends it to a SHA-256 hash chain, persists it.
- `GET /receipts` — all stored receipts as JSON.
- `GET /stream` — SSE stream for the dashboard.
- `GET /health`, `GET /healthz` — probes.
- `GET /metrics` — Prometheus counters.

## Signing (PhD Crypto Finding A2 + A1)

- Ed25519 via `cryptography.hazmat`. The 64-byte signature is base64url-encoded
  into the DSSE envelope `signatures[].sig`; `keyid` is a stable identifier.
- The signature is computed over the canonical DSSE PAE
  (`github.com/secure-systems-lab/dsse/protocol.md`):

  ```
  PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
  SP = 0x20, LEN = ASCII decimal
  ```

- The private key is read from `SZL_ED25519_KEY_PATH`
  (default `/run/secrets/szl-receipts/ed25519.pem`). If absent, the server runs
  in **unsigned mode** and emits an explicit `UNSIGNED-NO-ED25519-KEY` sentinel
  — it never fabricates a signature.

Honest labeling: this is a software Ed25519 key in a Kubernetes Secret. It is
**not** HSM/KMS-custodied. Hardware key custody is roadmap (cf. `pqc.ts:327`).
No L3 SLSA, no COSE_Sign1 claim here.

## Durability (PhD Systems Scope 6)

On startup the server walks `SZL_RECEIPT_STORE` (default `/data/receipts`),
rehydrates the in-memory `_receipts` list ordered by `created_at`, and rebuilds
the chain head from each receipt's `chain.prev_hash`. It logs the count.

## Observability (PhD Systems Scope 9)

Real OpenTelemetry SDK + OTLP/gRPC exporter. When
`OTEL_EXPORTER_OTLP_ENDPOINT` is set, the server emits a `szl_receipts.boot`
span on startup and a `szl_receipts.append` span per receipt (attributes:
`receipt_id`, `prev_hash`, `chain_index`). Unset = no export.

## Environment

| Var | Default | Purpose |
|---|---|---|
| `SZL_PORT` | `8080` | listen port |
| `SZL_RECEIPT_STORE` | `/data/receipts` | persisted store path |
| `SZL_ED25519_KEY_PATH` | `/run/secrets/szl-receipts/ed25519.pem` | private key PEM |
| `SZL_KEY_ID` | `szl-receipts-ed25519-2026` | DSSE keyid |
| `SZL_LOG_LEVEL` | `info` | `debug`/`info` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (unset) | OTLP/gRPC endpoint; unset = no export |
| `OTEL_SERVICE_NAME` | `szl-receipts-server` | OTel service.name |

## Build

```
docker build -t ghcr.io/szl-holdings/szl-receipts-server:uds-v0.3.1 .
```

Image was not built in this PR's authoring environment (no container runtime
present). CI build + `cosign` signing ships in a follow-up PR.
