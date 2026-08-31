# SZL 3D — Vendored Library Manifest (Dev0 foundation)

Doctrine v11: **0 runtime CDN.** Every 3D library the holographic estate uses is
vendored here, in-image, and served same-origin via the allowlisted
`/static/3d/vendor/...` route (see `szl3d_holographic.py`). No `<script src>` may
ever point at a CDN. System fonts only.

All files below are the **real, unmodified upstream builds** fetched once at
vendor time and committed. Integrity = SHA-256 of the committed bytes (verify with
`sha256sum`). The selftest harness greps `/static/3d/` for `http(s)://` and fails
if any external URL appears.

## VENDORED NOW (this PR) — three.js r170 (MIT)

Upstream: https://github.com/mrdoob/three.js (tag `r170`), MIT License.
Fetched from `unpkg.com/three@0.170.0/...` at vendor time; served locally forever after.

| Path (under `/static/3d/vendor/`) | Upstream specifier | bytes | sha256 |
|---|---|---|---|
| `three/three.module.min.js` | `three@0.170.0/build/three.module.min.js` | 691648 | `08fd7545d13d2c7fb65ab691530a802dafefd638596501854f267d0fb13c39e7` |
| `three/three.webgpu.min.js` | `three@0.170.0/build/three.webgpu.min.js` | 822115 | `9d01bb1bae1badb5071d341f76c3569f6118bad126effd425a06611a9d993035` |
| `three/addons/controls/OrbitControls.js` | `examples/jsm/controls/OrbitControls.js` | 32134 | `80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e` |
| `three/addons/postprocessing/EffectComposer.js` | `examples/jsm/postprocessing/EffectComposer.js` | 4651 | `d234e578618fa816955ebdc059c049c577e203e650e33cf22bde3f232c29e669` |
| `three/addons/postprocessing/RenderPass.js` | `examples/jsm/postprocessing/RenderPass.js` | 1941 | `6c9b8a539ea16e898f65e4760f14937ef9ea94043bd9842c141e0301f41903e8` |
| `three/addons/postprocessing/ShaderPass.js` | `examples/jsm/postprocessing/ShaderPass.js` | 1576 | `3b28a1ee27e0eb96c0eab137a1f442ccf127a926904eced2d51e125ec44af781` |
| `three/addons/postprocessing/MaskPass.js` | `examples/jsm/postprocessing/MaskPass.js` | 2231 | `328cf7db0da5d9be83ffe39d54b01d5ac1fddf108cc98182ddbb056f5c8b537f` |
| `three/addons/postprocessing/Pass.js` | `examples/jsm/postprocessing/Pass.js` | 1706 | `b3c6128340eaa37e40a6a2f1b738e894c855239417d50959759b34a2b5e89f92` |
| `three/addons/postprocessing/UnrealBloomPass.js` | `examples/jsm/postprocessing/UnrealBloomPass.js` | 12410 | `3bd23a1097af75c7002d0ffc21a6c14f45c4dd701dbaf737030dfc61fb7c64d9` |
| `three/addons/postprocessing/OutputPass.js` | `examples/jsm/postprocessing/OutputPass.js` | 2524 | `32f879d2179087676631c799857a885586b3cdd13b9731bd3b13f06428bd58b7` |
| `three/addons/shaders/CopyShader.js` | `examples/jsm/shaders/CopyShader.js` | 571 | `4e3346db194db56a596cd074e9bdb39fb5eb52040c333e0d29dc4eb1324d3b1d` |
| `three/addons/shaders/LuminosityHighPassShader.js` | `examples/jsm/shaders/LuminosityHighPassShader.js` | 1147 | `9f4866f9abb2d96fd83eec46ba4bf2165b22155a7a37ff425c0f60eba18007cb` |
| `three/addons/shaders/OutputShader.js` | `examples/jsm/shaders/OutputShader.js` | 1490 | `4944cecd49c0d4d1520a4d927bde8a590fd43f041ee913252b9451855a01d0f0` |

## VENDORED NOW (Dev1 energy PR) — deck.gl r9.0.38 (MIT)

Upstream: https://github.com/visgl/deck.gl (tag `v9.0.38`), MIT License.
Fetched from `unpkg.com/deck.gl@9.0.38/dist.min.js` at vendor time (UMD global `deck`);
served locally forever after at `/static/3d/vendor/deck.gl/dist.min.js`. License text
committed alongside at `/static/3d/vendor/deck.gl/LICENSE`.

