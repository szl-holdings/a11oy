// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/worldmodel.js — LATENT WORLD-MODEL / PHYSICAL-PREDICTION organ for the
// holographic frontier ring, inspired by (clean-room, not a reproduction of) Meta's
// V-JEPA 2 self-supervised video world model.
//
// Renders the latent rollout as a 3D trajectory: OBSERVED latent points (ground-truth
// path) vs PREDICTED latent points (the ẑ_{t+1} JEPA-style predictor output), each
// projected from the high-dimensional latent space onto 3 display axes. The gap between
// the two paths at each step is the "physical surprise" (L2 distance) — it animates as a
// pulsing connector whose length/brightness tracks the live prediction_error. Honesty
// label "MODELED" is read VERBATIM from the JSON and displayed as-is; never upgraded.
//
// Surface export shape (mirrors interpretability.js / neuromorphic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   prediction_error          — mean L2 distance, predicted vs observed latent (↓ better)
//   physical_surprise[]       — per-step L2 "surprise" (JEPA prediction-error signal)
//   action_anticipation_acc   — MODELED analogue of V-JEPA 2's action-anticipation accuracy
//   free_energy_consistency   — MODELED energy/free-energy-style on-manifold consistency
//   observed_latents[] / predicted_latents[] — the rollout trajectory (latent_dim-D, we
//                               project the first 3 dims to XYZ for display)
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   V-JEPA 2: Assran, Bardes, Fan et al. (2025) arXiv:2506.09985
//     https://arxiv.org/abs/2506.09985
//   V-JEPA 2 code + pretrained encoders (Meta FAIR):
//     https://github.com/facebookresearch/vjepa2
//   JEPA position paper: LeCun (2022) "A Path Towards Autonomous Machine Intelligence"
//     https://openreview.net/pdf?id=BZ5a1r-kVsf
//
// HONESTY LABELS: MODELED (simulation of the JEPA METHOD; no real video, no real robot
//   data, no trained weights). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (observed/ground-truth path), violet-blue 0x8a6bff
//   (predicted path + surprise-gap flash — data-viz only), proof-teal 0x3af4c8 (consistency
//   halo), greys for degraded/no-data. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

const ID    = "worldmodel";
const TITLE = "World Model · Latent Physical Prediction (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the world-model organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/worldmodel/predict?seed=42&horizon=12&latent_dim=16";

// data-viz hues — purple BANNED
const C_OBS    = 0x5b8dee;  // lattice-blue (observed / ground-truth latent path)
const C_PRED   = 0x8a6bff;  // violet-blue (predicted latent path — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (free-energy consistency halo)
const C_GRID   = 0x1b3a44;  // floor / link colour

const MAX_STEPS = 64;  // visual cap on rollout points (endpoint clamps horizon<=64)
const SCALE     = 1.8; // world-unit scale applied to projected latent coordinates

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _obsPts = [];     // Array<THREE.Mesh> — observed latent nodes
let _predPts = [];    // Array<THREE.Mesh> — predicted latent nodes
let _obsLine = null;  // THREE.Line — observed path
let _predLine = null; // THREE.Line — predicted path
let _gaps = null;     // THREE.LineSegments — surprise connectors (obs[i+1] <-> pred[i])
let _halo = null;     // THREE.Mesh — free-energy consistency halo

// per-gap flash timers (index by step)
let _flash = new Float32Array(MAX_STEPS);

// live state
const S = {
  label:        null,
  predErr:      null,   // prediction_error
  surprise:     null,   // physical_surprise[]
  actionAcc:    null,   // action_anticipation_acc
  consistency:  null,   // free_energy_consistency
  observed:     null,   // observed_latents[]
  predicted:    null,   // predicted_latents[]
  horizon:      null,
  latentDim:    null,
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildHalo();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onPredict, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

function _buildHalo() {
  const THREE = _THREE;
  // Free-energy consistency halo — a torus around the trajectory's centroid whose
  // fullness/brightness tracks free_energy_consistency (higher = tighter/on-manifold).
  _halo = new THREE.Mesh(
    new THREE.TorusGeometry(1.4, 0.03, 10, 64),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.35, transparent: true, opacity: 0.45 }),
  );
  _halo.position.set(0, 1.2, 0);
  _halo.rotation.x = Math.PI / 2;
  _group.add(_halo);
}

// project a latent_dim-D vector to XYZ using its first 3 dims (or fewer, padded with 0)
function _project(vec) {
  const x = (vec[0] || 0) * SCALE;
  const y = 1.2 + (vec[1] || 0) * SCALE * 0.6;
  const z = (vec[2] || 0) * SCALE;
  return [x, y, z];
}

