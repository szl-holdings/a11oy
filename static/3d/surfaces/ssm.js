// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ssm.js — STATE-SPACE-MODEL (Mamba-3 successor) sequence-mixing organ for the
// holographic frontier ring.
//
// Renders a 3D ribbon/trajectory of a selective state-space scan's hidden state evolving
// over sequence steps, driven by a live snapshot from /api/killinchu/v1/ssm/scan. Two
// ribbons are drawn side by side: a REAL-valued state trajectory (decay-only diagonal SSM)
// and a COMPLEX-valued state trajectory (rotation-capable, the Mamba-3 addition) — so the
// state-tracking gap is directly visible as ribbon shape, not just a number. HUD shows
// real vs complex task accuracy plus the O(L) vs O(L^2) compute gap (sub-quadratic win).
// Honesty label "MODELED" is read VERBATIM from the JSON and displayed as-is; it is never
// upgraded.
//
// Surface export shape (mirrors interpretability.js / neuromorphic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   task                      — 'copy' | 'parity' | 'induction'
//   seq_len, state_dim        — scan dimensions
//   real_state_accuracy       — accuracy of the REAL-valued selective-SSM state tracker
//   complex_state_accuracy    — accuracy of the COMPLEX-valued state tracker (Mamba-3 add)
//   compute_flops_quadratic   — MODELED Transformer O(L^2) self-attention FLOPs
//   compute_flops_ssm         — MODELED SSM O(L) scan FLOPs
//   throughput_ratio          — quadratic / ssm (the sub-quadratic win)
//   sample.trajectory_real / trajectory_complex_magnitude — per-step hidden-state samples
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Mamba — Gu & Dao (2023) "Linear-Time Sequence Modeling with Selective State Spaces".
//     arXiv:2312.00752. https://arxiv.org/abs/2312.00752
//   Mamba-2 — Dao & Gu (2024) "Transformers are SSMs...Structured State Space Duality".
//     arXiv:2405.21060. https://arxiv.org/abs/2405.21060
//   state-spaces/mamba (official implementation, Apache-2.0):
//     https://github.com/state-spaces/mamba
//   Mamba-3 — Lahoti et al. (2026) "Mamba-3: Improved Sequence Modeling using State Space
//     Principles". arXiv:2603.15569 (ICLR 2026). https://arxiv.org/abs/2603.15569
//
// HONESTY LABELS: MODELED (deterministic simulation of the RECURRENCE; no trained
//   Mamba/Mamba-2/Mamba-3 checkpoint, no measured GPU benchmark). Read verbatim from
//   JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (real-state ribbon), violet-blue 0x8a6bff (complex-state
//   ribbon — data-viz only), proof-teal 0x3af4c8 (accent / plain-language). Purple BANNED
//   as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

import { createShowcase } from "./_showcase.js";

const ID    = "ssm";
const TITLE = "State-Space Model · Selective Scan (live, Mamba-3-style)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the SSM organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/ssm/scan?seed=42&seq_len=32&state_dim=16&task=parity";

// data-viz hues — purple BANNED
const C_REAL    = 0x5b8dee;  // lattice-blue (real-valued state ribbon)
const C_COMPLEX = 0x8a6bff;  // violet-blue (complex-valued state ribbon — data-viz only)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal accent (compute-gap bar / plain-language)
const C_GRID    = 0x1b3a44;  // floor / link colour

const MAX_STEPS = 64;   // ribbon vertex cap (matches endpoint seq_len ceiling in practice)
const RIBBON_LEN_WORLD = 14;  // world-units the ribbon spans along its axis
const RIBBON_SEP = 3.2;       // world-units separating the two ribbons (real vs complex)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _realLine = null, _complexLine = null;     // THREE.Line ribbons (trajectory curves)
let _realDots = null, _complexDots = null;     // THREE.Points per-step markers
let _gapBar = null;                            // THREE.Mesh — O(L) vs O(L^2) compute-gap bar
let _gapBarBg = null;

