# RESULT — Runtime-CDN Doctrine Fix (G7: 0 runtime CDN)

**Owner:** Senior front-end engineer, SZL Holdings
**Date:** 2026-06-14
**Scope:** Repos `szl-holdings/a11oy` + `szl-holdings/killinchu`; Spaces `SZLHOLDINGS/a11oy` + `SZLHOLDINGS/killinchu`
**Defect class:** G7 violation — surfaces loading third-party assets (Google Fonts, esm.sh modules) from external runtime CDNs via hard-coded `<link>`/import tags instead of self-hosted, same-origin assets.

---

## 1. Summary

QA Team A's full-tab walk found a runtime-CDN doctrine violation: `a11oy /nemo` and
`a11oy /estate-hologram` loaded **Space Grotesk / JetBrains Mono** from
`fonts.googleapis.com` + `fonts.gstatic.com` via `<link>` tags. A full 0-CDN sweep of
the **served** a11oy HTML surfaced additional runtime-CDN loads (esm.sh three.js on the
3D surfaces, including the `/chaski` reception page) and several bare font-family
declarations missing fallbacks. All were remediated to **0 external runtime URLs** using
the existing self-hosted patterns already shipped on the clean pages. The same quick
grep + fix was applied to `killinchu`. The doctrine guard was additively extended to
cover the QA-flagged surfaces so CI catches any regression. Every fix is
**ADDITIVE / surgical** — no existing gate weakened, no behavior changed.

**Live result: ZERO external runtime URLs on every served surface (verified with Playwright).**

---

## 2. What replaced the CDN assets

### 2a. Fonts (the named G7 defect)
- Removed every external Google Fonts `<link>` (`preconnect` + `css2` stylesheet) tag.
- Replaced with the **existing self-hosted `@font-face` bundle** that the clean pages
  (e.g. `pages/console.html`) already use:
  - `@font-face { font-family:'Space Grotesk'; src:url('/vendor/fonts/SpaceGrotesk.woff2') format('woff2'); ... }`
  - `@font-face { font-family:'JetBrains Mono'; src:url('/vendor/fonts/JetBrainsMono.woff2') ... }`
  - These `.woff2` blobs are the vendored assets in `_vendor_blobs.py`, served same-origin
    by the `/vendor/fonts/{fname}` route on the global FastAPI app — reachable from every surface.
- Added geometric **system fallback stacks** to every font declaration so the surface still
  renders correctly even before/without the web font:
  - sans: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`
  - mono: `ui-monospace, "SF Mono", Menlo, monospace`
- Bare `'Inter'` declarations (Inter is **not** vendored) were given a system fallback
  rather than introducing a new CDN load.

### 2b. esm.sh three.js (additional runtime-CDN loads found in the sweep)
- Replaced `https://esm.sh/three@…` script imports with **bare specifiers resolved by an
  importmap** to the same-origin vendored three.js **r170**:
  - `"three"` → `/static/3d/vendor/three/three.module.min.js`
  - `"three/webgpu"` → `/static/3d/vendor/three/three.webgpu.min.js`
  - `"three/addons/"` → `/static/3d/vendor/three/addons/`
  - vendored bundle served by `szl3d_holographic.py` at `/static/3d/vendor/*`
    (same pattern already shipped on `throne-room`).
- `OrbitControls` now imports from `three/addons/controls/OrbitControls.js` (vendored).

No new font/asset file was added (all vendored blobs already exist and are already
served/baked), so **no `Dockerfile` COPY change and no `hf-sync.yml` list change were required.**

---

## 3. Files fixed

### a11oy — font CDN removed (`<link>` → self-hosted `@font-face` + system fallback)
- `web/nemo.html` — **PRIMARY defect** (Space Grotesk + JetBrains Mono via `<link>`)
- `web/estate-hologram.html` — same defect (GitHub/HF source; box redeploy handled by Forge)
- `web/agentic-gpu.html`, `web/fleet-c2.html`, `web/living-anatomy.html`,
  `web/v4_fleet_panel.html`, `web/elite_console.html`, `web/console_index.html`
- `pages/landing.html`, `pages/observability.html`, `pages/superpowers.html`,
  `pages/warhacker.html`, `pages/wires.html`
- `console/index.html`, `index.html` (root)

### a11oy — esm.sh three.js removed (esm.sh import → vendored importmap)
- `pages/throne-room.html` + `pages/throne-room.js`
- `console/throne-room.html` + `console/throne-room.js`
- `pages/wasi-rikuq.html`
- `pages/chaski.html` — **follow-up:** `/chaski` is a routed served surface (FileResponse)
  that loaded three.js + OrbitControls from esm.sh at runtime. The runtime module renders
  the R3F recipe with three.js **core only**, so the dead `@react-three/fiber|drei`,
  `react`, `react-dom` importmap entries were dropped and the map collapsed to the vendored
  three.js + addons specifiers. Now 0 external requests.

### a11oy — doctrine guard hardened (additive)
- `tests/test_zero_cdn_guard.py` — extended `SERVED_GLOBS` to add the QA-flagged routed
  surfaces (`web/nemo.html`, `web/estate-hologram.html`, `pages/chaski.html`) so CI now
  fails the build on any future regression to an external font/module CDN on exactly the
  surfaces QA had to find by hand. Named individually (NOT `web/*.html`) so unrouted build
  artifacts are deliberately excluded.

### killinchu — font CDN removed
- `static/landing.html` — replaced Google Fonts `<link>` with the existing self-hosted
  `/vendor/fonts/fonts.css` pattern. The three served python pages
  (`killinchu_elite_console.py`, `killinchu_maritime_view.py`, `killinchu_mesh_view.py`)
  were already clean.

