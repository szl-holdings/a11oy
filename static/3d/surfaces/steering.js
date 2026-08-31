// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/steering.js — STEERING VECTORS / ACTIVATION ADDITION (ActAdd) /
// REPRESENTATION ENGINEERING (RepE) organ for the holographic frontier ring.
//
// Renders a 3D "injection spine": a chosen residual-stream layer receives an
// additive steering vector v_steer = mean(h_pos) - mean(h_neg), built from a
// contrastive prompt pair ("Love" vs "Hate"), scaled by a swept coefficient.
// A row of coefficient nodes along the spine light up lattice-blue -> proof-teal
// as the MODELED sentiment_score rises, while a parallel held-out capability
// ribbon stays flat, driven by a live JumpReLU-sibling snapshot from
// /api/killinchu/v1/steering/sweep. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// DISTINCT FROM the interpretability/SAE organ: interpretability DECOMPOSES
// and EXPLAINS internal activations (passive readout of dictionary features);
// this organ INTERVENES and CONTROLS behaviour by injecting a vector into the
// forward pass at a chosen layer (active control, inference-time, no
// fine-tuning). Same visual language (ring/lattice geometry, KPI card,
// plain-language toggle), different technique and different endpoint.
//
// Surface export shape (mirrors interpretability.js / specdecode.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   layer, d_model, contrastive_pair{positive,negative}, steering_vector_norm,
//   coefficients[], sentiment_score[], capability_score[], sentiment_shift,
//   capability_drift
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Activation Addition (ActAdd): Turner et al. 2023, arXiv:2308.10248
//     https://arxiv.org/abs/2308.10248
//   Representation Engineering (RepE): Zou et al. 2023, arXiv:2310.01405
//     https://arxiv.org/abs/2310.01405
//
// HONESTY LABELS: MODELED (deterministic closed-form re-implementation of the
//   mean-difference steering-vector + additive-injection arithmetic; NOT a
//   run against a real model's weights/activations; NEVER-CLAIMED-AS a
//   production steering system). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (coefficient/injection spine), violet-blue
//   0x8a6bff (high-|coefficient| flash — data-viz only), proof-teal 0x3af4c8
//   (sentiment-shift accent / capability ribbon). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via ctx.THREE (page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "steering";
const TITLE = "Steering Vectors · Activation Addition / RepE (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the steering organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/steering/sweep?seed=42&layer=12&d_model=512&n_coeffs=9&coeff_max=6";

// data-viz hues — purple BANNED
const C_NODE    = 0x5b8dee;  // lattice-blue (coefficient node / injection spine)
const C_TOP     = 0x8a6bff;  // violet-blue (high-|coefficient| flash — data-viz only)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT  = 0x3af4c8;  // proof-teal (sentiment-shift accent / capability ribbon)
const C_GRID    = 0x1b3a44;  // floor / link colour

// injection-spine geometry: coefficient nodes laid out along X, sentiment
// height on Y, capability ribbon as a thin bar just below the spine.
const N_SLOTS  = 16;   // visual coefficient slots along the spine (matches endpoint cap)
const SPAN     = 9.0;  // world-units spanned end-to-end along X
const AMP      = 2.6;  // world-units of Y amplitude for +-1 sentiment_score

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _spine   = null;        // THREE.Line — the coefficient axis (injection spine)
let _nodes   = [];          // Array<THREE.Mesh> — one per coefficient slot
let _links   = [];          // Array<THREE.Line> — vertical link from axis to node
let _ribbon  = null;        // THREE.Line — held-out capability score ribbon
let _hub     = null;        // THREE.Mesh — central steering-vector hub (norm indicator)

// per-slot flash timers
const _flash = new Float32Array(N_SLOTS);

