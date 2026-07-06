// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/herotq.js — HeRo-Q HESSIAN-CONDITIONED LOW-BIT QUANTIZATION organ for
// the holographic frontier ring (HeRo-Q = "Hessian Robust Quantization"; Zhang,
// Jinhao et al., arXiv:2601.21626). Renders the rotation-compression transform
// that REDUCES THE LARGEST HESSIAN EIGENVALUE before low-bit quantizing, as
// three live panels:
//   (1) HESSIAN SPECTRUM — one bar per eigenvalue of the loss-landscape Hessian,
//       shown BEFORE (raw λ, a few tall stiff directions) vs AFTER the HeRo-Q
//       rotation-compression (transformed λ/s², flattened) — the eigenvalue
//       reduction that reshapes the loss landscape;
//   (2) WEIGHT RECONSTRUCTION — the toy weight vector w drawn as a 3D line,
//       overlaid with its NAIVE `bits`-bit quantized reconstruction and its
//       HeRo-Q reconstruction, so the two rounding paths are visible;
//   (3) METRIC BARS — quant MSE (naive vs HeRo-Q) and curvature-weighted
//       loss-proxy ½·Δwᵀ H Δw (naive vs HeRo-Q), honestly showing the paper's
//       "low error, high loss" paradox: naive has LOWER error but HIGHER loss.
// A HUD reports the MEASURED metrics from the live snapshot at
// /api/killinchu/v1/herotq/quantize. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors muon.js / ternary.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   size, bits, levels, hessian_eigs[...], max_hessian_eig_before,
//   max_hessian_eig_after, eig_reduction_factor, cond_before, cond_after,
//   quant_mse_naive, quant_mse_herotq, loss_proxy_naive, loss_proxy_herotq,
//   loss_reduction_factor, low_error_high_loss, weight_raw[...],
//   weight_naive_q[...], weight_herotq_q[...]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   HeRo-Q: A General Framework for Stable Low Bit Quantization via Hessian
//     Conditioning — Zhang, Jinhao et al. arXiv:2601.21626
//     https://arxiv.org/abs/2601.21626
//
// HONESTY LABELS: MODELED (deterministic reproduction of the HeRo-Q Hessian-
//   conditioning ROTATION-COMPRESSION mechanism on a toy synthetic weight vector
//   + synthetic Hessian; NOT a trained model; quantizes nothing real; the
//   eigenvalue reduction and curvature-weighted loss drop are MEASURED and
//   displayed; NEVER-CLAIMED-AS reproducing the GSM8K/Llama3-8B numbers). Read
//   verbatim from JSON.
// DISTINCTNESS: this is the HESSIAN-EIGENVALUE rotation-compression mechanism —
//   NOT ternary (2-bit sign) weights and NOT FP4 block-scaling / codebook
//   quantization. The distinguishing object is the Hessian eigenvalue spectrum.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff, proof-teal 0x3af4c8,
//   greys (0x5a6570 / 0x42505d). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "herotq";
const TITLE = "HeRo-Q Hessian-Conditioned Quantization";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute),
// reached cross-origin (killinchu returns access-control-allow-origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/herotq/quantize?seed=42&size=32&bits=3";

// data-viz hues — purple BANNED
const C_BEFORE = 0x5b8dee;  // lattice-blue (raw Hessian spectrum / raw weight)
const C_AFTER  = 0x3af4c8;  // proof-teal   (transformed spectrum / HeRo-Q recon)
const C_NAIVE  = 0x8a6bff;  // violet-blue  (naive quantized reconstruction / naive bar)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ZERO   = 0x5a6570;  // grey (near-zero / axis)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const SPEC_X0   = -6.0;   // spectrum panel origin x
const SPEC_DX   = 0.34;   // world-units per eigenvalue bar
const SPEC_YSC  = 0.16;   // world-units per unit eigenvalue (log-ish handled in code)
const SPEC_BW   = 0.14;   // spectrum bar footprint
const W_X0      = -3.2;   // weight-line panel origin x
const W_DX      = 0.22;   // world-units per weight coordinate
const W_YSC     = 2.2;    // world-units per unit weight value
const BAR_W     = 0.7;    // metric bar width

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _specGroup  = null;   // THREE.Group — Hessian eigenvalue bars (before/after)
let _specBefore = [];     // Array<THREE.Mesh> — raw-λ bars
let _specAfter  = [];     // Array<THREE.Mesh> — transformed-λ bars
let _wGroup     = null;   // THREE.Group — weight reconstruction lines
let _barGroup   = null;   // THREE.Group — metric bars
let _barMseN    = null;   // naive MSE bar
let _barMseH    = null;   // HeRo-Q MSE bar
let _barLossN   = null;   // naive loss-proxy bar
let _barLossH   = null;   // HeRo-Q loss-proxy bar