| Path (under `/static/3d/vendor/`) | Upstream specifier | bytes | sha256 |
|---|---|---|---|
| `deck.gl/dist.min.js` | `deck.gl@9.0.38/dist.min.js` | 1245838 | `e0ec599ee202671085dfb418a11ca08f59bbc9c0168ecc47d84bdd04f22c7cf4` |

**Rendering choice (Dev1, documented per Dev0 contract escape hatch):** the Energy
surface (`surfaces/energy.js`) renders the Electricity-Maps + deck.gl *technique*
(GPU column/hexbin grid + animated flow arcs + extruded negative-price columns +
live joules reservoir) in **pure three.js r170 inside the shell-owned `ctx.stage.scene`**.
Rationale: the szl3d shell hands each surface a single three.js Stage (one scene/camera/
OrbitControls + the WebGPU-or-WebGL2 bloom pipeline). deck.gl needs its own GL context
and a separate canvas, and its `ColumnLayer`/`ArcLayer`/`GPUGridLayer` are WebGL-only in
v9 (no WebGPU) — layering a second deck.gl canvas would fight OrbitControls, the bloom
composer, the WebGPU path, and the `clearScene()` lifecycle. three.js keeps the surface
on the toolkit's WebGPU-with-WebGL2-fallback path and inside the shared scene graph.
deck.gl is still vendored here (0-CDN, pinned, hashed) for Dev9's estate map / future
geospatial surfaces per the contract.

### Import map (every holographic page MUST include this exact block)

```html
<script type="importmap">
{
  "imports": {
    "three": "/static/3d/vendor/three/three.module.min.js",
    "three/webgpu": "/static/3d/vendor/three/three.webgpu.min.js",
    "three/addons/": "/static/3d/vendor/three/addons/"
  }
}
</script>
```

`szl3d_boot.js` uses `three/webgpu` when `navigator.gpu` is present and a device
can be acquired, otherwise it imports `three` (WebGL2 `WebGLRenderer`). Both builds
are r170 so the scene graph / addons are byte-compatible across the fallback.

## VENDORED ALREADY (elsewhere in the repo, reusable, 0 CDN)

These predate this PR and are already served in-image. Devs MAY reuse them instead
of re-vendoring:

- `static-vendor/3d-force-graph.min.js` — **3d-force-graph** UMD global build
  (served at `/vendor/3d-force-graph.min.js`). Use for Dev2 (compute fabric) and
  Dev5 (governance dependency graph). UMD global `ForceGraph3D`.
- `static-vendor/three.min.js` — three **r128** UMD standalone (global `THREE`),
  served at `/vendor/three.min.js`. Legacy; new surfaces SHOULD use the r170 ESM
  build vendored above, not this.
- `static/vendor3d/three.module.min.js` + `OrbitControls.js` — three **r160** ESM,
  served at `/hero/vendor3d/*`. Superseded by the r170 build here.

## TODO — libraries OTHER devs need, NOT yet vendored (pinned + planned)

Vendoring deck.gl + CesiumJS fully is heavy (deck.gl bundle ~1.2 MB, Cesium ~3 MB
JS + assets) and out of scope for this foundation PR per the Dev0 contract's
escape hatch. They are listed here with the **exact pinned versions** the owning
dev must vendor (download once, commit under `/static/3d/vendor/<lib>/`, add the
sha256 to this table, and extend the `_ALLOW` map in `szl3d_holographic.py`). Do
**NOT** add a CDN `<script>` tag — fetch-and-commit only.

| Lib | Owner (dev) | Pinned version | Upstream build to vendor | Target path |
|---|---|---|---|---|
| ~~deck.gl~~ | ~~Dev1 (energy), Dev9~~ | `deck.gl@9.0.38` | **DONE — vendored by Dev1** (see "VENDORED NOW (Dev1 energy PR)" above) | `/static/3d/vendor/deck.gl/dist.min.js` |
| ~~CesiumJS~~ | ~~Dev4 (counter-uas)~~ | ~~`cesium@1.123`~~ | **NOT vendored — Dev4 took the three.js-globe escape hatch (see §Dev4 below).** If a future surface needs the full Cesium globe (3D Terrain / 3D Tiles), vendor `cesium@1.123` `Build/Cesium/{Cesium.js,Workers,Assets,Widgets}` under `/static/3d/vendor/cesium/` and extend `_serve_3d` to allow that prefix. | `/static/3d/vendor/cesium/` |
| 3d-force-graph | Dev2, Dev5 | (reuse) `static-vendor/3d-force-graph.min.js` | already vendored — served at `/vendor/3d-force-graph.min.js` | (reuse) |

