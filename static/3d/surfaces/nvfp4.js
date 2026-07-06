// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/nvfp4.js — NVFP4 4-BIT TRAINING-FORMAT organ for the holographic
// frontier ring. Visualizes a deterministic toy arithmetic demonstration of
// block-scaled 4-bit floating-point (FP4 E2M1) quantization, from the live
// snapshot at /api/killinchu/v1/nvfp4/quantize. Three things are rendered:
//   (1) reconstruction-error MSE bars per scheme — naive-FP4 (single global
//       scale) vs MXFP4 (32-elem blocks, power-of-two scale) vs NVFP4 (16-elem
//       blocks, E4M3 FP8 scale + FP32 global; two-level). Errors are MEASURED
//       and shown, never hidden.
//   (2) a cumulative rounding-bias line — deterministic round-to-nearest
//       (DRIFTS) vs stochastic rounding (stays near zero) over N roundings of a
//       fixed delta.
//   (3) a two-level NVFP4 scaling-pipeline diagram: tensor -> FP32 global scale
//       -> E4M3 block scale -> FP4 value.
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is;
// never upgraded.
//
// Surface export shape (mirrors ternary.js / kvcache.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   size, outliers, tensor_amax, best_scheme, fp4_levels[],
//   schemes[]{name, block_size, scale_format, two_level, mse, max_abs_err},
//   rounding{n, delta, det_final_bias, stoch_final_bias,
//            det_bias_series[], stoch_bias_series[]}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   NVFP4 pretraining — Agrusa, Rouhani, Micikevicius, Patwary, Shoeybi et al.
//     (NVIDIA) arXiv:2509.25149  https://arxiv.org/abs/2509.25149
//   MXFP4 / OCP Microscaling — Rouhani et al. arXiv:2310.10537
//     https://arxiv.org/pdf/2310.10537
//   Introducing NVFP4 (NVIDIA blog):
//     https://developer.nvidia.com/blog/introducing-nvfp4-for-efficient-and-accurate-low-precision-inference/
//   Oscillation-Reduced MXFP4 Training (TetraJet) arXiv:2502.20853
//     https://arxiv.org/abs/2502.20853
//
// HONESTY LABELS: MODELED (deterministic ARITHMETIC DEMONSTRATION of the FP4
//   block-scaling + two-level-scaling + stochastic-rounding MECHANISMS on a toy
//   synthetic tensor; NO GPU kernel executed, NOT the trained model; error is
//   MEASURED and displayed). Read verbatim from JSON; never upgraded here.
// COLOURS: proof-teal 0x3af4c8 (NVFP4 / best), lattice-blue 0x5b8dee (MXFP4 /
//   deterministic line), violet-blue 0x8a6bff (naive / accent), greys
//   (0x5a6570 / 0x42505d, degraded / stochastic line). Purple BANNED.
// 0 RUNTIME CDN. Vendored three.js via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "nvfp4";
const TITLE = "NVFP4 4-bit Training Format";

// Endpoint hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/nvfp4/quantize?seed=42&size=32&outliers=3";

// data-viz hues — purple BANNED
const C_NV      = 0x3af4c8;  // proof-teal   (NVFP4 / best scheme)
const C_MX      = 0x5b8dee;  // lattice-blue (MXFP4 / deterministic rounding line)
const C_NAIVE   = 0x8a6bff;  // violet-blue  (naive-FP4 / accent)
const C_STOCH   = 0x3af4c8;  // proof-teal   (stochastic rounding line)
const C_ZERO    = 0x5a6570;  // grey (zero baseline / neutral)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor    = null;
let _bars     = [];   // Array<THREE.Mesh> — one MSE bar per scheme
let _detLine  = null; // THREE.Line — deterministic cumulative bias
let _stochLine= null; // THREE.Line — stochastic cumulative bias
let _biasZero = null; // THREE.Line — zero baseline for the bias plot
let _pipe     = [];   // Array<THREE.Mesh> — two-level pipeline diagram stages

// bar layout
const BAR_X0   = 0.0;
const BAR_GAP  = 1.5;
const BAR_W    = 0.7;
const BAR_MAXH = 3.2;

