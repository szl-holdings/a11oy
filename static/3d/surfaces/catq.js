// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/catq.js — POST-TRAINING CALIBRATION TERNARY QUANT (CAT-Q) organ for
// the holographic frontier ring. A SUB-ORGAN UPGRADE of the `ternary` organ:
// same weight-precision axis {-1,0,+1}, distinct PTQ-vs-QAT mechanism. Renders
// a 3D weight-magnitude histogram of a frozen synthetic heavy-tailed weight
// vector, with the ABSMEAN hard-snap threshold and the CAT-Q LEARNED threshold
// drawn as gates; bars are coloured by the ternary code each rule assigns
// (+1 -> add proof-teal, -1 -> subtract lattice-blue, 0 -> skip grey). A HUD
// shows the MEASURED reconstruction / calibration-task error, absmean vs CAT-Q,
// from the live snapshot at /api/killinchu/v1/catq/calibrate. Honesty label
// "MODELED" is read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// Surface export shape (mirrors ternary.js / aimc.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   num_weights, num_calibration_samples, modulation_groups, softening_steps,
//   absmean_threshold, catq_threshold_frac, ternary_counts_absmean{neg,zero,pos},
//   ternary_counts_catq{neg,zero,pos}, recon_err_absmean, recon_err_catq,
//   recon_err_improvement_frac, calib_task_err_absmean, calib_task_err_catq,
//   error_vs_calibration[{n,task_err}], bits_per_weight_ternary
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFIED real):
//   CAT-Q: Cost-efficient and Accurate Ternary Quantization for LLMs
//     Wang, Li, Kang, Fan, Yao (2026). arXiv:2606.26650
//     https://arxiv.org/abs/2606.26650
//
// HONESTY LABEL: MODELED — toy analytic sim of the post-training calibration-
//   ternarization MECHANISM, not CAT-Q. Seeded synthetic heavy-tailed weights,
//   seeded toy activations, a tiny closed-form/least-squares "learnable
//   modulation" + fixed tanh-anneal "softened ternarization"; NO real LLM, NO
//   BitTern code, NO 512-sample calibration of a 1.7B–235B model, NO GPU-hours.
//   Explicitly a SUB-ORGAN UPGRADE of ternary (same weight-precision axis,
//   distinct PTQ-vs-QAT mechanism), not a new axis. Read verbatim from JSON.
// COLOURS: proof-teal 0x3af4c8 (+1 -> add), lattice-blue 0x5b8dee (-1 ->
//   subtract), violet-blue 0x8a6bff (learned-threshold / calibration accent),
//   greys (0 -> skip / degraded). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "catq";
const TITLE = "Post-Training Calibration Ternary Quant · CAT-Q (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/catq/calibrate?seed=42&num_weights=256&num_calibration_samples=512&mode=catq";

// data-viz hues — purple BANNED
const C_POS      = 0x3af4c8;  // proof-teal (+1 weight -> add)
const C_NEG      = 0x5b8dee;  // lattice-blue (-1 weight -> subtract)
const C_LEARNED  = 0x8a6bff;  // violet-blue (learned-threshold / calibration accent)
const C_ZERO     = 0x5a6570;  // grey (0 weight -> skip / structured sparsity)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// histogram layout geometry
const N_BINS     = 24;     // magnitude bins per side of the histogram
const BIN_GAP    = 0.42;   // world-units between bins
const MAX_H      = 4.0;    // max bar height (world units)
const ROW_ABS    = 0.0;    // z-row for the ABSMEAN (before) histogram
const ROW_CATQ   = 3.2;    // z-row for the CAT-Q (after) histogram

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _show = null;

// geometry handles
let _floor     = null;
let _barsAbs   = [];   // Array<THREE.Mesh> — absmean (before) histogram bars
let _barsCatq  = [];   // Array<THREE.Mesh> — CAT-Q (after) histogram bars
let _gateAbs   = null; // THREE.Mesh — absmean hard threshold gate
let _gateCatq  = null; // THREE.Mesh — CAT-Q learned threshold gate

