// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/kan.js — KOLMOGOROV-ARNOLD NETWORK (KAN) organ for the holographic
// frontier ring. Renders the tiny fitted KAN as a node-edge lattice where each
// EDGE is drawn as its own learned spline curve (not a flat scalar-weight
// line) — the defining visual difference from an MLP. A HUD shows param
// counts (KAN vs MLP baseline), final fit error, and the symbolic-distillation
// snap for the selected edge. Honesty label "MODELED" is read VERBATIM from
// the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   task.formula, kan.n_params, kan.final_mse, kan.loss_curve[],
//   mlp_baseline.n_params, mlp_baseline.final_mse, comparison.kan_fewer_params,
//   edge_activation_shapes[] ({edge, curve:[[u,phi(u)]...]}),
//   symbolic_distillation[] ({edge, symbolic_form, coefficient, residual_sse})
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   KAN: Kolmogorov-Arnold Networks:
//     Liu, Wang, Vaidya, Ruehle, Halverson, Soljacic, Hou & Tegmark 2024, arXiv:2404.19756
//     https://arxiv.org/abs/2404.19756
//   pykan reference implementation (MIT, REFERENCE ONLY — no code copied):
//     https://github.com/KindXiaoming/pykan
//
// HONESTY LABELS: MODELED (small, from-scratch, deterministic illustrative KAN;
//   NOT pykan; NEVER-CLAIMED-AS a production/large-scale KAN). Read verbatim
//   from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (KAN edges/lattice), violet-blue 0x8a6bff
//   (hidden-layer nodes), proof-teal 0x3af4c8 (accepted/best-fit accents, HUD).
//   Greys for degraded/MLP-baseline contrast. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Lambda stays Conjecture 1. Trust never 100%.

const ID    = "kan";
const TITLE = "Kolmogorov-Arnold Network · Per-Edge Splines (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the KAN organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/kan/fit?seed=42&hidden=3&knots=7&epochs=60";

// data-viz hues — purple BANNED
const C_EDGE     = 0x5b8dee;  // lattice-blue (KAN edge-spline curves)
const C_NODE     = 0x8a6bff;  // violet-blue (hidden-layer nodes)
const C_ACCENT   = 0x3af4c8;  // proof-teal (best-fit / output node / HUD accent)
const C_MLP      = 0x5a6570;  // grey (MLP-baseline contrast lattice)
const C_DIM      = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID     = 0x1b3a44;  // floor / link colour

// lattice layout geometry: 2 inputs -> H hidden -> 1 output, laid out along X
const LAYER_GAP   = 4.2;   // world-units between layers along X
const NODE_GAP    = 1.6;   // world-units between nodes within a layer (Y)
const MAX_HIDDEN  = 8;     // pre-allocated hidden-node capacity (perf cap)
const CURVE_SEGS  = 23;    // spline sample segments per edge (matches server's 24 samples)

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _markerBaseScale = 1.0;

// geometry handles
let _floor        = null;
let _inputNodes    = [];              // Array<THREE.Mesh> — x, y input nodes
let _hiddenNodes   = [];              // Array<THREE.Mesh> — hidden-layer nodes
let _outputNode    = null;            // THREE.Mesh — single output node
let _edgeCurves1   = [];              // Array<Array<THREE.Line>> — [inputIdx][hiddenIdx] spline curve lines
let _edgeCurves2   = [];              // Array<THREE.Line> — [hiddenIdx] -> output spline curve lines
let _marker        = null;            // THREE.Mesh — HUD pulsing "fit quality" marker

