// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/inplacettt.js — IN-PLACE TEST-TIME TRAINING (InPlaceTTT) organ for
// the holographic frontier ring (Feng et al. 2026, ByteDance Seed + Peking
// University — "In-Place Test-Time Training", ICLR 2026 Oral). Renders a stock
// gated-MLP block whose EXISTING down-projection matrix W_down is re-purposed as
// FAST WEIGHTS (updated at inference time) while W_up and W_gate stay FROZEN as
// slow weights. A stream of token chunks flows past the block; a strictly-causal
// 1-D convolution builds the next-token-prediction target (no future leakage),
// and ONE gradient step per chunk mutates W_down. Two ribbons contrast the
// running next-token loss of the ADAPTING run (W_down mutates, proof-teal —
// FALLS) against the FROZEN-W_down control (lattice-blue — stays FLAT). A HUD
// reads the live snapshot at /api/killinchu/v1/inplacettt/adapt. Honesty label
// "MODELED" is read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// Surface export shape (mirrors titans.js / kla.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint, inside payload):
//   d_model, d_ff, vocab, chunk_size, num_chunks, learning_rate, freeze_up,
//   freeze_gate, fast_matrix, causal_kernel, causal_offsets, causal_guard_ok,
//   adapt_loss_start, adapt_loss_end, frozen_loss_start, frozen_loss_end,
//   adapt_loss_drop, frozen_loss_drop, improvement, loss_curve[], w_down_delta_norm
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   In-Place Test-Time Training (mechanism simulated here):
//     Feng, Luo, Hua, Zhang, He, Huang, Cai 2026, ByteDance Seed + Peking Univ,
//     arXiv:2604.06169 (ICLR 2026 Oral)
//     https://arxiv.org/abs/2604.06169
//   Official code:
//     https://github.com/ByteDance-Seed/In-Place-TTT
//
// DISTINCTNESS (scope-sensitive): vs titans (ADDS a separate memory module +
//   params, surprise-driven) — inplacettt ADDS NO PARAMETERS, hijacks the
//   existing W_down, and its update signal is an NTP-aligned loss. vs testtime
//   (spends more inference COMPUTE against FROZEN weights) — inplacettt MUTATES
//   weights (W_down is no longer frozen). Compute-allocation vs weight-mutation.
//
// HONESTY LABELS: MODELED (deterministic toy analytic simulation of the
//   down-projection-as-fast-weights / NTP-aligned / causal-chunk-update
//   mechanism; inspired-not-real; NOT the ByteDance model; toy 8-dim weights;
//   NO 128k-context / 4B-parameter claim). Read verbatim from JSON; never
//   upgraded here. The endpoint nests fields under `payload` and the label at
//   the top level — this surface handles the label at top-level OR inside
//   payload.label defensively.
// COLOURS: lattice-blue 0x5b8dee (frozen slow weights / frozen control / spine),
//   violet-blue 0x8a6bff (chunk stream / W_down fast-weight lattice), proof-teal
//   0x3af4c8 (adapting run / falling loss / HUD accent), greys (frozen-flat /
//   degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "inplacettt";
const TITLE = "In-Place Test-Time Training · W_down as Fast Weights (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the inplacettt organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/inplacettt/adapt?seed=42&chunk_size=16&learning_rate=0.2&num_chunks=24";

// data-viz hues — purple BANNED
const C_FROZEN = 0x5b8dee;  // lattice-blue (frozen slow weights / frozen control / spine)
const C_FAST   = 0x8a6bff;  // violet-blue (W_down fast-weight lattice / chunk stream)
const C_ADAPT  = 0x3af4c8;  // proof-teal (adapting run / falling loss / HUD accent)
const C_FLAT   = 0x5a6570;  // grey (flat frozen loss / low activity)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const FF_COLS     = 16;     // W_down columns rendered (d_ff fast-weight cells)
const DM_ROWS     = 8;      // W_down rows rendered (d_model)
const LATTICE_W   = 6.0;    // world-units the W_down lattice spans along X
const LATTICE_H   = 3.2;    // world-units the W_down lattice spans along Y
const MAX_CURVE   = 96;     // cap on loss-curve points rendered (== payload cap)
const CURVE_SPAN  = 12.0;   // world-units the loss ribbons span along X
const CURVE_Y     = 4.2;    // baseline height of the loss ribbons

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor      = null;
let _lattice    = [];                 // Array<THREE.Mesh> — W_down fast-weight cells
let _upBar      = null;               // THREE.Mesh — frozen W_up slab
let _gateBar    = null;               // THREE.Mesh — frozen W_gate slab
let _adaptLine  = null;               // THREE.Line — adapting-run loss ribbon
let _frozenLine = null;               // THREE.Line — frozen-control loss ribbon
let _core       = null;               // THREE.Mesh — central "improvement" core