// live state
const S = {
  label:            null,
  layer:            null,   // layer
  dModel:           null,   // d_model
  pair:             null,   // contrastive_pair {positive, negative}
  vecNorm:          null,   // steering_vector_norm
  coeffs:           null,   // coefficients[]
  sentiment:        null,   // sentiment_score[]
  capability:       null,   // capability_score[]
  sentimentShift:   null,   // sentiment_shift
  capabilityDrift:  null,   // capability_drift
  state:            "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpine();
  _buildHub();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSteering, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Pre-allocate a fixed row of coefficient-node meshes plus their vertical
// links to the injection spine, and a capability ribbon underneath. We
// toggle visibility/position/color in-place as live data arrives (no
// per-poll geometry churn).
function _buildSpine() {
  const THREE = _THREE;
  const baseY = 1.2;

  // injection spine: a straight line along X at sentiment=0 (baseline)
  {
    const pts = [new THREE.Vector3(-SPAN / 2, baseY, 0), new THREE.Vector3(SPAN / 2, baseY, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_NODE, transparent: true, opacity: 0.4 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const nodeGeo = new THREE.OctahedronGeometry(0.22, 0);
  for (let i = 0; i < N_SLOTS; i++) {
    const x = -SPAN / 2 + (SPAN * i) / (N_SLOTS - 1);
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(x, baseY, 0);
    mesh.visible = false;
    _group.add(mesh);
    _nodes.push(mesh);

    // vertical link from the baseline spine up/down to the node's sentiment height
    const linkGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x, baseY, 0), new THREE.Vector3(x, baseY, 0),
    ]);
    const linkMat = new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.3 });
    const link = new THREE.Line(linkGeo, linkMat);
    link.visible = false;
    _group.add(link);
    _links.push(link);
  }

  // held-out capability ribbon: a thin line beneath the spine, one point per slot
  {
    const pts = [];
    for (let i = 0; i < N_SLOTS; i++) {
      const x = -SPAN / 2 + (SPAN * i) / (N_SLOTS - 1);
      pts.push(new THREE.Vector3(x, baseY - 1.6, 0));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_ACCENT, transparent: true, opacity: 0.6 });
    _ribbon = new THREE.Line(geo, mat);
    _ribbon.visible = false;
    _group.add(_ribbon);
  }
}

