# OPS_NOTES.md — a11oy operational notes

Authored for SZL Holdings. Signed-off per repository DCO.
Doctrine v11 compliant — no fake-green labels, no marketing superlatives.

---

## Base image disclosure — Iron Bank gap

**Current base images are vanilla (not Iron Bank-approved):**

| Stage   | Image           | Notes                                      |
|---------|----------------|--------------------------------------------|
| builder | `node:22-alpine` | Official Docker Hub Node.js Alpine image   |
| runtime | `node:22-alpine` | Same — minimal Alpine; not hardened        |

Iron Bank-approved base images (e.g., `registry1.dso.mil/ironbank/opensource/nodejs/nodejs22`)
are **not** currently used. This is an honest gap, not a configuration oversight.

Iron Bank hardening is a Warhacker hardening item tracked in:
**[szl-holdings/a11oy#164 — chore(hardening): migrate to Iron Bank-approved base images](https://github.com/szl-holdings/a11oy/issues/164)**

Until that issue is resolved and the Dockerfile updated, do **not** label this image as
Iron Bank-compliant or DoD IL-approved. Claims of IL-5/IL-6 suitability require the
Iron Bank base plus a Platform One Continuous Authority to Operate (cATO) review.

---

## Serve mode (HTTP API)

The `serve` subcommand starts an HTTP API on `A11OY_PORT` (default `8080`).
It is implemented by `packages/receipt-substrate/src/server.ts` (serve-BE PR, pending merge).
Until that PR lands, the entrypoint exits with a clear error if `serve` is invoked and the
server module is absent — no silent hang, no fake-green probe response.

Probes:
- `GET /healthz` — liveness: returns `{"status":"ok"}` once the process is up.
- `GET /readyz`  — readiness: returns `{"status":"ready"}` after full initialisation.

---

## Container image registry

Production images: `ghcr.io/szl-holdings/a11oy`

Tagging strategy:
- `sha-<7-hex>` — every push to `main` (continuous delivery tag).
- `<semver>` + `latest` — published GitHub Releases only.
- `pr-<7-hex>` — pull-request builds (local daemon only; not pushed to GHCR).

---

## SLSA posture

Current level: **SLSA L1 (honest)** — source + build provenance documented via
`slsa-provenance.yml`. L2/L3 require Sigstore + isolated builders (roadmap item).

---

## Unified Receipt Ledger — the one durable sink (`/api/lake/v1`)

a11oy mounts the vendored szl-lake Unified Receipt Ledger onto the live app
(`szl_lake_ingest.register`, wired in `serve.py`). It is the ONE durable sink
every SZL component (ouroboros / hatun / router / mesh / vsp-otel / trust) POSTs
governance receipts to. SHA3-256 Khipu hash-chain (F4/F22) is **Conjecture 2**
(advisory BFT) — **not** a proven theorem.

Routes (additive, registered before the proxy + SPA catch-all):
- `POST /api/lake/v1/receipts`   — one receipt (JSON object), a JSON array, or NDJSON
- `GET  /api/lake/v1/receipts`   — query `?organ=&since=&limit=`
- `GET  /api/lake/v1/chain/head` — per-organ Khipu chain head + count `?organ=`
- `GET  /api/lake/v1/health`     — store reachable, total + per-organ counts

### Env contract

| Var | Purpose | Default |
|-----|---------|---------|
| `SZL_RECEIPT_SINK` | The sink URL downstream components POST to. **Set this on the Space** so other repos can `emit_receipt`. | `https://szlholdings-a11oy.hf.space/api/lake/v1` |
| `SZL_LAKE_DIR` | Local NDJSON store root for the live API (this process only — resets on rebuild). | `./khipu` |
| `SZL_CORPUS_REPO` | Durable HF dataset the ledger mirrors every receipt to (survives rebuilds). | `SZLHOLDINGS/a11oy-verifiable-corpus` |
| `HF_TOKEN` | Token used by the HFBucket mirror (already present in the Space). | — |

### Durability (honest)

The Space runs `storage=None`, so the local `$SZL_LAKE_DIR` store backs the live
API for the current process only. Every receipt is ALSO mirrored fire-and-forget
to the `SZL_CORPUS_REPO` dataset (prefix `lake/`) via the existing
`szl_hf_bucket.HFBucket` debounced background commit, so receipts survive
rebuilds. On boot, `szl_lake_ingest.hydrate_from_dataset()` replays the mirrored
receipts back through the local ledger to reconstruct the Khipu chain head (best-
effort daemon thread; honest no-op when token/repo/`huggingface_hub` are absent).
**ROADMAP:** the boot hydrate currently replays the full stream; bounding it to
the committed `head.json` + tail shards is a tracked follow-up (the write-side
mirror is LIVE; this is the read-back optimization).

---

## Known gaps (tracked)

| Gap | Tracking |
|-----|----------|
| Iron Bank base images | [#164](https://github.com/szl-holdings/a11oy/issues/164) |
| `serve` subcommand server module | serve-BE PR (pending) |
| SPA routes wired to real data | SPA-repair PR (pending) |
| SLSA L2/L3 isolated builder | ROADMAP.md |
| Unified ledger boot-hydrate full-stream replay | ROADMAP (bound to head.json + tail shards) |