---

## 4. Deliberately NOT changed (documented, out of scope / no runtime impact)
- **`a11oy web/console.html`, `web/operator.html`** — contain CDN refs (cdnjs three r128,
  esm.sh) but are **unused build artifacts**: NOT routed by `_ptg_serve` and have no
  FileResponse route, so they are never served at runtime. Left untouched; excluded from
  the guard glob on purpose.
- **a11oy root `index.html` rosie-widget** — references `szlholdings-readme.static.hf.space`,
  which is an **own-origin `*.hf.space`** asset, not an external CDN. Left untouched.
- **killinchu non-routed / build-artifact CDN hits** (`web/console.html`, `web/operator.html`,
  `web/v4_fleet_panel.html`, `static/drone-3d.html`, `static/3d/killinchu_airspace/index.html`,
  `live_wires.html`, `static/assets/index-*.css`, `static/vendor/deck.min.js`) — not routed at
  runtime; no runtime-CDN exposure. Left untouched.

---

## 5. Commit SHAs

### a11oy — GitHub (`szl-holdings/a11oy`, branch `main`)
| Commit | Content |
|---|---|
| `0ce331f82cd734323570231516c60a3f7c91e9c1` | Initial 0-CDN fix — 19 files (fonts + esm.sh three.js) |
| `c495132eecb630e1b7d28bfe4d1b56053ef8bfd6` | Follow-up — `pages/chaski.html` self-host three.js |
| `feac1a8e640a846a74ea76c22d8ca64861dd3e99` | Additive guard extension — `tests/test_zero_cdn_guard.py` |

### a11oy — HF Space (`SZLHOLDINGS/a11oy`, branch `main`, NDJSON commits)
| Commit | Content |
|---|---|
| `7153e35ba07ecc253d1b91380356f34d31858299` | Initial 0-CDN fix mirror — 19 files |
| `1c4bdd783025bb908ecdbb2ba766aa42cdc966e0` | `pages/chaski.html` mirror |
| `aa3154de427e169af12b2f591e9e0a02d4ad0fd9` | Guard extension mirror |

Factory restart (`POST /restart?factory=true`) issued to bake the `web/*.html`
(`image_only_assets`) changes; Space rebuilt and is **RUNNING**.

### killinchu — GitHub (`szl-holdings/killinchu`, branch `main`)
- `9d489ea77b4ae06d3795956a4855d530ff7075bf` — `static/landing.html`

### killinchu — HF Space (`SZLHOLDINGS/killinchu`)
- `87758dfb37146338b51ab80623ba7d4f8c70d04c` — `static/landing.html` mirror; factory restart issued; Space **RUNNING**.

> Note: Forge was committing concurrently. Every push fetched a **fresh HEAD** before
> writing the tree/commit and used 409/000 retry; all pushes were **additive/surgical**
> over the live tip (observed HEADs advanced between pushes — e.g. `e993047` → `c495132`).

---

## 6. Live 0-CDN verification (Playwright, per surface)

Verifier: `/tmp/verify_cdn.mjs` (chromium, `networkidle`, 000-retry). It fails on any
banned host substring **and** any external (non-`*.hf.space`) network request, and reports
the computed body font + rendered text length.

### a11oy — `https://szlholdings-a11oy.hf.space`
| Surface | HTTP | External runtime URLs | Computed font | Renders |
|---|---|---|---|---|
| `/nemo` | 200 | **0** | `"Space Grotesk", system-ui, …` | yes (17,540 chars) |
| `/estate-hologram` | 200 | **0** | `ui-monospace, SFMono-Regular, Menlo, …` | yes (2,367 chars) |
| `/chaski` | 200 | **0** | `-apple-system, BlinkMacSystemFont, …` | yes (1,394 chars) |
| `/throne-room` | 200 | **0** | `Inter, ui-sans-serif, system-ui, …` | yes |
| `/wasi-rikuq` | 200 | **0** | `-apple-system, …` | yes |
| `/agentic-gpu` | 200 | **0** | `"Space Grotesk", Georgia, serif` | yes |
| `/fleet-c2` | 200 | **0** | `"Space Grotesk", Georgia, serif` | yes |
| `/living-anatomy` | 200 | **0** | `"Space Grotesk", Georgia, serif` | yes |
| `/superpowers` | 200 | **0** | — | yes |
| `/warhacker` | 200 | **0** | — | yes |
| `/wires` | 200 | **0** | — | yes |
| `/observability` | 200 | **0** | — | yes |
| `/landing` | 200 | **0** | — | yes |

### killinchu — `https://szlholdings-killinchu.hf.space`
| Surface | HTTP | External runtime URLs | Computed font | Renders |
|---|---|---|---|---|
| `/landing` | 200 | **0** | `"Space Grotesk", system-ui, …` | yes (5,601 chars) |

**Across all surfaces tested: `bannedHits = []`, `externalCount = 0`, `linkTags = []`,
`scriptTags = []`.** No regression — every page returns 200 and renders content with the
correct self-hosted / system font applied.

---

## 7. Doctrine guards — GREEN
- `tests/test_zero_cdn_guard.py` — **3 passed** (now covering /nemo, /estate-hologram, /chaski + console + static-vendor).
- `test_szl3d_holographic.py` + `test_energy_ops_dashboard.py` — **25 passed** combined.
- All embedded JS validated with `node --check`; all Python with `ast.parse` before push.

---

*ADDITIVE / surgical throughout. No keys committed. No existing gate weakened.*
