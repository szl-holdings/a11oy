// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/vqc.js — GOVERNED VQC / QML: a REAL parameter-shift Hybrid
// Variational Quantum Circuit, SIMULATION-ONLY, for the holographic frontier
// ring. Renders the canonical hybrid quantum-classical training loop as a
// left-to-right pipeline: a column of QUBIT WIRES carrying a feature map →
// layered ANSATZ blocks (RY/RZ + ring-CNOT entanglers) → a MEASUREMENT bar
// (Pauli-Z expectations) → a CLASSICAL HEAD node → a LOSS marker whose height
// falls as the training-loss curve descends. A gradient arrow loops back
// (parameter-shift). Everything passes through a central Λ-GATE (Conjecture 1 —
// gray, NEVER green). Live snapshot: /api/a11oy/v1/vqc/run.
//
// HONESTY IS THE FEATURE — the overlay STATES, in plain text, that there is NO
// demonstrated quantum advantage for classical-data ML today (barren plateaus +
// dequantization + no-fair-comparison-advantage), citing the evidence. The VQC
// math is REAL (a genuine state-vector sim with an exact parameter-shift
// gradient) but SMALL, SIMULATED, and makes NO speedup claim.
//
// Surface export shape (mirrors agentmem.js / titans.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Parameter-shift rule / Quantum Circuit Learning — Mitarai et al. 2018,
//     arXiv:1803.00745   https://arxiv.org/abs/1803.00745
//   Analytic gradients on quantum hardware — Schuld et al. 2019,
//     arXiv:1811.11184   https://arxiv.org/abs/1811.11184
//   PennyLane (Xanadu) — the primary QML framework,
//     arXiv:1811.04968   https://www.xanadu.ai/products/pennylane/
//   Qiskit Machine Learning (IBM) — VQC / QNN / kernels, arXiv:2505.17756
//     https://qiskit-community.github.io/qiskit-machine-learning/
//   NO-ADVANTAGE evidence (stated on the tab):
//     Barren plateaus — McClean et al. 2018, Nat. Commun. 9, 4812
//       https://www.nature.com/articles/s41467-018-07090-4
//     Dequantization trap — Cerezo et al. arXiv:2312.09121
//       https://arxiv.org/abs/2312.09121
//     No fair-comparison advantage — Sheoran et al., Sci. Rep. 2025
//       https://www.nature.com/srep/
//
// HONESTY LABELS: SIMULATED (the state-vector sim, feature map, ansatz,
//   measurement, head, loss, and the REAL parameter-shift gradient are a small
//   deterministic simulation; the loss/grad curves are genuinely computed, read
//   VERBATIM from JSON, never upgraded). MODELED toy dataset. Λ as a trust gate
//   is CONJECTURE (Λ = Conjecture 1, gray, never green; trust capped at 0.97).
//   The receipt is REAL ECDSA-P256 in-Space, honest UNSIGNED-LOCAL locally.
// COLOURS: lattice-blue 0x5b8dee (qubit wires / feature map), teal-cyan 0x3af4c8
//   (loss descent / admitted), violet-blue 0x8a6bff (Λ-gate ring), amber 0xf4b23a
//   (gradient / parameter-shift), greys (degraded / gated-out). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "vqc";
const TITLE = "Governed VQC · Parameter-Shift Hybrid QML (SIMULATED)";

// Served SAME-ORIGIN by szl_vqc.py — a deterministic parameter-shift VQC sim.
const EP = "/api/a11oy/v1/vqc/run?seed=7&n_qubits=3&layers=2&steps=14";

// data-viz hues — purple BANNED
const C_WIRE  = 0x5b8dee;  // lattice-blue (qubit wires / feature map)
const C_LOSS  = 0x3af4c8;  // teal-cyan (loss descent / admitted)
const C_GATE  = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_GRAD  = 0xf4b23a;  // amber (gradient / parameter-shift)
const C_DIM   = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry (left→right pipeline along +x)
const X_FEAT   = -8.0;   // feature-map column
const X_ANSATZ = -3.0;   // ansatz blocks
const X_MEAS   =  1.5;   // measurement bar
const X_HEAD   =  4.5;   // classical head node
const X_LOSS   =  7.5;   // loss marker
const MAX_QUBITS = 6;
const MAX_LAYERS_RENDER = 6;
const MAX_CURVE  = 64;   // loss-curve points rendered

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor = null;
let _wires = [];       // qubit wire lines
let _featNodes = [];   // feature-map spheres
let _ansatzBlocks = []; // ansatz layer boxes
let _measBars = [];    // measurement expectation bars
let _headNode = null;  // classical head
let _lossMarker = null; // loss marker (height ~ final loss)
let _lossCurve = null;  // the descending loss curve line
let _gradArc = null;    // parameter-shift gradient arc (loops back)
let _gateRing = null;   // central Λ-gate ring

