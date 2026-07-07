// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/dla.js — DYNAMIC LINEAR ATTENTION (DLA) organ for the holographic
// frontier ring (Xin Wang et al., arXiv:2606.10650). Renders the multi-state
// memory dynamic-state-merging mechanism as three live panels:
//   (1) STATE-BOUNDARY RIBBON — the token sequence laid out along a line with
//       state-boundary markers for FIXED (importance-blind, evenly spaced) vs
//       DLA (information-aware, snapped to semantic transitions), and spikes
//       showing the per-token information-variation signal;
//   (2) ERROR-ACCUMULATION CURVES — two rising curves of cumulative
//       reconstruction error (fixed higher, DLA lower) over the sequence;
//   (3) METRIC BARS — cumulative error (fixed vs DLA) and transition
//       info-preserved-% (fixed vs DLA), the MEASURED headline numbers.
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/dla/attention. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors keyless.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   L, d, capacity, n_transitions, transition_positions[], states_fixed,
//   states_dla, err_accum_fixed, err_accum_dla, err_reduction_pct,
//   info_preserved_fixed, info_preserved_dla, err_curve_fixed[],
//   err_curve_dla[], boundaries_fixed[], boundaries_dla[], info_var_head[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real):
//   Dynamic Linear Attention — Xin Wang, Hui Shen, Boyuan Zheng, Xueshen Liu,
//     Minkyoung Cho, Zhongwei Wan, Zesen Zhao, Zhuoqing Mao, Shen Yan, Mi Zhang.
//     arXiv:2606.10650  https://arxiv.org/abs/2606.10650
//
// HONESTY LABELS: MODELED (deterministic reproduction of the information-aware
//   dynamic state-merging + capacity-bounded-memory MECHANISM on a toy synthetic
//   sequence; NOT a trained linear-attention model; trains nothing; the state
//   counts honour the capacity bound and the error/info metrics are MEASURED;
//   NEVER-CLAIMED-AS a production kernel). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "dla";
const TITLE = "Dynamic Linear Attention";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/dla/attention?seed=42&L=32&capacity=8";

// data-viz hues — purple BANNED
const C_FIXED = 0x5b8dee;  // lattice-blue (FIXED policy — bars / curve / boundaries)
const C_DLA   = 0x3af4c8;  // proof-teal   (DLA policy — bars / curve / boundaries)
const C_INFO  = 0x8a6bff;  // violet-blue  (information-variation spikes)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_TOK   = 0x5a6570;  // grey (token baseline dots)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const SEQ_W    = 8.0;    // sequence ribbon width along X
const CURVE_W  = 8.0;    // error-curve width along X
const BAR_W    = 0.7;    // metric-bar width
const MAX_PTS  = 16;     // cap points rendered (matches head trim)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _show = null;

// geometry handles
let _floor       = null;
let _seqGroup    = null;
let _tokDots     = [];    // Array<THREE.Mesh> — token baseline dots
let _infoSpikes  = [];    // Array<THREE.Mesh> — info-variation spikes
let _bndFixed    = [];    // Array<THREE.Mesh> — fixed boundary markers
let _bndDla      = [];    // Array<THREE.Mesh> — dla boundary markers
let _curveGroup  = null;
let _curveFixed  = [];    // Array<THREE.Mesh> — fixed error-curve segments
let _curveDla    = [];    // Array<THREE.Mesh> — dla error-curve segments
let _barGroup    = null;
let _barErrFixed = null;
let _barErrDla   = null;
let _barInfoFixed= null;
let _barInfoDla  = null;

