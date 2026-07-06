// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/aimc.js — ANALOG IN-MEMORY COMPUTING ATTENTION organ for the
// holographic frontier ring (charge-domain gain-cell crossbar attention,
// Leroux et al. 2025-style). Renders an idealized analog crossbar as a lattice
// of nodes: the query drives charge along columns to compute query·key
// dot-products IN MEMORY. Three score bars per column visualize the exact
// DIGITAL baseline (lattice-blue), the raw NOISY ANALOG pathway (violet-blue),
// and the CALIBRATED analog pathway (proof-teal) that recovers accuracy. A HUD
// shows analog_mse vs calibrated_mse + the operations-avoided energy tally read
// live from /api/killinchu/v1/aimc/attend. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors mla.js / kvcache.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   seq_len, dim, noise_sigma, analog_mse, calibrated_mse, calibration_gain,
//   accuracy_recovered_pct, adc_dac_ops_avoided, memory_move_reads_avoided,
//   total_ops_avoided, paper_energy_reduction_claim, paper_latency_reduction_claim,
//   sample_digital_scores[], sample_analog_scores[], sample_calibrated_scores[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   AIMC attention — analog in-memory gain-cell crossbar attention (mechanism
//   simulated here):
//     Leroux et al. 2025, Nature Computational Science
//     https://www.nature.com/articles/s43588-025-00854-1
//   IBM Research plain-language summary (reference):
//     https://research.ibm.com/blog/how-can-analog-in-memory-computing-power-transformer-models
//
// HONESTY LABELS: MODELED (deterministic simulation of the charge-domain crossbar
//   attention arithmetic on ordinary CPU floats; NOT a run on real analog gain-cell
//   hardware; NEVER-CLAIMED-AS the Leroux et al. chip). Read verbatim from JSON;
//   never upgraded here. CRITICAL HONESTY: the energy/latency advantage figures are
//   the PAPER's published CLAIM reproduced at toy scale via an operations-avoided
//   accounting model — NOT measured on real analog hardware, NOT a measured SZL
//   result. Doctrine v11: never claim more than is real.
// COLOURS: lattice-blue 0x5b8dee (exact digital baseline / crossbar rows), violet-
//   blue 0x8a6bff (raw noisy analog pathway), proof-teal 0x3af4c8 (calibrated
//   pathway / HUD accent), greys (device-noise / degraded state). Purple BANNED as
//   UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

const ID    = "aimc";
const TITLE = "Analog In-Memory Computing Attention · Gain-Cell Crossbar (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the AIMC organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/aimc/attend?seed=42&seq_len=128&dim=64&noise_sigma=0.05";

// data-viz hues — purple BANNED
const C_DIGITAL = 0x5b8dee;  // lattice-blue (exact digital baseline / crossbar rows)
const C_ANALOG  = 0x8a6bff;  // violet-blue (raw noisy analog pathway)
const C_CALIB   = 0x3af4c8;  // proof-teal (calibrated pathway / HUD accent)
const C_NOISE   = 0x6b7a86;  // grey (device-noise cue)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// crossbar + score-bar layout geometry
const GRID_N     = 8;       // crossbar rendered as GRID_N x GRID_N node lattice
const NODE_GAP   = 0.5;     // world-units between crossbar nodes
const BAR_GAP    = 0.5;     // world-units between score-bar columns along X
const MAX_BARS   = 24;      // cap on score-bar columns rendered (perf)
const MAX_BAR_H  = 5.0;     // world-units — score bar height at unit score
const MIN_BAR_H  = 0.04;    // floor height so a bar never fully vanishes

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor      = null;
let _crossbar   = [];               // Array<THREE.Mesh> — crossbar lattice nodes
let _crossLines = [];               // Array<THREE.Line> — crossbar row/column wires
let _barsDig    = [];               // Array<THREE.Mesh> — digital baseline score bars
let _barsAna    = [];               // Array<THREE.Mesh> — raw analog score bars
let _barsCal    = [];               // Array<THREE.Mesh> — calibrated score bars
let _query      = null;             // THREE.Mesh — pulsing query-drive marker

