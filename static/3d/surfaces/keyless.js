// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/keyless.js — KEYLESS ATTENTION (VALUE-ONLY CACHE) organ for the
// holographic frontier ring (Xin Gao, arXiv:2606.21848). Renders the
// value-only-cache mechanism vs standard QKV attention as three live panels:
//   (1) CACHE-SIZE BARS — standard cache (K+V = 2·L·d) vs keyless cache
//       (V-only = L·d), the exact 50% shrink shown as two boxes;
//   (2) ATTENTION-MAP HEATMAPS — the standard softmax(Q·Kᵀ/√d) map vs the
//       keyless softmax((Q·R)·Vᵀ/√d) map, as two grids of coloured cells;
//   (3) OUTPUT-FIDELITY BAR — mean per-token cosine similarity between the two
//       attention outputs, the MEASURED "matches within X on the toy" metric.
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/keyless/attention. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors muon.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   L, d, m, bytes_per_entry, kv_entries_standard, kv_entries_keyless,
//   kv_bytes_standard, kv_bytes_keyless, reduction_pct, cosine_mean,
//   cosine_min, mse, scores_std_head[[...]], scores_keyless_head[[...]]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real):
//   Keyless Attention: Value-Space Routing and Value-Only Caching for Efficient
//     Transformers — Xin Gao. arXiv:2606.21848
//     https://arxiv.org/abs/2606.21848
//
// HONESTY LABELS: MODELED (deterministic reproduction of the value-only-cache +
//   value-space-routing MECHANISM on a toy synthetic sequence; NOT a trained
//   transformer; trains nothing; the 50% cache shrink is exact arithmetic and
//   the output fidelity is MEASURED; NEVER-CLAIMED-AS a production kernel).
//   Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "keyless";
const TITLE = "Keyless Attention (Value-Only Cache)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/keyless/attention?seed=42&L=16&d=16&m=3";

// data-viz hues — purple BANNED
const C_STD      = 0x5b8dee;  // lattice-blue (standard cache bar / std heatmap)
const C_KEYLESS  = 0x3af4c8;  // proof-teal   (keyless cache bar / keyless heatmap)
const C_FID      = 0x8a6bff;  // violet-blue  (output-fidelity bar)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_ZERO     = 0x5a6570;  // grey (near-zero heatmap cell)
const C_GRID     = 0x1b3a44;  // floor / link colour

// layout geometry
const HEAT_CELL  = 0.16;   // heatmap cell size
const HEAT_GAP   = 0.17;   // heatmap cell pitch
const HEAT_MAX   = 8;      // cap cells per axis rendered (matches head trim)
const BAR_W      = 0.9;    // cache-bar width

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor      = null;
let _heatStd    = [];     // Array<THREE.Mesh> — standard attention-map cells
let _heatKeyless= [];     // Array<THREE.Mesh> — keyless attention-map cells
let _heatGroup  = null;
let _barStd     = null;   // THREE.Mesh — standard cache-size bar (K+V)
let _barKeyless = null;   // THREE.Mesh — keyless cache-size bar (V-only)
let _barFid     = null;   // THREE.Mesh — output-fidelity (cosine) bar
let _barGroup   = null;