// live state
const S = {
  label:      null,
  L:          null,
  d:          null,
  capacity:   null,
  nTrans:     null,   // n_transitions
  transPos:   null,   // transition_positions[]
  statesFixed:null,
  statesDla:  null,
  errFixed:   null,   // err_accum_fixed
  errDla:     null,   // err_accum_dla
  errRed:     null,   // err_reduction_pct
  infoFixed:  null,   // info_preserved_fixed
  infoDla:    null,   // info_preserved_dla
  curveFixed: null,   // err_curve_fixed[]
  curveDla:   null,   // err_curve_dla[]
  bndFixed:   null,   // boundaries_fixed[]
  bndDla:     null,   // boundaries_dla[]
  infoVar:    null,   // info_var_head[]
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSequence();
  _buildCurves();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onDla, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

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

// sequence ribbon: token dots along a line, info-variation spikes above each,
// and two rows of boundary markers (fixed | dla). Pre-allocate fixed pools.
function _buildSequence() {
  const THREE = _THREE;
  _seqGroup = new THREE.Group();
  _seqGroup.position.set(0, 0.05, -2.2);
  _group.add(_seqGroup);

  const dotGeo   = new THREE.SphereGeometry(0.07, 8, 8);
  const spikeGeo = new THREE.BoxGeometry(0.05, 1.0, 0.05);
  const bndGeo   = new THREE.BoxGeometry(0.06, 1.0, 0.28);

  for (let i = 0; i < MAX_PTS; i++) {
    const dot = new THREE.Mesh(dotGeo, new THREE.MeshStandardMaterial({ color: C_TOK, emissive: C_TOK, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }));
    dot.visible = false; _seqGroup.add(dot); _tokDots.push(dot);

    const sp = new THREE.Mesh(spikeGeo, new THREE.MeshStandardMaterial({ color: C_INFO, emissive: C_INFO, emissiveIntensity: 0.35, transparent: true, opacity: 0.0 }));
    sp.visible = false; _seqGroup.add(sp); _infoSpikes.push(sp);

    const bf = new THREE.Mesh(bndGeo, new THREE.MeshStandardMaterial({ color: C_FIXED, emissive: C_FIXED, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }));
    bf.visible = false; _seqGroup.add(bf); _bndFixed.push(bf);

    const bd = new THREE.Mesh(bndGeo, new THREE.MeshStandardMaterial({ color: C_DLA, emissive: C_DLA, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }));
    bd.visible = false; _seqGroup.add(bd); _bndDla.push(bd);
  }
}

// two error-accumulation curves rendered as chains of small box segments.
function _buildCurves() {
  const THREE = _THREE;
  _curveGroup = new THREE.Group();
  _curveGroup.position.set(0, 0.05, 2.4);
  _group.add(_curveGroup);
  const segGeo = new THREE.BoxGeometry(0.10, 0.10, 0.10);

  for (let i = 0; i < MAX_PTS; i++) {
    const sf = new THREE.Mesh(segGeo, new THREE.MeshStandardMaterial({ color: C_FIXED, emissive: C_FIXED, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }));
    sf.visible = false; _curveGroup.add(sf); _curveFixed.push(sf);

    const sd = new THREE.Mesh(segGeo, new THREE.MeshStandardMaterial({ color: C_DLA, emissive: C_DLA, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }));
    sd.visible = false; _curveGroup.add(sd); _curveDla.push(sd);
  }
}

function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(-4.6, 0, 0.0);
  _group.add(_barGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  _barErrFixed = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_FIXED, emissive: C_FIXED, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _barErrFixed.position.set(0, 0.5, 0); _barGroup.add(_barErrFixed);

  _barErrDla = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_DLA, emissive: C_DLA, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _barErrDla.position.set(0.95, 0.5, 0); _barGroup.add(_barErrDla);

  _barInfoFixed = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_FIXED, emissive: C_FIXED, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _barInfoFixed.position.set(2.1, 0.5, 0); _barGroup.add(_barInfoFixed);

  _barInfoDla = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: C_DLA, emissive: C_DLA, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }));
  _barInfoDla.position.set(3.05, 0.5, 0); _barGroup.add(_barInfoDla);
}

