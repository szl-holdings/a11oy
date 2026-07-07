// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/testtime.js — TEST-TIME-COMPUTE / REASONING-SCALING-LAWS organ for the
// holographic frontier ring. The THIRD scaling axis (alongside pretrain scaling and
// post-train scaling): how much extra INFERENCE-time compute buys how much accuracy.
//
// Renders two 3D growing curves driven by a live closed-form snapshot from
// /api/killinchu/v1/testtime/scaling:
//   1. pass@N (best-of-N / repeated-sampling coverage) — a curve that climbs across
//      N = 1,2,4,...,256 parallel samples.
//   2. sequential revision accuracy vs number of reasoning/revision steps — a curve
//      with diminishing returns as k grows.
// A HUD shows accuracy climbing as compute (N / steps) increases, plus the derived
// scaling_exponent and effective_oom_multiplier. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors neuromorphic.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   base_accuracy, N_samples, pass_at_N, pass_at_N_curve[]
//   sequential_steps, revised_accuracy, revised_accuracy_curve[]
//   scaling_exponent, effective_oom_multiplier
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   DeepSeek-R1 (RL reasoning / long CoT): DeepSeek-AI et al. 2025, arXiv:2501.12948
//     https://arxiv.org/abs/2501.12948
//   Scaling LLM Test-Time Compute Optimally: Snell et al. 2024, arXiv:2408.03314
//     https://arxiv.org/abs/2408.03314
//   Large Language Monkeys (repeated sampling / pass@N): Brown et al. 2024, arXiv:2407.21787
//     https://arxiv.org/abs/2407.21787
//
// HONESTY LABELS: MODELED (closed-form scaling-law simulation; no LLM calls, no live
//   model eval). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (pass@N curve), violet-blue 0x8a6bff (revision curve),
//   proof-teal 0x3af4c8 (HUD accent / rising-compute marker). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "testtime";
const TITLE = "Test-Time Compute · Reasoning-Scaling Laws (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the test-time-compute organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/testtime/scaling?seed=42&p=0.2&N=64&steps=8";

// data-viz hues — purple BANNED
const C_PASSN  = 0x5b8dee;  // lattice-blue (pass@N curve)
const C_REVISE = 0x8a6bff;  // violet-blue (sequential revision curve — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (HUD / rising-compute marker)
const C_GRID   = 0x1b3a44;  // floor / link colour

// curve layout geometry
const CURVE_LEN   = 10.0;   // world-units along X (compute axis, log-spaced)
const CURVE_DEPTH = 3.0;    // world-units separating the two curve lanes (Z)
const CURVE_HEIGHT= 5.0;    // world-units of max curve rise (Y, accuracy axis)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _passLine = null;     // THREE.Line — pass@N growing curve
let _passDots = [];       // Array<THREE.Mesh> — markers along pass@N curve
let _revLine  = null;     // THREE.Line — sequential-revision growing curve
let _revDots  = [];       // Array<THREE.Mesh> — markers along revision curve
let _marker   = null;     // THREE.Mesh — HUD "current compute" marker (pulses)
let _floor    = null;

