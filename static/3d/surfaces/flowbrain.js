// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/flowbrain.js — CONTINUOUS BELIEF-FLOW LENS on the governed brain.
//
// Reframes the governed brain's belief-tier evolution (CONJECTURE → CORROBORATED →
// LOAD-BEARING) as a CONTINUOUS confidence flow x_t ∈ [0,1]: the named tiers are NOT
// discrete states the belief occupies, they are THRESHOLDS the flow crosses. A belief is
// wherever its flow value is; a "tier" is just the last line it stepped over.
//
// It also renders the SplitUNet-style AXIS-FACTORIZATION of the estate's evidence tensor as
// two orthogonal axes — a long "1D-time" telemetry/pulse axis ⊗ a short "1D-node" topology
// axis — the decomposition the surface borrows conceptually. This factorization is
// STRUCTURAL-ONLY (a labeling of shape, not a MEASURED spectral result).
//
// DATA: same-origin, relative — no CDN, no cross-origin fetch.
//   /api/a11oy/v1/frontier/flowbrain            → status/info (labels, tier thresholds,
//                                                  axis-factorization shape, source, doctrine)
//   /api/a11oy/v1/frontier/flowbrain/trajectory → x_t[] over the anatomy pulses for a REAL
//                                                  brain-graph node (degree/layer-derived),
//                                                  threshold_crossings[], unsigned content receipt.
//   The flow is a deterministic logistic derived from a real node's degree/layer — NO node
//   fact is fabricated; unknown node degrades to an honest demo over the real graph.
//
// VISUALIZES:
//   1. THREE THRESHOLD PLANES at the tier thresholds (0.0 / 0.50 / 0.85) — faint horizontal
//      grids. Tiers are lines, not boxes.
//   2. THE FLOW CURVE x_t rising left→right through the planes; a marker rides the curve.
//      Each threshold-crossing point is a small proof-teal node ("stepped over the line").
//   3. THE AXIS CROSS — a long lattice-blue "time" axis ⊗ a short violet-blue "node" axis,
//      the borrowed 1D⊗1D factorization, labeled STRUCTURAL-ONLY.
//   No green/1.0/VERIFIED state; the flow ceiling is the 0.97 Trust ceiling, never 1.0.
//
// PRIMARY SOURCE (cited verbatim, ID only — 0 runtime CDN, no URL fetch):
//   B[FM]²: Brain Foundation Model via Flow Matching with SplitUNet — MIT + KU Leuven,
//   arXiv:2606.20812. We borrow ONLY the continuous-flow-over-discretization principle and
//   the axis-factorization framing. HONEST NOTE: there is NO EEG here and NO flow-matching
//   model is trained or run — this is a governance lens over our OWN brain-graph, nothing more.
//
// HONESTY LABEL: STRUCTURAL-ONLY — the flow is a deterministic shape derived from real graph
//   degree/layer; the synthesis (that belief evolution is well-modeled as a continuous flow) is
//   CONJECTURE, never a theorem. Read VERBATIM from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (flow / time axis), violet-blue 0x8a6bff (node axis / marker),
//   proof-teal 0x3af4c8 (threshold-crossing nodes), greys (planes / no-live-data).
//   PURPLE BANNED. No green/1.0 verified state.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; BFT stays Conjecture 2; introduces no theorem. Degrades grey on
//   404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "flowbrain";
const TITLE = "FlowBrain · Continuous Belief-Flow Lens (live)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP      = "/api/a11oy/v1/frontier/flowbrain";
const EP_TRAJ = "/api/a11oy/v1/frontier/flowbrain/trajectory";

// data-viz hues — purple BANNED, no green
const C_FLOW  = 0x5b8dee;  // lattice-blue (flow curve / long time axis)
const C_NODE  = 0x8a6bff;  // violet-blue (short node axis / riding marker)
const C_CROSS = 0x3af4c8;  // proof-teal (threshold-crossing nodes)
const C_DIM   = 0x42505d;  // grey (threshold planes / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / plane colour