// live state
const S = {
  label:        null,
  seqLen:       null,   // seq_len
  dim:          null,   // dim
  noiseSigma:   null,   // noise_sigma
  analogMse:    null,   // analog_mse
  calibMse:     null,   // calibrated_mse
  calibGain:    null,   // calibration_gain
  accRecovered: null,   // accuracy_recovered_pct
  adcDacOps:    null,   // adc_dac_ops_avoided
  memMoveOps:   null,   // memory_move_reads_avoided
  totalOps:     null,   // total_ops_avoided
  energyClaim:  null,   // paper_energy_reduction_claim (PAPER's claim, not measured)
  latencyClaim: null,   // paper_latency_reduction_claim (PAPER's claim, not measured)
  digScores:    null,   // sample_digital_scores[]
  anaScores:    null,   // sample_analog_scores[]
  calScores:    null,   // sample_calibrated_scores[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(3, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCrossbar();
  _buildScoreBars();
  _buildQuery();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onAimc, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Idealized analog gain-cell crossbar: a GRID_N x GRID_N lattice of nodes with
// row + column wires. Each node stores a Key element; the query drives charge
// down the columns to accumulate the dot-product IN MEMORY.
function _buildCrossbar() {
  const THREE = _THREE;
  const nodeGeo = new THREE.OctahedronGeometry(0.09, 0);
  const originX = -5.0, baseY = 0.6, baseZ = -1.8;

  for (let r = 0; r < GRID_N; r++) {
    for (let c = 0; c < GRID_N; c++) {
      const mesh = new THREE.Mesh(
        nodeGeo,
        new THREE.MeshStandardMaterial({ color: C_NOISE, emissive: C_NOISE, emissiveIntensity: 0.2, transparent: true, opacity: 0.75 }),
      );
      mesh.position.set(originX + c * NODE_GAP, baseY + r * NODE_GAP, baseZ);
      _group.add(mesh);
      _crossbar.push(mesh);
    }
  }
  // row wires (lattice-blue) + column wires (proof-teal charge paths)
  for (let r = 0; r < GRID_N; r++) {
    const pts = [
      new THREE.Vector3(originX, baseY + r * NODE_GAP, baseZ),
      new THREE.Vector3(originX + (GRID_N - 1) * NODE_GAP, baseY + r * NODE_GAP, baseZ),
    ];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_DIGITAL, transparent: true, opacity: 0.3 }));
    _group.add(line); _crossLines.push(line);
  }
  for (let c = 0; c < GRID_N; c++) {
    const pts = [
      new THREE.Vector3(originX + c * NODE_GAP, baseY, baseZ),
      new THREE.Vector3(originX + c * NODE_GAP, baseY + (GRID_N - 1) * NODE_GAP, baseZ),
    ];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: C_CALIB, transparent: true, opacity: 0.25 }));
    _group.add(line); _crossLines.push(line);
  }
}

// Three interleaved score-bar columns per position: exact digital baseline
// (lattice-blue), raw noisy analog (violet-blue), calibrated (proof-teal).
// We scale each bar's Y in-place as live data arrives (no per-poll churn),
// base centered at y=0 via geometry translation so scaling grows upward.
function _buildScoreBars() {
  const THREE = _THREE;
  const barGeo = new THREE.BoxGeometry(0.12, 1, 0.12);
  barGeo.translate(0, 0.5, 0); // base at y=0; scaling Y grows upward

  function mkBar(color, emis) {
    const m = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: emis, transparent: true, opacity: 0.9 }),
    );
    m.scale.set(1, MIN_BAR_H, 1);
    m.visible = false;
    _group.add(m);
    return m;
  }
  for (let i = 0; i < MAX_BARS; i++) {
    const x = i * BAR_GAP;
    const bd = mkBar(C_DIGITAL, 0.3); bd.position.set(x - 0.14, 0, 0.4);
    const ba = mkBar(C_ANALOG, 0.34); ba.position.set(x,       0, 0.4);
    const bc = mkBar(C_CALIB, 0.42);  bc.position.set(x + 0.14, 0, 0.4);
    _barsDig.push(bd); _barsAna.push(ba); _barsCal.push(bc);
  }
}