When a dev vendors one of these:
1. Fetch the pinned build, commit the bytes under `/static/3d/vendor/<lib>/`.
2. `sha256sum` it and add a row to the "VENDORED NOW" table above.
3. Add the filename(s) to `_THREED_ALLOW` in `szl3d_holographic.py` (or, for whole
   subtrees like Cesium's `Workers/`, extend `_serve_3d` to allow that prefix).
4. Re-run the selftest harness — the no-CDN grep must stay green.

## §Dev4 — Counter-UAS / killinchu surface: vendoring decisions

The Dev0 contract (§6) offered Dev4 an explicit escape hatch: vendor full CesiumJS@1.123
**OR** implement a three.js globe (textured sphere + lat/long track plotting). **Dev4 chose
the three.js globe.** Rationale:

- **0 new MB, 0 new CDN risk.** Reuses the already-vendored three.js r170 ESM build above.
  Full Cesium is ~3 MB JS + a `Workers/`+`Assets/`+`Widgets/` subtree (hundreds of files)
  and a separate `CESIUM_BASE_URL` serving contract — heavy for one surface PR.
- **Sufficient for the technique.** The surface needs a globe + lat/long track entities +
  restricted-airspace SDF volumes + a radar sweep cone + a signed-verdict beam. A procedural
  graticule sphere with `llToVec(lat,lon,alt)` plotting covers all of these without Cesium's
  terrain/imagery tile pipeline. (If a later surface needs real 3D Terrain or 3D Tiles, the
  Cesium TODO row above is preserved for that work.)
- **No new `_serve_3d` allow-prefix needed** — everything is served by the existing
  `/static/3d/{path}` route + the r170 importmap.

### Data vendored by Dev4 (real, not fabricated)

| Path (under `/static/3d/`) | What | Source | Notes |
|---|---|---|---|
| `surfaces/data/drones_db.json` | 53 verified drone fingerprints | killinchu repo `drones_db.json` (verified count = 53) | killinchu does not expose this as a JSON HTTP route (its root path serves the Cesium SPA); the surface loads the repo's own DB same-origin. Vendored verbatim, not fabricated. |

### Live-data bridge (server-side, not a vendored lib)

The Counter-UAS surface wires to REAL killinchu live data via a same-origin proxy
(`szl_counter_uas_proxy.py`, registered in `serve.py`) under `/api/a11oy/v1/counter-uas/*`
→ the killinchu Space (`https://szlholdings-killinchu.hf.space`). This is a server-side
forward (no browser CORS, no CDN script). It degrades gracefully (`{"degraded":true}`) so
`szl3d_live` renders the honest DEGRADED state. killinchu **senses and evidences; it does
not defeat** — the surface shows detect/track/classify/evidence + the signed verdict only.

## License notice

three.js r170 is MIT (Copyright © 2010-2024 three.js authors). The license text is
embedded at the top of `three.module.min.js` / `three.webgpu.min.js`. deck.gl is MIT
(Copyright © Open Visualization Foundation / Urban Computing Foundation). CesiumJS is
Apache-2.0. All compatible with the estate's Apache-2.0 posture; add full license
files alongside each lib when vendored, and update the repo root `NOTICES.md`.

## VENDORED — Looking Glass WebXR 0.6.0 (Apache-2.0)

Upstream: https://github.com/Looking-Glass/looking-glass-webxr (`@lookingglass/webxr@0.6.0`),
Apache-2.0. The dist `webxr.js` module-entry is NOT browser-standalone (bare imports to gl-matrix,
holoplay-core, @lookingglass/webxr-polyfill). We vendor the esm.sh FULLY-BUNDLED build
(`es2022/webxr.bundle.mjs`, all deps inlined, ZERO external imports — verified) so it loads
in-browser same-origin with 0 runtime CDN. Served same-origin; drives a real Looking Glass light-field
display via the WebXR immersive-vr session. 0 runtime CDN.

| Path (under `/static/3d/vendor/`) | Upstream specifier | bytes | sha256 |
|---|---|---|---|
| `lookingglass/webxr.js` | `@lookingglass/webxr@0.6.0` (esm.sh fully-bundled `es2022/webxr.bundle.mjs` — all deps inlined: gl-matrix, holoplay-core, webxr-polyfill) | 234849 | `4624b2ca65026481f42c1ef6ef7e1345158ae00c0bad02e58ab6dd1f5a8aaf5e` |