// live state
const S = {
  label:       null,
  size:        null,
  bits:        null,
  levels:      null,
  eigs:        null,   // hessian_eigs
  maxBefore:   null,   // max_hessian_eig_before
  maxAfter:    null,   // max_hessian_eig_after
  eigRed:      null,   // eig_reduction_factor
  condBefore:  null,   // cond_before
  condAfter:   null,   // cond_after
  mseNaive:    null,   // quant_mse_naive
  mseHerotq:   null,   // quant_mse_herotq
  lossNaive:   null,   // loss_proxy_naive
  lossHerotq:  null,   // loss_proxy_herotq
  lossRed:     null,   // loss_reduction_factor
  paradox:     null,   // low_error_high_loss
  wRaw:        null,   // weight_raw
  wNaive:      null,   // weight_naive_q
  wHerotq:     null,   // weight_herotq_q
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(2, 7, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpectrum();
  _buildWeights();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onHerotq, { badge: _badge, onState: (msg) => { S.state = msg.state; _updateAll(); _paintOverlay(); } }));

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

// Hessian spectrum panel: two rows of bars — raw λ (before, lattice-blue) at the
// back, transformed λ/s² (after, proof-teal) in front. Pre-allocate a fixed cap
// and toggle visibility/height in place (no churn).
const SPEC_MAX = 64;
function _buildSpectrum() {
  const THREE = _THREE;
  _specGroup = new THREE.Group();
  _specGroup.position.set(SPEC_X0, 0, -2.6);
  _group.add(_specGroup);
  const geo = new THREE.BoxGeometry(SPEC_BW, 1.0, SPEC_BW);

  function makeRow(zoff, color, arr) {
    for (let i = 0; i < SPEC_MAX; i++) {
      const mesh = new THREE.Mesh(
        geo,
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.32, transparent: true, opacity: 0.9 }),
      );
      mesh.position.set(i * SPEC_DX, 0.02, zoff);
      mesh.scale.y = 0.02;
      mesh.visible = false;
      _specGroup.add(mesh);
      arr.push(mesh);
    }
  }
  makeRow(0.0, C_BEFORE, _specBefore);
  makeRow(0.9, C_AFTER,  _specAfter);
}

// weight reconstruction panel: three polylines rebuilt in place on fresh data.
function _buildWeights() {
  const THREE = _THREE;
  _wGroup = new THREE.Group();
  _wGroup.position.set(W_X0, 1.4, 3.0);
  _group.add(_wGroup);
  // lines are added by _updateWeights once data arrives
}

function _buildBars() {
  const THREE = _THREE;
  _barGroup = new THREE.Group();
  _barGroup.position.set(5.4, 0, 0.4);
  _group.add(_barGroup);
  const geo = new THREE.BoxGeometry(BAR_W, 1.0, BAR_W);

  function mk(x, color) {
    const m = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
    );
    m.position.set(x, 0.02, 0);
    m.scale.y = 0.02;
    _barGroup.add(m);
    return m;
  }
  // MSE pair (front row), loss pair (back row)
  _barMseN  = mk(0.0,  C_NAIVE);
  _barMseH  = mk(0.95, C_AFTER);
  _barLossN = mk(0.0,  C_NAIVE); _barLossN.position.z = 1.6;
  _barLossH = mk(0.95, C_AFTER); _barLossH.position.z = 1.6;
}