// live state
const S = {
  label:        null,
  dModel:       null,   // d_model
  dFf:          null,   // d_ff
  vocab:        null,   // vocab
  chunkSize:    null,   // chunk_size
  numChunks:    null,   // num_chunks
  learningRate: null,   // learning_rate
  freezeUp:     null,   // freeze_up
  freezeGate:   null,   // freeze_gate
  fastMatrix:   null,   // fast_matrix
  causalKernel: null,   // causal_kernel[]
  causalGuard:  null,   // causal_guard_ok
  adaptStart:   null,   // adapt_loss_start
  adaptEnd:     null,   // adapt_loss_end
  frozenStart:  null,   // frozen_loss_start
  frozenEnd:    null,   // frozen_loss_end
  adaptDrop:    null,   // adapt_loss_drop
  frozenDrop:   null,   // frozen_loss_drop
  improvement:  null,   // improvement
  curve:        null,   // loss_curve[]
  deltaNorm:    null,   // w_down_delta_norm
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildFrozenSlabs();
  _buildLattice();
  _buildLossRibbons();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onAdapt, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Two FROZEN slow-weight slabs (W_up, W_gate) — rendered lattice-blue and held
// static: they never change colour or scale from live data (they are frozen).
function _buildFrozenSlabs() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(1.4, 2.4, 0.35);
  _upBar = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_FROZEN, emissive: C_FROZEN, emissiveIntensity: 0.14, transparent: true, opacity: 0.55 }),
  );
  _upBar.position.set(-4.8, 1.4, 0);
  _group.add(_upBar);

  _gateBar = new THREE.Mesh(
    geo,
    new THREE.MeshStandardMaterial({ color: C_FROZEN, emissive: C_FROZEN, emissiveIntensity: 0.14, transparent: true, opacity: 0.55 }),
  );
  _gateBar.position.set(-4.8, 1.4, -1.1);
  _group.add(_gateBar);
}

// The W_down FAST-WEIGHT lattice: a d_model x d_ff grid of cells. Pre-allocated;
// cell brightness/scale animate as W_down "adapts" (driven by w_down_delta_norm
// and the adapting-run loss drop). Violet-blue at rest, warms to proof-teal as
// the fast weights move.
function _buildLattice() {
  const THREE = _THREE;
  const cellGeo = new THREE.BoxGeometry(0.26, 0.26, 0.26);
  for (let r = 0; r < DM_ROWS; r++) {
    for (let c = 0; c < FF_COLS; c++) {
      const x = -LATTICE_W / 2 + (c / (FF_COLS - 1)) * LATTICE_W;
      const y = 0.6 + (r / (DM_ROWS - 1)) * LATTICE_H;
      const mesh = new THREE.Mesh(
        cellGeo,
        new THREE.MeshStandardMaterial({ color: C_FAST, emissive: C_FAST, emissiveIntensity: 0.18, transparent: true, opacity: 0.0 }),
      );
      mesh.position.set(x, y, 1.4);
      mesh.visible = false;
      _group.add(mesh);
      _lattice.push(mesh);
    }
  }
}

// Two loss ribbons over the chunk axis: adapting (proof-teal, should FALL) and
// frozen control (grey/lattice-blue, should stay FLAT). Pre-allocated as Lines
// with MAX_CURVE points; positions rewritten in-place from live loss_curve.
function _buildLossRibbons() {
  const THREE = _THREE;

  function mkLine(color) {
    const pts = [];
    for (let i = 0; i < MAX_CURVE; i++) {
      const x = -CURVE_SPAN / 2 + (i / (MAX_CURVE - 1)) * CURVE_SPAN;
      pts.push(new THREE.Vector3(x, CURVE_Y, -3.0));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.85 });
    const line = new THREE.Line(geo, mat);
    line.visible = false;
    _group.add(line);
    return line;
  }

  _adaptLine  = mkLine(C_ADAPT);
  _frozenLine = mkLine(C_FLAT);
}

