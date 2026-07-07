// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/mor.js — MIXTURE-OF-RECURSIONS (MoR) organ for the holographic
// frontier ring. Renders ONE shared transformer block applied at a VARIABLE
// per-token recursion DEPTH: a per-token depth HEATMAP (each token coloured by
// how many times the SAME shared weights were looped over it, 1..max_depth),
// plus a HUD showing compute_saved vs a fixed-max-depth recursive baseline and
// the MODELED quality-retained proxy. Live snapshot comes from
// /api/a11oy/v1/mor/route. Honesty label "MODELED" is read VERBATIM from
// the JSON and displayed as-is; it is never upgraded.
//
// >>> DISTINCT FROM THE 'router' ORGAN <<<
//   router = parameter SELECTION: dispatch each token/query to one of several
//     DIFFERENT, independently-parameterized models/experts (which weights).
//   mor    = parameter REUSE: loop ONE shared block a variable number of times
//     per token (how many times the same weights). One weight set here; only
//     the recursion depth changes. The surface copy states this explicitly.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   tokens, max_depth, threshold, per_token_depth[], depth_histogram[],
//   mean_depth, fixed_depth_flops, mor_flops, compute_saved_frac,
//   speedup_vs_fixed, kv_cache_frac, quality_retained, shared_block
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Mixture-of-Recursions (adaptive per-token recursion depth over a shared block):
//     Bae et al. 2025, arXiv:2507.10524
//     https://arxiv.org/abs/2507.10524
//   MoR reference implementation (reference only):
//     https://github.com/raymin0223/mixture_of_recursions
//
// HONESTY LABELS: MODELED (deterministic re-implementation of the adaptive
//   depth-routing arithmetic; NOT the MoR model; NEVER-CLAIMED-AS production).
//   Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (depth-1 / shallow), violet-blue 0x8a6bff
//   (mid depth), proof-teal 0x3af4c8 (deepest recursion / HUD accent), greys
//   (degraded / no-live-data). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "mor";
const TITLE = "Mixture-of-Recursions · Adaptive Per-Token Depth (live)";

// Endpoint is served SAME-ORIGIN by the flagship (szl_mor.py), a deterministic
// adaptive depth-routing simulation. Same-origin avoids CORS and cross-Space
// fault coupling.
const EP = "/api/a11oy/v1/mor/route?seed=42&tokens=256&max_depth=4&threshold=0.5";

// data-viz hues — purple BANNED. Depth ramp: shallow(blue) -> mid(violet-blue)
// -> deep(proof-teal). Greys reserved for degraded / no-live state.
const C_SHALLOW = 0x5b8dee;  // lattice-blue   (depth 1 — token exited early / easy)
const C_MID     = 0x8a6bff;  // violet-blue    (mid recursion depth)
const C_DEEP    = 0x3af4c8;  // proof-teal     (deepest recursion / HUD accent)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// per-token depth heatmap layout geometry
const COLS       = 16;    // heatmap columns
const ROWS       = 16;    // heatmap rows  (COLS*ROWS = 256 = default token count)
const CELL       = 0.62;  // world-units between heatmap cells
const MAX_CELLS  = COLS * ROWS;

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor    = null;
let _cellMesh = [];    // Array<THREE.Mesh> — one per token cell in the heatmap
let _column   = null;  // THREE.Group — depth-histogram columns
let _colBars  = [];    // Array<THREE.Mesh> — one bar per depth bucket
let _marker   = null;  // THREE.Mesh — HUD "compute saved" pulsing marker

// live state
const S = {
  label:        null,
  tokens:       null,   // tokens
  maxDepth:     null,   // max_depth
  threshold:    null,   // threshold
  perToken:     null,   // per_token_depth[]
  histogram:    null,   // depth_histogram[]
  meanDepth:    null,   // mean_depth
  savedFrac:    null,   // compute_saved_frac
  speedup:      null,   // speedup_vs_fixed
  kvFrac:       null,   // kv_cache_frac
  quality:      null,   // quality_retained
  sharedBlock:  null,   // shared_block (bool)
  state:        "init",
};

// map a recursion depth (1..maxDepth) onto the shallow->mid->deep hue ramp
function _depthColor(depth, maxDepth) {
  if (maxDepth <= 1) return C_DEEP;
  const f = (depth - 1) / (maxDepth - 1);   // 0 (shallow) .. 1 (deep)
  if (f <= 0.5) return _lerpHex(C_SHALLOW, C_MID, f / 0.5);
  return _lerpHex(C_MID, C_DEEP, (f - 0.5) / 0.5);
}

