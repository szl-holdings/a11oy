// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/agenttts.js — AGENT TEST-TIME-COMPUTE (multi-agent TTC) organ for the
// holographic frontier ring. Test-time compute scaling applied to LLM AGENTS
// (multi-step tool-use / coordinated reasoning) — DISTINCT from the single-model
// `testtime` surface. Two honest agent-specific facts change the scaling story:
//   1. single-agent success COMPOUNDS over the trajectory: depth-D task with per-step
//      success s succeeds end-to-end only with p = s^D (the "depth tax").
//   2. selection uses a REAL, imperfect verifier (precision v): best-of-N agents only
//      helps to the extent the verifier can pick a correct trajectory, so the honest
//      ceiling of verifier-guided best-of-N is bounded by v — never 1.0.
//
// Renders three 3D growing curves driven by a live closed-form snapshot from
// /api/a11oy/v1/agenttts/scaling:
//   1. coverage(N)  — perfect-oracle best-of-N agents (a correct trajectory EXISTS).
//   2. selected(N)  — verifier-guided realised success (coverage * verifier), the gap
//      to coverage is the honest COST of an imperfect verifier.
//   3. sequential revision accuracy vs revision rounds R — diminishing returns.
// A HUD shows success climbing as agent compute (N breadth / R depth) increases, plus
// the derived scaling_exponent, effective_oom_multiplier and advisory_trust (capped at
// 0.97). Honesty label "MODELED" is read VERBATIM and displayed as-is; never upgraded.
//
// Surface export shape (mirrors testtime.js / neuromorphic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   step_success, task_depth, p_single, verifier_precision
//   N_agents, coverage_at_N, selected_at_N, verifier_gap, breadth_curve[]
//   revisions, revised_accuracy, revision_curve[]
//   scaling_exponent, effective_oom_multiplier, advisory_trust
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Scaling LLM Test-Time Compute Optimally: Snell et al. 2024, arXiv:2408.03314
//     https://arxiv.org/abs/2408.03314
//   Large Language Monkeys (repeated sampling / pass@N): Brown et al. 2024, arXiv:2407.21787
//     https://arxiv.org/abs/2407.21787
//   PaCoRe (parallel coordinated reasoning / agent TTC): Hu et al. 2026, arXiv:2601.05593
//     https://arxiv.org/abs/2601.05593
//
// HONESTY LABELS: MODELED (closed-form agent-TTC scaling; no agent runs, no LLM calls).
//   Read verbatim from JSON; never upgraded here. Λ advisory-only (never proven).
// COLOURS: lattice-blue 0x5b8dee (coverage / oracle), proof-teal 0x3af4c8 (verifier-guided
//   selected / HUD accent), violet-blue 0x8a6bff (revision curve). Purple BANNED as UI/bg.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100% (capped 0.97).

import { createShowcase } from "./_showcase.js";

const ID    = "agenttts";
const TITLE = "Agent Test-Time Compute · Multi-Agent TTC (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted backend (same-origin, szl_agent_tts.py):
// exact closed-form best-of-N AGENTS + verifier-guided selection + sequential-revision
// scaling (label MODELED, read verbatim). No cross-origin dependency — this surface is
// a11oy-native from day one.
const EP = "/api/a11oy/v1/agenttts/scaling?seed=42&s=0.7&depth=5&N=64&revisions=8&verifier=0.85";

// data-viz hues — purple BANNED
const C_COVER  = 0x5b8dee;  // lattice-blue (oracle coverage curve)
const C_SELECT = 0x3af4c8;  // proof-teal (verifier-guided selected curve / HUD accent)
const C_REVISE = 0x8a6bff;  // violet-blue (sequential revision curve — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// curve layout geometry
const CURVE_LEN    = 10.0;  // world-units along X (compute axis, log-spaced)
const CURVE_DEPTH  = 3.0;   // world-units separating curve lanes (Z)
const CURVE_HEIGHT = 5.0;   // world-units of max curve rise (Y, success axis)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _coverLine = null;    // THREE.Line — oracle coverage growing curve
let _coverDots = [];      // Array<THREE.Mesh> — markers along coverage curve
let _selLine  = null;     // THREE.Line — verifier-guided selected growing curve
let _selDots  = [];       // Array<THREE.Mesh> — markers along selected curve
let _revLine  = null;     // THREE.Line — sequential-revision growing curve
let _revDots  = [];       // Array<THREE.Mesh> — markers along revision curve
let _marker   = null;     // THREE.Mesh — HUD "current selected" marker (pulses)
let _floor    = null;