function _buildHub() {
  const THREE = _THREE;
  // Central hub = the steering vector itself (v_steer); scale reflects its norm.
  _hub = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.5, 1),
    new THREE.MeshStandardMaterial({ color: C_TOP, emissive: C_TOP, emissiveIntensity: 0.35, wireframe: true, transparent: true, opacity: 0.6 }),
  );
  _hub.position.set(0, 3.6, 0);
  _group.add(_hub);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSteering(j) {
  // read honesty label VERBATIM — never upgrade
  S.label           = (j.label || "MODELED").toUpperCase();
  S.layer           = typeof j.layer                  === "number" ? j.layer                  : null;
  S.dModel          = typeof j.d_model                === "number" ? j.d_model                : null;
  S.pair            = j.contrastive_pair && typeof j.contrastive_pair === "object" ? j.contrastive_pair : null;
  S.vecNorm         = typeof j.steering_vector_norm   === "number" ? j.steering_vector_norm   : null;
  S.coeffs          = Array.isArray(j.coefficients)    ? j.coefficients    : null;
  S.sentiment       = Array.isArray(j.sentiment_score) ? j.sentiment_score : null;
  S.capability      = Array.isArray(j.capability_score)? j.capability_score: null;
  S.sentimentShift  = typeof j.sentiment_shift        === "number" ? j.sentiment_shift        : null;
  S.capabilityDrift = typeof j.capability_drift       === "number" ? j.capability_drift       : null;

  _updateSpine();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the injection spine + capability ribbon from live data
// =============================================================================
function _updateSpine() {
  const THREE = _THREE;
  const live = S.state === "live";
  const baseY = 1.2;
  const sentiment  = live && S.sentiment  ? S.sentiment  : [];
  const capability = live && S.capability ? S.capability : [];
  const n = live ? Math.min(sentiment.length, N_SLOTS) : 0;

  for (let i = 0; i < N_SLOTS; i++) {
    const mesh = _nodes[i];
    const link = _links[i];
    const show = i < n;
    if (!show) {
      mesh.visible = false;
      link.visible = false;
      continue;
    }
    const x = -SPAN / 2 + (SPAN * i) / (N_SLOTS - 1);
    const sc = Math.max(-1, Math.min(1, sentiment[i]));
    const y = baseY + sc * AMP;

    mesh.visible = true;
    mesh.position.set(x, y, 0);
    const strong = Math.abs(sc) > 0.7;
    const col = strong ? C_TOP : C_NODE;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = 0.2 + 0.7 * Math.abs(sc);
    mesh.material.opacity = 0.9;
    if (strong) _flash[i] = Math.min(30 + Math.abs(sc) * 60, 90);

    link.visible = true;
    const pos = link.geometry.attributes.position;
    pos.setXYZ(0, x, baseY, 0);
    pos.setXYZ(1, x, y, 0);
    pos.needsUpdate = true;
    link.material.color.setHex(C_GRID);
    link.material.opacity = 0.3;
  }

  _spine.material.color.setHex(live ? C_NODE : C_DIM);
  _spine.material.opacity = live ? 0.4 : 0.15;

  if (_ribbon) {
    if (live && n > 0) {
      const pos = _ribbon.geometry.attributes.position;
      for (let i = 0; i < N_SLOTS; i++) {
        const x = -SPAN / 2 + (SPAN * i) / (N_SLOTS - 1);
        const cap = i < capability.length ? capability[i] : (capability[capability.length - 1] || 0.9);
        // capability in [0,1]; map to a thin band so "flat" reads visually flat
        const y = baseY - 1.6 + (cap - 0.9) * 4.0;
        pos.setXYZ(i, x, y, 0);
      }
      pos.needsUpdate = true;
      _ribbon.visible = true;
      _ribbon.material.color.setHex(C_ACCENT);
      _ribbon.material.opacity = 0.6;
    } else {
      _ribbon.visible = false;
    }
  }

  if (_hub) {
    if (live && S.vecNorm != null) {
      const s = 0.6 + Math.min(1.4, S.vecNorm / 30);
      _hub.scale.setScalar(s);
      _hub.material.color.setHex(C_TOP);
      _hub.material.emissive.setHex(C_TOP);
      _hub.material.opacity = 0.6;
    } else {
      _hub.scale.setScalar(0.6);
      _hub.material.color.setHex(C_DIM);
      _hub.material.emissive.setHex(C_DIM);
      _hub.material.opacity = 0.25;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.15;
  if (_hub) { _hub.rotation.y += 0.008; _hub.rotation.x += 0.004; }

  const live = S.state === "live";
  _nodes.forEach((mesh, i) => {
    if (_flash[i] > 0) {
      _flash[i] -= 1;
      const f = _flash[i] / 90;
      const col = live ? C_TOP : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.2 + 0.9 * f);
    }
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "activation addition", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A <b>steering vector</b> is the mean difference of residual-stream activations on a ' +
    'contrastive prompt pair (<b>\u201cLove\u201d</b> vs <b>\u201cHate\u201d</b>); scaled by a ' +
    'coefficient and <b>added</b> into the forward pass at one layer, it shifts the model\u2019s ' +
    'output <b>sentiment</b> while a held-out <b>capability</b> metric stays flat \u2014 inference-time ' +
    'control, no fine-tuning. Honesty label <b>MODELED</b> (no real model weights/activations). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "steering vectors (ActAdd / RepE)";
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

  grid.appendChild(kpiRow("st-layer",  "injection layer"));
  grid.appendChild(kpiRow("st-pair",   "contrastive pair"));
  grid.appendChild(kpiRow("st-norm",   "steering vector norm \u2014 MODELED"));
  grid.appendChild(kpiRow("st-shift",  "sentiment_shift (sweep effect)"));
  grid.appendChild(kpiRow("st-drift",  "capability_drift (held-out cost)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Turner et al. arXiv:2308.10248 (ActAdd) \u00b7 Zou et al. arXiv:2310.01405 (RepE). MODELED \u00b7 not claimed-as.";
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
  pd.id = "st-plain";
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
  const shift = S.sentimentShift  != null ? S.sentimentShift.toFixed(2)  : "loading\u2026";
  const drift = S.capabilityDrift != null ? S.capabilityDrift.toFixed(3) : "loading\u2026";
  const layer = S.layer != null ? String(S.layer) : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of retraining a model, you can nudge its behaviour at " +
    "the moment it answers. Take one example of what you want more of (\u201cLove\u201d) and one " +
    "of what you want less of (\u201cHate\u201d), find the internal direction that separates them at " +
    "layer <b>" + layer + "</b>, then add a scaled copy of that direction into every answer. " +
    "Turning the dial up shifted the output's <b>sentiment by " + shift + "</b> on our scale, " +
    "while a separate, unrelated skill check moved by only <b>" + drift + "</b> \u2014 showing the " +
    "nudge is targeted, not a lobotomy. No retraining, no fine-tuning: this is a live dial, not " +
    "a rewrite. This view is a <b>MODELED</b> simulation of the technique, not a readout from a " +
    "live production model.";
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
  _set("st-layer", t || (S.layer != null ? String(S.layer) : "\u2014"));
  _set("st-pair",  t || (S.pair ? ('"' + S.pair.positive + '" vs "' + S.pair.negative + '"') : "\u2014"));
  _set("st-norm",  t || fx(S.vecNorm, 3));
  _set("st-shift", t || fx(S.sentimentShift, 4));
  _set("st-drift", t || fx(S.capabilityDrift, 4));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "activation addition" });
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
  _spine = null; _nodes = []; _links = []; _ribbon = null; _hub = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.layer = S.dModel = S.pair = S.vecNorm = null;
  S.coeffs = S.sentiment = S.capability = S.sentimentShift = S.capabilityDrift = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