function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.7, 1),
    new THREE.MeshStandardMaterial({ color: C_ADAPT, emissive: C_ADAPT, emissiveIntensity: 0.45, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, 0.6, 0);
  _group.add(_core);
}

// =============================================================================
// live data handler
// =============================================================================
function _onAdapt(j) {
  // The endpoint nests its metrics under `payload`; the honesty label may sit
  // at the TOP LEVEL or (defensively) inside payload.label. Read it VERBATIM
  // from wherever it is — never upgrade.
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label        = String(rawLabel).toUpperCase();

  S.dModel       = typeof p.d_model           === "number" ? p.d_model           : null;
  S.dFf          = typeof p.d_ff              === "number" ? p.d_ff              : null;
  S.vocab        = typeof p.vocab             === "number" ? p.vocab             : null;
  S.chunkSize    = typeof p.chunk_size        === "number" ? p.chunk_size        : null;
  S.numChunks    = typeof p.num_chunks        === "number" ? p.num_chunks        : null;
  S.learningRate = typeof p.learning_rate     === "number" ? p.learning_rate     : null;
  S.freezeUp     = typeof p.freeze_up         === "boolean" ? p.freeze_up        : null;
  S.freezeGate   = typeof p.freeze_gate       === "boolean" ? p.freeze_gate      : null;
  S.fastMatrix   = typeof p.fast_matrix       === "string"  ? p.fast_matrix      : null;
  S.causalKernel = Array.isArray(p.causal_kernel)          ? p.causal_kernel     : null;
  S.causalGuard  = typeof p.causal_guard_ok   === "boolean" ? p.causal_guard_ok  : null;
  S.adaptStart   = typeof p.adapt_loss_start  === "number" ? p.adapt_loss_start  : null;
  S.adaptEnd     = typeof p.adapt_loss_end    === "number" ? p.adapt_loss_end    : null;
  S.frozenStart  = typeof p.frozen_loss_start === "number" ? p.frozen_loss_start : null;
  S.frozenEnd    = typeof p.frozen_loss_end   === "number" ? p.frozen_loss_end   : null;
  S.adaptDrop    = typeof p.adapt_loss_drop   === "number" ? p.adapt_loss_drop   : null;
  S.frozenDrop   = typeof p.frozen_loss_drop  === "number" ? p.frozen_loss_drop  : null;
  S.improvement  = typeof p.improvement       === "number" ? p.improvement       : null;
  S.curve        = Array.isArray(p.loss_curve)             ? p.loss_curve        : null;
  S.deltaNorm    = typeof p.w_down_delta_norm === "number" ? p.w_down_delta_norm : null;

  _updateGeometry();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the lattice + ribbons from live data
// =============================================================================
function _updateGeometry() {
  const live = S.state === "live";

  // frozen slow-weight slabs: always lattice-blue when live, grey when not —
  // and NEVER animated (they are frozen; that is the point).
  [_upBar, _gateBar].forEach((bar) => {
    if (!bar) return;
    const col = live ? C_FROZEN : C_DIM;
    bar.material.color.setHex(col);
    bar.material.emissive.setHex(col);
    bar.material.opacity = live ? 0.55 : 0.22;
  });

  // W_down fast-weight lattice: activity scales with the total weight movement
  // (w_down_delta_norm) and the adapting-run loss drop. Cells warm from
  // violet-blue toward proof-teal as the fast weights adapt.
  const delta = live && S.deltaNorm != null ? S.deltaNorm : 0;
  const drop  = live && S.adaptDrop != null ? Math.max(0, S.adaptDrop) : 0;
  const warm  = Math.min(1, drop * 60);          // how "teal" (adapted) the lattice looks
  const act   = Math.min(1, delta / 2.0);        // overall movement intensity
  for (let i = 0; i < _lattice.length; i++) {
    const mesh = _lattice[i];
    if (!live) { mesh.visible = false; continue; }
    mesh.visible = true;
    // deterministic per-cell phase so the lattice shimmers coherently
    const adapted = ((i * 2654435761) % 1000) / 1000 < warm;
    const col = adapted ? C_ADAPT : C_FAST;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = 0.18 + 0.5 * act + (adapted ? 0.25 : 0);
    mesh.material.opacity = 0.35 + 0.5 * act;
    mesh.scale.setScalar(0.8 + 0.5 * act + (adapted ? 0.25 : 0));
  }

  // loss ribbons: map the live loss_curve onto the two Lines. Adapting should
  // slope DOWN; frozen should be FLAT. We normalise both against a shared range.
  const curve = live && S.curve && S.curve.length ? S.curve.slice(0, MAX_CURVE) : [];
  if (curve.length && _adaptLine && _frozenLine) {
    let lo = Infinity, hi = -Infinity;
    for (const c of curve) {
      const a = typeof c.adapt_loss === "number" ? c.adapt_loss : 0;
      const f = typeof c.frozen_loss === "number" ? c.frozen_loss : 0;
      lo = Math.min(lo, a, f); hi = Math.max(hi, a, f);
    }
    const rng = hi - lo || 1;
    _writeRibbon(_adaptLine, curve, "adapt_loss", lo, rng, -2.6);
    _writeRibbon(_frozenLine, curve, "frozen_loss", lo, rng, -3.4);
    _adaptLine.visible = true;
    _frozenLine.visible = true;
    _adaptLine.material.color.setHex(C_ADAPT);
    _frozenLine.material.color.setHex(C_FLAT);
  } else {
    if (_adaptLine) _adaptLine.visible = false;
    if (_frozenLine) _frozenLine.visible = false;
  }

  // central core: size/colour reflect the adapting advantage (improvement)
  if (_core) {
    if (live && S.improvement != null) {
      _core.material.color.setHex(C_ADAPT);
      _core.material.emissive.setHex(C_ADAPT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.8 + Math.max(0, S.improvement) * 40);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.8);
    }
  }
}