// live state
const S = {
  label:      null,
  L:          null,
  d:          null,
  m:          null,
  bytesPer:   null,   // bytes_per_entry
  kvEntStd:   null,   // kv_entries_standard
  kvEntKey:   null,   // kv_entries_keyless
  kvBytesStd: null,   // kv_bytes_standard
  kvBytesKey: null,   // kv_bytes_keyless
  reduction:  null,   // reduction_pct
  cosMean:    null,   // cosine_mean
  cosMin:     null,   // cosine_min
  mse:        null,
  scoresStd:  null,   // Array<Array<number>>
  scoresKey:  null,   // Array<Array<number>>
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(5, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(2, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHeatmaps();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onKeyless, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// two grids of coloured cells (standard | keyless attention maps). Pre-allocate
// a fixed HEAT_MAX x HEAT_MAX per side; toggle visibility/color in place.
function _buildHeatmaps() {
  const THREE = _THREE;
  _heatGroup = new THREE.Group();
  _heatGroup.position.set(0.0, 0.05, 2.6);
  _group.add(_heatGroup);
  const cellGeo = new THREE.PlaneGeometry(HEAT_CELL, HEAT_CELL);

  function makeGrid(offsetX, arr) {
    for (let r = 0; r < HEAT_MAX; r++) {
      for (let c = 0; c < HEAT_MAX; c++) {
        const mesh = new THREE.Mesh(
          cellGeo,
          new THREE.MeshBasicMaterial({ color: C_ZERO, transparent: true, opacity: 0.0, side: THREE.DoubleSide }),
        );
        mesh.rotation.x = -Math.PI / 2;
        mesh.position.set(offsetX + c * HEAT_GAP, 0.02, r * HEAT_GAP);
        mesh.visible = false;
        _heatGroup.add(mesh);
        arr.push(mesh);
      }
    }
  }
  makeGrid(0.0, _heatStd);
  makeGrid(HEAT_MAX * HEAT_GAP + 0.8, _heatKeyless);
}

function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(-3.4, 0, 0.0);
  _group.add(_barGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  _barStd = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_STD, emissive: C_STD, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barStd.position.set(0, 0.5, 0);
  _barGroup.add(_barStd);

  _barKeyless = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_KEYLESS, emissive: C_KEYLESS, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barKeyless.position.set(1.3, 0.5, 0);
  _barGroup.add(_barKeyless);

  _barFid = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_FID, emissive: C_FID, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
  );
  _barFid.position.set(2.6, 0.5, 0);
  _barGroup.add(_barFid);
}

// =============================================================================
// live data handler
// =============================================================================
function _onKeyless(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.L          = typeof src.L                   === "number" ? src.L                   : null;
  S.d          = typeof src.d                   === "number" ? src.d                   : null;
  S.m          = typeof src.m                   === "number" ? src.m                   : null;
  S.bytesPer   = typeof src.bytes_per_entry     === "number" ? src.bytes_per_entry     : null;
  S.kvEntStd   = typeof src.kv_entries_standard === "number" ? src.kv_entries_standard : null;
  S.kvEntKey   = typeof src.kv_entries_keyless  === "number" ? src.kv_entries_keyless  : null;
  S.kvBytesStd = typeof src.kv_bytes_standard   === "number" ? src.kv_bytes_standard   : null;
  S.kvBytesKey = typeof src.kv_bytes_keyless    === "number" ? src.kv_bytes_keyless    : null;
  S.reduction  = typeof src.reduction_pct       === "number" ? src.reduction_pct       : null;
  S.cosMean    = typeof src.cosine_mean         === "number" ? src.cosine_mean         : null;
  S.cosMin     = typeof src.cosine_min          === "number" ? src.cosine_min          : null;
  S.mse        = typeof src.mse                 === "number" ? src.mse                 : null;

  S.scoresStd  = Array.isArray(src.scores_std_head)     ? src.scores_std_head     : null;
  S.scoresKey  = Array.isArray(src.scores_keyless_head) ? src.scores_keyless_head : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateHeatmaps();
  _updateBars();
}

// colour a heatmap grid from an attention map: base hue, |value| -> opacity.
// Near-zero -> grey.
function _paintHeat(arr, mat, baseColor) {
  const live = S.state === "live";
  const rows = (live && mat && mat.length) ? Math.min(mat.length, HEAT_MAX) : 0;
  const cols = (live && mat && mat[0]) ? Math.min(mat[0].length, HEAT_MAX) : 0;

  // find max for normalization (attention weights are in [0,1])
  let amax = 0.0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const v = Math.abs(mat[r][c]);
      if (v > amax) amax = v;
    }
  }
  if (amax <= 0.0) amax = 1.0;

  for (let r = 0; r < HEAT_MAX; r++) {
    for (let c = 0; c < HEAT_MAX; c++) {
      const mesh = arr[r * HEAT_MAX + c];
      if (!live || r >= rows || c >= cols) { mesh.visible = false; continue; }
      mesh.visible = true;
      const v = mat[r][c];
      const mag = Math.min(1.0, Math.abs(v) / amax);
      const color = mag < 0.04 ? C_ZERO : baseColor;
      mesh.material.color.setHex(color);
      mesh.material.opacity = 0.18 + 0.75 * mag;
    }
  }
}