// live state
const S = {
  label:    null,
  task:     null,
  seqLen:   null,
  stateDim: null,
  realAcc:  null,
  complexAcc: null,
  flopsQuad: null,
  flopsSSM:  null,
  throughputRatio: null,
  trajReal: null,     // Array<Array<number>> per-step real-channel state vector
  trajComplexMag: null, // Array<Array<number>> per-step complex-channel magnitude vector
  state:    "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 19);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRibbons();
  _buildGapBar();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onScan, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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
}

function _emptyRibbonPoints() {
  const pts = [];
  for (let i = 0; i < MAX_STEPS; i++) pts.push(new (_THREE.Vector3)(0, 0, 0));
  return pts;
}

function _buildRibbons() {
  const THREE = _THREE;

  // REAL-state ribbon (lattice-blue), offset to one side
  const realGeo = new THREE.BufferGeometry().setFromPoints(_emptyRibbonPoints());
  _realLine = new THREE.Line(realGeo, new THREE.LineBasicMaterial({ color: C_REAL, transparent: true, opacity: 0.85, linewidth: 2 }));
  _realLine.position.x = -RIBBON_SEP / 2;
  _group.add(_realLine);

  _realDots = new THREE.Points(realGeo, new THREE.PointsMaterial({ color: C_REAL, size: 0.12, transparent: true, opacity: 0.9 }));
  _realDots.position.x = -RIBBON_SEP / 2;
  _group.add(_realDots);

  // COMPLEX-state ribbon (violet-blue), offset to the other side
  const complexGeo = new THREE.BufferGeometry().setFromPoints(_emptyRibbonPoints());
  _complexLine = new THREE.Line(complexGeo, new THREE.LineBasicMaterial({ color: C_COMPLEX, transparent: true, opacity: 0.85, linewidth: 2 }));
  _complexLine.position.x = RIBBON_SEP / 2;
  _group.add(_complexLine);

  _complexDots = new THREE.Points(complexGeo, new THREE.PointsMaterial({ color: C_COMPLEX, size: 0.12, transparent: true, opacity: 0.9 }));
  _complexDots.position.x = RIBBON_SEP / 2;
  _group.add(_complexDots);
}

function _buildGapBar() {
  const THREE = _THREE;
  // background track (grey) + foreground bar (teal) visualizing O(L) vs O(L^2) compute gap.
  _gapBarBg = new THREE.Mesh(
    new THREE.BoxGeometry(8, 0.18, 0.18),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, transparent: true, opacity: 0.35 }),
  );
  _gapBarBg.position.set(0, -0.6, 6);
  _group.add(_gapBarBg);

  _gapBar = new THREE.Mesh(
    new THREE.BoxGeometry(0.4, 0.22, 0.22),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4 }),
  );
  _gapBar.position.set(-3.8, -0.6, 6);
  _group.add(_gapBar);
}