// scene extents for the flow plot (x = time/pulse axis, y = confidence x_t, z = depth)
const PLOT_W = 10.0;   // width along the pulse axis
const PLOT_H = 6.0;    // height mapping x_t∈[0,1] (0.97 ceiling sits just below the top)
const Y0     = 0.2;    // floor offset

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _curve = null;         // THREE.Line — the flow x_t
let _marker = null;        // riding marker
let _planes = [];          // threshold planes {mesh, thr}
let _crossNodes = [];      // proof-teal crossing markers
let _timeAxis = null, _nodeAxis = null;  // the 1D⊗1D axis cross
let _floor = null;

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,   // STRUCTURAL-ONLY (verbatim)
  claim:      null,   // CONJECTURE (synthesis)
  lambda:     null,   // "Conjecture 1"
  trustCeil:  null,
  thresholds: null,   // { CONJECTURE, CORROBORATED, "LOAD-BEARING" }
  xt:         [],     // flow samples
  crossings:  [],     // [{tier, threshold, crossed_at_pulse, reached}]
  nodeId:     null,   // real node the flow was derived from
  nodeDeg:    null,
  nodeLayer:  null,
  timeLen:    null,   // axis-factorization long axis length
  nodeLen:    null,   // axis-factorization short axis length
  measuredWhere: null,
  receipt:    null,   // content-digest (unsigned)
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 5.5, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlanes();       // three tier-threshold planes (lines, not boxes)
  _buildAxisCross();    // 1D-time ⊗ 1D-node factorization
  _buildCurve();        // empty flow line, filled on live data

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  // info first (thresholds + axis shape), then the trajectory (the flow itself).
  _polls.push(ctx.live.poll(EP, 8000, _onInfo, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));
  _polls.push(ctx.live.poll(EP_TRAJ, 8000, _onTraj, {}));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.14; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// map a pulse index i∈[0,N-1] to scene x, and x_t∈[0,1] to scene y.
function _sx(i, n) { return -PLOT_W / 2 + (n > 1 ? (i / (n - 1)) : 0) * PLOT_W; }
function _sy(v)    { return Y0 + Math.max(0, Math.min(1, v)) * PLOT_H; }

// three faint horizontal planes at the tier thresholds. A tier is a LINE crossed, not a box.
function _buildPlanes() {
  const THREE = _THREE;
  const defaults = [0.0, 0.50, 0.85];
  for (const thr of defaults) {
    const g = new THREE.PlaneGeometry(PLOT_W + 1.5, 3.0);
    const m = new THREE.MeshBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.07, side: THREE.DoubleSide, wireframe: true });
    const mesh = new THREE.Mesh(g, m);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.set(0, _sy(thr), 0);
    _group.add(mesh);
    _planes.push({ mesh, thr });
  }
}

// the borrowed SplitUNet axis-factorization: a LONG lattice-blue time axis ⊗ a SHORT
// violet-blue node axis, meeting at the plot origin. STRUCTURAL-ONLY (shape, not a reading).
function _buildAxisCross() {
  const THREE = _THREE;
  const ox = -PLOT_W / 2 - 0.6, oy = Y0 - 0.05, oz = 0;
  // long time axis (along +x)
  const tg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(ox, oy, oz), new THREE.Vector3(ox + PLOT_W + 1.0, oy, oz),
  ]);
  _timeAxis = new THREE.Line(tg, new THREE.LineBasicMaterial({ color: C_FLOW, transparent: true, opacity: 0.5 }));
  _group.add(_timeAxis);
  // short node axis (along +z), deliberately shorter — the "1D-node" factor
  const ng = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(ox, oy, oz - 1.6), new THREE.Vector3(ox, oy, oz + 1.6),
  ]);
  _nodeAxis = new THREE.Line(ng, new THREE.LineBasicMaterial({ color: C_NODE, transparent: true, opacity: 0.5 }));
  _group.add(_nodeAxis);
}