function _disposeTrajectory() {
  const THREE = _THREE;
  [_obsPts, _predPts].forEach((arr) => {
    arr.forEach((m) => {
      if (m.geometry && m.geometry.dispose) m.geometry.dispose();
      if (m.material && m.material.dispose) m.material.dispose();
      if (_group) _group.remove(m);
    });
  });
  _obsPts = []; _predPts = [];
  [_obsLine, _predLine, _gaps].forEach((o) => {
    if (!o) return;
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material && o.material.dispose) o.material.dispose();
    if (_group) _group.remove(o);
  });
  _obsLine = _predLine = _gaps = null;
}

// (re)build the trajectory geometry from live observed/predicted latents
function _buildTrajectory() {
  const THREE = _THREE;
  _disposeTrajectory();
  const obs = S.observed || [];
  const pred = S.predicted || [];
  if (!obs.length) return;

  const nodeGeo = new THREE.SphereGeometry(0.16, 12, 8);

  // observed path (ground-truth latent trajectory)
  const obsPositions = [];
  obs.forEach((v, i) => {
    const [x, y, z] = _project(v);
    obsPositions.push(new THREE.Vector3(x, y, z));
    const mat = new THREE.MeshStandardMaterial({ color: C_OBS, emissive: C_OBS, emissiveIntensity: 0.3, metalness: 0.2, roughness: 0.5 });
    const mesh = new THREE.Mesh(nodeGeo, mat);
    mesh.position.set(x, y, z);
    _group.add(mesh);
    _obsPts.push(mesh);
  });
  const obsLineGeo = new THREE.BufferGeometry().setFromPoints(obsPositions);
  _obsLine = new THREE.Line(obsLineGeo, new THREE.LineBasicMaterial({ color: C_OBS, transparent: true, opacity: 0.65 }));
  _group.add(_obsLine);

  // predicted path (ẑ_{t+1} predictor output) — offset slightly so both paths are visible
  const predPositions = [];
  const gapPts = [];
  pred.forEach((v, i) => {
    const [x, y, z] = _project(v);
    predPositions.push(new THREE.Vector3(x, y, z));
    const mat = new THREE.MeshStandardMaterial({ color: C_PRED, emissive: C_PRED, emissiveIntensity: 0.3, metalness: 0.2, roughness: 0.5, wireframe: false });
    const mesh = new THREE.Mesh(nodeGeo, mat);
    mesh.scale.setScalar(0.8);
    mesh.position.set(x, y, z);
    _group.add(mesh);
    _predPts.push(mesh);

    // surprise connector: predicted[i] <-> observed[i+1] (the actual next ground-truth state)
    const nextObs = obs[i + 1];
    if (nextObs) {
      const [ox, oy, oz] = _project(nextObs);
      gapPts.push(new THREE.Vector3(x, y, z), new THREE.Vector3(ox, oy, oz));
    }
  });
  const predLineGeo = new THREE.BufferGeometry().setFromPoints(predPositions);
  _predLine = new THREE.Line(predLineGeo, new THREE.LineBasicMaterial({ color: C_PRED, transparent: true, opacity: 0.65 }));
  _group.add(_predLine);

  const gapGeo = new THREE.BufferGeometry().setFromPoints(gapPts);
  _gaps = new THREE.LineSegments(gapGeo, new THREE.LineBasicMaterial({ color: C_PRED, transparent: true, opacity: 0.35 }));
  _group.add(_gaps);

  // seed flash timers proportional to per-step physical_surprise (bigger surprise -> brighter pulse)
  const surprise = S.surprise || [];
  const maxS = surprise.reduce((m, v) => Math.max(m, v || 0), 0.0001);
  for (let i = 0; i < MAX_STEPS; i++) {
    const norm = i < surprise.length ? (surprise[i] / maxS) : 0;
    _flash[i] = norm * 90;
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onPredict(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.predErr     = typeof j.prediction_error === "number" ? j.prediction_error : null;
  S.surprise    = Array.isArray(j.physical_surprise) ? j.physical_surprise : null;
  S.actionAcc   = typeof j.action_anticipation_acc === "number" ? j.action_anticipation_acc : null;
  S.consistency = typeof j.free_energy_consistency === "number" ? j.free_energy_consistency : null;
  S.observed    = Array.isArray(j.observed_latents) ? j.observed_latents : null;
  S.predicted   = Array.isArray(j.predicted_latents) ? j.predicted_latents : null;
  S.horizon     = typeof j.rollout_horizon === "number" ? j.rollout_horizon : null;
  S.latentDim   = typeof j.latent_dim === "number" ? j.latent_dim : null;

  _buildTrajectory();
  _updateHalo();
  _paintOverlay();
}

// =============================================================================
// geometry updater — halo driven by free_energy_consistency
// =============================================================================
function _updateHalo() {
  const live = S.state === "live";
  if (!_halo) return;
  const cons = S.consistency != null ? S.consistency : 0.5;
  const col = live ? C_ACCENT : C_DIM;
  _halo.material.color.setHex(col);
  _halo.material.emissive.setHex(col);
  _halo.material.emissiveIntensity = live ? 0.2 + 0.6 * cons : 0.12;
  _halo.material.opacity = live ? 0.5 : 0.2;
  _halo.scale.setScalar(live ? (0.6 + cons) : 0.8);  // fuller halo = higher consistency
}

// =============================================================================
// per-frame animation — the surprise gap "pulses" to animate physical surprise
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00010) * 0.18;
  if (_halo) _halo.rotation.z += 0.004;

  const live = S.state === "live";

  _predPts.forEach((mesh, i) => {
    const base = 0.8;
    if (_flash[i] > 0) {
      _flash[i] -= 0.6;
      const f = Math.max(0, _flash[i]) / 90;
      const col = live ? C_PRED : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.2 + 0.9 * f;
      mesh.scale.setScalar(base + 0.5 * f);
    } else {
      mesh.scale.setScalar(base);
    }
  });

  if (_gaps && live) {
    const pulse = 0.25 + 0.2 * Math.abs(Math.sin(t * 0.003));
    _gaps.material.opacity = pulse;
  } else if (_gaps) {
    _gaps.material.opacity = 0.1;
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
    maxWidth: "min(94%,440px)",
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
    'A <b>latent world model</b> predicts the next state \u1e91\u2095\u208a\u2081 in ' +
    '<b>representation space</b> \u2014 never pixels \u2014 the JEPA principle behind Meta ' +
    'V-JEPA 2. The gap between the predicted (violet) and observed (blue) path is the ' +
    '<b>physical surprise</b>. Honesty label <b>MODELED</b> (a simulation of the method ' +
    '\u2014 no real video, no robot data, no trained weights). 0 runtime CDN.';
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
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "worldmodel";
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

  grid.appendChild(kpiRow("wm-err",    "prediction error (mean L2)"));
  grid.appendChild(kpiRow("wm-surp",   "physical surprise (latest step)"));
  grid.appendChild(kpiRow("wm-acc",    "action-anticipation acc \u2014 MODELED"));
  grid.appendChild(kpiRow("wm-cons",   "free-energy consistency"));
  grid.appendChild(kpiRow("wm-dim",    "latent_dim \u00d7 horizon"));
  grid.appendChild(kpiRow("wm-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Assran, Bardes, Fan et al. arXiv:2506.09985 (V-JEPA 2) \u00b7 github.com/facebookresearch/vjepa2 \u00b7 LeCun 2022 JEPA position paper (OpenReview). MODELED \u00b7 not claimed-as.";
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
  pd.id = "wm-plain";
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
  const err = S.predErr != null ? S.predErr.toFixed(4) : "loading\u2026";
  const acc = S.actionAcc != null ? (S.actionAcc * 100).toFixed(1) + "%" : "loading\u2026";
  const cons = S.consistency != null ? (S.consistency * 100).toFixed(1) + "%" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Instead of predicting the next video frame pixel-by-pixel, " +
    "this world model predicts the next <b>abstract state</b> of a scene \u2014 the same " +
    "trick Meta\u2019s V-JEPA 2 uses to learn physics from watching video. Right now its " +
    "average miss (\u201cphysical surprise\u201d) is <b>" + err + "</b>, its modeled ability " +
    "to anticipate what happens next is <b>" + acc + "</b>, and its rollout stays <b>" + cons +
    "</b> consistent with a physically plausible trajectory. " +
    "Plain: this is the shape of computation that lets an AI reason about cause-and-effect " +
    "in the physical world without labeling every pixel \u2014 but this view is a <b>MODELED</b> " +
    "simulation of the technique, not a readout from a trained V-JEPA 2 model or real video.";
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
  _set("wm-err",   t || fx(S.predErr, 5));
  const lastSurprise = (S.surprise && S.surprise.length) ? S.surprise[S.surprise.length - 1] : null;
  _set("wm-surp",  t || fx(lastSurprise, 5));
  _set("wm-acc",   t || (S.actionAcc != null ? (S.actionAcc * 100).toFixed(1) + "%" : "\u2014"));
  _set("wm-cons",  t || fx(S.consistency, 4));
  _set("wm-dim",   t || ((S.latentDim != null && S.horizon != null) ? (S.latentDim + " \u00d7 " + S.horizon) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("wm-label", t || (S.label || "MODELED"));
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
  _obsPts = []; _predPts = []; _obsLine = null; _predLine = null; _gaps = null; _halo = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.predErr = S.surprise = S.actionAcc = S.consistency = null;
  S.observed = S.predicted = S.horizon = S.latentDim = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
