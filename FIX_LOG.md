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

**PR:** #434 (`feat/pnt-pinn-surfaces`) · **MERGED** to main (squash adf132a) · drift
allowlist follow-up #437 **MERGED** (squash) — main `hf-module-drift` gate now GREEN.

**Live re-check (a-11-oy.com, box redeployed main).**
- `/pnt` — serves the new "PNT · Quantum Nav" page (refs `surfaces/pnt.js`); headless:
  WEBGL2, canvas 1280x668, HUD builds with the full Q-CTRL Ironstone Opal overlay,
  honesty chip MODELED, UNSIGNED/STRUCTURAL-ONLY shown honestly. (Live API polls were
  HTTP 429 rate-limited during the probe — the HUD honestly shows "OFFLINE · no data yet"
  rather than a fake line, which is correct doctrine-v11 behavior; data populates when not
  throttled.)
- `/pinn` — serves the new "PINN · Physical-Bounds Certifier" page (refs `surfaces/pinn.js`,
  live copy has the `uInvModel` shader fix); headless: WEBGL2, canvas 1280x668, **0 console
  errors**, HUD builds, live cert lands → MEASURED T=341.29K / P=56.18W / t=91s → DERIVED
  E=5112J, DSSE Ed25519 SIGNED.

Both routes are now distinct live surfaces in production — no longer the generic Command
Center. D4 complete.

---

## Post-merge: main drift gate red on serve.py (PR #441 /fabric, not my work)

After my four PRs merged GREEN, a later sibling PR **#441** (dedicated `/fabric` surface)
landed an additive `@app.get("/fabric")` route in `serve.py` WITHOUT a matching drift
allowlist entry. The next main `hf-module-drift` run (sha 2aecbdf) then went **red**.

**Diagnosis (authoritative, reproduced locally against the live HF Space tree):** the only
error was `serve.py`. GitHub main blob = `ac311f0`; live HF Space blob = `62f1532`. The
`git diff 62f1532..ac311f0 -- serve.py` is EXACTLY #441's additive `/fabric` route (verified:
live serve.py HAS my `/pnt`+`/pinn` routes via `pnt.html`/`pinn.html`, but LACKS `fabric.html`).
So the box has redeployed main up to my work but not yet #441 — GitHub is ahead, the box lags.
Same accepted "ahead=github, pending Forge redeploy" class as the D1/D4 entries.

The checker's `ahead=huggingface?` label was a FALSE read: GitHub's per-file commit-date
lookup was rate-limited (returned `None`), so the date heuristic defaulted toward HF. The
content delta is unambiguously GitHub-ahead.

**Fix:** PR #444 — add a `serve.py` entry to `.github/hf-module-drift-allow.json` (pending
#441 redeploy; removable once OIDs reconcile). Verified locally: with the entry the guard
reports 0 errors / 1 allowlisted warning. (As with #437, the reusable workflow evaluates
`ref=main`, so the entry only takes effect once merged.)

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
- Fabric — endpoint `/api/a11oy/v1/compute-pool` is LIVE 200; surface mounts clean
  (`fabric:OK` via `__SZL3D_SHELL__`). Correctly wired to live data. (demos 7,8)
- Governance/Restraint — the `governance.js` surface polls `/api/a11oy/v1/assurance/{artifact,
  credential,compliance,attest}` + `/forge/ledger`. **All five return 404 on the live box**
  (verified by curl). The surface therefore renders its honest OFFLINE/404 state rather than a
  fabricated graph (correct doctrine-v11 behavior). This is a **backend deployment gap** (the
  assurance endpoints are not served by the box), not a repo wiring bug — it cannot be fixed
  from this source repo without fabricating data, which doctrine forbids. The spec's named
  Governance demos (13 trust radar, 14 gate ALLOW/DENY) want `/restraint/info` (which IS live
  200); rewiring governance.js to `/restraint` would be a follow-up surface change, owned by
  the spec's "Forge (box) + dev team" lane per LIVE_DEMOS_SPEC §SPLIT-OF-WORK.

**Scope note.** Per LIVE_DEMOS_SPEC §SPLIT-OF-WORK, the ~15-demo polish layer is explicitly
assigned to "Forge (box) + the dev team"; this engineer's lane was the broken basics (D3/D4)
plus the named priority surfaces PNT + PINN — all complete and live-verified. The Governance
backend gap is flagged here for that team.