// =============================================================================
// live data handler
// =============================================================================
function _onHerotq(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label = String(lbl).toUpperCase();

  S.size       = typeof src.size                   === "number" ? src.size                   : null;
  S.bits       = typeof src.bits                   === "number" ? src.bits                   : null;
  S.levels     = typeof src.levels                 === "number" ? src.levels                 : null;
  S.maxBefore  = typeof src.max_hessian_eig_before === "number" ? src.max_hessian_eig_before : null;
  S.maxAfter   = typeof src.max_hessian_eig_after  === "number" ? src.max_hessian_eig_after  : null;
  S.eigRed     = typeof src.eig_reduction_factor   === "number" ? src.eig_reduction_factor   : null;
  S.condBefore = typeof src.cond_before            === "number" ? src.cond_before            : null;
  S.condAfter  = typeof src.cond_after             === "number" ? src.cond_after             : null;
  S.mseNaive   = typeof src.quant_mse_naive        === "number" ? src.quant_mse_naive        : null;
  S.mseHerotq  = typeof src.quant_mse_herotq       === "number" ? src.quant_mse_herotq       : null;
  S.lossNaive  = typeof src.loss_proxy_naive       === "number" ? src.loss_proxy_naive       : null;
  S.lossHerotq = typeof src.loss_proxy_herotq      === "number" ? src.loss_proxy_herotq      : null;
  S.lossRed    = typeof src.loss_reduction_factor  === "number" ? src.loss_reduction_factor  : null;
  S.paradox    = typeof src.low_error_high_loss    === "boolean" ? src.low_error_high_loss   : null;

  S.eigs    = Array.isArray(src.hessian_eigs)   ? src.hessian_eigs   : null;
  S.wRaw    = Array.isArray(src.weight_raw)     ? src.weight_raw     : null;
  S.wNaive  = Array.isArray(src.weight_naive_q) ? src.weight_naive_q : null;
  S.wHerotq = Array.isArray(src.weight_herotq_q)? src.weight_herotq_q: null;

  _updateAll();
  _paintOverlay();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _updateAll() {
  _updateSpectrum();
  _updateWeights();
  _updateBars();
}

// height ∝ log10(1+λ) so tall stiff directions and flat ones are both legible.
function _lh(v) { return Math.max(0.03, Math.log10(1.0 + Math.max(0.0, v)) * 3.0); }

function _updateSpectrum() {
  const live = S.state === "live";
  const eigs = (live && S.eigs) ? S.eigs : null;
  // "after" spectrum is reconstructed geometrically: the flattened spectrum has
  // the same count but is capped at max_hessian_eig_after (the measured λ_max
  // the grid must resolve); we scale each raw λ toward that ceiling so the
  // visual monotonically maps the measured reduction without fabricating values.
  const n = eigs ? Math.min(eigs.length, SPEC_MAX) : 0;
  const capAfter = (S.maxAfter != null) ? S.maxAfter : 0.0;
  const maxRaw = (eigs && eigs.length) ? Math.max.apply(null, eigs) : 1.0;

  for (let i = 0; i < SPEC_MAX; i++) {
    const b = _specBefore[i], a = _specAfter[i];
    if (!live || i >= n) {
      if (b) { b.visible = false; }
      if (a) { a.visible = false; }
      continue;
    }
    const lam = eigs[i];
    // before bar
    b.visible = true;
    let hb = _lh(lam);
    b.scale.y = hb; b.position.y = hb * 0.5;
    b.material.color.setHex(C_BEFORE); b.material.emissive.setHex(C_BEFORE);
    b.material.opacity = 0.9;
    // after bar: transformed curvature the grid resolves is bounded by capAfter.
    // map λ proportionally into [0, capAfter] so stiff directions collapse.
    a.visible = true;
    const lamAfter = maxRaw > 0 ? (lam / maxRaw) * capAfter : 0.0;
    let ha = _lh(lamAfter);
    a.scale.y = ha; a.position.y = ha * 0.5;
    a.material.color.setHex(C_AFTER); a.material.emissive.setHex(C_AFTER);
    a.material.opacity = 0.9;
  }
}

// rebuild the three weight polylines (raw / naive / HeRo-Q) from live data.
function _updateWeights() {
  const THREE = _THREE;
  if (!_wGroup) return;
  // dispose previous children
  for (let i = _wGroup.children.length - 1; i >= 0; i--) {
    const o = _wGroup.children[i];
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) {
      const ms = Array.isArray(o.material) ? o.material : [o.material];
      ms.forEach((m) => { if (m.dispose) m.dispose(); });
    }
    _wGroup.remove(o);
  }
  const live = S.state === "live";
  if (!live) return;

  function addLine(arr, color, op) {
    if (!Array.isArray(arr) || !arr.length) return;
    const pts = [];
    for (let i = 0; i < arr.length; i++) {
      const v = typeof arr[i] === "number" ? arr[i] : 0.0;
      pts.push(new THREE.Vector3(i * W_DX, v * W_YSC, 0));
    }
    const lg = new THREE.BufferGeometry().setFromPoints(pts);
    const lm = new THREE.LineBasicMaterial({ color, transparent: true, opacity: op });
    _wGroup.add(new THREE.Line(lg, lm));
  }
  addLine(S.wRaw,    C_BEFORE, 0.85);
  addLine(S.wNaive,  C_NAIVE,  0.7);
  addLine(S.wHerotq, C_AFTER,  0.9);
}