// bias-plot layout
const PLOT_X0  = 6.2;
const PLOT_W   = 4.2;
const PLOT_Y   = 1.6;
const PLOT_H   = 2.0;

// pipeline layout
const PIPE_X0  = 0.0;
const PIPE_Z   = 4.4;
const PIPE_GAP = 1.7;

// live state
const S = {
  label:       null,
  size:        null,
  outliers:    null,
  tensorAmax:  null,
  bestScheme:  null,
  fp4Levels:   null,   // array
  schemes:     null,   // array of {name, mse, max_abs_err, block_size, scale_format, two_level}
  rDelta:      null,
  rN:          null,
  detFinal:    null,
  stochFinal:  null,
  detSeries:   null,   // array
  stochSeries: null,   // array
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(5, 7, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(4, 1, 2); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildBars();
  _buildBiasPlot();
  _buildPipeline();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onNvfp4, { badge: _badge, onState: (m) => { S.state = m.state; _updateScene(); _paintOverlay(); } }));

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

// three MSE bars: naive-FP4 (violet-blue), MXFP4 (lattice-blue), NVFP4 (proof-teal)
function _buildBars() {
  const THREE = _THREE;
  const cols = [C_NAIVE, C_MX, C_NV];
  const geo = new THREE.BoxGeometry(BAR_W, 1, BAR_W);
  for (let i = 0; i < 3; i++) {
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: cols[i], emissive: cols[i], emissiveIntensity: 0.35, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(BAR_X0 + i * BAR_GAP, 0.5, 0);
    mesh.scale.y = 0.02;
    _group.add(mesh);
    _bars.push(mesh);
  }
}

// two poly-lines for cumulative rounding bias + a zero baseline
function _buildBiasPlot() {
  const THREE = _THREE;
  // zero baseline
  const zg = new THREE.BufferGeometry();
  zg.setAttribute("position", new THREE.Float32BufferAttribute([PLOT_X0, PLOT_Y, 0, PLOT_X0 + PLOT_W, PLOT_Y, 0], 3));
  _biasZero = new THREE.Line(zg, new THREE.LineBasicMaterial({ color: C_ZERO, transparent: true, opacity: 0.5 }));
  _group.add(_biasZero);

  const dg = new THREE.BufferGeometry();
  dg.setAttribute("position", new THREE.Float32BufferAttribute([PLOT_X0, PLOT_Y, 0, PLOT_X0, PLOT_Y, 0], 3));
  _detLine = new THREE.Line(dg, new THREE.LineBasicMaterial({ color: C_MX }));
  _group.add(_detLine);

  const sg = new THREE.BufferGeometry();
  sg.setAttribute("position", new THREE.Float32BufferAttribute([PLOT_X0, PLOT_Y, 0, PLOT_X0, PLOT_Y, 0], 3));
  _stochLine = new THREE.Line(sg, new THREE.LineBasicMaterial({ color: C_STOCH }));
  _group.add(_stochLine);
}