// live state
const S = {
  label:        null,
  baseAcc:      null,   // base_accuracy
  N:            null,   // N_samples
  passAtN:      null,   // pass_at_N
  passCurve:    null,   // pass_at_N_curve[]
  steps:        null,   // sequential_steps
  revAcc:       null,   // revised_accuracy
  revCurve:     null,   // revised_accuracy_curve[]
  scalingExp:   null,   // scaling_exponent
  effOom:       null,   // effective_oom_multiplier
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(2, 8, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(2, 2.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCurves();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onScaling, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate curve line geometries with a fixed max point-count; we update
// point positions in-place as live data arrives (no per-poll geometry churn).
const _MAX_PTS = 16;

function _buildCurves() {
  const THREE = _THREE;

  // pass@N curve lane (Z = 0)
  {
    const pts = new Array(_MAX_PTS).fill(0).map(() => new THREE.Vector3(0, 0, 0));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_PASSN, transparent: true, opacity: 0.85, linewidth: 2 });
    _passLine = new THREE.Line(geo, mat);
    _group.add(_passLine);

    const dotGeo = new THREE.SphereGeometry(0.09, 10, 8);
    for (let i = 0; i < _MAX_PTS; i++) {
      const m = new THREE.Mesh(dotGeo, new THREE.MeshStandardMaterial({ color: C_PASSN, emissive: C_PASSN, emissiveIntensity: 0.3 }));
      m.visible = false;
      _group.add(m);
      _passDots.push(m);
    }
  }

  // sequential-revision curve lane (Z = CURVE_DEPTH)
  {
    const pts = new Array(_MAX_PTS).fill(0).map(() => new THREE.Vector3(0, 0, CURVE_DEPTH));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_REVISE, transparent: true, opacity: 0.85, linewidth: 2 });
    _revLine = new THREE.Line(geo, mat);
    _group.add(_revLine);

    const dotGeo = new THREE.SphereGeometry(0.09, 10, 8);
    for (let i = 0; i < _MAX_PTS; i++) {
      const m = new THREE.Mesh(dotGeo, new THREE.MeshStandardMaterial({ color: C_REVISE, emissive: C_REVISE, emissiveIntensity: 0.3 }));
      m.visible = false;
      _group.add(m);
      _revDots.push(m);
    }
  }

  // baseline axes (compute axis + accuracy axis ticks), grey, data-viz only
  const axisPts = [
    new THREE.Vector3(0, 0, -0.6), new THREE.Vector3(0, CURVE_HEIGHT, -0.6),          // accuracy axis
    new THREE.Vector3(0, 0, -0.6), new THREE.Vector3(CURVE_LEN, 0, -0.6),             // compute axis
  ];
  const axisGeo = new THREE.BufferGeometry().setFromPoints(axisPts);
  const axisLine = new THREE.LineSegments(axisGeo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.4 }));
  _group.add(axisLine);
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.22, 1),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, 0, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onScaling(j) {
  // read honesty label VERBATIM — never upgrade
  S.label      = (j.label || "MODELED").toUpperCase();
  S.baseAcc    = typeof j.base_accuracy    === "number" ? j.base_accuracy    : null;
  S.N          = typeof j.N_samples        === "number" ? j.N_samples        : null;
  S.passAtN    = typeof j.pass_at_N        === "number" ? j.pass_at_N        : null;
  S.passCurve  = Array.isArray(j.pass_at_N_curve) ? j.pass_at_N_curve : null;
  S.steps      = typeof j.sequential_steps === "number" ? j.sequential_steps : null;
  S.revAcc     = typeof j.revised_accuracy === "number" ? j.revised_accuracy : null;
  S.revCurve   = Array.isArray(j.revised_accuracy_curve) ? j.revised_accuracy_curve : null;
  S.scalingExp = typeof j.scaling_exponent === "number" ? j.scaling_exponent : null;
  S.effOom     = typeof j.effective_oom_multiplier === "number" ? j.effective_oom_multiplier : null;

  _updateCurves();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the two growing curves from live data
// =============================================================================
function _logX(n, nMax) {
  // log-spaced compute axis: n=1 -> x=0, n=nMax -> x=CURVE_LEN
  const lo = Math.log10(Math.max(1, 1));
  const hi = Math.log10(Math.max(2, nMax));
  const v  = Math.log10(Math.max(1, n));
  return CURVE_LEN * (v - lo) / Math.max(1e-6, (hi - lo));
}

function _linX(k, kMax) {
  return CURVE_LEN * (k / Math.max(1, kMax));
}

function _updateCurves() {
  const THREE = _THREE;
  const live = S.state === "live";

  // --- pass@N curve ---
  if (live && S.passCurve && S.passCurve.length) {
    const nMax = S.passCurve.reduce((m, r) => Math.max(m, r.n), 1);
    const pos = _passLine.geometry.attributes.position;
    const n = Math.min(_MAX_PTS, S.passCurve.length);
    for (let i = 0; i < _MAX_PTS; i++) {
      if (i < n) {
        const row = S.passCurve[i];
        const x = _logX(row.n, nMax);
        const y = row.pass_at_n * CURVE_HEIGHT;
        pos.setXYZ(i, x, y, 0);
        _passDots[i].position.set(x, y, 0);
        _passDots[i].visible = true;
      } else {
        // repeat last point so the line doesn't dangle at origin
        const row = S.passCurve[n - 1];
        const x = _logX(row.n, nMax);
        const y = row.pass_at_n * CURVE_HEIGHT;
        pos.setXYZ(i, x, y, 0);
        _passDots[i].visible = false;
      }
    }
    pos.needsUpdate = true;
    _passLine.geometry.computeBoundingSphere();
    _passLine.material.color.setHex(C_PASSN);
    _passLine.material.opacity = 0.85;
  } else {
    _passDots.forEach((d) => { d.visible = false; });
    _passLine.material.color.setHex(C_DIM);
    _passLine.material.opacity = 0.25;
  }

  // --- sequential-revision curve ---
  if (live && S.revCurve && S.revCurve.length) {
    const kMax = S.revCurve.reduce((m, r) => Math.max(m, r.k), 1);
    const pos = _revLine.geometry.attributes.position;
    const n = Math.min(_MAX_PTS, S.revCurve.length);
    for (let i = 0; i < _MAX_PTS; i++) {
      if (i < n) {
        const row = S.revCurve[i];
        const x = _linX(row.k, kMax);
        const y = row.revised_accuracy * CURVE_HEIGHT;
        pos.setXYZ(i, x, y, CURVE_DEPTH);
        _revDots[i].position.set(x, y, CURVE_DEPTH);
        _revDots[i].visible = true;
      } else {
        const row = S.revCurve[n - 1];
        const x = _linX(row.k, kMax);
        const y = row.revised_accuracy * CURVE_HEIGHT;
        pos.setXYZ(i, x, y, CURVE_DEPTH);
        _revDots[i].visible = false;
      }
    }
    pos.needsUpdate = true;
    _revLine.geometry.computeBoundingSphere();
    _revLine.material.color.setHex(C_REVISE);
    _revLine.material.opacity = 0.85;
  } else {
    _revDots.forEach((d) => { d.visible = false; });
    _revLine.material.color.setHex(C_DIM);
    _revLine.material.opacity = 0.25;
  }

  // --- HUD marker: sits at the current (N, pass@N) point, pulses proof-teal ---
  if (_marker) {
    if (live && S.passAtN != null && S.N != null && S.passCurve && S.passCurve.length) {
      const nMax = S.passCurve.reduce((m, r) => Math.max(m, r.n), 1);
      const x = _logX(S.N, nMax);
      const y = S.passAtN * CURVE_HEIGHT;
      _marker.position.set(x, y, 0);
      _marker.material.color.setHex(C_ACCENT);
      _marker.material.emissive.setHex(C_ACCENT);
      _marker.material.opacity = 0.85;
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00010) * 0.15;
  if (_marker) {
    _marker.rotation.y += 0.02;
    _marker.rotation.x += 0.01;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _marker.scale.setScalar(pulse);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "test-time compute", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The <b>third scaling axis</b> (alongside pretrain and post-train): spend more ' +
    '<b>inference-time compute</b> \u2014 parallel repeated sampling (<b>pass@N</b>) or ' +
    'sequential reasoning steps \u2014 and trade it for accuracy. Honesty label ' +
    '<b>MODELED</b> (closed-form scaling law; no LLM calls, no live model eval). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "test-time-compute";
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

  grid.appendChild(kpiRow("tt-base",  "base accuracy p"));
  grid.appendChild(kpiRow("tt-n",     "N samples (parallel compute)"));
  grid.appendChild(kpiRow("tt-passn", "pass@N \u2014 MODELED"));
  grid.appendChild(kpiRow("tt-steps", "sequential steps k"));
  grid.appendChild(kpiRow("tt-rev",   "revised accuracy \u2014 MODELED"));
  grid.appendChild(kpiRow("tt-exp",   "scaling exponent"));
  grid.appendChild(kpiRow("tt-oom",   "effective compute (orders of magnitude)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "DeepSeek-R1, DeepSeek-AI et al. arXiv:2501.12948 \u00b7 Snell et al. arXiv:2408.03314 (optimal test-time compute) \u00b7 Brown et al. arXiv:2407.21787 (Large Language Monkeys / pass@N). MODELED \u00b7 not claimed-as.";
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
  pd.id = "tt-plain";
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
  const n    = S.N != null ? String(S.N) : "loading\u2026";
  const pAtN = S.passAtN != null ? (S.passAtN * 100).toFixed(2) + "%" : "loading\u2026";
  const steps= S.steps != null ? String(S.steps) : "loading\u2026";
  const rAcc = S.revAcc != null ? (S.revAcc * 100).toFixed(2) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of training a bigger model, you can spend more " +
    "compute <i>at answer time</i>. Drawing <b>" + n + " independent samples</b> and " +
    "keeping the best one (\u201cbest-of-N\u201d) pushes the chance of getting a correct " +
    "answer to <b>" + pAtN + "</b>. Letting the model take <b>" + steps + " sequential " +
    "reasoning/revision steps</b> instead pushes accuracy to <b>" + rAcc + "</b>, but with " +
    "<i>diminishing returns</i> \u2014 each extra step helps less than the last. " +
    "Plain: this is the third lever for making AI smarter \u2014 next to \u201ctrain a bigger " +
    "model\u201d and \u201cfine-tune it more\u201d, you can also just let it \u201cthink longer\u201d " +
    "at inference time. This view is a <b>MODELED</b> closed-form scaling law, not a live " +
    "model evaluation.";
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
  _set("tt-base",  t || pct(S.baseAcc, 2));
  _set("tt-n",     t || (S.N != null ? String(S.N) : "\u2014"));
  _set("tt-passn", t || pct(S.passAtN, 4));
  _set("tt-steps", t || (S.steps != null ? String(S.steps) : "\u2014"));
  _set("tt-rev",   t || pct(S.revAcc, 4));
  _set("tt-exp",   t || fx(S.scalingExp, 6));
  _set("tt-oom",   t || fx(S.effOom, 3));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "test-time compute" });
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
  _passLine = null; _passDots = []; _revLine = null; _revDots = []; _marker = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.baseAcc = S.N = S.passAtN = S.passCurve = null;
  S.steps = S.revAcc = S.revCurve = S.scalingExp = S.effOom = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