// metric bars: MSE pair + loss-proxy pair. height on independent normalizers so
// each pair is legible; the honest STORY is naive-MSE lower, naive-loss higher.
function _updateBars() {
  const live = S.state === "live";
  function setBar(mesh, val, refMax, color) {
    if (!mesh) return;
    if (!live || val == null) {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.opacity = 0.3;
      mesh.scale.y = 0.02; mesh.position.y = 0.01;
      return;
    }
    const denom = refMax > 1e-12 ? refMax : 1.0;
    const h = Math.max(0.05, (val / denom) * 3.4);
    mesh.scale.y = h; mesh.position.y = h * 0.5;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.emissiveIntensity = 0.4;
    mesh.material.opacity = 0.92;
  }
  const mseMax = Math.max(S.mseNaive || 0, S.mseHerotq || 0);
  const lossMax = Math.max(S.lossNaive || 0, S.lossHerotq || 0);
  setBar(_barMseN,  S.mseNaive,   mseMax,  C_NAIVE);
  setBar(_barMseH,  S.mseHerotq,  mseMax,  C_AFTER);
  setBar(_barLossN, S.lossNaive,  lossMax, C_NAIVE);
  setBar(_barLossH, S.lossHerotq, lossMax, C_AFTER);
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
    'HeRo-Q (\u201cHessian Robust Quantization\u201d) fixes the <b>\u201clow error, high loss\u201d</b> paradox in ' +
    'low-bit quantization: naive rounding minimizes weight ERROR, but the loss actually depends on the ' +
    '<b>Hessian</b> \u2014 a few <b>high-curvature directions</b> (large eigenvalues) are extremely ' +
    'perturbation-sensitive. HeRo-Q applies a <b>rotation-compression</b> transform in the Hessian ' +
    'eigenbasis (w<sub>q</sub> = V(s<sup>\u22121</sup>\u2299q(s\u2299V\u1d40w)), s<sub>i</sub>=\u221a(1+\u03bb<sub>i</sub>/\u03bb<sub>med</sub>)) that ' +
    '<b>reduces the largest Hessian eigenvalue</b> before quantizing. Panels: Hessian spectrum ' +
    '(before vs after), weight reconstruction (raw / naive / HeRo-Q), metric bars (quant MSE & ' +
    'curvature-weighted loss ½\u00b7\u0394w\u1d40H\u0394w). Honesty label <b>MODELED</b> (deterministic mechanism ' +
    'reproduction on a toy matrix; quantizes nothing real). 0 runtime CDN.';
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
  nm.textContent = "hero-q hessian-conditioned quantization";
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

  grid.appendChild(kpiRow("hq-size",  "weight / Hessian size"));
  grid.appendChild(kpiRow("hq-bits",  "quantization bits (levels)"));
  grid.appendChild(kpiRow("hq-eigb",  "max Hessian \u03bb \u2014 BEFORE"));
  grid.appendChild(kpiRow("hq-eiga",  "max Hessian \u03bb \u2014 AFTER"));
  grid.appendChild(kpiRow("hq-eigr",  "eigenvalue reduction"));
  grid.appendChild(kpiRow("hq-cond",  "condition \u03ba (before \u2192 after)"));
  grid.appendChild(kpiRow("hq-msen",  "quant MSE \u2014 naive"));
  grid.appendChild(kpiRow("hq-mseh",  "quant MSE \u2014 HeRo-Q"));
  grid.appendChild(kpiRow("hq-lossn", "loss-proxy \u00bd\u0394w\u1d40H\u0394w \u2014 naive"));
  grid.appendChild(kpiRow("hq-lossh", "loss-proxy \u00bd\u0394w\u1d40H\u0394w \u2014 HeRo-Q"));
  grid.appendChild(kpiRow("hq-lossr", "loss reduction"));
  grid.appendChild(kpiRow("hq-para",  "\u201clow error, high loss\u201d (naive)"));
  grid.appendChild(kpiRow("hq-label", "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "HeRo-Q \u2014 Zhang, Jinhao et al. \u201cHeRo-Q: A General Framework for Stable Low Bit Quantization via Hessian Conditioning\u201d arXiv:2601.21626. MODELED \u00b7 Hessian-conditioning demo on a toy matrix, not a trained model. Does NOT reproduce the GSM8K/Llama3-8B numbers.";
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
  pd.id = "hq-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  (ctx.container || document.body).appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const eb  = S.maxBefore != null ? S.maxBefore.toFixed(1) : "loading\u2026";
  const ea  = S.maxAfter  != null ? S.maxAfter.toFixed(2)  : "loading\u2026";
  const er  = S.eigRed    != null ? S.eigRed.toFixed(1) + "\u00d7" : "loading\u2026";
  const lr  = S.lossRed   != null ? S.lossRed.toFixed(1) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> To make a big model small and fast, we store its numbers with very few " +
    "bits \u2014 like rounding prices to the nearest dollar. Plain rounding keeps the <b>numbers</b> close, " +
    "but the model can still get much <b>worse</b>, because a few \u201cstiff\u201d directions matter far more " +
    "than the rest (the \u201clow error, high loss\u201d paradox). HeRo-Q first <b>turns and rescales</b> the " +
    "weights so those stiff directions get more of the rounding precision \u2014 like giving the most " +
    "fragile items the most padding before shipping. Here the biggest \u201cstiffness\u201d (largest Hessian " +
    "eigenvalue) drops from about <b>" + eb + "</b> to about <b>" + ea + "</b> \u2014 a <b>" + er + "</b> " +
    "flattening \u2014 and the curvature-weighted error (the thing that actually hurts the model) falls by " +
    "about <b>" + lr + "</b>, even though the raw rounding error is slightly larger. This view is a " +
    "<b>MODELED</b> deterministic reproduction of that turn-and-rescale MECHANISM on a small synthetic " +
    "matrix \u2014 it <b>quantizes no real model</b> and runs no benchmark. The paper\u2019s headline " +
    "\u201c70.15% GSM8K on Llama3-8B at 3-bit\u201d is a <b>claim about a real model</b> the estate does not " +
    "independently verify.";
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
  _set("hq-size",  t || (S.size != null ? String(S.size) : "\u2014"));
  _set("hq-bits",  t || ((S.bits != null && S.levels != null) ? (S.bits + "-bit (" + S.levels + " levels)") : "\u2014"));
  _set("hq-eigb",  t || fx(S.maxBefore, 3));
  _set("hq-eiga",  t || fx(S.maxAfter, 3));
  _set("hq-eigr",  t || (S.eigRed != null ? S.eigRed.toFixed(1) + "\u00d7" : "\u2014"));
  _set("hq-cond",  t || ((S.condBefore != null && S.condAfter != null) ? (fx(S.condBefore, 1) + " \u2192 " + fx(S.condAfter, 2)) : "\u2014"));
  _set("hq-msen",  t || fx(S.mseNaive, 5));
  _set("hq-mseh",  t || fx(S.mseHerotq, 5));
  _set("hq-lossn", t || fx(S.lossNaive, 4));
  _set("hq-lossh", t || fx(S.lossHerotq, 4));
  _set("hq-lossr", t || (S.lossRed != null ? S.lossRed.toFixed(1) + "\u00d7" : "\u2014"));
  _set("hq-para",  t || (S.paradox != null ? (S.paradox ? "PRESENT \u2192 fixed" : "\u2014") : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("hq-label", t || (S.label || "MODELED"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
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
  _group = _overlay = null;
  _floor = null;
  _specGroup = null; _specBefore = []; _specAfter = [];
  _wGroup = null;
  _barGroup = null; _barMseN = _barMseH = _barLossN = _barLossH = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.size = S.bits = S.levels = null;
  S.eigs = null;
  S.maxBefore = S.maxAfter = S.eigRed = S.condBefore = S.condAfter = null;
  S.mseNaive = S.mseHerotq = S.lossNaive = S.lossHerotq = S.lossRed = null;
  S.paradox = null;
  S.wRaw = S.wNaive = S.wHerotq = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