// =============================================================================
// live data handler
// =============================================================================
function _onScan(j) {
  // read honesty label VERBATIM — never upgrade
  S.label      = (j.label || "MODELED").toUpperCase();
  S.task       = typeof j.task === "string" ? j.task : null;
  S.seqLen     = typeof j.seq_len === "number" ? j.seq_len : null;
  S.stateDim   = typeof j.state_dim === "number" ? j.state_dim : null;
  S.realAcc    = typeof j.real_state_accuracy === "number" ? j.real_state_accuracy : null;
  S.complexAcc = typeof j.complex_state_accuracy === "number" ? j.complex_state_accuracy : null;
  S.flopsQuad  = typeof j.compute_flops_quadratic === "number" ? j.compute_flops_quadratic : null;
  S.flopsSSM   = typeof j.compute_flops_ssm === "number" ? j.compute_flops_ssm : null;
  S.throughputRatio = typeof j.throughput_ratio === "number" ? j.throughput_ratio : null;

  const sample = j.sample || {};
  S.trajReal       = Array.isArray(sample.trajectory_real) ? sample.trajectory_real : null;
  S.trajComplexMag = Array.isArray(sample.trajectory_complex_magnitude) ? sample.trajectory_complex_magnitude : null;

  _updateRibbons();
  _updateGapBar();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives ribbon shape from the live trajectory
// =============================================================================
function _vecNorm(vec) {
  // L2 norm of a per-step state vector (collapses state_dim channels to one scalar height)
  let s = 0;
  for (let i = 0; i < vec.length; i++) s += vec[i] * vec[i];
  return Math.sqrt(s);
}

function _trajToPoints(traj) {
  const THREE = _THREE;
  const pts = [];
  if (!traj || !traj.length) {
    for (let i = 0; i < MAX_STEPS; i++) pts.push(new THREE.Vector3(0, 0, 0));
    return pts;
  }
  const n = Math.min(traj.length, MAX_STEPS);
  // normalize height by the max norm across the trajectory so ribbons are comparable
  let maxNorm = 0.0001;
  for (let i = 0; i < n; i++) maxNorm = Math.max(maxNorm, _vecNorm(traj[i]));
  for (let i = 0; i < n; i++) {
    const z = (i / Math.max(n - 1, 1)) * RIBBON_LEN_WORLD - RIBBON_LEN_WORLD / 2;
    const h = (_vecNorm(traj[i]) / maxNorm) * 3.0;  // scaled hidden-state magnitude -> height
    // slight lateral wobble from the first channel's raw value, for visual richness
    const lateral = traj[i][0] !== undefined ? Math.max(-1, Math.min(1, traj[i][0])) * 0.5 : 0;
    pts.push(new THREE.Vector3(lateral, h, z));
  }
  // pad remaining slots by repeating the last point (keeps buffer size constant)
  const last = pts[pts.length - 1] || new THREE.Vector3(0, 0, 0);
  while (pts.length < MAX_STEPS) pts.push(last.clone());
  return pts;
}

function _updateRibbons() {
  const live = S.state === "live";
  const THREE = _THREE;

  const realPts = live ? _trajToPoints(S.trajReal) : _emptyRibbonPoints();
  const complexPts = live ? _trajToPoints(S.trajComplexMag) : _emptyRibbonPoints();

  if (_realLine) {
    _realLine.geometry.setFromPoints(realPts);
    _realLine.geometry.computeBoundingSphere();
    const col = live ? C_REAL : C_DIM;
    _realLine.material.color.setHex(col);
    _realLine.material.opacity = live ? 0.85 : 0.25;
  }
  if (_realDots) {
    _realDots.geometry.setFromPoints(realPts);
    const col = live ? C_REAL : C_DIM;
    _realDots.material.color.setHex(col);
    _realDots.material.opacity = live ? 0.9 : 0.2;
  }
  if (_complexLine) {
    _complexLine.geometry.setFromPoints(complexPts);
    _complexLine.geometry.computeBoundingSphere();
    const col = live ? C_COMPLEX : C_DIM;
    _complexLine.material.color.setHex(col);
    _complexLine.material.opacity = live ? 0.85 : 0.25;
  }
  if (_complexDots) {
    _complexDots.geometry.setFromPoints(complexPts);
    const col = live ? C_COMPLEX : C_DIM;
    _complexDots.material.color.setHex(col);
    _complexDots.material.opacity = live ? 0.9 : 0.2;
  }
}

function _updateGapBar() {
  if (!_gapBar) return;
  const live = S.state === "live";
  // bar length encodes log10(throughput_ratio) clamped to a reasonable visual range
  const ratio = (live && S.throughputRatio) ? S.throughputRatio : 1;
  const logRatio = Math.max(0, Math.min(4, Math.log10(Math.max(ratio, 1))));  // 0..4 decades
  const len = 0.4 + logRatio * 1.9;  // world units
  _gapBar.scale.x = len / 0.4;
  _gapBar.position.x = -3.8 + (len / 0.4) * 0.2;
  const col = live ? C_ACCENT : C_DIM;
  _gapBar.material.color.setHex(col);
  _gapBar.material.emissive.setHex(col);
  _gapBar.material.emissiveIntensity = live ? 0.4 : 0.15;
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00010) * 0.15;
  if (_realLine) _realLine.rotation.y += 0.0015;
  if (_complexLine) _complexLine.rotation.y += 0.0015;
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "selective scan", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A <b>selective state-space scan</b> (h<sub>t</sub> = A(x<sub>t</sub>)\u00b7h<sub>t-1</sub> + B(x<sub>t</sub>)\u00b7x<sub>t</sub>) ' +
    'runs over a synthetic sequence task. The <b style="color:#5b8dee">blue ribbon</b> is a ' +
    '<b>real-valued</b> state (decay-only); the <b style="color:#8a6bff">violet ribbon</b> is a ' +
    '<b>complex-valued</b> state (decay + rotation \u2014 the Mamba-3 addition). Honesty label ' +
    '<b>MODELED</b> (a simulation of the recurrence \u2014 no trained checkpoint, no measured GPU ' +
    'benchmark). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "ssm";
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

  grid.appendChild(kpiRow("ssm-task",     "task"));
  grid.appendChild(kpiRow("ssm-dims",     "seq_len \u00d7 state_dim"));
  grid.appendChild(kpiRow("ssm-real",     "real-state accuracy"));
  grid.appendChild(kpiRow("ssm-complex",  "complex-state accuracy (Mamba-3)"));
  grid.appendChild(kpiRow("ssm-flopsq",   "compute FLOPs \u2014 O(L\u00b2) attention"));
  grid.appendChild(kpiRow("ssm-flopss",   "compute FLOPs \u2014 O(L) SSM scan"));
  grid.appendChild(kpiRow("ssm-ratio",    "throughput ratio (quad / ssm)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Gu & Dao arXiv:2312.00752 (Mamba) \u00b7 Dao & Gu arXiv:2405.21060 (Mamba-2) \u00b7 Lahoti et al. arXiv:2603.15569 (Mamba-3, complex-valued state tracking) \u00b7 github.com/state-spaces/mamba. MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ssm-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const task = S.task || "loading\u2026";
  const real = S.realAcc != null ? (S.realAcc * 100).toFixed(1) + "%" : "loading\u2026";
  const cplx = S.complexAcc != null ? (S.complexAcc * 100).toFixed(1) + "%" : "loading\u2026";
  const ratio = S.throughputRatio != null ? S.throughputRatio.toFixed(1) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Transformers compare every token to every other token, so their " +
    "compute grows with the <i>square</i> of sequence length (O(L\u00b2)). A <b>state-space model</b> " +
    "(the architecture family behind Mamba) instead keeps a running summary (\u201cstate\u201d) that updates " +
    "once per token, so compute grows only <i>linearly</i> (O(L)) \u2014 our modeled FLOP counts show " +
    "roughly a <b>" + ratio + "</b> compute advantage at this sequence length. But early state-space " +
    "models had a weakness: a real-number-only state can only fade, not <i>flip</i>, so it fails at " +
    "exact tasks like <b>" + task + "</b> (here: <b>" + real + "</b> accuracy). Mamba-3's key addition is " +
    "letting the state be a <b>complex number</b> \u2014 it can rotate, which lets it flip sign exactly " +
    "when needed, jumping accuracy to <b>" + cplx + "</b>. " +
    "Plain: linear-cost sequence models are catching up to Transformers not just on speed, but on " +
    "exact reasoning tasks. This view is a <b>MODELED</b> simulation of the mechanism, not a trained " +
    "production model.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function fexp(v) { return typeof v === "number" ? v.toExponential(3) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("ssm-task",     t || (S.task || "\u2014"));
  _set("ssm-dims",     t || ((S.seqLen != null && S.stateDim != null) ? `${S.seqLen} \u00d7 ${S.stateDim}` : "\u2014"));
  _set("ssm-real",     t || (S.realAcc != null ? (S.realAcc * 100).toFixed(2) + "%" : "\u2014"));
  _set("ssm-complex",  t || (S.complexAcc != null ? (S.complexAcc * 100).toFixed(2) + "%" : "\u2014"));
  _set("ssm-flopsq",   t || fexp(S.flopsQuad));
  _set("ssm-flopss",   t || fexp(S.flopsSSM));
  _set("ssm-ratio",    t || (S.throughputRatio != null ? S.throughputRatio.toFixed(2) + "\u00d7" : "\u2014"));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "selective scan" });
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
  _group = _show = null;
  _realLine = _complexLine = _realDots = _complexDots = _gapBar = _gapBarBg = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.task = S.seqLen = S.stateDim = null;
  S.realAcc = S.complexAcc = S.flopsQuad = S.flopsSSM = S.throughputRatio = null;
  S.trajReal = S.trajComplexMag = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
