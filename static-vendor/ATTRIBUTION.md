# Vendored anvaka graph stack — ATTRIBUTION (0-CDN, in-image)

All files below are **vendored locally** (no runtime CDN) and referenced with relative
`<script src="/vendor/...">` tags only. Author: **Andrei Kashcha** (GitHub
[@anvaka](https://github.com/anvaka)). We do **not** relicense or claim authorship of
these libraries — "make it our own" means our data + our tab logic + our adaptation
layer; the rendering/layout primitives stay attributed to Andrei Kashcha.

| Vendored file | Source repo + path | SPDX license | Global exposed | Copyright |
|---|---|---|---|---|
| `ngraph.graph.min.js` | [anvaka/ngraph.graph](https://github.com/anvaka/ngraph.graph) `dist/` | BSD-3-Clause | `createGraph` | © 2013-2026 Andrei Kashcha |
| `ngraph.forcelayout.min.js` | [anvaka/ngraph.forcelayout](https://github.com/anvaka/ngraph.forcelayout) `dist/` | BSD-3-Clause | `ngraphCreateLayout` | © 2013-2026 Andrei Kashcha |
| `ngraph.path.min.js` | [anvaka/ngraph.path](https://github.com/anvaka/ngraph.path) `dist/` | MIT | `ngraphPath` (`.aStar/.aGreedy/.nba`) | © 2017-2026 Andrei Kashcha |
| `ngraph.events.umd.js` | [anvaka/ngraph.events](https://github.com/anvaka/ngraph.events) `index.js` (ESM source, wrapped UMD) | BSD-3-Clause | `ngraphEvents` | © 2013-2026 Andrei Kashcha |
| `panzoom.min.js` | [anvaka/panzoom](https://github.com/anvaka/panzoom) `dist/` | MIT | `panzoom` | © 2016-2026 Andrei Kashcha |
| `vivagraph.min.js` | [anvaka/VivaGraphJS](https://github.com/anvaka/VivaGraphJS) `dist/vivagraph.min.js` | BSD-3-Clause | `Viva` | © 2011-2026 Andrei Kashcha |

Each library's full LICENSE text is kept beside its vendored file as `LICENSE.<lib>`.

## Deferred to a later round (NOT vendored in R1)
These anvaka libraries ship only as CommonJS-with-deep-`require()`-trees or as
un-built TypeScript source. Without an npm/bundler step in the offline build sandbox
they cannot be turned into a single self-contained browser global safely, so they are
**deferred** rather than shipped half-wired:

- **ngraph.three** (`index.js` requires `three`, `ngraph.merge`, `ngraph.forcelayout3d`,
  `three.trackball`) — deep require tree.
- **three.map.control** (`index.js` requires `wheel`, `ngraph.events`, `amator`,
  `./lib/kinetic`) — deep require tree.
- **ngraph.cw** (`index.js` requires `ngraph.random`) — small but unbundled.
- **w-gl** (`index.ts` + `src/` TypeScript only, no prebuilt `build/`/`dist/`) — needs a
  TS bundler.

3D tabs are instead driven by the already-vendored **`ngraph.forcelayout`
`{dimensions:3}`** deterministic layout (the core "upgrade engine") rendered with the
already-in-image **`three.min.js` + `3d-force-graph.min.js`** — fully 0-CDN. Re-vendor the
four deferred libs once a one-time offline bundle pass is available.

## Charting libs for the energy surfaces (0-CDN, in-image)

Vendored for the Proven Energy Engine dashboards (`/energy-harvest` and siblings).
Referenced same-origin via `/vendor/...` only; we do not relicense or claim authorship.

| Vendored file | Source repo | SPDX license | Global exposed | Copyright |
|---|---|---|---|---|
| `uPlot.iife.min.js` + `uPlot.min.css` | [leeoniya/uPlot](https://github.com/leeoniya/uPlot) v1.6.32 `dist/` | MIT | `uPlot` | © 2022 Leon Sorokin |
| `echarts.min.js` | [apache/echarts](https://github.com/apache/echarts) `dist/` | Apache-2.0 | `echarts` | © The Apache Software Foundation |

uPlot's full MIT text is kept beside the file as `LICENSE.uplot`; ECharts ships its
Apache-2.0 header inline at the top of `echarts.min.js`.