function _buildCurve() {
  const THREE = _THREE;
  const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, Y0, 0)]);
  _curve = new THREE.Line(g, new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.85 }));
  _group.add(_curve);

  _marker = new THREE.Mesh(
    new THREE.SphereGeometry(0.16, 16, 12),
    new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.5, transparent: true, opacity: 0.95 }),
  );
  _marker.position.set(_sx(0, 1), Y0, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handlers — read VERBATIM, never upgrade
// =============================================================================
function _onInfo(j) {
  S.label = (j.label || "STRUCTURAL-ONLY").toUpperCase();
  S.claim = typeof j.claim === "string" ? j.claim.toUpperCase() : null;

  const th = j.tier_thresholds || null;
  if (th && typeof th === "object") S.thresholds = th;

  const af = j.axis_factorization || {};
  if (af.time_axis && typeof af.time_axis.length === "number") S.timeLen = af.time_axis.length;
  if (af.node_axis && typeof af.node_axis.length === "number") S.nodeLen = af.node_axis.length;
  S.measuredWhere = typeof af.measured_where === "string" ? af.measured_where : null;

  const d = j.doctrine || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;

  _updatePlanes();
  _paintOverlay();
}

function _onTraj(j) {
  const tr = j.trajectory || {};
  S.xt = Array.isArray(tr.x_t) ? tr.x_t.filter((v) => typeof v === "number") : [];
  S.crossings = Array.isArray(tr.threshold_crossings) ? tr.threshold_crossings : [];
  if (tr.tier_thresholds && typeof tr.tier_thresholds === "object") S.thresholds = tr.tier_thresholds;

  const n = j.node || {};
  S.nodeId    = typeof n.id === "string" ? n.id : null;
  S.nodeDeg   = typeof n.degree === "number" ? n.degree : null;
  S.nodeLayer = typeof n.layer === "number" ? n.layer : null;

  const rc = j.receipt || {};
  S.receipt = typeof rc.digest === "string" ? rc.digest : null;

  _updateCurve();
  _updatePlanes();
  _paintOverlay();
}

function _updatePlanes() {
  const live = S.state === "live";
  // re-place the three planes at the live thresholds if provided.
  if (S.thresholds && _planes.length === 3) {
    const order = ["CONJECTURE", "CORROBORATED", "LOAD-BEARING"];
    for (let i = 0; i < 3; i++) {
      const thr = S.thresholds[order[i]];
      if (typeof thr === "number") { _planes[i].thr = thr; _planes[i].mesh.position.y = _sy(thr); }
      _planes[i].mesh.material.opacity = live ? 0.09 : 0.05;
    }
  }
  const axCol = live ? undefined : C_DIM;
  if (axCol != null) {
    if (_timeAxis) _timeAxis.material.color.setHex(axCol);
    if (_nodeAxis) _nodeAxis.material.color.setHex(axCol);
  } else {
    if (_timeAxis) _timeAxis.material.color.setHex(C_FLOW);
    if (_nodeAxis) _nodeAxis.material.color.setHex(C_NODE);
  }
}

function _updateCurve() {
  const THREE = _THREE;
  const live = S.state === "live";
  const n = S.xt.length;

  // rebuild the flow line from the samples.
  const pts = [];
  for (let i = 0; i < n; i++) pts.push(new THREE.Vector3(_sx(i, n), _sy(S.xt[i]), 0));
  if (!pts.length) pts.push(new THREE.Vector3(_sx(0, 1), Y0, 0));
  _curve.geometry.setFromPoints(pts);
  _curve.material.color.setHex(live && n ? C_FLOW : C_DIM);

  // clear + rebuild crossing nodes at each reached threshold-crossing pulse.
  for (const c of _crossNodes) { try { _group.remove(c); c.geometry.dispose(); c.material.dispose(); } catch (_) {} }
  _crossNodes = [];
  if (live && n) {
    for (const cr of S.crossings) {
      if (!cr || cr.reached !== true) continue;
      const pi = typeof cr.crossed_at_pulse === "number" ? cr.crossed_at_pulse : null;
      if (pi == null || pi < 0 || pi >= n) continue;
      const node = new THREE.Mesh(
        new THREE.OctahedronGeometry(0.17, 0),
        new THREE.MeshStandardMaterial({ color: C_CROSS, emissive: C_CROSS, emissiveIntensity: 0.5, transparent: true, opacity: 0.95 }),
      );
      node.position.set(_sx(pi, n), _sy(S.xt[pi]), 0);
      node.userData.label = cr.tier;
      _group.add(node);
      _crossNodes.push(node);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.10;

  const live = S.state === "live";
  const n = S.xt.length;
  if (_marker && live && n > 1) {
    const phase = (t * 0.00018) % 1;              // marker rides the flow left→right
    const fi = phase * (n - 1);
    const i0 = Math.floor(fi), i1 = Math.min(n - 1, i0 + 1), fr = fi - i0;
    const y = _sy(S.xt[i0] + (S.xt[i1] - S.xt[i0]) * fr);
    _marker.position.set(_sx(i0, n) + (_sx(i1, n) - _sx(i0, n)) * fr, y, 0);
    _marker.material.emissiveIntensity = 0.35 + 0.25 * (0.5 + 0.5 * Math.sin(t * 0.004));
  } else if (_marker) {
    _marker.material.emissiveIntensity = 0.12;
  }
  for (const c of _crossNodes) c.rotation.y += 0.03;
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [
      { label: "STRUCTURAL-ONLY", text: "flow shape", name: "lbl" },
      { label: "CONJECTURE", text: "synthesis", name: "syn" },
    ],
    legend: ["STRUCTURAL-ONLY", "CONJECTURE"],
  });
  const host = _show.body;

  try {
    _show.attachSceneLabels({
      objects: () => _crossNodes,
      text: (o) => o.userData.label,
      weight: () => 1, topN: 3, hover: true,
    });
  } catch (_) {}

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The governed brain’s belief tiers (<b>CONJECTURE → CORROBORATED → LOAD-BEARING</b>) ' +
    'seen as a <b>continuous confidence flow</b> x<sub>t</sub>∈[0,1]: the tiers are ' +
    '<b>thresholds crossed</b>, not states occupied. The flow is derived from a <b>real ' +
    'brain-graph node</b>’s degree/layer (no node fact invented). Also shown: the borrowed ' +
    '<b>1D-time ⊗ 1D-node</b> axis-factorization. Label <b>STRUCTURAL-ONLY</b>; the synthesis ' +
    'is <b>CONJECTURE</b> — not a theorem. Flow ceiling is the <b>0.97 Trust ceiling</b>, never 1.0.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "flowbrain";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("fb-node",   "flow derived from (real node)"));
  grid.appendChild(kpiRow("fb-now",    "current flow x_t (start → end)"));
  grid.appendChild(kpiRow("fb-cross",  "tiers crossed (thresholds)"));
  grid.appendChild(kpiRow("fb-axes",   "axis-factorization (time ⊗ node)"));
  grid.appendChild(kpiRow("fb-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("fb-lambda", "Λ"));
  grid.appendChild(kpiRow("fb-receipt","content receipt (unsigned)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent =
    "Source idea: B[FM]² — Brain Foundation Model via Flow Matching with SplitUNet " +
    "(MIT + KU Leuven, arXiv:2606.20812). We borrow ONLY the continuous-flow-over-discretization " +
    "principle + the 1D⊗1D axis-factorization framing. HONEST: NO EEG, no flow-matching model " +
    "trained/run — a governance lens over our own brain-graph. STRUCTURAL-ONLY · synthesis " +
    "CONJECTURE · not verified · adds nothing to the locked-8.";
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
  pd.id = "fb-plain";
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
  pd.innerHTML =
    "<b>What this means:</b> normally we sort a belief into one of three boxes — a hunch " +
    "(<b>conjecture</b>), a backed-up claim (<b>corroborated</b>), or something the system leans on " +
    "(<b>load-bearing</b>). This tab instead shows belief as a <b>rising line of confidence</b> from 0 " +
    "to (at most) 0.97, and treats those three boxes as just <b>marks on the wall</b> the line steps " +
    "past. The rising line here is computed from a <b>real node</b> in our own knowledge-graph (how " +
    "connected it is, how deep it sits) — we don’t make up its facts. The idea of treating belief " +
    "as a smooth flow instead of fixed boxes is <b>borrowed</b> from a brain-modeling paper (B[FM]²); " +
    "we borrow the <b>idea only</b> — there is <b>no brain data, no EEG, no trained model</b> here. So " +
    "it is honestly labeled <b>STRUCTURAL-ONLY</b>, the claim that belief is well-described this way is " +
    "our <b>CONJECTURE</b>, and the line <b>never reaches a “certain / 1.0”</b> state. Plain: a " +
    "clearer way to look at confidence, clearly labeled, no overclaim.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _crossSummary() {
  const reached = S.crossings.filter((c) => c && c.reached === true).map((c) => c.tier);
  if (!reached.length) return "—";
  return reached.join(" · ");
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) {
    _show.setChip("lbl", S.label || "STRUCTURAL-ONLY", { text: "flow shape" });
    _show.setChip("syn", S.claim || "CONJECTURE", { text: "synthesis" });
  }
  const node = S.nodeId ? (S.nodeId + (S.nodeDeg != null ? (" · deg " + S.nodeDeg) : "") + (S.nodeLayer != null ? (" · L" + S.nodeLayer) : "")) : "—";
  const now = S.xt.length ? (S.xt[0].toFixed(2) + " → " + S.xt[S.xt.length - 1].toFixed(2)) : "—";
  const axes = (S.timeLen != null && S.nodeLen != null) ? (S.timeLen + " (time) ⊗ " + S.nodeLen + " (node)") : "—";
  _set("fb-node",    t || node);
  _set("fb-now",     t || now);
  _set("fb-cross",   t || _crossSummary());
  _set("fb-axes",    t || axes);
  _set("fb-trust",   t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("fb-lambda",  t || (S.lambda || "—"));
  _set("fb-receipt", t || (S.receipt ? (S.receipt.slice(0, 12) + "…") : "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — dispose everything; must not affect other organs
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
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _curve = _marker = null; _planes = []; _crossNodes = [];
  _timeAxis = _nodeAxis = null; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.claim = S.lambda = null; S.trustCeil = null; S.thresholds = null;
  S.xt = []; S.crossings = []; S.nodeId = null; S.nodeDeg = S.nodeLayer = null;
  S.timeLen = S.nodeLen = null; S.measuredWhere = null; S.receipt = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP, EP_TRAJ], mount, unmount };