// live state
const S = {
  label:        null,
  stepSucc:     null,   // step_success
  depth:        null,   // task_depth
  pSingle:      null,   // p_single
  verifier:     null,   // verifier_precision
  N:            null,   // N_agents
  coverAtN:     null,   // coverage_at_N
  selAtN:       null,   // selected_at_N
  vGap:         null,   // verifier_gap
  breadth:      null,   // breadth_curve[]
  revisions:    null,   // revisions
  revAcc:       null,   // revised_accuracy
  revCurve:     null,   // revision_curve[]
  scalingExp:   null,   // scaling_exponent
  effOom:       null,   // effective_oom_multiplier
  advTrust:     null,   // advisory_trust
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

function _mkLine(color, z) {
  const THREE = _THREE;
  const pts = new Array(_MAX_PTS).fill(0).map(() => new THREE.Vector3(0, 0, z));
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.85, linewidth: 2 });
  const line = new THREE.Line(geo, mat);
  _group.add(line);
  const dots = [];
  const dotGeo = new THREE.SphereGeometry(0.09, 10, 8);
  for (let i = 0; i < _MAX_PTS; i++) {
    const m = new THREE.Mesh(dotGeo, new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.3 }));
    m.visible = false;
    _group.add(m);
    dots.push(m);
  }
  return { line, dots };
}