// =============================================================================
// live data handler
// =============================================================================
function _onDla(j) {
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.L           = typeof src.L                    === "number" ? src.L                    : null;
  S.d           = typeof src.d                    === "number" ? src.d                    : null;
  S.capacity    = typeof src.capacity             === "number" ? src.capacity             : null;
  S.nTrans      = typeof src.n_transitions        === "number" ? src.n_transitions        : null;
  S.statesFixed = typeof src.states_fixed         === "number" ? src.states_fixed         : null;
  S.statesDla   = typeof src.states_dla           === "number" ? src.states_dla           : null;
  S.errFixed    = typeof src.err_accum_fixed      === "number" ? src.err_accum_fixed      : null;
  S.errDla      = typeof src.err_accum_dla        === "number" ? src.err_accum_dla        : null;
  S.errRed      = typeof src.err_reduction_pct    === "number" ? src.err_reduction_pct    : null;
  S.infoFixed   = typeof src.info_preserved_fixed === "number" ? src.info_preserved_fixed : null;
  S.infoDla     = typeof src.info_preserved_dla   === "number" ? src.info_preserved_dla   : null;

  S.transPos   = Array.isArray(src.transition_positions) ? src.transition_positions : null;
  S.curveFixed = Array.isArray(src.err_curve_fixed)       ? src.err_curve_fixed       : null;
  S.curveDla   = Array.isArray(src.err_curve_dla)         ? src.err_curve_dla         : null;
  S.bndFixed   = Array.isArray(src.boundaries_fixed)      ? src.boundaries_fixed      : null;
  S.bndDla     = Array.isArray(src.boundaries_dla)        ? src.boundaries_dla        : null;
  S.infoVar    = Array.isArray(src.info_var_head)         ? src.info_var_head         : null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateSequence();
  _updateCurves();
  _updateBars();
}

function _hideAll(arr) { for (const m of arr) { m.visible = false; m.material.opacity = 0.0; } }

function _updateSequence() {
  const live = S.state === "live";
  const n = (live && S.infoVar) ? Math.min(S.infoVar.length, MAX_PTS) : 0;

  if (!n) { _hideAll(_tokDots); _hideAll(_infoSpikes); _hideAll(_bndFixed); _hideAll(_bndDla); return; }

  // normalize info-variation for spike heights
  let vmax = 0.0;
  for (let i = 0; i < n; i++) { const v = Math.abs(S.infoVar[i]); if (v > vmax) vmax = v; }
  if (vmax <= 0.0) vmax = 1.0;

  const step = SEQ_W / Math.max(1, n - 1);
  const x0 = -SEQ_W / 2;
  const bndFixedSet = new Set((S.bndFixed || []).filter((b) => b < n));
  const bndDlaSet   = new Set((S.bndDla   || []).filter((b) => b < n));

  for (let i = 0; i < MAX_PTS; i++) {
    const dot = _tokDots[i], sp = _infoSpikes[i], bf = _bndFixed[i], bd = _bndDla[i];
    if (i >= n) { dot.visible = sp.visible = bf.visible = bd.visible = false; continue; }
    const x = x0 + i * step;

    dot.visible = true; dot.material.opacity = 0.85;
    dot.position.set(x, 0.05, 0);

    const mag = Math.min(1.0, Math.abs(S.infoVar[i]) / vmax);
    const h = Math.max(0.03, mag * 2.2);
    sp.visible = true; sp.material.opacity = 0.25 + 0.7 * mag;
    sp.scale.y = h; sp.position.set(x, h * 0.5, 0);

    // fixed boundary markers (front row)
    if (bndFixedSet.has(i)) { bf.visible = true; bf.material.opacity = 0.9; bf.scale.y = 1.6; bf.position.set(x, 0.8, 0.55); }
    else { bf.visible = false; bf.material.opacity = 0.0; }

    // dla boundary markers (back row)
    if (bndDlaSet.has(i)) { bd.visible = true; bd.material.opacity = 0.9; bd.scale.y = 1.6; bd.position.set(x, 0.8, -0.55); }
    else { bd.visible = false; bd.material.opacity = 0.0; }
  }
}

// plot a cumulative-error curve as a chain of segments; height ∝ error.
function _plotCurve(arr, curve, refMax) {
  const live = S.state === "live";
  const n = (live && curve) ? Math.min(curve.length, MAX_PTS) : 0;
  if (!n) { _hideAll(arr); return; }
  const step = CURVE_W / Math.max(1, n - 1);
  const x0 = -CURVE_W / 2;
  for (let i = 0; i < MAX_PTS; i++) {
    const m = arr[i];
    if (i >= n) { m.visible = false; m.material.opacity = 0.0; continue; }
    const x = x0 + i * step;
    const h = (curve[i] / (refMax || 1)) * 3.0;
    m.visible = true; m.material.opacity = 0.92;
    m.position.set(x, Math.max(0.05, h), 0);
  }
}

