# Safe Route Wiring — killinchu /beyond + /elite, rosie /jarvis

**Date:** 2026-06-05 · **Author:** route-wiring squad (Opus 4.8)
**Signed-off-by:** Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
**Honesty floor:** Λ = Conjecture 1 (NOT a theorem). Formula count = 5 (live API). SLSA L2 = 5/5 organs verified, bundle NOT. No L3/FedRAMP/Iron Bank/CMMC. No fake green.

---

## TL;DR

All three routes boot + return **200 locally** with **no regression**, tested against the
**exact module set the Space Dockerfile COPYs** (the precise failure mode that broke the
parent's prior attempt: serve.py importing modules the Dockerfile never COPYs).

| Organ | Route | Local status | Notes |
|---|---|---|---|
| killinchu | `GET /beyond` | **200** | 3-tab proof console |
| killinchu | `GET /killinchu/beyond` | **200** | alias |
| killinchu | `GET /elite` | **200** | 14-tab console |
| killinchu | `GET /killinchu/elite` | **200** | alias |
| killinchu | `GET /api/killinchu/v1/borrowed-powers` | **200** | live aggregator |
| killinchu | `GET /api/killinchu/v1/autonomy/system-types` | **200** | beyond API |
| killinchu | `GET /api/killinchu/v1/hotl/register` | **200** | beyond API |
| killinchu | `POST /api/killinchu/v1/autonomy/evaluate` | **200** | beyond handler executes |
| rosie | `GET /jarvis` | **200** | console |
| rosie | `GET/POST /api/rosie/v1/jarvis/*` | **200** | ask/recommend/act/audit/roadmap/health |

No regression on either organ (see full tables below).

---

## Root cause (per organ)

### killinchu — missing module + missing COPY + late registration
The live Space serve.py (commit `05f6964dc15c`, 2276 lines — known-good, boots+200) **predates**
the beyond/elite wiring. Three things were missing:
1. `killinchu_beyond.py` + `killinchu_elite_console.py` were not registered in the Space serve.py at all.
2. The Space Dockerfile (per-file `COPY`, never `COPY . .`) never COPY'd those two modules.
3. A SPA catch-all `@app.get("/{full_path:path}")` (line 2208 in the known-good Space serve.py)
   shadows any route registered *after* it. So registration must land **before** that line.

**Why the parent's prior attempt 000'd:** the parent synced the *GitHub* serve.py onto the Space.
The GitHub serve.py imports modules (e.g. `killinchu_drone_3d_health`, `szl_sidebar`, `szl_demo`)
that the **Space Dockerfile does not COPY** — those imports are try/except-guarded so they don't
crash, BUT the GitHub serve.py also differs structurally. The safe fix is to patch the **known-good
Space serve.py**, not replace it.

### rosie — module present, never registered + mount shadowing
`rosie_jarvis.py` is **already on the Space** (identical to GitHub source, 625 lines) and the Space
Dockerfile **already COPYs** `rosie_jarvis.py` + `web/jarvis.html` (PR #131). The *only* missing piece
was the registration call in `app.py` (3047 lines). Additionally `_rosie_api.mount("/api/rosie", ...)`
(line 2437) and the catch-all `_rosie_api.mount("/", ...)` (line 2645) would shadow late routes —
but `rosie_jarvis.register()` **self-lifts** its routes to the front of `_rosie_api.router.routes`,
so they win over both mounts regardless of where `register()` is called. Verified: jarvis `/jarvis`
route sits at router index 6, the `/api/rosie` mount at index 225 → jarvis resolves first.

---

## The fix (minimal, additive)

### killinchu
- **serve.py** (base = known-good Space `05f6964dc15c`): inserted two `try/except`-guarded registration
  blocks **immediately before** the catch-all (`@app.get("/{full_path:path}")`):
  - `killinchu_elite_console.register(app, ns="killinchu", emit_receipt=_emit_receipt)`
  - `killinchu_beyond.register(app, emit_receipt=_emit_receipt, ns="killinchu")`
  - Both reuse the host `_emit_receipt` (already defined at line 315 — Khipu DAG + real cosign DSSE).
  - Both modules are self-contained (fastapi + stdlib); `beyond.py`'s optional `szl_dsse` +
    `szl_khipu_consensus` imports are try/except-guarded and **already COPY'd** (Dockerfile lines 67, 183).
- **Dockerfile**: added two per-file COPY lines before `CMD`:
  - `COPY killinchu_elite_console.py ./killinchu_elite_console.py`
  - `COPY killinchu_beyond.py ./killinchu_beyond.py`

### rosie
- **app.py** (base = known-good Space `main`, 3047 lines): inserted one `try/except`-guarded block
  **before the `__main__` launch** (the module self-lifts, so call-site order is safe):
  - `import rosie_jarvis as _jarvis; _jarvis.register(_rosie_api, ns="rosie")`
- **Dockerfile**: **no change needed** — `rosie_jarvis.py` + `web/jarvis.html` already COPY'd (lines 181-182).
- **rosie_jarvis.py**: unchanged (identical to what's already live on the Space; included in manifest for completeness/idempotency).

---

## LOCAL boot + route test — real results

Tests run by importing the patched entrypoint inside a sandbox containing **only** the files the
Space Dockerfile COPYs (GitHub working tree as the source for each COPY'd path), then exercising
routes via `fastapi.testclient.TestClient`. `KILLINCHU_ROOT` was pointed at the sandbox so `/`
resolves `static/index.html` exactly as it would at `/app` in the container.

### killinchu — `import serve` clean → `IMPORT_OK`, app object = FastAPI
```
GET  /                                              -> 200
GET  /beyond                                        -> 200
GET  /elite                                         -> 200
GET  /killinchu/beyond                              -> 200
GET  /killinchu/elite                               -> 200
GET  /api/killinchu/v1/honest                       -> 200
GET  /api/killinchu/v1/borrowed-powers              -> 200
GET  /api/killinchu/v1/autonomy/system-types        -> 200
GET  /api/killinchu/v1/hotl/register                -> 200
GET  /healthz                                       -> 200
GET  /api/health                                    -> 200
GET  /api/killinchu/v1/version                      -> 200
GET  /console                                       -> 200
GET  /operator                                      -> 200
POST /api/killinchu/v1/autonomy/evaluate            -> 200
```
Registration log (stderr, real): `[killinchu] Elite console registered: [...] (14 tabs)` and
`[killinchu] Beyond-Cannonico proofs registered: [...] (3 tabs)`.

**Note (honest):** when `KILLINCHU_ROOT` is left at the default `/app`, `GET /` returns 500
(`File at path /app/static/index.html does not exist`) — this is a *sandbox-only* artifact (no
`/app` outside the container). With `KILLINCHU_ROOT` pointed at the sandbox (which holds the same
`static/` the Dockerfile COPYs), `GET /` = 200. In the real Space, `static/index.html` lives at
`/app/static/index.html`, so `/` is 200 there. No code change needed; flagged for full transparency.

### rosie — `import app` clean → `IMPORT_OK`, app object = FastAPI
```
GET  /jarvis                                    -> 200
GET  /api/rosie/v1/jarvis/health                -> 200
GET  /api/rosie/v1/jarvis/recommend             -> 200
GET  /api/rosie/v1/jarvis/roadmap               -> 200
GET  /api/rosie/v1/jarvis/audit                 -> 200
POST /api/rosie/v1/jarvis/ask                   -> 200
POST /api/rosie/v1/jarvis/act                   -> 200
--- regression / existing surface ---
GET  /                                          -> 200   (Gradio mount intact)
GET  /api/health                                -> 200
GET  /console                                   -> 200
GET  /console/v3                                -> 200
--- route ordering proof ---
JARVIS_AT idx=6 ; MOUNT_AT(/api/rosie) idx=225 ; ORDER_OK
```
Self-lift confirmed: jarvis routes precede both the `/api/rosie` mount and the `/` catch-all mount.

### Honest caveats (NOT failures — pre-existing, try/except-guarded in the known-good Space entrypoints)
Some optional modules are not in the Dockerfile COPY set and log `ModuleNotFoundError` at import
(guarded, do **not** crash boot, **not** introduced by this change):
- killinchu: `killinchu_drone_3d_health`, `szl_demo`, `szl_sidebar`
- rosie: `szl_otel`, `szl_brain_v3`, `szl_thesis_about`, `szl_kernels_organ`, `rosie_aide_v4`,
  `operator_shell_v4`, `rosie_v4_orchestrate`, `rosie_v4_cockpit`, `szl_demo`, `szl_smoke_fix`,
  `szl_deepdive_gaps`
These exist in the known-good live Spaces today and are orthogonal to /beyond, /elite, /jarvis.

---

## Per-file PUSH MANIFEST (parent pushes via HF commit API)

Base Space commits patched: **killinchu `05f6964dc15c`**, **rosie `main` (3047-line app.py)**.

### killinchu — Space `huggingface.co/spaces/SZLHOLDINGS/killinchu`
| Space path | Local file | Change |
|---|---|---|
| `serve.py` | `team/space_fixes/killinchu/serve.py` | **MODIFIED** — +elite/+beyond register blocks before catch-all (2276 → 2323 lines) |
| `Dockerfile` | `team/space_fixes/killinchu/Dockerfile` | **MODIFIED** — +2 COPY lines (elite_console, beyond) |
| `killinchu_elite_console.py` | `team/space_fixes/killinchu/killinchu_elite_console.py` | **NEW on Space** (from GitHub source, unchanged) |
| `killinchu_beyond.py` | `team/space_fixes/killinchu/killinchu_beyond.py` | **NEW on Space** (from GitHub source, unchanged) |

### rosie — Space `huggingface.co/spaces/SZLHOLDINGS/rosie`
| Space path | Local file | Change |
|---|---|---|
| `app.py` | `team/space_fixes/rosie/app.py` | **MODIFIED** — +jarvis register block before `__main__` (3047 → 3074 lines) |
| `rosie_jarvis.py` | `team/space_fixes/rosie/rosie_jarvis.py` | **UNCHANGED** (already live on Space; included for idempotency) |
| `Dockerfile` | `team/space_fixes/rosie/Dockerfile` | **NO CHANGE NEEDED** (already COPYs rosie_jarvis.py + web/jarvis.html) — included as reference only |

**After push:** factory-rebuild each Space, then verify LIVE (retry 3-6× on transient `000` egress):
- killinchu: `/beyond` 200, `/elite` 200, `/` still 200
- rosie: `/jarvis` 200, `/api/rosie/v1/jarvis/health` 200, `/` (Gradio) still 200

---

## GitHub PRs (source-of-truth)
- killinchu source already carries beyond/elite wiring (PRs #56, #57 merged). A reconcile PR is
  opened to keep the **Space-shaped** serve.py/Dockerfile in `deploy/space/` as drift reference (see PR link in run output).
- rosie source already carries the jarvis register call (PR #131 merged at app.py:3125). The Space
  app.py simply lacked it. PR opened to document the Space-sync (see run output).