function _lerpHex(a, b, t) {
  t = Math.max(0, Math.min(1, t));
  const ar = (a >> 16) & 255, ag = (a >> 8) & 255, ab = a & 255;
  const br = (b >> 16) & 255, bg = (b >> 8) & 255, bb = b & 255;
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bl = Math.round(ab + (bb - ab) * t);
  return (r << 16) | (g << 8) | bl;
}

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHeatmap();
  _buildHistogram();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onMor, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateScene(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(36, 36, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Pre-allocate a fixed COLS x ROWS grid of token cells. Colour/height are
// toggled in-place per poll from live per_token_depth (no geometry churn).
function _buildHeatmap() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(CELL * 0.82, 1.0, CELL * 0.82);
  const x0 = -(COLS - 1) * CELL * 0.5;
  const z0 = -(ROWS - 1) * CELL * 0.5;
  for (let i = 0; i < MAX_CELLS; i++) {
    const col = i % COLS;
    const row = (i / COLS) | 0;
    const mesh = new THREE.Mesh(
      cellGeo,
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.12, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(x0 + col * CELL, 0.02, z0 + row * CELL);
    mesh.scale.y = 0.05;
    mesh.visible = false;
    _group.add(mesh);
    _cellMesh.push(mesh);
  }
}

// depth-histogram columns rise behind the heatmap (one bar per depth bucket)
function _buildHistogram() {
  const THREE = _THREE;
  _column = new THREE.Group();
  _column.position.set(0, 0, -(ROWS * CELL * 0.5) - 2.4);
  const MAXBARS = 16;
  const barGeo = new THREE.BoxGeometry(0.55, 1.0, 0.55);
  for (let d = 0; d < MAXBARS; d++) {
    const bar = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    bar.position.set((d - MAXBARS / 2) * 0.75, 0.02, 0);
    bar.scale.y = 0.05;
    bar.visible = false;
    _column.add(bar);
    _colBars.push(bar);
  }
  _group.add(_column);
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.30, 1),
    new THREE.MeshStandardMaterial({ color: C_DEEP, emissive: C_DEEP, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, 3.6, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onMor(j) {
  // read honesty label VERBATIM — never upgrade. Endpoint puts label at the
  // TOP LEVEL of the JSON (this module's own response shape), so read j.label;
  // fall back to a nested payload.label defensively in case of a wrapper.
  const rawLabel = (j && typeof j.label === "string") ? j.label
                 : (j && j.payload && typeof j.payload.label === "string") ? j.payload.label
                 : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : (j || {});

  S.label       = String(rawLabel).toUpperCase();
  S.tokens      = typeof src.tokens             === "number" ? src.tokens             : null;
  S.maxDepth    = typeof src.max_depth          === "number" ? src.max_depth          : null;
  S.threshold   = typeof src.threshold          === "number" ? src.threshold          : null;
  S.perToken    = Array.isArray(src.per_token_depth) ? src.per_token_depth : null;
  S.histogram   = Array.isArray(src.depth_histogram) ? src.depth_histogram : null;
  S.meanDepth   = typeof src.mean_depth         === "number" ? src.mean_depth         : null;
  S.savedFrac   = typeof src.compute_saved_frac === "number" ? src.compute_saved_frac : null;
  S.speedup     = typeof src.speedup_vs_fixed   === "number" ? src.speedup_vs_fixed   : null;
  S.kvFrac      = typeof src.kv_cache_frac      === "number" ? src.kv_cache_frac      : null;
  S.quality     = typeof src.quality_retained   === "number" ? src.quality_retained   : null;
  S.sharedBlock = typeof src.shared_block       === "boolean" ? src.shared_block      : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the heatmap + histogram from live data
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const maxDepth = live && S.maxDepth ? S.maxDepth : 0;
  const depths = live && S.perToken && S.perToken.length ? S.perToken : [];

  // --- per-token depth heatmap ---
  for (let i = 0; i < MAX_CELLS; i++) {
    const mesh = _cellMesh[i];
    if (!live || i >= depths.length || maxDepth <= 0) {
      mesh.visible = false;
      continue;
    }
    const d = depths[i];
    mesh.visible = true;
    const color = _depthColor(d, maxDepth);
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    // deeper recursion => taller, brighter cell (more compute spent on token)
    const h = 0.25 + (d / maxDepth) * 2.4;
    mesh.scale.y = h;
    mesh.position.y = h * 0.5;
    mesh.material.emissiveIntensity = 0.18 + 0.4 * (d / maxDepth);
    mesh.material.opacity = 0.92;
  }

  // --- depth histogram columns ---
  const hist = live && S.histogram && S.histogram.length ? S.histogram : [];
  const maxCount = hist.length ? Math.max(1, ...hist) : 1;
  for (let d = 0; d < _colBars.length; d++) {
    const bar = _colBars[d];
    if (!live || d >= hist.length) { bar.visible = false; continue; }
    bar.visible = true;
    const color = _depthColor(d + 1, hist.length);
    bar.material.color.setHex(color);
    bar.material.emissive.setHex(color);
    const h = 0.15 + (hist[d] / maxCount) * 3.4;
    bar.scale.y = h;
    bar.position.y = h * 0.5;
    bar.material.emissiveIntensity = 0.35;
    bar.material.opacity = 0.9;
  }

  // --- compute-saved marker ---
  if (_marker) {
    if (live && S.savedFrac != null) {
      _marker.material.color.setHex(C_DEEP);
      _marker.material.emissive.setHex(C_DEEP);
      _marker.material.opacity = 0.85;
      // marker scale reads the compute-saved fraction (bigger = more saved)
      _marker.scale.setScalar(0.7 + (S.savedFrac || 0) * 1.4);
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
      _marker.scale.setScalar(0.7);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.16;
  if (_marker) {
    _marker.rotation.y += 0.022;
    _marker.rotation.x += 0.011;
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "adaptive depth", name: "mor" }],
    legend: ["MODELED", "SAMPLE"],
    description:
    'ONE shared transformer block is applied a <b>variable number of times per token</b>: a lightweight ' +
    'router gives each token a recursion <b>depth</b> (1…N loops of the <i>same</i> weights). ' +
    'Easy tokens exit early; hard tokens recurse deeper. Cells below are coloured by depth ' +
    '(blue = shallow → teal = deep); height = compute spent. ' +
    'Honesty label <b>MODELED</b> (deterministic depth-routing simulation; NOT the MoR model). 0 runtime CDN.' +
    '<br><br>' +
    '<b style="color:#3af4c8">Not the &lsquo;router&rsquo; organ.</b> ' +
    'The <b>router</b> organ is parameter <b>SELECTION</b> — it dispatches each token to one of several ' +
    '<i>different, independently-parameterized</i> models/experts (<i>which</i> weights). ' +
    '<b>Mixture-of-Recursions</b> is parameter <b>REUSE</b> — it loops <i>one</i> shared block a variable ' +
    'number of times per token (<i>how many times</i> the same weights). One weight set here; only the depth changes.',
    citations:
      "Bae et al. arXiv:2507.10524 (Mixture-of-Recursions) \u00b7 github.com/raymin0223/mixture_of_recursions. MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["mor-tokens"]    = _show.addField("tokens routed");
  _el["mor-maxdepth"]  = _show.addField("max_depth (loops of ONE block)");
  _el["mor-meandepth"] = _show.addField("mean recursion depth");
  _el["mor-saved"]     = _show.addField("compute_saved vs fixed-depth \u2014 MODELED");
  _el["mor-speedup"]   = _show.addField("speedup_vs_fixed \u2014 MODELED");
  _el["mor-kv"]        = _show.addField("KV-cache footprint vs uniform");
  _el["mor-quality"]   = _show.addField("quality_retained (proxy)");
  _el["mor-shared"]    = _show.addField("shared block? (parameter REUSE)");
  _el["mor-label"]     = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const md      = S.maxDepth  != null ? String(S.maxDepth) : "loading\u2026";
  const mean    = S.meanDepth != null ? S.meanDepth.toFixed(2) : "loading\u2026";
  const savedPc = S.savedFrac != null ? (S.savedFrac * 100).toFixed(1) + "%" : "loading\u2026";
  const spd     = S.speedup   != null ? S.speedup.toFixed(2) + "\u00d7" : "loading\u2026";
  return (
    "<b>What this means:</b> A normal model runs every word through the <i>same</i> amount of work. " +
    "Mixture-of-Recursions reuses <b>one</b> block of the model and simply <b>loops it more times " +
    "for hard words and fewer times for easy words</b> (up to <b>" + md + "</b> loops). On average each " +
    "word here needs about <b>" + mean + "</b> loops instead of the full " + md + ", which saves roughly " +
    "<b>" + savedPc + "</b> of the compute (about a <b>" + spd + "</b> speedup) while keeping quality, " +
    "because only the genuinely hard words get the deep treatment. " +
    "<b>Key difference from a &lsquo;router&rsquo;:</b> a router picks <i>which</i> of several different " +
    "models to use; MoR reuses <i>one</i> model and only changes <i>how many times</i> it runs. " +
    "This view is a <b>MODELED</b> simulation of the depth-routing math, not a run of the real MoR model.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("mor-tokens",    t || (S.tokens   != null ? String(S.tokens)   : "\u2014"));
  _set("mor-maxdepth",  t || (S.maxDepth != null ? String(S.maxDepth) : "\u2014"));
  _set("mor-meandepth", t || fx(S.meanDepth, 3));
  _set("mor-saved",     t || pct(S.savedFrac, 2));
  _set("mor-speedup",   t || (S.speedup != null ? S.speedup.toFixed(3) + "\u00d7" : "\u2014"));
  _set("mor-kv",        t || pct(S.kvFrac, 2));
  _set("mor-quality",   t || pct(S.quality, 2));
  _set("mor-shared",    t || (S.sharedBlock === true ? "yes (ONE reused block)" : S.sharedBlock === false ? "no" : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("mor-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("mor", S.label || "MODELED", { text: "adaptive depth" }); _show.refreshPlain(); }
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _floor = null; _cellMesh = []; _column = null; _colBars = []; _marker = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.tokens = S.maxDepth = S.threshold = null;
  S.perToken = S.histogram = S.meanDepth = S.savedFrac = null;
  S.speedup = S.kvFrac = S.quality = S.sharedBlock = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