function _buildCurves() {
  const THREE = _THREE;

  // oracle coverage lane (Z = 0) + verifier-guided selected lane (same Z, drawn under it)
  const cover = _mkLine(C_COVER, 0);   _coverLine = cover.line; _coverDots = cover.dots;
  const sel   = _mkLine(C_SELECT, 0);  _selLine  = sel.line;    _selDots  = sel.dots;
  // sequential-revision lane (Z = CURVE_DEPTH)
  const rev   = _mkLine(C_REVISE, CURVE_DEPTH); _revLine = rev.line; _revDots = rev.dots;

  // baseline axes (compute axis + success axis ticks), grey, data-viz only
  const axisPts = [
    new THREE.Vector3(0, 0, -0.6), new THREE.Vector3(0, CURVE_HEIGHT, -0.6),          // success axis
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
    new THREE.MeshStandardMaterial({ color: C_SELECT, emissive: C_SELECT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, 0, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onScaling(j) {
  // read honesty label VERBATIM — never upgrade
  S.label     = (j.label || "MODELED").toUpperCase();
  S.stepSucc  = typeof j.step_success      === "number" ? j.step_success      : null;
  S.depth     = typeof j.task_depth        === "number" ? j.task_depth        : null;
  S.pSingle   = typeof j.p_single          === "number" ? j.p_single          : null;
  S.verifier  = typeof j.verifier_precision=== "number" ? j.verifier_precision: null;
  S.N         = typeof j.N_agents          === "number" ? j.N_agents          : null;
  S.coverAtN  = typeof j.coverage_at_N     === "number" ? j.coverage_at_N     : null;
  S.selAtN    = typeof j.selected_at_N     === "number" ? j.selected_at_N     : null;
  S.vGap      = typeof j.verifier_gap      === "number" ? j.verifier_gap      : null;
  S.breadth   = Array.isArray(j.breadth_curve) ? j.breadth_curve : null;
  S.revisions = typeof j.revisions         === "number" ? j.revisions         : null;
  S.revAcc    = typeof j.revised_accuracy  === "number" ? j.revised_accuracy  : null;
  S.revCurve  = Array.isArray(j.revision_curve) ? j.revision_curve : null;
  S.scalingExp= typeof j.scaling_exponent  === "number" ? j.scaling_exponent  : null;
  S.effOom    = typeof j.effective_oom_multiplier === "number" ? j.effective_oom_multiplier : null;
  S.advTrust  = typeof j.advisory_trust    === "number" ? j.advisory_trust    : null;

  _updateCurves();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the three growing curves from live data
// =============================================================================
function _logX(n, nMax) {
  const lo = 0;                                   // log10(1)
  const hi = Math.log10(Math.max(2, nMax));
  const v  = Math.log10(Math.max(1, n));
  return CURVE_LEN * (v - lo) / Math.max(1e-6, (hi - lo));
}

function _linX(k, kMax) {
  return CURVE_LEN * (k / Math.max(1, kMax));
}

// drive one breadth curve (line + dots) from rows[].<field>, log-spaced by rows[].n
function _driveBreadth(line, dots, rows, field, live, z) {
  if (live && rows && rows.length) {
    const nMax = rows.reduce((m, r) => Math.max(m, r.n), 1);
    const pos = line.geometry.attributes.position;
    const n = Math.min(_MAX_PTS, rows.length);
    for (let i = 0; i < _MAX_PTS; i++) {
      const src = i < n ? rows[i] : rows[n - 1];
      const x = _logX(src.n, nMax);
      const y = src[field] * CURVE_HEIGHT;
      pos.setXYZ(i, x, y, z);
      if (i < n) { dots[i].position.set(x, y, z); dots[i].visible = true; }
      else dots[i].visible = false;
    }
    pos.needsUpdate = true;
    line.geometry.computeBoundingSphere();
    line.material.opacity = 0.85;
  } else {
    dots.forEach((d) => { d.visible = false; });
    line.material.color.setHex(C_DIM);
    line.material.opacity = 0.25;
  }
}

function _updateCurves() {
  const live = S.state === "live";

  // --- oracle coverage + verifier-guided selected curves (both breadth, Z=0) ---
  _driveBreadth(_coverLine, _coverDots, S.breadth, "coverage", live, 0);
  _driveBreadth(_selLine,   _selDots,   S.breadth, "selected", live, 0);
  if (live && S.breadth && S.breadth.length) {
    _coverLine.material.color.setHex(C_COVER);
    _selLine.material.color.setHex(C_SELECT);
  }

  // --- sequential-revision curve (Z = CURVE_DEPTH) ---
  if (live && S.revCurve && S.revCurve.length) {
    const kMax = S.revCurve.reduce((m, r) => Math.max(m, r.r), 1);
    const pos = _revLine.geometry.attributes.position;
    const n = Math.min(_MAX_PTS, S.revCurve.length);
    for (let i = 0; i < _MAX_PTS; i++) {
      const src = i < n ? S.revCurve[i] : S.revCurve[n - 1];
      const x = _linX(src.r, kMax);
      const y = src.revised_accuracy * CURVE_HEIGHT;
      pos.setXYZ(i, x, y, CURVE_DEPTH);
      if (i < n) { _revDots[i].position.set(x, y, CURVE_DEPTH); _revDots[i].visible = true; }
      else _revDots[i].visible = false;
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

  // --- HUD marker: sits at the current (N, selected) point, pulses proof-teal ---
  if (_marker) {
    if (live && S.selAtN != null && S.N != null && S.breadth && S.breadth.length) {
      const nMax = S.breadth.reduce((m, r) => Math.max(m, r.n), 1);
      const x = _logX(S.N, nMax);
      const y = S.selAtN * CURVE_HEIGHT;
      _marker.position.set(x, y, 0);
      _marker.material.color.setHex(C_SELECT);
      _marker.material.emissive.setHex(C_SELECT);
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
    chips: [{ label: "MODELED", text: "agent TTC", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Test-time compute for <b>agents</b> (multi-step tool-use), not a single model. An ' +
    'agent’s success <b>compounds</b> over its trajectory (p = s<sup>depth</sup>), and ' +
    'best-of-N agents only help as far as a <b>real, imperfect verifier</b> can pick a ' +
    'correct one — so verifier-guided success is bounded by verifier precision, never ' +
    '1.0. Honesty label <b>MODELED</b> (closed-form; no agent runs). Λ advisory-only.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "agent-TTC";
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
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("at-step",  "per-step success s"));
  grid.appendChild(kpiRow("at-depth", "task depth (steps)"));
  grid.appendChild(kpiRow("at-p",     "single-agent success p=s^depth"));
  grid.appendChild(kpiRow("at-n",     "N agents (parallel breadth)"));
  grid.appendChild(kpiRow("at-cover", "coverage@N (oracle) — MODELED"));
  grid.appendChild(kpiRow("at-sel",   "selected@N (verifier-guided) — MODELED"));
  grid.appendChild(kpiRow("at-vf",    "verifier precision v"));
  grid.appendChild(kpiRow("at-gap",   "verifier gap (oracle − verifier)"));
  grid.appendChild(kpiRow("at-rev",   "revised accuracy (R rounds) — MODELED"));
  grid.appendChild(kpiRow("at-exp",   "scaling exponent"));
  grid.appendChild(kpiRow("at-oom",   "effective agent compute (orders of mag)"));
  grid.appendChild(kpiRow("at-trust", "advisory trust (≤ 0.97)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Snell et al. arXiv:2408.03314 (optimal test-time compute) · Brown et al. arXiv:2407.21787 (Large Language Monkeys / pass@N) · Hu et al. arXiv:2601.05593 (PaCoRe, parallel coordinated reasoning, ACL 2026). MODELED · Λ advisory-only · not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "at-plain";
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
  const n    = S.N != null ? String(S.N) : "loading…";
  const cov  = S.coverAtN != null ? (S.coverAtN * 100).toFixed(2) + "%" : "loading…";
  const sel  = S.selAtN != null ? (S.selAtN * 100).toFixed(2) + "%" : "loading…";
  const rAcc = S.revAcc != null ? (S.revAcc * 100).toFixed(2) + "%" : "loading…";
  pd.innerHTML =
    "<b>What this means:</b> Instead of building a bigger model, you can run an AI " +
    "<i>agent</i> harder at answer time. Because an agent takes many tool-use steps, one " +
    "slip anywhere can fail the whole task — so a single run often succeeds much less " +
    "than you’d hope. Launching <b>" + n + " agents in parallel</b> means a correct " +
    "run exists <b>" + cov + "</b> of the time (perfect-hindsight “coverage”). But " +
    "you still have to <i>pick</i> the good run with a checker/verifier, and real verifiers " +
    "are imperfect — so the answer you actually ship is correct <b>" + sel + "</b> of the " +
    "time. Letting agents <b>revise</b> their work instead pushes accuracy to <b>" + rAcc +
    "</b>, with diminishing returns. Plain: more agent compute helps, but a shaky verifier " +
    "caps the payoff — which is why we never claim certainty (trust capped at 0.97, and " +
    "Λ stays advisory, never “proven”). This is a <b>MODELED</b> closed-form " +
    "scaling law, not a live agent evaluation.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "—"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("at-step",  t || pct(S.stepSucc, 2));
  _set("at-depth", t || (S.depth != null ? String(S.depth) : "—"));
  _set("at-p",     t || pct(S.pSingle, 4));
  _set("at-n",     t || (S.N != null ? String(S.N) : "—"));
  _set("at-cover", t || pct(S.coverAtN, 4));
  _set("at-sel",   t || pct(S.selAtN, 4));
  _set("at-vf",    t || pct(S.verifier, 2));
  _set("at-gap",   t || pct(S.vGap, 4));
  _set("at-rev",   t || pct(S.revAcc, 4));
  _set("at-exp",   t || fx(S.scalingExp, 6));
  _set("at-oom",   t || fx(S.effOom, 3));
  _set("at-trust", t || pct(S.advTrust, 4));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "agent TTC" });
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
  _coverLine = null; _coverDots = []; _selLine = null; _selDots = [];
  _revLine = null; _revDots = []; _marker = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.stepSucc = S.depth = S.pSingle = S.verifier = null;
  S.N = S.coverAtN = S.selAtN = S.vGap = S.breadth = null;
  S.revisions = S.revAcc = S.revCurve = S.scalingExp = S.effOom = S.advTrust = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