function _updateHeatmaps() {
  _paintHeat(_heatStd,     S.scoresStd, C_STD);
  _paintHeat(_heatKeyless, S.scoresKey, C_KEYLESS);
}

// cache-size bars: height ∝ entry count (standard is exactly 2× keyless), so
// the 50% shrink is visible directly. Fidelity bar: height ∝ cosine_mean.
function _updateBars() {
  const live = S.state === "live";

  function setCacheBar(mesh, entries, refMax, color) {
    if (!mesh) return;
    if (!live || entries == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.05;
      mesh.position.y = 0.025;
      return;
    }
    const h = Math.max(0.08, (entries / (refMax || 1)) * 3.0);
    mesh.scale.y = h;
    mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.4;
    mesh.material.opacity = 0.92;
  }

  const refMax = (S.kvEntStd != null && S.kvEntStd > 0) ? S.kvEntStd : 1;
  setCacheBar(_barStd,     S.kvEntStd, refMax, C_STD);
  setCacheBar(_barKeyless, S.kvEntKey, refMax, C_KEYLESS);

  // fidelity bar — cosine_mean mapped from [-1,1] to a positive height
  if (_barFid) {
    if (!live || S.cosMean == null) {
      _barFid.material.color.setHex(C_DIM);
      _barFid.material.emissive.setHex(C_DIM);
      _barFid.material.opacity = 0.3;
      _barFid.scale.y = 0.05;
      _barFid.position.y = 0.025;
    } else {
      const h = Math.max(0.08, ((S.cosMean + 1.0) / 2.0) * 3.0);
      _barFid.scale.y = h;
      _barFid.position.y = h * 0.5;
      _barFid.material.color.setHex(C_FID);
      _barFid.material.emissive.setHex(C_FID);
      _barFid.material.emissiveIntensity = 0.4;
      _barFid.material.opacity = 0.92;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.12;
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "value-only cache", name: "kl" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'Keyless Attention <b>eliminates the key projection</b> entirely: a value-space <b>routing matrix R</b> ' +
      'replaces W<sub>k</sub>, so logits are formed as softmax((Q\u00b7R)\u00b7V\u1d40/\u221ad) and the decode ' +
      'cache stores <b>values only</b>. Standard QKV attention caches both K and V (2\u00b7L\u00b7d); keyless caches ' +
      'V alone (L\u00b7d) \u2014 an <b>exactly 50%</b> reduction. Panels: cache-size bars (standard vs keyless), ' +
      'attention-map heatmaps (standard vs keyless), and an output-fidelity bar (mean per-token cosine similarity ' +
      'between the two outputs). Honesty label <b>MODELED</b> (deterministic mechanism reproduction on a toy ' +
      'sequence; trains nothing). 0 runtime CDN.',
    citations:
      "Keyless Attention \u2014 Xin Gao, \u201cValue-Space Routing and Value-Only Caching for Efficient Transformers\u201d arXiv:2606.21848 (arxiv.org/abs/2606.21848). MODELED \u00b7 mechanism demo on a toy sequence, not a trained transformer.",
    plain: { html: _plainHtml },
  });

  _el["kl-dims"]      = _show.addField("sequence (L \u00d7 d)");
  _el["kl-m"]         = _show.addField("factorization depth m");
  _el["kl-entstd"]    = _show.addField("cache entries \u2014 STANDARD (K+V)");
  _el["kl-entkey"]    = _show.addField("cache entries \u2014 KEYLESS (V-only)");
  _el["kl-bytestd"]   = _show.addField("cache bytes \u2014 STANDARD");
  _el["kl-bytekey"]   = _show.addField("cache bytes \u2014 KEYLESS");
  _el["kl-reduction"] = _show.addField("KV-cache reduction");
  _el["kl-cosmean"]   = _show.addField("output fidelity \u2014 mean cosine (MEASURED)");
  _el["kl-cosmin"]    = _show.addField("output fidelity \u2014 min cosine");
  _el["kl-mse"]       = _show.addField("output MSE (standard vs keyless)");
  _el["kl-label"]     = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const red  = S.reduction != null ? S.reduction.toFixed(1) + "%" : "loading\u2026";
  const cos  = S.cosMean   != null ? S.cosMean.toFixed(3)         : "loading\u2026";
  const bs   = S.kvBytesStd != null ? S.kvBytesStd + " B"         : "loading\u2026";
  const bk   = S.kvBytesKey != null ? S.kvBytesKey + " B"         : "loading\u2026";
  return (
    "<b>What this means:</b> To generate text fast, a model keeps a running memory of every earlier word \u2014 " +
    "the \u201cKV cache.\u201d Normally it stores two things per word (a <b>key</b> and a <b>value</b>). Keyless " +
    "Attention throws away the key entirely and reroutes the lookup through the values themselves, so it only " +
    "stores <b>one</b> thing per word. That halves the memory: here from about <b>" + bs + "</b> down to <b>" +
    bk + "</b> \u2014 a <b>" + red + "</b> cut. On this small synthetic test the two methods produce outputs " +
    "that overlap with an average cosine similarity of about <b>" + cos + "</b>. This view is a <b>MODELED</b> " +
    "deterministic reproduction of that cache-halving MECHANISM on a tiny synthetic sequence \u2014 it <b>trains " +
    "no model</b> and runs no GPU kernel. The paper\u2019s headline that keyless matches or beats standard " +
    "attention on <b>real</b> models (GPT-2, Pythia, Qwen2, Llama 3.2) is a <b>claim about real training runs</b> " +
    "the estate does not independently verify.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("kl-dims",      t || ((S.L != null && S.d != null) ? (S.L + " \u00d7 " + S.d) : "\u2014"));
  _set("kl-m",         t || (S.m != null ? String(S.m) : "\u2014"));
  _set("kl-entstd",    t || (S.kvEntStd != null ? String(S.kvEntStd) : "\u2014"));
  _set("kl-entkey",    t || (S.kvEntKey != null ? String(S.kvEntKey) : "\u2014"));
  _set("kl-bytestd",   t || (S.kvBytesStd != null ? (S.kvBytesStd + " B") : "\u2014"));
  _set("kl-bytekey",   t || (S.kvBytesKey != null ? (S.kvBytesKey + " B") : "\u2014"));
  _set("kl-reduction", t || (S.reduction != null ? (S.reduction.toFixed(1) + "%") : "\u2014"));
  _set("kl-cosmean",   t || fx(S.cosMean, 4));
  _set("kl-cosmin",    t || fx(S.cosMin, 4));
  _set("kl-mse",       t || fx(S.mse, 4));
  // honesty label verbatim — never upgraded
  _set("kl-label",     t || (S.label || "MODELED"));
  if (_show) { _show.setChip("kl", S.label || "MODELED", { text: "value-only cache" }); _show.refreshPlain(); }
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
  _floor = null;
  _heatStd = []; _heatKeyless = []; _heatGroup = null;
  _barStd = null; _barKeyless = null; _barFid = null; _barGroup = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.L = S.d = S.m = null;
  S.bytesPer = S.kvEntStd = S.kvEntKey = S.kvBytesStd = S.kvBytesKey = null;
  S.reduction = S.cosMean = S.cosMin = S.mse = null;
  S.scoresStd = S.scoresKey = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