// two-level scaling pipeline: tensor -> FP32 global -> E4M3 block -> FP4 value
function _buildPipeline() {
  const THREE = _THREE;
  const stageCols = [C_NAIVE, C_NAIVE, C_MX, C_NV];  // tensor, global, block, fp4
  const shapes = [
    new THREE.BoxGeometry(0.6, 0.6, 0.6),
    new THREE.OctahedronGeometry(0.42, 0),
    new THREE.OctahedronGeometry(0.42, 0),
    new THREE.IcosahedronGeometry(0.42, 0),
  ];
  for (let i = 0; i < 4; i++) {
    const c = stageCols[i];
    const mesh = new THREE.Mesh(
      shapes[i],
      new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.3, transparent: true, opacity: 0.85, wireframe: i > 0 }),
    );
    mesh.position.set(PIPE_X0 + i * PIPE_GAP, 0.55, PIPE_Z);
    _group.add(mesh);
    _pipe.push(mesh);
    // connecting link to previous stage
    if (i > 0) {
      const lg = new THREE.BufferGeometry();
      lg.setAttribute("position", new THREE.Float32BufferAttribute([
        PIPE_X0 + (i - 1) * PIPE_GAP, 0.55, PIPE_Z,
        PIPE_X0 + i * PIPE_GAP,       0.55, PIPE_Z,
      ], 3));
      const link = new THREE.Line(lg, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.6 }));
      _group.add(link);
      _pipe.push(link);
    }
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onNvfp4(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level or nested.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;
  S.label      = String(lbl).toUpperCase();

  S.size       = typeof src.size        === "number" ? src.size        : null;
  S.outliers   = typeof src.outliers    === "number" ? src.outliers    : null;
  S.tensorAmax = typeof src.tensor_amax === "number" ? src.tensor_amax : null;
  S.bestScheme = typeof src.best_scheme === "string" ? src.best_scheme : null;
  S.fp4Levels  = Array.isArray(src.fp4_levels) ? src.fp4_levels : null;
  S.schemes    = Array.isArray(src.schemes)    ? src.schemes    : null;

  if (src.rounding && typeof src.rounding === "object") {
    const r = src.rounding;
    S.rDelta      = typeof r.delta            === "number" ? r.delta            : null;
    S.rN          = typeof r.n                === "number" ? r.n                : null;
    S.detFinal    = typeof r.det_final_bias   === "number" ? r.det_final_bias   : null;
    S.stochFinal  = typeof r.stoch_final_bias === "number" ? r.stoch_final_bias : null;
    S.detSeries   = Array.isArray(r.det_bias_series)   ? r.det_bias_series   : null;
    S.stochSeries = Array.isArray(r.stoch_bias_series) ? r.stoch_bias_series : null;
  }

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// scene updater
// =============================================================================
function _schemeByName(nm) {
  if (!S.schemes) return null;
  for (const s of S.schemes) if (s && s.name === nm) return s;
  return null;
}

function _updateScene() {
  const live = S.state === "live" && S.schemes;

  // ---- MSE bars ----
  const order = ["naive-FP4", "MXFP4", "NVFP4"];
  const cols  = [C_NAIVE, C_MX, C_NV];
  let maxMse = 0;
  if (live) {
    for (const nm of order) {
      const s = _schemeByName(nm);
      if (s && typeof s.mse === "number" && s.mse > maxMse) maxMse = s.mse;
    }
  }
  for (let i = 0; i < _bars.length; i++) {
    const bar = _bars[i];
    if (!live || maxMse <= 0) {
      bar.material.color.setHex(C_DIM);
      bar.material.emissive.setHex(C_DIM);
      bar.material.opacity = 0.35;
      bar.scale.y = 0.02;
      bar.position.y = 0.01;
      continue;
    }
    const s = _schemeByName(order[i]);
    const mse = (s && typeof s.mse === "number") ? s.mse : 0;
    const h = Math.max(0.02, (mse / maxMse) * BAR_MAXH);
    bar.scale.y = h;
    bar.position.y = h / 2;
    const isBest = S.bestScheme && order[i] === S.bestScheme;
    bar.material.color.setHex(cols[i]);
    bar.material.emissive.setHex(cols[i]);
    bar.material.emissiveIntensity = isBest ? 0.65 : 0.3;
    bar.material.opacity = 0.92;
  }

  // ---- rounding-bias lines ----
  _updateBiasLine(_detLine, live ? S.detSeries : null);
  _updateBiasLine(_stochLine, live ? S.stochSeries : null);

  // ---- pipeline highlight ----
  for (const m of _pipe) {
    if (m.material && m.material.emissive) {
      m.material.emissiveIntensity = live ? 0.4 : 0.12;
      m.material.opacity = live ? 0.85 : 0.3;
    }
  }
}

function _updateBiasLine(line, series) {
  if (!line) return;
  const THREE = _THREE;
  if (!series || series.length < 2) {
    // collapse to a flat segment on the baseline
    line.geometry.setAttribute("position", new THREE.Float32BufferAttribute([PLOT_X0, PLOT_Y, 0, PLOT_X0 + PLOT_W, PLOT_Y, 0], 3));
    line.geometry.attributes.position.needsUpdate = true;
    line.visible = S.state === "live";
    return;
  }
  // symmetric vertical scale from the max abs across BOTH series so the drift
  // vs near-zero contrast is faithful (never invented — from live data only).
  let amax = 1e-6;
  const scan = (arr) => { if (Array.isArray(arr)) for (const v of arr) { const a = Math.abs(v); if (a > amax) amax = a; } };
  scan(S.detSeries); scan(S.stochSeries);
  const n = series.length;
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const x = PLOT_X0 + (i / (n - 1)) * PLOT_W;
    const y = PLOT_Y + (series[i] / amax) * (PLOT_H / 2);
    pos[i * 3 + 0] = x;
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = 0;
  }
  line.geometry.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  line.geometry.attributes.position.needsUpdate = true;
  line.geometry.computeBoundingSphere();
  line.visible = true;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  for (let i = 0; i < _pipe.length; i++) {
    const m = _pipe[i];
    if (m && m.rotation && m.geometry && m.geometry.type !== "BufferGeometry") {
      m.rotation.y += 0.012;
    }
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
  h.textContent = TITLE + " (live)";
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A synthetic tensor with a few injected <b>outliers</b> is quantized to 4-bit float (<b>FP4 E2M1</b>) three ways, ' +
    'then dequantized: <b>naive</b> (one global scale) vs <b>MXFP4</b> (32-elem blocks, power-of-two scale) vs ' +
    '<b>NVFP4</b> (16-elem blocks, <b>E4M3</b> FP8 block scale + <b>FP32</b> global \u2014 <b>two-level</b>). Bars show ' +
    'the MEASURED reconstruction <b>MSE</b> per scheme (shown, NOT hidden). The line plot contrasts <b>deterministic</b> ' +
    'round-to-nearest (drifts) vs <b>stochastic</b> rounding (near zero) over repeated roundings. Honesty label ' +
    '<b>MODELED</b> \u2014 arithmetic demonstration only, no GPU kernel executed. 0 runtime CDN.';
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
  nm.textContent = "nvfp4 4-bit training format";
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

  grid.appendChild(kpiRow("nv-size",    "tensor (size \u00d7 size)"));
  grid.appendChild(kpiRow("nv-outl",    "injected outliers"));
  grid.appendChild(kpiRow("nv-amax",    "tensor max |value|"));
  grid.appendChild(kpiRow("nv-naive",   "MSE \u2014 naive-FP4 (global scale)"));
  grid.appendChild(kpiRow("nv-mx",      "MSE \u2014 MXFP4 (32-blk pow2)"));
  grid.appendChild(kpiRow("nv-nv",      "MSE \u2014 NVFP4 (16-blk E4M3+FP32)"));
  grid.appendChild(kpiRow("nv-best",    "best scheme (lowest MSE)"));
  grid.appendChild(kpiRow("nv-rn",      "rounding demo \u2014 N roundings"));
  grid.appendChild(kpiRow("nv-det",     "cumulative bias \u2014 deterministic"));
  grid.appendChild(kpiRow("nv-stoch",   "cumulative bias \u2014 stochastic"));
  grid.appendChild(kpiRow("nv-label",   "honesty label"));
  card.appendChild(grid);

  // scaling-pipeline legend (two-level)
  const pipe = document.createElement("div");
  pipe.style.cssText = "font-size:10px;color:#9fb1bf;line-height:1.5;border-top:1px solid #1d2a36;padding-top:6px";
  pipe.innerHTML =
    "<b style='color:#c9d6df'>two-level scaling pipeline:</b><br>" +
    "tensor <span style='color:#8a6bff'>\u25a0</span> \u2192 FP32 global scale <span style='color:#8a6bff'>\u25c8</span> " +
    "\u2192 E4M3 block scale <span style='color:#5b8dee'>\u25c8</span> \u2192 FP4 value <span style='color:#3af4c8'>\u2b21</span>";
  card.appendChild(pipe);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "NVFP4 \u2014 Agrusa, Rouhani, Micikevicius, Patwary, Shoeybi et al. (NVIDIA) arXiv:2509.25149 \u00b7 MXFP4/OCP arXiv:2310.10537 \u00b7 TetraJet arXiv:2502.20853. MODELED \u00b7 arithmetic-only \u00b7 not claimed-as.";
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
  pd.id = "nv-plain";
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
  const nvMse    = _schemeByName("NVFP4");
  const naiveMse = _schemeByName("naive-FP4");
  const nvTxt    = (nvMse && typeof nvMse.mse === "number")       ? nvMse.mse.toExponential(2)    : "loading\u2026";
  const naiveTxt = (naiveMse && typeof naiveMse.mse === "number") ? naiveMse.mse.toExponential(2) : "loading\u2026";
  const detTxt   = S.detFinal   != null ? S.detFinal.toFixed(2)   : "loading\u2026";
  const stochTxt = S.stochFinal != null ? S.stochFinal.toFixed(2) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Training big models in only 4 bits per number saves memory and speeds up the math, " +
    "but 4 bits is very coarse \u2014 so how you pick the <i>scale</i> matters enormously. The <b>naive</b> approach uses " +
    "one scale for the whole tensor; a single large \u201coutlier\u201d value then crushes precision for everything else " +
    "(error here \u2248 <b>" + naiveTxt + "</b>). <b>MXFP4</b> scales each 32-number block, and <b>NVFP4</b> scales each " +
    "smaller 16-number block with a more precise scale plus a second whole-tensor scale (\u201ctwo-level\u201d) \u2014 giving the " +
    "lowest error here (\u2248 <b>" + nvTxt + "</b>). The line plot shows a second idea: always rounding the same way " +
    "(<b>deterministic</b>) lets tiny errors pile up in one direction (bias drifts to \u2248 <b>" + detTxt + "</b>), while " +
    "<b>stochastic</b> rounding \u2014 flipping a weighted coin each time \u2014 cancels out (stays near <b>" + stochTxt + "</b>). " +
    "This view is <b>MODELED</b>: a deterministic arithmetic demonstration on a tiny synthetic tensor, with the error " +
    "MEASURED and shown. <b>No GPU kernel runs here</b>, and it does not reproduce NVIDIA's 12-billion-parameter, " +
    "10-trillion-token training run or its speed claims \u2014 those are NVIDIA's, not independently verified.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _mseTxt(nm) {
  const s = _schemeByName(nm);
  return (s && typeof s.mse === "number") ? s.mse.toExponential(3) : "\u2014";
}

function _paintOverlay() {
  const t = _tok(S.state);
  _set("nv-size",  t || (S.size != null ? (S.size + " \u00d7 " + S.size) : "\u2014"));
  _set("nv-outl",  t || (S.outliers != null ? String(S.outliers) : "\u2014"));
  _set("nv-amax",  t || (typeof S.tensorAmax === "number" ? S.tensorAmax.toFixed(3) : "\u2014"));
  _set("nv-naive", t || _mseTxt("naive-FP4"));
  _set("nv-mx",    t || _mseTxt("MXFP4"));
  _set("nv-nv",    t || _mseTxt("NVFP4"));
  _set("nv-best",  t || (S.bestScheme || "\u2014"));
  _set("nv-rn",    t || ((S.rN != null && S.rDelta != null) ? (S.rN + " \u00d7 \u03b4=" + S.rDelta) : "\u2014"));
  _set("nv-det",   t || (typeof S.detFinal === "number" ? S.detFinal.toFixed(3) : "\u2014"));
  _set("nv-stoch", t || (typeof S.stochFinal === "number" ? S.stochFinal.toFixed(3) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("nv-label", t || (S.label || "MODELED"));
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
  _floor = null; _bars = []; _detLine = null; _stochLine = null; _biasZero = null; _pipe = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.size = S.outliers = S.tensorAmax = S.bestScheme = null;
  S.fp4Levels = S.schemes = null;
  S.rDelta = S.rN = S.detFinal = S.stochFinal = S.detSeries = S.stochSeries = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
