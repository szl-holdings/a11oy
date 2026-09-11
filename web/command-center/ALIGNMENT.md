# Estate alignment — MEASURED 2026-09-11

Honesty doctrine v11. This file is a session observation, not a production certificate.

## Surfaces

| Role | URL | MEASURED this session |
| --- | --- | --- |
| Product origin | https://a-11-oy.com | `/command` serves the public Command Center SPA |
| Product health | https://a-11-oy.com/healthz | `ok` · doctrine v11 · lock 749/14/163 · kernel `c7c0ba17` · **signer ABSENT** |
| Product honest | https://a-11-oy.com/api/a11oy/v1/honest | doctrine v11 · locked_count 8 · Λ Conjecture 1 · energy null · git_sha `0abde0c` · **signer_state LOCKED** |
| Runtime Space | https://szlholdings-a11oy.hf.space/healthz | **byte-identical** to product `/healthz` |
| Proof registry | https://a11oy.net | static RECORD · `/health.json` is STATIC_DOCUMENT · signer unavailable |
| Proof refresh | https://a11oy.net/estate-refresh-2026-09-11.json | OBSERVED 2026-09-11T18:56:52Z |
| Source | https://github.com/szl-holdings/a11oy | canonical |
| This package | `web/command-center/` on `console-web` | replica source |

## Do not flatten these two signer facts

- Lean `GET /healthz` reports **signer ABSENT**. That is the fail-closed public stamp.
- `GET /api/a11oy/v1/honest` reports **signer_state LOCKED** at git_sha `0abde0c4114bdc8c603b984e884f657d74f9ab88`.
- Do not copy DSSE-LIVE onto lean `/healthz`.
- Do not treat lean ABSENT as “no key exists anywhere.”
- Ledger count 0 UNSIGNED means a mounted key is not a public receipt stream.

## Python ↔ Hugging Face

- Canonical `Dockerfile` and `requirements-audit.txt` on main pin `huggingface_hub==1.31.0` after #2098.
- Space Dockerfile raw matches that pin.
- That is **source-pin alignment**, not built-image readback.
- #2087 stays open until `importlib.metadata.version('huggingface-hub')` is observed in the published image.
- Satellite pins still drift (`install.sh` 1.19, backup workflow 1.29, frontend lock 1.23). Do not call the estate “one pin.”
- No Hub write from this replica thread. Promote GitHub → hf-sync only after review.

## Proof lag (not a runtime fail)

- a11oy.net Hub atlas snapshot dates 2026-08-31.
- a11oy.net `/health.json` sha `82ad048…` is the last published static revision, not live uptime.
- Dated `estate-refresh-2026-09-11.json` exists and must not rewrite `estate.json` history.

## Command Center replica

- Kernel: `lambda.ts`, `pulse.ts`, `receipt.ts`, `frontier.ts`, tests 6/6 local PASS.
- UI wiring: Frontiers + Verify belong in the hash router. Opaque fetch is UNKNOWN, never LIVE.
- Merge target is `console-web`. Human cutover only for a-11-oy.com assets.

## Still missing (frontier, not shipped)

1. Independent image readback of hub 1.31.0 (#2087).
2. Public ledger receipts (count 0 UNSIGNED).
3. Reconcile lean `/healthz` ABSENT vs rollup/honest LOCKED without lying on either door.
4. Keyless Fulcio, POVM stream, TPM/SEV-SNP, formal POVM Lean.
5. Energy joules (no RAPL `energy_uj`).
6. Merge replica source to `console-web`, then a human review before any Pages wire.

Λ remains Conjecture 1. Locked-8 remains 8. No ATO.