function _buildQuery() {
  const THREE = _THREE;
  _query = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.28, 1),
    new THREE.MeshStandardMaterial({ color: C_CALIB, emissive: C_CALIB, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _query.position.set(-5.7, 2.4, -1.8);
  _group.add(_query);
}

// =============================================================================
// live data handler
// =============================================================================
function _onAimc(j) {
  // read honesty label VERBATIM — never upgrade. handle top-level 'label' OR
  // nested 'payload.label' to match our own module's shape.
  const lbl = (j && j.label != null) ? j.label
            : (j && j.payload && j.payload.label != null) ? j.payload.label
            : "MODELED";
  const src = (j && j.payload && typeof j.payload === "object") ? j.payload : j;

  S.label        = String(lbl).toUpperCase();
  S.seqLen       = typeof src.seq_len                 === "number" ? src.seq_len                 : null;
  S.dim          = typeof src.dim                     === "number" ? src.dim                     : null;
  S.noiseSigma   = typeof src.noise_sigma             === "number" ? src.noise_sigma             : null;
  S.analogMse    = typeof src.analog_mse              === "number" ? src.analog_mse              : null;
  S.calibMse     = typeof src.calibrated_mse          === "number" ? src.calibrated_mse          : null;
  S.calibGain    = typeof src.calibration_gain        === "number" ? src.calibration_gain        : null;
  S.accRecovered = typeof src.accuracy_recovered_pct  === "number" ? src.accuracy_recovered_pct  : null;
  S.adcDacOps    = typeof src.adc_dac_ops_avoided     === "number" ? src.adc_dac_ops_avoided     : null;
  S.memMoveOps   = typeof src.memory_move_reads_avoided === "number" ? src.memory_move_reads_avoided : null;
  S.totalOps     = typeof src.total_ops_avoided       === "number" ? src.total_ops_avoided       : null;
  S.energyClaim  = typeof src.paper_energy_reduction_claim  === "string" ? src.paper_energy_reduction_claim  : null;
  S.latencyClaim = typeof src.paper_latency_reduction_claim === "string" ? src.paper_latency_reduction_claim : null;
  S.digScores    = Array.isArray(src.sample_digital_scores)    ? src.sample_digital_scores    : null;
  S.anaScores    = Array.isArray(src.sample_analog_scores)     ? src.sample_analog_scores     : null;
  S.calScores    = Array.isArray(src.sample_calibrated_scores) ? src.sample_calibrated_scores : null;

  _updateBars();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the score bars + crossbar tint from live data
// =============================================================================
function _updateBars() {
  const live = S.state === "live";
  const dig = live && S.digScores ? S.digScores : [];
  const ana = live && S.anaScores ? S.anaScores : [];
  const cal = live && S.calScores ? S.calScores : [];

  // normalize bar heights against the max absolute digital score so the trio
  // is comparable per column.
  let maxAbs = 0.0;
  for (let i = 0; i < dig.length; i++) { const a = Math.abs(dig[i]); if (a > maxAbs) maxAbs = a; }
  if (maxAbs <= 1e-9) maxAbs = 1.0;

  for (let i = 0; i < MAX_BARS; i++) {
    const has = live && i < dig.length;
    _barsDig[i].visible = has;
    _barsAna[i].visible = has;
    _barsCal[i].visible = has;
    if (!has) continue;
    const hd = Math.max(MIN_BAR_H, (Math.abs(dig[i]) / maxAbs) * MAX_BAR_H);
    const ha = Math.max(MIN_BAR_H, (Math.abs(ana[i] != null ? ana[i] : dig[i]) / maxAbs) * MAX_BAR_H);
    const hc = Math.max(MIN_BAR_H, (Math.abs(cal[i] != null ? cal[i] : dig[i]) / maxAbs) * MAX_BAR_H);
    _barsDig[i].scale.y = hd;
    _barsAna[i].scale.y = ha;
    _barsCal[i].scale.y = hc;
  }

  // crossbar node tint: violet-blue when live (charge flowing), grey degraded.
  const nodeColor = live ? C_ANALOG : C_DIM;
  for (let n = 0; n < _crossbar.length; n++) {
    _crossbar[n].material.color.setHex(nodeColor);
    _crossbar[n].material.emissive.setHex(nodeColor);
    _crossbar[n].material.opacity = live ? 0.75 : 0.2;
  }
  for (let l = 0; l < _crossLines.length; l++) {
    _crossLines[l].material.opacity = live ? 0.28 : 0.08;
  }
  if (_query) {
    const qc = live ? C_CALIB : C_DIM;
    _query.material.color.setHex(qc);
    _query.material.emissive.setHex(qc);
    _query.material.opacity = live ? 0.85 : 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.11;
  if (_query) {
    _query.rotation.y += 0.02;
    _query.rotation.x += 0.011;
    const pulse = 1.0 + 0.14 * Math.sin(t * 0.004);
    _query.scale.setScalar(pulse);
  }
  // gentle shimmer along crossbar nodes to suggest charge accumulation
  for (let n = 0; n < _crossbar.length; n++) {
    const m = _crossbar[n];
    m.material.emissiveIntensity = 0.2 + 0.12 * (0.5 + 0.5 * Math.sin(t * 0.003 + n * 0.4));
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
    maxWidth: "min(94%,460px)",
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
    'Instead of moving the KV cache out of memory and through ADC/DAC converters, an analog ' +
    '<b>gain-cell crossbar</b> stores the Keys and computes query\u00b7key dot-products as a ' +
    'physical <b>charge-domain multiply-accumulate</b> in place. Bars per column compare the ' +
    'exact <b>digital</b> baseline (lattice-blue), the raw <b>analog</b> pathway with device ' +
    'noise (violet-blue), and the <b>calibrated</b> pathway (proof-teal) that recovers accuracy. ' +
    'Honesty label <b>MODELED</b> \u2014 a deterministic simulation on ordinary CPU floats, NOT ' +
    'real analog hardware. Energy/latency wins shown are the <b>paper\u2019s claim, not a measured ' +
    'SZL result</b>. 0 runtime CDN.';
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
  nm.textContent = "analog in-memory computing attention";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:58%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("ai-seqlen",  "seq_len (crossbar columns)"));
  grid.appendChild(kpiRow("ai-dim",     "dim (crossbar rows)"));
  grid.appendChild(kpiRow("ai-noise",   "noise_sigma (device imprecision)"));
  grid.appendChild(kpiRow("ai-anamse",  "analog_mse (raw, vs digital)"));
  grid.appendChild(kpiRow("ai-calmse",  "calibrated_mse (vs digital) \u2014 MODELED"));
  grid.appendChild(kpiRow("ai-acc",     "accuracy_recovered_pct"));
  grid.appendChild(kpiRow("ai-ops",     "total_ops_avoided (ADC/DAC + moves)"));
  grid.appendChild(kpiRow("ai-energy",  "energy reduction (paper\u2019s claim)"));
  grid.appendChild(kpiRow("ai-latency", "latency reduction (paper\u2019s claim)"));
  grid.appendChild(kpiRow("ai-label",   "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.innerHTML = "AIMC attention \u2014 Leroux et al. 2025, Nature Computational Science " +
    "(nature.com/articles/s43588-025-00854-1) \u00b7 IBM Research summary. MODELED \u00b7 not " +
    "claimed-as. Energy/latency = paper\u2019s claim, NOT a measured SZL figure.";
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
  pd.id = "ai-plain";
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
  const acc = S.accRecovered != null ? S.accRecovered.toFixed(1) + "%" : "loading\u2026";
  const ops = S.totalOps     != null ? S.totalOps.toLocaleString() : "loading\u2026";
  const nz  = S.noiseSigma   != null ? S.noiseSigma.toFixed(3) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Today a chip has to haul the model\u2019s attention \u201cmemory\u201d " +
    "(the KV cache) out of storage and convert it back and forth through analog\u2194digital " +
    "converters just to do the math \u2014 that shuttling is where most of the energy and time " +
    "goes. <b>Analog in-memory computing</b> stores those numbers as tiny electrical charges " +
    "and lets the math happen <i>inside the memory itself</i>: the query flows in as a voltage " +
    "and the answer literally adds itself up along each wire. Because the storage is analog it " +
    "is slightly imprecise (device noise, here <b>" + nz + "</b>), but a one-time <b>calibration</b> " +
    "step rescales the results and recovers about <b>" + acc + "</b> of the lost accuracy. Skipping " +
    "the conversions and the memory shuttling avoids roughly <b>" + ops + "</b> operations at this " +
    "toy scale. <b>Important honesty note:</b> the huge energy (up to ~100,000\u00d7) and latency " +
    "(up to ~100\u00d7) savings are the <b>research paper\u2019s published claim</b> for real analog " +
    "hardware \u2014 they are <b>NOT measured on real hardware here and NOT a measured SZL result</b>. " +
    "This view is a <b>MODELED</b> deterministic simulation running on an ordinary digital CPU, " +
    "not a run of the actual analog chip.";
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
  _set("ai-seqlen",  t || (S.seqLen != null ? S.seqLen.toLocaleString() : "\u2014"));
  _set("ai-dim",     t || (S.dim != null ? String(S.dim) : "\u2014"));
  _set("ai-noise",   t || fx(S.noiseSigma, 3));
  _set("ai-anamse",  t || fx(S.analogMse, 6));
  _set("ai-calmse",  t || fx(S.calibMse, 6));
  _set("ai-acc",     t || (S.accRecovered != null ? S.accRecovered.toFixed(2) + "%" : "\u2014"));
  _set("ai-ops",     t || (S.totalOps != null ? S.totalOps.toLocaleString() : "\u2014"));
  // energy/latency figures are the PAPER's claim, NOT a measured SZL result.
  _set("ai-energy",  t || (S.energyClaim != null ? S.energyClaim : "paper\u2019s claim, not measured SZL"));
  _set("ai-latency", t || (S.latencyClaim != null ? S.latencyClaim : "paper\u2019s claim, not measured SZL"));
  // honesty label verbatim — never upgraded
  _set("ai-label", t || (S.label || "MODELED"));
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
  _floor = null; _crossbar = []; _crossLines = [];
  _barsDig = []; _barsAna = []; _barsCal = []; _query = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.dim = S.noiseSigma = null;
  S.analogMse = S.calibMse = S.calibGain = S.accRecovered = null;
  S.adcDacOps = S.memMoveOps = S.totalOps = null;
  S.energyClaim = S.latencyClaim = null;
  S.digScores = S.anaScores = S.calScores = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