// live state
const S = {
  label:            null,
  numWeights:       null,
  numCalib:         null,
  modGroups:        null,
  softSteps:        null,
  absmeanThresh:    null,   // absmean_threshold
  catqThreshFrac:   null,   // catq_threshold_frac
  absNeg:           null, absZero: null, absPos: null,   // ternary_counts_absmean
  catqNeg:          null, catqZero: null, catqPos: null, // ternary_counts_catq
  reconErrAbs:      null,   // recon_err_absmean (MEASURED)
  reconErrCatq:     null,   // recon_err_catq (MEASURED)
  reconImprovFrac:  null,   // recon_err_improvement_frac
  taskErrAbs:       null,   // calib_task_err_absmean (MEASURED)
  taskErrCatq:      null,   // calib_task_err_catq (MEASURED)
  bitsPerWeight:    null,   // bits_per_weight_ternary
  curve:            null,   // error_vs_calibration [{n, task_err}]
  state:            "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 8, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(5, 1, 1.5); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHistograms();
  _buildGates();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onCatq, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Two rows of magnitude-histogram bars: the "before" (absmean hard-snap) row and
// the "after" (CAT-Q learned-threshold + calibrated modulation) row. We toggle
// height / colour in-place as live data arrives (no per-poll geometry churn).
function _buildHistograms() {
  const THREE = _THREE;
  const barGeo = new THREE.BoxGeometry(0.28, 1.0, 0.28);
  for (let b = 0; b < N_BINS; b++) {
    const mAbs = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_ZERO, emissive: C_ZERO, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mAbs.position.set(b * BIN_GAP, 0.5, ROW_ABS);
    mAbs.visible = false;
    _group.add(mAbs);
    _barsAbs.push(mAbs);

    const mCatq = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_ZERO, emissive: C_ZERO, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    mCatq.position.set(b * BIN_GAP, 0.5, ROW_CATQ);
    mCatq.visible = false;
    _group.add(mCatq);
    _barsCatq.push(mCatq);
  }
}

// Threshold "gates": thin planes marking the absmean hard threshold (before row)
// and the CAT-Q learned threshold (after row). Bins to the left of the gate
// ternarize to 0 (skip); bins to the right ternarize to ±1.
function _buildGates() {
  const THREE = _THREE;
  const gateGeo = new THREE.BoxGeometry(0.06, MAX_H, 0.9);
  _gateAbs = new THREE.Mesh(
    gateGeo,
    new THREE.MeshStandardMaterial({ color: C_ZERO, emissive: C_ZERO, emissiveIntensity: 0.4, transparent: true, opacity: 0.0 }),
  );
  _gateAbs.position.set(0, MAX_H / 2, ROW_ABS);
  _gateAbs.visible = false;
  _group.add(_gateAbs);

  _gateCatq = new THREE.Mesh(
    gateGeo,
    new THREE.MeshStandardMaterial({ color: C_LEARNED, emissive: C_LEARNED, emissiveIntensity: 0.55, transparent: true, opacity: 0.0 }),
  );
  _gateCatq.position.set(0, MAX_H / 2, ROW_CATQ);
  _gateCatq.visible = false;
  _group.add(_gateCatq);
}

// =============================================================================
// live data handler
// =============================================================================
function _onCatq(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label           = String(lbl).toUpperCase();

  S.numWeights      = typeof src.num_weights                === "number" ? src.num_weights                : null;
  S.numCalib        = typeof src.num_calibration_samples    === "number" ? src.num_calibration_samples    : null;
  S.modGroups       = typeof src.modulation_groups          === "number" ? src.modulation_groups          : null;
  S.softSteps       = typeof src.softening_steps            === "number" ? src.softening_steps            : null;
  S.absmeanThresh   = typeof src.absmean_threshold          === "number" ? src.absmean_threshold          : null;
  S.catqThreshFrac  = typeof src.catq_threshold_frac        === "number" ? src.catq_threshold_frac        : null;
  S.reconErrAbs     = typeof src.recon_err_absmean          === "number" ? src.recon_err_absmean          : null;
  S.reconErrCatq    = typeof src.recon_err_catq             === "number" ? src.recon_err_catq             : null;
  S.reconImprovFrac = typeof src.recon_err_improvement_frac === "number" ? src.recon_err_improvement_frac : null;
  S.taskErrAbs      = typeof src.calib_task_err_absmean     === "number" ? src.calib_task_err_absmean     : null;
  S.taskErrCatq     = typeof src.calib_task_err_catq        === "number" ? src.calib_task_err_catq        : null;
  S.bitsPerWeight   = typeof src.bits_per_weight_ternary    === "number" ? src.bits_per_weight_ternary    : null;
  S.curve           = Array.isArray(src.error_vs_calibration) ? src.error_vs_calibration : null;

  if (src.ternary_counts_absmean && typeof src.ternary_counts_absmean === "object") {
    S.absNeg  = typeof src.ternary_counts_absmean.neg  === "number" ? src.ternary_counts_absmean.neg  : null;
    S.absZero = typeof src.ternary_counts_absmean.zero === "number" ? src.ternary_counts_absmean.zero : null;
    S.absPos  = typeof src.ternary_counts_absmean.pos  === "number" ? src.ternary_counts_absmean.pos  : null;
  }
  if (src.ternary_counts_catq && typeof src.ternary_counts_catq === "object") {
    S.catqNeg  = typeof src.ternary_counts_catq.neg  === "number" ? src.ternary_counts_catq.neg  : null;
    S.catqZero = typeof src.ternary_counts_catq.zero === "number" ? src.ternary_counts_catq.zero : null;
    S.catqPos  = typeof src.ternary_counts_catq.pos  === "number" ? src.ternary_counts_catq.pos  : null;
  }

  _updateHistograms();
  _paintOverlay();
}

// =============================================================================
// geometry updater — draws the before/after magnitude histograms + gates
// =============================================================================
// Deterministic per-bin heavy-tailed magnitude profile (LCG family, mirrors the
// module) so the histogram shape is stable across polls and never fabricated
// beyond a heavy-tailed envelope: most mass near zero, a light tail out to the
// right (the pretrained-weight outliers). This is a VISUAL proxy for the
// reported distribution — the numeric metrics come only from the live JSON.
function _binMass(b) {
  // heavy-tailed-ish falloff with a small deterministic ripple
  let s = ((b + 1) * 2654435761) >>> 0;
  s = (1664525 * s + 1013904223) >>> 0;
  const ripple = 0.12 * ((s / 4294967295) - 0.5);
  const x = b / (N_BINS - 1);
  const env = Math.exp(-3.1 * x) + 0.05 * Math.exp(-0.6 * (1.0 - x)); // bulk + tail
  return Math.max(0.02, env + ripple);
}

function _updateHistograms() {
  const live = S.state === "live";

  // gate bin positions from live thresholds (normalized to the bin axis).
  // absmean threshold in weight-units -> map through a nominal magnitude span;
  // CAT-Q learned threshold = catq_threshold_frac * (absmean_threshold/0.5)
  // since absmean_threshold = 0.5*beta => beta = absmean_threshold/0.5.
  const beta = (S.absmeanThresh != null) ? (S.absmeanThresh / 0.5) : 1.0;
  const span = Math.max(1e-6, 3.0 * beta);                 // nominal |w| axis span
  const absBin  = live && S.absmeanThresh  != null ? Math.min(N_BINS - 1, (S.absmeanThresh / span) * N_BINS) : 0;
  const catqThr = (S.catqThreshFrac != null) ? S.catqThreshFrac * beta : null;
  const catqBin = live && catqThr != null ? Math.min(N_BINS - 1, (catqThr / span) * N_BINS) : 0;

  for (let b = 0; b < N_BINS; b++) {
    const mass = _binMass(b);
    const h = MAX_H * mass;

    _updateBar(_barsAbs[b],  b, h, live, absBin,  false);
    _updateBar(_barsCatq[b], b, h, live, catqBin, true);
  }

  _placeGate(_gateAbs,  absBin,  ROW_ABS,  C_ZERO,    live);
  _placeGate(_gateCatq, catqBin, ROW_CATQ, C_LEARNED, live);
}

function _updateBar(mesh, b, h, live, gateBin, isCatq) {
  if (!mesh) return;
  if (!live) { mesh.visible = false; return; }
  mesh.visible = true;
  mesh.scale.y = Math.max(0.04, h);
  mesh.position.y = mesh.scale.y * 0.5;
  // bins beyond the (soft/hard) threshold ternarize to ±1; below -> 0 (skip).
  let color;
  if (b < gateBin) {
    color = C_ZERO;                              // 0 -> skip (grey)
  } else {
    color = (b % 2 === 0) ? C_POS : C_NEG;       // ±1 -> add / subtract
  }
  mesh.material.color.setHex(color);
  mesh.material.emissive.setHex(color);
  mesh.material.emissiveIntensity = (b < gateBin) ? 0.14 : (isCatq ? 0.6 : 0.42);
  mesh.material.opacity = (b < gateBin) ? 0.32 : 0.95;
}

function _placeGate(gate, bin, row, litColor, live) {
  if (!gate) return;
  if (!live) { gate.visible = false; return; }
  gate.visible = true;
  gate.position.set(bin * BIN_GAP - BIN_GAP * 0.5, MAX_H / 2, row);
  gate.material.color.setHex(litColor);
  gate.material.emissive.setHex(litColor);
  gate.material.opacity = 0.5;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  if (_gateCatq && _gateCatq.visible) {
    const pulse = 0.5 + 0.18 * Math.sin(t * 0.004);
    _gateCatq.material.opacity = pulse;
  }
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
    'A <b>SUB-ORGAN UPGRADE of ternary</b> (same weight-precision axis {\u22121,0,+1}, distinct PTQ-vs-QAT ' +
    'mechanism). Instead of training a ternary model from scratch, <b>CAT-Q</b> ternarizes an already-' +
    'pretrained model <b>post-training</b> from a small calibration set. Two components: <b>learnable ' +
    'modulation</b> (a closed-form least-squares fit reshapes the per-group scale + threshold) and ' +
    '<b>softened ternarization</b> (a tanh-anneal transition instead of a hard snap). The two histograms ' +
    'show the same frozen weights ternarized by the <b>absmean hard threshold</b> (before) vs the ' +
    '<b>CAT-Q learned threshold</b> (after). HUD reports MEASURED reconstruction / calibration-task error, ' +
    'absmean vs CAT-Q. Honesty label <b>MODELED</b>. 0 runtime CDN.';
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
  nm.textContent = "post-training calibration ternary quant (cat-q)";
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

  grid.appendChild(kpiRow("cq-weights",   "frozen weights (heavy-tailed)"));
  grid.appendChild(kpiRow("cq-calib",     "calibration samples"));
  grid.appendChild(kpiRow("cq-groups",    "modulation groups (LM)"));
  grid.appendChild(kpiRow("cq-steps",     "softening steps (ST, tanh-anneal)"));
  grid.appendChild(kpiRow("cq-absthr",    "absmean hard threshold"));
  grid.appendChild(kpiRow("cq-catqthr",   "CAT-Q learned threshold frac"));
  grid.appendChild(kpiRow("cq-absmix",    "absmean mix (\u22121 / 0 / +1)"));
  grid.appendChild(kpiRow("cq-catqmix",   "CAT-Q mix (\u22121 / 0 / +1)"));
  grid.appendChild(kpiRow("cq-reconabs",  "recon err \u2014 absmean (MEASURED)"));
  grid.appendChild(kpiRow("cq-reconcatq", "recon err \u2014 CAT-Q (MEASURED)"));
  grid.appendChild(kpiRow("cq-reconimp",  "recon err REDUCED by CAT-Q"));
  grid.appendChild(kpiRow("cq-taskabs",   "calib-task err \u2014 absmean"));
  grid.appendChild(kpiRow("cq-taskcatq",  "calib-task err \u2014 CAT-Q"));
  grid.appendChild(kpiRow("cq-curve",     "task err vs calib (first \u2192 last)"));
  grid.appendChild(kpiRow("cq-bpw",       "bits/weight (ternary) \u2014 MODELED"));
  grid.appendChild(kpiRow("cq-label",     "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "CAT-Q \u2014 Wang, Li, Kang, Fan, Yao (2026) arXiv:2606.26650. SUB-ORGAN UPGRADE of ternary (same weight-precision axis, distinct PTQ-vs-QAT mechanism). MODELED \u00b7 not claimed-as.";
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
  pd.id = "cq-plain";
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
  const impPct = S.reconImprovFrac != null ? (S.reconImprovFrac * 100).toFixed(1) + "%" : "loading\u2026";
  const abs    = S.reconErrAbs     != null ? (S.reconErrAbs * 100).toFixed(1) + "%"    : "loading\u2026";
  const cq     = S.reconErrCatq    != null ? (S.reconErrCatq * 100).toFixed(1) + "%"   : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Squeezing a language model down to three-value (\u201cternary\u201d) weights " +
    "\u2014 minus one, zero, plus one \u2014 normally means re-training it from scratch on ~100 billion words, " +
    "which is hugely expensive. <b>CAT-Q</b> instead takes a model that is <b>already trained</b>, freezes " +
    "it, and calibrates the ternary conversion using only a tiny sample set \u2014 no re-training. It does this " +
    "two ways: it <b>learns a better cut-off</b> (which weights become zero) and gently <b>eases</b> weights " +
    "toward their ternary value instead of snapping them hard. Here, on a toy frozen weight set, that lowers " +
    "the conversion error from about <b>" + abs + "</b> (plain absmean snap) to about <b>" + cq + "</b> \u2014 an " +
    "improvement of roughly <b>" + impPct + "</b>, with <b>no re-training</b>. This is a <b>SUB-ORGAN UPGRADE " +
    "of the ternary organ</b>: the same three-value weight idea, but a post-training-calibration mechanism " +
    "instead of train-from-scratch. It is <b>MODELED</b> \u2014 a deterministic toy simulation of the mechanism, " +
    "NOT a real large model, NOT the CAT-Q authors' code, and it does NOT reproduce their published results " +
    "versus BitNet or their ~100,000\u00d7 training-data reduction.";
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
  _set("cq-weights",   t || (S.numWeights != null ? String(S.numWeights) : "\u2014"));
  _set("cq-calib",     t || (S.numCalib != null ? String(S.numCalib) : "\u2014"));
  _set("cq-groups",    t || (S.modGroups != null ? String(S.modGroups) : "\u2014"));
  _set("cq-steps",     t || (S.softSteps != null ? String(S.softSteps) : "\u2014"));
  _set("cq-absthr",    t || fx(S.absmeanThresh, 4));
  _set("cq-catqthr",   t || fx(S.catqThreshFrac, 3));
  _set("cq-absmix",    t || ((S.absNeg != null) ? (S.absNeg + " / " + S.absZero + " / " + S.absPos) : "\u2014"));
  _set("cq-catqmix",   t || ((S.catqNeg != null) ? (S.catqNeg + " / " + S.catqZero + " / " + S.catqPos) : "\u2014"));
  _set("cq-reconabs",  t || pct(S.reconErrAbs, 2));
  _set("cq-reconcatq", t || pct(S.reconErrCatq, 2));
  _set("cq-reconimp",  t || pct(S.reconImprovFrac, 2));
  _set("cq-taskabs",   t || pct(S.taskErrAbs, 2));
  _set("cq-taskcatq",  t || pct(S.taskErrCatq, 2));
  let curveTxt = "\u2014";
  if (S.curve && S.curve.length >= 2) {
    const f = S.curve[0], l = S.curve[S.curve.length - 1];
    if (typeof f.task_err === "number" && typeof l.task_err === "number") {
      curveTxt = f.task_err.toFixed(2) + " \u2192 " + l.task_err.toFixed(2);
    }
  }
  _set("cq-curve",     t || curveTxt);
  _set("cq-bpw",       t || fx(S.bitsPerWeight, 4));
  // honesty label verbatim — never upgraded
  _set("cq-label",     t || (S.label || "MODELED"));
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
  _floor = null; _barsAbs = []; _barsCatq = []; _gateAbs = null; _gateCatq = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.numWeights = S.numCalib = S.modGroups = S.softSteps = null;
  S.absmeanThresh = S.catqThreshFrac = null;
  S.absNeg = S.absZero = S.absPos = null;
  S.catqNeg = S.catqZero = S.catqPos = null;
  S.reconErrAbs = S.reconErrCatq = S.reconImprovFrac = null;
  S.taskErrAbs = S.taskErrCatq = S.bitsPerWeight = S.curve = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
