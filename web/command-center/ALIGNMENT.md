# Estate alignment — MEASURED 2026-09-11T23:02Z

Honesty doctrine v11. This file is a session observation, not a production certificate.

## Surfaces

| Role | URL | MEASURED this session |
| --- | --- | --- |
| Product origin | https://a-11-oy.com | `/console` flagship live, Λ ~0.915 |
| Product health | https://a-11-oy.com/healthz | `ok` · doctrine v11 · lock 749/14/163 · kernel `c7c0ba17` · **signer ABSENT** |
| Product rollup | https://a-11-oy.com/api/a11oy/healthz | `ok` v2.0.0 · **DSSE-LIVE** fp `9926bf69` ECDSA-P256 · preflight DEGRADED · frontier 8/8 |
| Signing status | https://a-11-oy.com/api/a11oy/v1/signing-status | `persistent:env:SZL_COSIGN_PRIVATE_PEM` · hmac-sha256:a11oy-env-injected |
| Public ledger | https://a-11-oy.com/api/a11oy/v1/ledger | count **0** · `signed=false` · signature_state **UNSIGNED** |
| Product honest | https://a-11-oy.com/api/a11oy/v1/honest | git_sha `329fb9acb0e9bdf253e9f598f738566383a75618` · locked-8 intact · Λ Conjecture 1 |
| Build info | https://a-11-oy.com/api/build-info | same git_sha `329fb9ac` |
| Energy ledger | https://a-11-oy.com/api/a11oy/v1/energy/ledger | persistence MEASURED · **joules_label SAMPLE** · joules_measured 0.0 · stripe dry-run |
| Runtime Space | https://szlholdings-a11oy.hf.space/healthz | same lean stamp as product `/healthz` (signer ABSENT). Card Running. |
| Proof registry | https://a11oy.net | static RECORD · `/health.json` STATIC_DOCUMENT · signer unavailable · sha `82ad048` |
| Source | https://github.com/szl-holdings/a11oy | canonical product repo |
| This package | `web/command-center/` on `console-web` | replica source. Not the flagship. |

## Four signer doors — never flattened

1. Lean `GET /healthz` → **ABSENT**. Fail-closed public stamp.
2. Rollup `GET /api/a11oy/healthz` → **DSSE-LIVE** fingerprint `9926bf69b799ea66` ECDSA-P256.
3. `GET /api/a11oy/v1/signing-status` → persistent env key mounted.
4. `GET /api/a11oy/v1/ledger` → public receipts **UNSIGNED**, count 0.

Key mounted ≠ public receipts ≠ lean healthz. SIGNED is never inferred from HASH-LINKED.

## Python ↔ Hugging Face

- Canonical `Dockerfile` and `requirements-audit.txt` on main pin `huggingface_hub==1.31.0` after #2098.
- That is **source-pin alignment**, not built-image readback.
- #2087 was closed by a human via #2120. The remaining technical gate is still `importlib.metadata.version('huggingface-hub')` on the published image. Do not claim Hub 1.31 is runtime-consumed from a source pin or a landing-binder merge.
- Satellite pins still drift. Do not call the estate “one pin.”
- No Hub write from this replica thread. Promote GitHub → hf-sync only after review.

## Proof lag (not a runtime fail)

- a11oy.net Hub atlas snapshot dates 2026-08-31.
- a11oy.net `/health.json` sha `82ad048…` is the last published static revision, not live uptime.
- Dated `estate-refresh-2026-09-11.json` exists and must not rewrite `estate.json` history.

## Command Center replica

- Kernel on this branch: `lambda.ts`, `pulse.ts`, `receipt.ts`, `frontier.ts`, `crypto.ts`, `immune.ts`.
- DSSE PAE / TPM analogue land separately; until those files exist here, this package is UNSIGNED-honest SHA-256 + disclosed product doors.
- Merge target is `console-web`. Human cutover only for a-11-oy.com assets.
- Do not replace Space `SZLHOLDINGS/a11oy`. Do not flip DNS. Do not host this UI on a11oy.net.

## Still missing (frontier, not shipped)

1. Independent image readback of hub 1.31.0.
2. Public ledger receipts (count 0 UNSIGNED) — product Cosign verify stays UNAVAILABLE.
3. Keep lean ABSENT and rollup DSSE-LIVE as two doors.
4. Keyless Fulcio, POVM stream, TPM quotes / SEV-SNP / TDX (browser analogue only).
5. Energy **joules** MEASURED (RAPL `energy_uj`). Persistence MEASURED is not joules.
6. Replica DSSE/TPM source files on this branch.

Λ remains Conjecture 1. Locked-8 remains 8. No ATO.