// live state
const S = {
  label:        null,
  formula:      null,   // task.formula
  kanParams:    null,   // kan.n_params
  kanMse:       null,   // kan.final_mse
  kanLoss:      null,   // kan.loss_curve[]
  mlpParams:    null,   // mlp_baseline.n_params
  mlpMse:       null,   // mlp_baseline.final_mse
  fewerParams:  null,   // comparison.kan_fewer_params (bool)
  edgeShapes:   null,   // edge_activation_shapes[]
  distilled:    null,   // symbolic_distillation[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(3, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(4, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLattice();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 6000, _onKan, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate input/hidden/output node meshes and edge-spline curve lines.
// We toggle visibility / geometry points / color in-place as live data
// arrives (no per-poll geometry churn beyond BufferGeometry point updates).
function _buildLattice() {
  const THREE = _THREE;

  const nodeGeo = new THREE.SphereGeometry(0.22, 16, 16);

  // input nodes (x, y) at layer x=0
  for (let i = 0; i < 2; i++) {
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.3, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(0, (i - 0.5) * NODE_GAP * 2, 0);
    _group.add(mesh);
    _inputNodes.push(mesh);
  }

  // hidden nodes at layer x=LAYER_GAP (pre-allocated to MAX_HIDDEN, toggled visible)
  for (let h = 0; h < MAX_HIDDEN; h++) {
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.3, transparent: true, opacity: 0.9 }),
    );
    mesh.position.set(LAYER_GAP, (h - (MAX_HIDDEN - 1) / 2) * NODE_GAP, 0);
    mesh.visible = false;
    _group.add(mesh);
    _hiddenNodes.push(mesh);
  }

  // output node at layer x=2*LAYER_GAP
  _outputNode = new THREE.Mesh(
    nodeGeo,
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.95 }),
  );
  _outputNode.position.set(2 * LAYER_GAP, 0, 0);
  _group.add(_outputNode);

  // layer-1 edge-spline curves: [inputIdx][hiddenIdx], each a THREE.Line whose
  // points trace phi(u) as a curve from the input node to the hidden node,
  // bowed in Z by the spline's own shape (this is the KAN-vs-MLP visual tell:
  // a curved, individually-shaped line per edge instead of a straight one).
  const curveMat = () => new THREE.LineBasicMaterial({ color: C_EDGE, transparent: true, opacity: 0.55 });
  for (let ii = 0; ii < 2; ii++) {
    const row = [];
    for (let h = 0; h < MAX_HIDDEN; h++) {
      const pts = new Array(CURVE_SEGS + 1).fill(0).map(() => new THREE.Vector3(0, 0, 0));
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(geo, curveMat());
      line.visible = false;
      _group.add(line);
      row.push(line);
    }
    _edgeCurves1.push(row);
  }

  // layer-2 edge-spline curves: [hiddenIdx] -> output
  for (let h = 0; h < MAX_HIDDEN; h++) {
    const pts = new Array(CURVE_SEGS + 1).fill(0).map(() => new THREE.Vector3(0, 0, 0));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(geo, curveMat());
    line.visible = false;
    _group.add(line);
    _edgeCurves2.push(line);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.26, 1),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(2 * LAYER_GAP, -1.4, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onKan(j) {
  const body = (j && j.payload) ? j.payload : (j || {});
  // read honesty label VERBATIM — never upgrade
  S.label       = (body.label || "MODELED").toUpperCase();
  S.formula     = (body.task && body.task.formula) || null;
  S.kanParams   = (body.kan && typeof body.kan.n_params === "number") ? body.kan.n_params : null;
  S.kanMse      = (body.kan && typeof body.kan.final_mse === "number") ? body.kan.final_mse : null;
  S.kanLoss     = (body.kan && Array.isArray(body.kan.loss_curve)) ? body.kan.loss_curve : null;
  S.mlpParams   = (body.mlp_baseline && typeof body.mlp_baseline.n_params === "number") ? body.mlp_baseline.n_params : null;
  S.mlpMse      = (body.mlp_baseline && typeof body.mlp_baseline.final_mse === "number") ? body.mlp_baseline.final_mse : null;
  S.fewerParams = (body.comparison && typeof body.comparison.kan_fewer_params === "boolean") ? body.comparison.kan_fewer_params : null;
  S.edgeShapes  = Array.isArray(body.edge_activation_shapes) ? body.edge_activation_shapes : null;
  S.distilled   = Array.isArray(body.symbolic_distillation) ? body.symbolic_distillation : null;

  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the lattice curves from live edge-shape data
// =============================================================================
function _updateLattice() {
  const THREE = _THREE;
  const live = S.state === "live";
  const shapes = live && S.edgeShapes ? S.edgeShapes : [];

  // index shapes by edge name for quick lookup ("x->h0", "y->h2", "h1->out")
  const byName = {};
  for (const s of shapes) if (s && s.edge) byName[s.edge] = s.curve;

  // Hidden-count derivation: count distinct "hN->out" entries.
  let hCount = 0;
  for (const s of shapes) { if (s && /^h\d+->out$/.test(s.edge)) hCount++; }
  hCount = live ? Math.min(MAX_HIDDEN, Math.max(hCount, 0)) : 0;

  for (let h = 0; h < MAX_HIDDEN; h++) {
    _hiddenNodes[h].visible = h < hCount;
  }

  const inputNames = ["x", "y"];
  for (let ii = 0; ii < 2; ii++) {
    for (let h = 0; h < MAX_HIDDEN; h++) {
      const line = _edgeCurves1[ii][h];
      const curve = h < hCount ? byName[`${inputNames[ii]}->h${h}`] : null;
      if (!curve) { line.visible = false; continue; }
      line.visible = true;
      _paintCurve(line, curve, _inputNodes[ii].position, _hiddenNodes[h].position, C_EDGE);
    }
  }

  for (let h = 0; h < MAX_HIDDEN; h++) {
    const line = _edgeCurves2[h];
    const curve = h < hCount ? byName[`h${h}->out`] : null;
    if (!curve) { line.visible = false; continue; }
    line.visible = true;
    _paintCurve(line, curve, _hiddenNodes[h].position, _outputNode.position, C_ACCENT);
  }

  // node/marker degrade to grey when not live
  const nodeColor = live ? C_NODE : C_DIM;
  for (const n of _inputNodes) { n.material.color.setHex(nodeColor); n.material.emissive.setHex(nodeColor); }
  for (const n of _hiddenNodes) { n.material.color.setHex(nodeColor); n.material.emissive.setHex(nodeColor); }
  const outColor = live ? C_ACCENT : C_DIM;
  _outputNode.material.color.setHex(outColor);
  _outputNode.material.emissive.setHex(outColor);

  if (_marker) {
    if (live && S.kanMse != null) {
      _marker.material.color.setHex(C_ACCENT);
      _marker.material.emissive.setHex(C_ACCENT);
      _marker.material.opacity = 0.85;
      // marker size inversely proportional to fit error (tighter fit -> bigger pulse)
      _markerBaseScale = Math.max(0.6, Math.min(1.8, 1.0 / (0.15 + S.kanMse)));
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
      _markerBaseScale = 1.0;
    }
  }
}

// Paint a spline curve's sampled (u, phi(u)) points as a 3D line running from
// nodeFrom to nodeTo, bowing in Z proportional to phi(u) (this is what makes
// each KAN edge visually distinct — an MLP's edges would all be straight).
function _paintCurve(line, curveData, fromPos, toPos, colorHex) {
  const THREE = _THREE;
  const n = curveData.length;
  const pos = line.geometry.attributes.position;
  const count = Math.min(pos.count, n);
  // normalize phi(u) range for a bounded visual bow
  let maxAbs = 1e-6;
  for (let i = 0; i < n; i++) maxAbs = Math.max(maxAbs, Math.abs(curveData[i][1]));
  for (let i = 0; i < count; i++) {
    const t = i / (count - 1);
    const x = fromPos.x + (toPos.x - fromPos.x) * t;
    const y = fromPos.y + (toPos.y - fromPos.y) * t;
    const phi = curveData[Math.min(i, n - 1)][1];
    const z = (phi / maxAbs) * 0.9; // bow amplitude capped at ~0.9 world units
    pos.setXYZ(i, x, y, z);
  }
  pos.needsUpdate = true;
  line.geometry.computeBoundingSphere();
  line.material.color.setHex(colorHex);
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.1;
  if (_marker) {
    _marker.rotation.y += 0.02;
    _marker.rotation.x += 0.01;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.0035);
    _marker.scale.setScalar(_markerBaseScale * pulse);
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
    'A <b>Kolmogorov-Arnold Network</b> puts a learnable curve (spline) on every ' +
    '<b>edge</b> instead of a single scalar weight; nodes just sum their inputs. ' +
    'Fitted here on the toy task <code>f(x,y)=exp(sin(\u03c0x)+y\u00b2)</code>, each curved ' +
    'line below is one edge\u2019s own learned shape. Honesty label <b>MODELED</b> ' +
    '(small from-scratch fit; NOT pykan). 0 runtime CDN.';
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
  nm.textContent = "kolmogorov-arnold network";
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

  grid.appendChild(kpiRow("kan-formula",  "target f(x,y)"));
  grid.appendChild(kpiRow("kan-params",   "KAN params \u2014 MODELED"));
  grid.appendChild(kpiRow("kan-mse",      "KAN final MSE"));
  grid.appendChild(kpiRow("kan-mlpparams","MLP-baseline params"));
  grid.appendChild(kpiRow("kan-mlpmse",   "MLP-baseline final MSE"));
  grid.appendChild(kpiRow("kan-fewer",    "KAN fewer params?"));
  grid.appendChild(kpiRow("kan-label",    "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Liu et al. 2024 arXiv:2404.19756 (KAN) \u00b7 pykan github.com/KindXiaoming/pykan (reference only). MODELED \u00b7 not claimed-as.";
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
  pd.id = "kan-plain";
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
  const kp = S.kanParams != null ? String(S.kanParams) : "loading\u2026";
  const mp = S.mlpParams != null ? String(S.mlpParams) : "loading\u2026";
  const km = S.kanMse != null ? S.kanMse.toFixed(4) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Most neural networks learn a number (a \u201cweight\u201d) for " +
    "each connection. A Kolmogorov-Arnold Network instead learns a whole <b>curve</b> for " +
    "each connection \u2014 you can see the exact shape of every one of those curves above. " +
    "That makes the network easier to read (you can often turn a curve back into a simple " +
    "formula \u2014 the \u201csymbolic distillation\u201d step) and, per the original paper, can " +
    "match accuracy with fewer connections at larger scale. Here it has <b>" + kp + "</b> " +
    "learned numbers vs a same-size ordinary network's <b>" + mp + "</b>, reaching a fit " +
    "error of <b>" + km + "</b> on the toy formula shown. This view is a small, from-scratch, " +
    "<b>MODELED</b> demonstration \u2014 not the original pykan library or a large-scale KAN.";
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
  _set("kan-formula",   t || (S.formula || "\u2014"));
  _set("kan-params",    t || (S.kanParams != null ? String(S.kanParams) : "\u2014"));
  _set("kan-mse",       t || fx(S.kanMse, 5));
  _set("kan-mlpparams", t || (S.mlpParams != null ? String(S.mlpParams) : "\u2014"));
  _set("kan-mlpmse",    t || fx(S.mlpMse, 5));
  _set("kan-fewer",     t || (S.fewerParams === true ? "yes" : S.fewerParams === false ? "no" : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("kan-label", t || (S.label || "MODELED"));
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
  _floor = null; _inputNodes = []; _hiddenNodes = []; _outputNode = null;
  _edgeCurves1 = []; _edgeCurves2 = []; _marker = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _markerBaseScale = 1.0;
  _stage = _THREE = _ctx = null;
  S.label = S.formula = S.kanParams = S.kanMse = S.kanLoss = null;
  S.mlpParams = S.mlpMse = S.fewerParams = S.edgeShapes = S.distilled = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
