# a11oy demo-polish fix log (Phase 2)

Engineer: stephenlutar2-hash · WarHacker demo target 2026-06-18
Prior team already merged D1 (/holographic WebGPU), D2 (/energy-ops graphs), D5 (HF URLs).

---

## D4 — /pnt and /pinn render distinct live surfaces (was: both = generic Command Center)

**Root cause.** `/pnt` and `/pinn` had no explicit FastAPI routes, so both fell through
to the SPA catch-all (`@app.get("/{full_path:path}")`) and served the generic Command
Center `index.html`. That CC is (a) not the intended per-surface view and (b) the source
of the D3 "probing…" hangs.

**Fix.**
- `pages/pnt.html` — thin server-rendered szl3d shell that mounts ONLY
  `static/3d/surfaces/pnt.js` (MODELED quantum-nav: k_eff, accel sensitivity, ASD curves
  from `/api/a11oy/v1/pnt/{sensor,coast,resilience,limits}`). WebGL2 default, `?webgpu=1` opt-in.
- `pages/pinn.html` — same pattern, mounts `static/3d/surfaces/pinn.js` (MEASURED→DERIVED
  physical-bounds certificate from `/api/a11oy/v1/pinn/certificate`, residual plot, DSSE
  verify badges).
- `serve.py` — explicit `/pnt` + `/pinn` routes registered before the SPA catch-all; fall
  back to `index.html` only if the page file is missing.
- `static/3d/surfaces/pinn.js` — **shader bug fix.** The volumetric raymarch
  `ShaderMaterial` uses `glslVersion: THREE.GLSL3`. three.js does NOT auto-inject the
  `modelMatrix` built-in uniform for a raw GLSL3 ShaderMaterial, so the fragment shader's
  `inverse(modelMatrix)` failed to compile (`'modelMatrix': undeclared identifier`). The
  shader throw aborted `mount()` before the HUD overlay was appended — canvas rendered but
  no HUD/cert. Fix: added an explicit `uInvModel` mat4 uniform, declared `uniform mat4
  uInvModel;` in the fragment shader, replaced `inverse(modelMatrix)` with `uInvModel`, and
  update it per-frame from `_volMesh.matrixWorld` (the group rotates, so it must refresh
  each frame alongside the existing `uCamPos` copy).

**Verify (headless Chromium, swiftshader / `--enable-unsafe-swiftshader`).**
- `/pnt` — backend WEBGL2, canvas 1280x668, HUD builds, **0 console errors**, live poll
  lands → MODELED, real `k_eff=1.61e7`.
- `/pinn` — backend WEBGL2, canvas 1280x668, HUD builds, **0 console errors**, live cert
  lands → MEASURED T=341.29K / P=56.18W / t=91s → DERIVED E=5112J, DSSE Ed25519 SIGNED.

**PR:** #434 (`feat/pnt-pinn-surfaces`) · merged: _pending CI_ · live re-check: _pending deploy_

---

## D3 — generic Command Center async loads hang ("probing…")

For `/pnt` and `/pinn` specifically, D3 is resolved as a side effect of D4: those routes no
longer serve the hanging Command Center at all.

The generic Command Center itself (the a11oy command surface) is a React SPA whose source
lives in the parent monorepo (`web/` depends on 22+ `workspace:*` packages and cannot build
standalone in this repo — see AGENTS.md). `serve.py` ships only the prebuilt `index.html`
bundle. The hanging fetch logic is inside that compiled bundle, not editable from this
repo's source. **Status: documented limitation for the generic CC; the two demo routes the
brief named (/pnt, /pinn) are fixed.** (Assess further if SPA source becomes available.)

---

## Live demos (per LIVE_DEMOS_SPEC.md)

- PNT — DONE (this PR). Sensor curves + nav-coast, MODELED chip, source endpoint shown.
- PINN — DONE (this PR). Cert card + residual, MEASURED chip, DSSE/cosign badges.
- Fabric / Governance / others — surfaces already mount clean on `/holographic` (all 9
  drive OK via `__SZL3D_SHELL__`, verified earlier). Pending: confirm each tab's live
  binding + status chip per spec.