function _updateCurves() {
  const live = S.state === "live";
  let refMax = 1.0;
  if (live && S.curveFixed && S.curveFixed.length) {
    refMax = S.curveFixed[S.curveFixed.length - 1] || 1.0;
    if (S.curveDla && S.curveDla.length) refMax = Math.max(refMax, S.curveDla[S.curveDla.length - 1] || 0);
  }
  _plotCurve(_curveFixed, S.curveFixed, refMax);
  _plotCurve(_curveDla,   S.curveDla,   refMax);
}

function _updateBars() {
  const live = S.state === "live";

  function setBar(mesh, val, refMax, color) {
    if (!mesh) return;
    if (!live || val == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.05; mesh.position.y = 0.025;
      return;
    }
    const h = Math.max(0.08, (val / (refMax || 1)) * 3.0);
    mesh.scale.y = h; mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.4;
    mesh.material.opacity = 0.92;
  }

  // error bars share a reference max (the larger of the two)
  const errRef = (live && S.errFixed != null) ? Math.max(S.errFixed, S.errDla || 0) : 1;
  setBar(_barErrFixed, S.errFixed, errRef, C_FIXED);
  setBar(_barErrDla,   S.errDla,   errRef, C_DLA);

  // info-preserved bars normalized to 100%
  setBar(_barInfoFixed, S.infoFixed, 100.0, C_FIXED);
  setBar(_barInfoDla,   S.infoDla,   100.0, C_DLA);
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
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,470px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Multi-state linear attention keeps a fixed-<b>capacity</b> memory of summarized token blocks. A <b>FIXED</b> ' +
    'policy merges states by importance-blind chunking (evenly spaced boundaries), blurring the few critical ' +
    '<b>transition</b> tokens and letting error <b>accumulate</b>. <b>DLA</b> uses <b>Information-Aware Dynamic ' +
    'State Merging</b> \u2014 boundaries snap to high information-variation transitions, stable runs are summarized ' +
    'aggressively \u2014 under the same <b>Capacity-Bounded Memory</b>. Panels: state-boundary ribbon (blue=fixed, ' +
    'teal=DLA, violet spikes=info variation), error-accumulation curves, and metric bars (cumulative error + ' +
    'transition info-preserved-%). Honesty label <b>MODELED</b> (deterministic mechanism reproduction on a toy ' +
    'sequence; trains nothing). 0 runtime CDN.';
  _overlay.appendChild(sub);

  const brow = document.createElement("div");
  brow.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  if (_badge && _badge.el) brow.appendChild(_badge.el);
  _overlay.appendChild(brow);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "dynamic linear attention \u00b7 dynamic state merging";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";

  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("dla-dims",     "sequence (L \u00d7 d)"));
  grid.appendChild(kpiRow("dla-cap",      "capacity bound"));
  grid.appendChild(kpiRow("dla-trans",    "high-importance transitions"));
  grid.appendChild(kpiRow("dla-sfixed",   "states \u2014 FIXED (bound)"));
  grid.appendChild(kpiRow("dla-sdla",     "states \u2014 DLA (bound)"));
  grid.appendChild(kpiRow("dla-errfixed", "error accumulation \u2014 FIXED"));
  grid.appendChild(kpiRow("dla-errdla",   "error accumulation \u2014 DLA"));
  grid.appendChild(kpiRow("dla-errred",   "error reduction (DLA vs fixed)"));
  grid.appendChild(kpiRow("dla-infofixed","info preserved @ transitions \u2014 FIXED"));
  grid.appendChild(kpiRow("dla-infodla",  "info preserved @ transitions \u2014 DLA"));
  grid.appendChild(kpiRow("dla-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Dynamic Linear Attention \u2014 Xin Wang et al., arXiv:2606.10650 (arxiv.org/abs/2606.10650). MODELED \u00b7 mechanism demo on a toy sequence, not a trained linear-attention model.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "dla-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  // Fold the legacy panel into the shared showcase overlay (surfaces/_showcase.js):
  // title + live badge + doctrine legend live in the always-visible chrome; the
  // descriptive text + KPI card become the collapsible body so the 3D scene is the star.
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    legend: true,
  });
  _overlay.style.position = "static";
  _overlay.style.left = _overlay.style.top = "auto";
  _overlay.style.maxWidth = "none";
  _overlay.style.font = "inherit";
  if (_overlay.firstChild) _overlay.removeChild(_overlay.firstChild); // drop duplicate title
  _show.body.appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const cap  = S.capacity  != null ? String(S.capacity)          : "loading\u2026";
  const red  = S.errRed    != null ? S.errRed.toFixed(1) + "%"    : "loading\u2026";
  const iF   = S.infoFixed != null ? S.infoFixed.toFixed(1) + "%" : "loading\u2026";
  const iD   = S.infoDla   != null ? S.infoDla.toFixed(1) + "%"   : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> To read very long text cheaply, this kind of model can\u2019t remember every word \u2014 " +
    "it keeps only a fixed number of \u201cmemory slots\u201d (here <b>" + cap + "</b>) that each summarize a stretch " +
    "of words. The question is which stretches to lump together. The old <b>fixed</b> way chops the text into equal " +
    "pieces regardless of content, so the rare <b>turning-point</b> words \u2014 where the meaning shifts \u2014 get " +
    "smeared into big blocks and the mistakes pile up. <b>DLA</b> instead puts its memory boundaries exactly at those " +
    "turning points and heavily compresses the calm, repetitive parts. Using the <b>same</b> number of memory slots, " +
    "DLA cuts the built-up error by about <b>" + red + "</b> and keeps <b>" + iD + "</b> of the turning-point detail " +
    "versus only <b>" + iF + "</b> for the fixed method. This view is a <b>MODELED</b> deterministic reproduction of " +
    "that boundary-choosing MECHANISM on a tiny synthetic sequence \u2014 it <b>trains no model</b> and runs no GPU " +
    "kernel. The paper\u2019s headline that DLA beats the state of the art across <b>16 real datasets</b> is a " +
    "<b>claim about real training runs</b> the estate does not independently verify.";
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
  _set("dla-dims",      t || ((S.L != null && S.d != null) ? (S.L + " \u00d7 " + S.d) : "\u2014"));
  _set("dla-cap",       t || (S.capacity != null ? String(S.capacity) : "\u2014"));
  _set("dla-trans",     t || (S.nTrans != null ? (S.nTrans + (S.transPos ? " @ [" + S.transPos.join(", ") + "]" : "")) : "\u2014"));
  _set("dla-sfixed",    t || (S.statesFixed != null ? String(S.statesFixed) : "\u2014"));
  _set("dla-sdla",      t || (S.statesDla != null ? String(S.statesDla) : "\u2014"));
  _set("dla-errfixed",  t || fx(S.errFixed, 3));
  _set("dla-errdla",    t || fx(S.errDla, 3));
  _set("dla-errred",    t || (S.errRed != null ? (S.errRed.toFixed(1) + "%") : "\u2014"));
  _set("dla-infofixed", t || (S.infoFixed != null ? (S.infoFixed.toFixed(2) + "%") : "\u2014"));
  _set("dla-infodla",   t || (S.infoDla != null ? (S.infoDla.toFixed(2) + "%") : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("dla-label",     t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
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
  _group = _overlay = _show = null;
  _floor = null;
  _seqGroup = null; _tokDots = []; _infoSpikes = []; _bndFixed = []; _bndDla = [];
  _curveGroup = null; _curveFixed = []; _curveDla = [];
  _barGroup = null; _barErrFixed = null; _barErrDla = null; _barInfoFixed = null; _barInfoDla = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.L = S.d = S.capacity = S.nTrans = null;
  S.transPos = null; S.statesFixed = S.statesDla = null;
  S.errFixed = S.errDla = S.errRed = S.infoFixed = S.infoDla = null;
  S.curveFixed = S.curveDla = S.bndFixed = S.bndDla = S.infoVar = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