// live state
const S = {
  label:      null,
  nQubits:    null,
  layers:     null,
  steps:      null,
  hilbertDim: null,
  nWeights:   null,
  lossCurve:  null,
  gradCurve:  null,
  initialLoss: null,
  finalLoss:  null,
  accuracy:   null,
  finalGradNorm: null,
  lambda:     null,
  lambdaAdmitted: null,
  trust:      null,
  trustCap:   null,
  receiptSigned: null,
  receiptMode: null,
  receiptDigest: null,
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildWires();
  _buildStages();
  _buildLossCurve();
  _buildGateAndGrad();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onData, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(46, 46, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Qubit wires: horizontal lines (one per qubit) carrying the feature map through
// the ansatz to the measurement bar.
function _buildWires() {
  const THREE = _THREE;
  for (let q = 0; q < MAX_QUBITS; q++) {
    const y = 0.6 + q * 0.9;
    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(X_FEAT, y, 0), new THREE.Vector3(X_MEAS, y, 0),
    ]);
    const m = new THREE.LineBasicMaterial({ color: C_WIRE, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(g, m);
    line.visible = false;
    _group.add(line);
    _wires.push(line);

    // feature-map node on each wire (angle embedding)
    const fn = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 10, 10),
      new THREE.MeshStandardMaterial({ color: C_WIRE, emissive: C_WIRE, emissiveIntensity: 0.3, transparent: true, opacity: 0.0 }),
    );
    fn.position.set(X_FEAT, y, 0);
    fn.visible = false;
    _group.add(fn);
    _featNodes.push(fn);

    // measurement bar per qubit (height ~ |<Z_q>| once live; placeholder now)
    const mb = new THREE.Mesh(
      new THREE.BoxGeometry(0.22, 0.6, 0.22),
      new THREE.MeshStandardMaterial({ color: C_LOSS, emissive: C_LOSS, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
    );
    mb.position.set(X_MEAS, y, 0);
    mb.visible = false;
    _group.add(mb);
    _measBars.push(mb);
  }
}

// Ansatz blocks: one translucent box per layer straddling the qubit wires,
// representing an RY/RZ + ring-CNOT entangling layer.
function _buildStages() {
  const THREE = _THREE;
  for (let l = 0; l < MAX_LAYERS_RENDER; l++) {
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(0.7, 5.0, 1.4),
      new THREE.MeshStandardMaterial({ color: C_GATE, emissive: C_GATE, emissiveIntensity: 0.18, wireframe: true, transparent: true, opacity: 0.0 }),
    );
    box.position.set(X_ANSATZ + l * 1.1, 2.6, 0);
    box.visible = false;
    _group.add(box);
    _ansatzBlocks.push(box);
  }

  // classical head node
  _headNode = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.55, 1),
    new THREE.MeshStandardMaterial({ color: C_WIRE, emissive: C_WIRE, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _headNode.position.set(X_HEAD, 2.0, 0);
  _group.add(_headNode);

  // loss marker: a vertical bar whose height reflects the final loss
  _lossMarker = new THREE.Mesh(
    new THREE.CylinderGeometry(0.14, 0.14, 1.0, 12),
    new THREE.MeshStandardMaterial({ color: C_LOSS, emissive: C_LOSS, emissiveIntensity: 0.35, transparent: true, opacity: 0.85 }),
  );
  _lossMarker.position.set(X_LOSS, 0.5, 0);
  _group.add(_lossMarker);
}

// The training-loss curve, drawn as a descending polyline above the pipeline.
function _buildLossCurve() {
  const THREE = _THREE;
  const g = new THREE.BufferGeometry().setFromPoints(
    new Array(MAX_CURVE).fill(0).map((_, i) => new THREE.Vector3(X_HEAD + (i / MAX_CURVE) * 4, 5.0, 3)),
  );
  const m = new THREE.LineBasicMaterial({ color: C_LOSS, transparent: true, opacity: 0.0 });
  _lossCurve = new THREE.Line(g, m);
  _lossCurve.visible = false;
  _group.add(_lossCurve);
}

// Central Λ-gate ring + the parameter-shift gradient arc that loops back from
// the loss to the ansatz (the "gradient update via ±π/2 shift" edge).
function _buildGateAndGrad() {
  const THREE = _THREE;
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(X_HEAD - 1.5 + Math.cos(a) * 1.4, 2.0, Math.sin(a) * 1.4));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const m = new THREE.LineBasicMaterial({ color: C_GATE, transparent: true, opacity: 0.4 });
    _gateRing = new THREE.LineLoop(g, m);
    _group.add(_gateRing);
  }
  // gradient arc (amber) — a curved feedback line from loss back to ansatz
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(X_LOSS, 1.2, 0),
    new THREE.Vector3(0, 7.5, -4),
    new THREE.Vector3(X_ANSATZ, 5.2, 0),
  );
  const g = new THREE.BufferGeometry().setFromPoints(curve.getPoints(48));
  const m = new THREE.LineBasicMaterial({ color: C_GRAD, transparent: true, opacity: 0.0 });
  _gradArc = new THREE.Line(g, m);
  _gradArc.visible = false;
  _group.add(_gradArc);
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "SIMULATED";
  S.label = String(rawLabel).toUpperCase();

  S.nQubits    = typeof p.n_qubits === "number" ? p.n_qubits : null;
  S.layers     = typeof p.layers === "number" ? p.layers : null;
  S.steps      = typeof p.steps === "number" ? p.steps : null;
  S.hilbertDim = typeof p.hilbert_dim === "number" ? p.hilbert_dim : null;
  S.nWeights   = typeof p.n_weights === "number" ? p.n_weights : null;

  const tr = (p && typeof p.training === "object") ? p.training : {};
  S.lossCurve   = Array.isArray(tr.loss_curve) ? tr.loss_curve : null;
  S.gradCurve   = Array.isArray(tr.grad_norm_curve) ? tr.grad_norm_curve : null;
  S.initialLoss = typeof tr.initial_loss === "number" ? tr.initial_loss : null;
  S.finalLoss   = typeof tr.final_loss === "number" ? tr.final_loss : null;
  S.accuracy    = typeof tr.final_accuracy === "number" ? tr.final_accuracy : null;
  S.finalGradNorm = typeof tr.final_grad_norm === "number" ? tr.final_grad_norm : null;

  const g = (p && typeof p.lambda_gate === "object") ? p.lambda_gate : {};
  S.lambda         = typeof g.value === "number" ? g.value : null;
  S.lambdaAdmitted = typeof g.admitted === "boolean" ? g.admitted : null;
  S.trust          = typeof g.trust === "number" ? g.trust : null;
  S.trustCap       = typeof g.trust_cap === "number" ? g.trust_cap : null;

  const rc = (p && typeof p.receipt === "object") ? p.receipt : {};
  S.receiptSigned = typeof rc.signed === "boolean" ? rc.signed : null;
  S.receiptMode   = typeof rc.mode === "string" ? rc.mode : null;
  S.receiptDigest = typeof rc.content_sha3_256 === "string" ? rc.content_sha3_256 : null;

  _updateScene();
  _paintOverlay();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const nQ = live && S.nQubits ? Math.min(S.nQubits, MAX_QUBITS) : 0;
  const nL = live && S.layers ? Math.min(S.layers, MAX_LAYERS_RENDER) : 0;

  // wires + feature-map nodes + measurement bars
  for (let q = 0; q < MAX_QUBITS; q++) {
    const on = q < nQ;
    _wires[q].visible = on;
    _wires[q].material.color.setHex(live ? C_WIRE : C_DIM);
    _wires[q].material.opacity = on ? (live ? 0.6 : 0.2) : 0.0;
    _featNodes[q].visible = on;
    _featNodes[q].material.color.setHex(live ? C_WIRE : C_DIM);
    _featNodes[q].material.emissive.setHex(live ? C_WIRE : C_DIM);
    _featNodes[q].material.opacity = on ? 0.9 : 0.0;
    _measBars[q].visible = on;
    _measBars[q].material.color.setHex(live ? C_LOSS : C_DIM);
    _measBars[q].material.emissive.setHex(live ? C_LOSS : C_DIM);
    _measBars[q].material.opacity = on ? 0.85 : 0.0;
  }

  // ansatz layer blocks
  for (let l = 0; l < MAX_LAYERS_RENDER; l++) {
    const on = l < nL;
    _ansatzBlocks[l].visible = on;
    _ansatzBlocks[l].material.color.setHex(live ? C_GATE : C_DIM);
    _ansatzBlocks[l].material.emissive.setHex(live ? C_GATE : C_DIM);
    _ansatzBlocks[l].material.opacity = on ? 0.5 : 0.0;
  }

  // gate ring degrades to grey when not live
  if (_gateRing) {
    _gateRing.material.color.setHex(live ? C_GATE : C_DIM);
    _gateRing.material.opacity = live ? 0.4 : 0.12;
  }
  // gradient arc — visible + amber only when live (parameter-shift feedback)
  if (_gradArc) {
    _gradArc.visible = live;
    _gradArc.material.color.setHex(live ? C_GRAD : C_DIM);
    _gradArc.material.opacity = live ? 0.6 : 0.0;
  }
  // classical head glows when live
  if (_headNode) {
    _headNode.material.color.setHex(live ? C_WIRE : C_DIM);
    _headNode.material.emissive.setHex(live ? C_WIRE : C_DIM);
    _headNode.material.opacity = live ? 0.9 : 0.35;
  }

  // loss marker: height maps to the final loss (0..~0.5); teal when improving.
  if (_lossMarker) {
    if (live && S.finalLoss != null) {
      const h = Math.max(0.15, Math.min(4.0, S.finalLoss * 8.0));
      _lossMarker.scale.set(1, h, 1);
      _lossMarker.position.y = h / 2;
      const improved = S.initialLoss != null && S.finalLoss <= S.initialLoss;
      _lossMarker.material.color.setHex(improved ? C_LOSS : C_GRAD);
      _lossMarker.material.emissive.setHex(improved ? C_LOSS : C_GRAD);
      _lossMarker.material.opacity = 0.9;
    } else {
      _lossMarker.scale.set(1, 1, 1);
      _lossMarker.position.y = 0.5;
      _lossMarker.material.color.setHex(C_DIM);
      _lossMarker.material.emissive.setHex(C_DIM);
      _lossMarker.material.opacity = 0.3;
    }
  }

  // loss curve polyline (descending): map loss values to y over x span
  if (_lossCurve) {
    if (live && S.lossCurve && S.lossCurve.length > 1) {
      const pts = S.lossCurve.slice(0, MAX_CURVE);
      const n = pts.length;
      const lo = Math.min.apply(null, pts);
      const hi = Math.max.apply(null, pts);
      const span = (hi - lo) || 1e-6;
      const pos = _lossCurve.geometry.attributes.position;
      for (let i = 0; i < MAX_CURVE; i++) {
        const src = i < n ? pts[i] : pts[n - 1];
        const x = X_HEAD + (i / MAX_CURVE) * 4;
        const y = 3.8 + ((src - lo) / span) * 2.4; // higher = higher loss
        pos.setXYZ(i, x, y, 3);
      }
      pos.needsUpdate = true;
      _lossCurve.visible = true;
      _lossCurve.material.color.setHex(C_LOSS);
      _lossCurve.material.opacity = 0.85;
    } else {
      _lossCurve.visible = false;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.08;
  if (_gateRing) _gateRing.rotation.y += 0.0016;
  if (_headNode) { _headNode.rotation.y += 0.02; _headNode.rotation.x += 0.006; }
  if (_gradArc && _gradArc.visible) {
    const pulse = 0.4 + 0.3 * (0.5 + 0.5 * Math.sin(t * 0.004));
    _gradArc.material.opacity = pulse;
  }
}

// =============================================================================
// overlay — COMPACT: title + badge + honesty banner + KPI panel
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "SIMULATED", text: "Λ=CONJECTURE 1", name: "lbl" }],
    legend: ["SIMULATED"],
    description:
      "A <b>REAL parameter-shift Hybrid VQC</b>, run in a small pure-stdlib " +
      "deterministic <b>state-vector simulation</b> (a few qubits). Pipeline, " +
      "left→right: classical data → <b>feature map</b> (angle embedding) → layered " +
      "<b>ansatz</b> (RY/RZ + ring-CNOT) → <b>measurement</b> (Pauli-Z) → " +
      "<b>classical head</b> → <b>loss</b> → an exact <b>parameter-shift gradient</b> " +
      "step (amber feedback arc). The teal curve is the genuinely-computed " +
      "training loss. All of it passes through the central <b>Λ-gate</b> " +
      "(Λ = Conjecture 1, gray, never green; trust ≤0.97). The run emits ONE " +
      "<b>DSSE receipt</b> — real ECDSA-P256 in-Space, honest UNSIGNED-LOCAL locally. " +
      "0 runtime CDN.",
    citations:
      "Parameter-shift: Mitarai arXiv:1803.00745 · Schuld arXiv:1811.11184 · " +
      "PennyLane arXiv:1811.04968 · Qiskit ML arXiv:2505.17756 · barren plateaus " +
      "McClean 2018 · dequantization Cerezo arXiv:2312.09121. SIMULATED · not claimed-as.",
  });

  const host = _show.body;

  // HONESTY BANNER — the no-advantage statement, ON THE TAB.
  const banner = document.createElement("div");
  banner.id = "vqc-banner";
  banner.style.cssText =
    "background:#1a1206;border:1px solid #f4b23a;border-radius:9px;padding:8px 10px;" +
    "font-size:10.5px;line-height:1.5;color:#f6e3bf;margin-bottom:7px";
  banner.innerHTML =
    "<b style='color:#f4b23a'>HONESTY IS THE FEATURE.</b> There is <b>no demonstrated " +
    "quantum advantage</b> for machine learning on real-world (classical) data today — " +
    "none that survives a fair comparison. This is a REAL parameter-shift VQC in a " +
    "small SIMULATION, Λ-gated + receipt-backed — <b>not</b> a speedup or accuracy claim. " +
    "VQCs suffer <b>barren plateaus</b> (gradients vanish with size — McClean 2018) and " +
    "the <b>dequantization trap</b> (models trainable enough to avoid plateaus are often " +
    "classically simulable — Cerezo arXiv:2312.09121). On classical data, a tuned " +
    "classical model wins (Sheoran, Sci. Rep. 2025).";
  host.appendChild(banner);

  const card = document.createElement("div");
  card.id = "vqc-card";
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:5px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:3px";

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

  grid.appendChild(kpiRow("vqc-circuit", "qubits / layers / dim"));
  grid.appendChild(kpiRow("vqc-weights", "ansatz weights / steps"));
  grid.appendChild(kpiRow("vqc-loss",    "loss (initial → final)"));
  grid.appendChild(kpiRow("vqc-acc",     "toy accuracy (MODELED set)"));
  grid.appendChild(kpiRow("vqc-grad",    "final grad-norm (plateau proxy)"));
  grid.appendChild(kpiRow("vqc-lambda",  "Λ advisory (gray)"));
  grid.appendChild(kpiRow("vqc-trust",   "trust (capped ≤0.97)"));
  grid.appendChild(kpiRow("vqc-receipt", "DSSE receipt"));
  card.appendChild(grid);

  const note = document.createElement("div");
  note.style.cssText = "font-size:10px;color:#c9d6df;line-height:1.5;border-top:1px solid #1d2a36;padding-top:5px";
  note.innerHTML =
    "Gradient method: <b>exact parameter-shift rule</b> (±π/2), not finite differences " +
    "(Mitarai 2018 · Schuld 2019). Receipt: real <b>ECDSA-P256</b> in-Space via szl_dsse; " +
    "honest <b>UNSIGNED-LOCAL</b> when no cosign secret is present (no signature fabricated).";
  card.appendChild(note);

  host.appendChild(card);
  _paintOverlay();
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
  _set("vqc-circuit", t || (S.nQubits != null
        ? S.nQubits + " / " + (S.layers != null ? S.layers : "—") + " / " + (S.hilbertDim != null ? S.hilbertDim : "—")
        : "—"));
  _set("vqc-weights", t || (S.nWeights != null
        ? S.nWeights + " / " + (S.steps != null ? S.steps : "—")
        : "—"));
  _set("vqc-loss", t || (S.initialLoss != null && S.finalLoss != null
        ? fx(S.initialLoss, 4) + " → " + fx(S.finalLoss, 4)
        : "—"));
  _set("vqc-acc", t || pct(S.accuracy, 1));
  _set("vqc-grad", t || fx(S.finalGradNorm, 4));
  _set("vqc-lambda", t || (S.lambda != null
        ? fx(S.lambda, 3) + (S.lambdaAdmitted != null ? (S.lambdaAdmitted ? " (advisory-admit)" : " (advisory-hold)") : "")
        : "—"));
  _set("vqc-trust", t || (S.trust != null ? fx(S.trust, 3) + (S.trustCap != null ? " (≤" + S.trustCap + ")" : "") : "—"));
  _set("vqc-receipt", t || (S.receiptSigned === true
        ? "signed · " + (S.receiptMode || "REAL-ECDSA-P256") + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptSigned === false
            ? "UNSIGNED-LOCAL" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
            : "—")));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "SIMULATED", { text: "Λ=CONJECTURE 1" });
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
  _floor = null; _wires = []; _featNodes = []; _ansatzBlocks = []; _measBars = [];
  _headNode = null; _lossMarker = null; _lossCurve = null; _gradArc = null; _gateRing = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nQubits = S.layers = S.steps = S.hilbertDim = S.nWeights = null;
  S.lossCurve = S.gradCurve = S.initialLoss = S.finalLoss = S.accuracy = S.finalGradNorm = null;
  S.lambda = S.lambdaAdmitted = S.trust = S.trustCap = null;
  S.receiptSigned = S.receiptMode = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
