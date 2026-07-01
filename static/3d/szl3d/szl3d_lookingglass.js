// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// szl3d_lookingglass.js — native Looking Glass light-field display runtime (WebXR).
//
// Wraps the vendored @lookingglass/webxr 0.6.0 polyfill (Apache-2.0, self-hosted at
// /static/3d/vendor/lookingglass/webxr.js — 0 runtime CDN). Lets the holographic estate render
// NATIVELY on a Looking Glass light-field display (not just the quilt-PNG export): it installs
// a WebXR polyfill that intercepts the 'immersive-vr' session and routes it to the display.
//
// HONEST behavior (doctrine v11): the polyfill is lazy-loaded only on user gesture. If no
// Looking Glass hardware / WebXR is available it opens the polyfill's own popup window (its
// documented behavior) — we surface an honest status either way and never claim a display is
// present when it is not. WebXR + the popup are user-initiated; nothing auto-launches.
//
// Usage:
//   import * as lkg from "/static/3d/szl3d/szl3d_lookingglass.js";
//   await lkg.enter(stage, { targetY: 2.6, targetDiam: 30 });   // on a button click
//   lkg.available();  // boolean — is WebXR present at all (best-effort capability hint)

let _polyfillInstalled = false;
let _mod = null;

// Best-effort capability hint (no session request). True if the browser exposes WebXR.
export function available() {
  return (typeof navigator !== "undefined" && "xr" in navigator);
}

// Lazy-load the vendored polyfill module (same-origin, 0 CDN).
// The vendored file is the FULLY-BUNDLED build (all deps inlined: gl-matrix,
// holoplay-core, webxr-polyfill; zero external imports) so it loads in-browser with 0 CDN.
// The guarded catch stays as an honest safety net: if the bundle ever fails to load we surface
// an actionable message and point to the light-field quilt export — never faking a display.
async function _load() {
  if (_mod) return _mod;
  try {
    _mod = await import("/static/3d/vendor/lookingglass/webxr.js");
  } catch (e) {
    const msg = (e && e.message) || String(e);
    if (/resolve module specifier|Failed to fetch dynamically imported/i.test(msg)) {
      throw new Error("Looking Glass polyfill bundle failed to load in-browser. Native LG entry is unavailable here — use the light-field quilt export instead.");
    }
    throw e;
  }
  return _mod;
}

// Install the Looking Glass WebXR polyfill (once) and configure the light-field frustum.
// `cfg` maps onto LookingGlassConfig (targetX/Y/Z, targetDiam, fovy[rad], numViews, depthiness).
export async function install(cfg = {}) {
  const mod = await _load();
  const LookingGlassConfig = mod.LookingGlassConfig;
  const LookingGlassWebXRPolyfill = mod.LookingGlassWebXRPolyfill;
  if (!LookingGlassConfig || !LookingGlassWebXRPolyfill) throw new Error("looking-glass polyfill exports missing");
  // LookingGlassConfig is a SINGLETON — mutate it, never call as a constructor. Some properties
  // (e.g. numViews) are getter-only in this build; assign defensively so a read-only prop never
  // throws — honest: we set what the build allows and pass the rest to the polyfill constructor.
  const c = LookingGlassConfig;
  const set = (k, v) => { if (v == null) return; try { c[k] = v; } catch (_) { /* getter-only in this build */ } };
  set("targetX", cfg.targetX);
  set("targetY", cfg.targetY != null ? cfg.targetY : 0);
  set("targetZ", cfg.targetZ != null ? cfg.targetZ : 0);
  set("targetDiam", cfg.targetDiam != null ? cfg.targetDiam : 3);
  set("fovy", cfg.fovy != null ? cfg.fovy : (14 * Math.PI) / 180);   // RADIANS
  set("depthiness", cfg.depthiness);
  // numViews / tileHeight may be read-only on the singleton; pass them via the constructor instead.
  if (!_polyfillInstalled) {
    const opts = { targetY: cfg.targetY != null ? cfg.targetY : 0, targetZ: cfg.targetZ != null ? cfg.targetZ : 0, targetDiam: cfg.targetDiam != null ? cfg.targetDiam : 3, fovy: cfg.fovy != null ? cfg.fovy : (14 * Math.PI) / 180 };
    if (cfg.numViews != null) opts.numViews = cfg.numViews;
    try { new LookingGlassWebXRPolyfill(opts); } catch (_) { new LookingGlassWebXRPolyfill(); }
    _polyfillInstalled = true;
  }
  return c;
}

// Enter the Looking Glass immersive session for a booted szl3d stage.
// Enables renderer.xr, installs the polyfill, and requests an immersive-vr session which the
// polyfill routes to the display. Returns { entered:boolean, note:string } — honest.
export async function enter(stage, cfg = {}) {
  if (!stage || !stage.renderer) return { entered: false, note: "no renderer" };
  try {
    await install(cfg);
    const renderer = stage.renderer;
    try { renderer.xr.enabled = true; } catch (_) {}
    if (!(navigator.xr && navigator.xr.requestSession)) {
      return { entered: false, note: "WebXR unavailable in this browser — Looking Glass needs a WebXR-capable browser + the display's bridge." };
    }
    const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor"] });
    await renderer.xr.setSession(session);
    return { entered: true, note: "Looking Glass session active (or polyfill preview window opened when no hardware is attached).", session };
  } catch (e) {
    return { entered: false, note: "Looking Glass session not started: " + ((e && e.message) || String(e)) };
  }
}

export async function exit(stage) {
  try { const s = stage && stage.renderer && stage.renderer.xr && stage.renderer.xr.getSession && stage.renderer.xr.getSession(); if (s) await s.end(); } catch (_) {}
}

export default { available, install, enter, exit };