function _writeRibbon(line, curve, key, lo, rng, z) {
  const pos = line.geometry.attributes.position;
  const n = Math.min(curve.length, MAX_CURVE);
  for (let i = 0; i < MAX_CURVE; i++) {
    const src = i < n ? curve[i] : curve[n - 1];
    const v = src && typeof src[key] === "number" ? src[key] : lo;
    const norm = (v - lo) / rng;                 // 0 (best) .. 1 (worst)
    const x = -CURVE_SPAN / 2 + (i / (MAX_CURVE - 1)) * CURVE_SPAN;
    const y = CURVE_Y + (1 - norm) * 2.2;        // lower loss -> higher ribbon
    pos.setXYZ(i, x, y, z);
  }
  pos.needsUpdate = true;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.14;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.009;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.improvement != null) ? (0.8 + Math.max(0, S.improvement) * 40) : 0.8;
    _core.scale.setScalar(base * pulse);
  }
  // gentle shimmer on the fast-weight lattice (the weights are "moving")
  if (_lattice.length && S.state === "live") {
    const a = 0.5 + 0.5 * Math.sin(t * 0.002);
    for (let i = 0; i < _lattice.length; i += 7) {
      const m = _lattice[i];
      if (m && m.visible) m.material.emissiveIntensity = 0.2 + 0.4 * a;
    }
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "in-place test-time training", name: "hl" }],
    legend: ["MODELED"],
    description:
      'Test-time adaptation with <b>no new module</b>: a stock MLP block\u2019s existing ' +
      '<b>down-projection W_down</b> is re-purposed as <b>fast weights</b> (updated at inference), ' +
      'while <b>W_up / W_gate stay frozen</b>. The update target is built by a <b>strictly-causal</b> ' +
      '1-D convolution over past tokens (no future leakage), and one gradient step runs <b>per chunk</b>. ' +
      'The <b>adapting</b> run\u2019s next-token loss <b>falls</b>; the <b>frozen-W_down control</b> stays <b>flat</b>. ' +
      'Honesty label <b>MODELED</b> (inspired-not-real toy simulation; NOT the ByteDance model). 0 runtime CDN.',
    citations:
      "Feng et al. 2026 (ByteDance Seed + Peking Univ) \u00b7 In-Place Test-Time Training \u00b7 arXiv:2604.06169 (ICLR 2026 Oral) \u00b7 github.com/ByteDance-Seed/In-Place-TTT. MODELED \u00b7 inspired-not-real \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["ip-fast"]    = _show.addField("fast weights (mutated)");
  _el["ip-frozen"]  = _show.addField("frozen slow weights");
  _el["ip-chunks"]  = _show.addField("chunks \u00d7 chunk_size");
  _el["ip-lr"]      = _show.addField("learning_rate (per chunk)");
  _el["ip-causal"]  = _show.addField("causal guard (no future leak)");
  _el["ip-adapt"]   = _show.addField("adapt loss (start \u2192 end) \u2014 MODELED");
  _el["ip-frozenl"] = _show.addField("frozen-control loss (flat)");
  _el["ip-improve"] = _show.addField("improvement (adapting advantage)");
  _el["ip-delta"]   = _show.addField("W_down movement (L1)");
  _el["ip-label"]   = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const chunks = S.numChunks   != null ? String(S.numChunks) : "loading\u2026";
  const aS = S.adaptStart != null ? S.adaptStart.toFixed(4) : "loading\u2026";
  const aE = S.adaptEnd   != null ? S.adaptEnd.toFixed(4)   : "loading\u2026";
  const fE = S.frozenEnd  != null ? S.frozenEnd.toFixed(4)  : "loading\u2026";
  return (
    "<b>What this means:</b> Normally an AI model\u2019s weights are <b>frozen</b> once training ends \u2014 " +
    "it can\u2019t learn anything new while it answers you. In-Place Test-Time Training lets the model " +
    "keep learning <i>as it reads</i>, <b>without bolting on any new part</b>: it quietly re-uses one " +
    "matrix it already has (the <b>down-projection W_down</b>) as a scratchpad it\u2019s allowed to nudge, " +
    "while the rest of the block stays fixed. To decide how to nudge it, the model looks only at what " +
    "it has <b>already seen</b> (a strict <b>no-peeking-at-the-future</b> rule) and takes one small step " +
    "per chunk of text. Over <b>" + chunks + "</b> chunks its next-word error <b>drops from " + aS + " to " + aE + "</b>, " +
    "while an identical copy whose W_down is <b>kept frozen</b> stays flat at <b>" + fE + "</b>. " +
    "<br><br><b>Inspired-not-real:</b> this view is a <b>MODELED</b> toy simulation of that mechanism " +
    "\u2014 random toy weights, an 8-dimension hidden state and a tiny synthetic sequence. It is <b>NOT the " +
    "ByteDance model</b> and does <b>NOT</b> reproduce the paper\u2019s 128k-context or 4B-parameter results; " +
    "the loss drop is a qualitative demonstration on a controlled stream, not a benchmark claim. " +
    "(Different from <b>titans</b>, which adds a whole new memory module, and from <b>testtime</b>, which " +
    "just spends more compute without changing any weights \u2014 here an existing weight actually moves.)");
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
  _set("ip-fast",   t || (S.fastMatrix ? S.fastMatrix + " (fast)" : "W_down (fast)"));
  _set("ip-frozen", t || ((S.freezeUp || S.freezeGate) ? "W_up + W_gate \u2014 frozen" : "\u2014"));
  _set("ip-chunks", t || (S.numChunks != null && S.chunkSize != null ? S.numChunks + " \u00d7 " + S.chunkSize : "\u2014"));
  _set("ip-lr",     t || fx(S.learningRate, 3));
  _set("ip-causal", t || (S.causalGuard === true ? "OK \u2014 past-only" : (S.causalGuard === false ? "VIOLATION" : "\u2014")));
  _set("ip-adapt",  t || (S.adaptStart != null && S.adaptEnd != null
        ? fx(S.adaptStart, 4) + " \u2192 " + fx(S.adaptEnd, 4)
        : "\u2014"));
  _set("ip-frozenl", t || (S.frozenEnd != null
        ? fx(S.frozenEnd, 4) + (S.frozenDrop != null ? " (\u0394 " + fx(S.frozenDrop, 4) + ")" : "")
        : "\u2014"));
  _set("ip-improve", t || (S.improvement != null ? "+" + fx(S.improvement, 4) : "\u2014"));
  _set("ip-delta",  t || fx(S.deltaNorm, 3));
  // honesty label verbatim — never upgraded
  _set("ip-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("hl", S.label || "MODELED", { text: "in-place test-time training" }); _show.refreshPlain(); }
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
  _floor = null; _lattice = []; _upBar = null; _gateBar = null;
  _adaptLine = null; _frozenLine = null; _core = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.dModel = S.dFf = S.vocab = null;
  S.chunkSize = S.numChunks = S.learningRate = null;
  S.freezeUp = S.freezeGate = S.fastMatrix = S.causalKernel = S.causalGuard = null;
  S.adaptStart = S.adaptEnd = S.frozenStart = S.frozenEnd = null;
  S.adaptDrop = S.frozenDrop = S.improvement = S.curve = S.deltaNorm = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
