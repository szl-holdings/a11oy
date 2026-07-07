// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/edgefusion.js — EDGEFUSION: energy-proportional, Λ-gated multi-sensor
// edge fusion (SZL synthesis) for the holographic frontier ring. Heterogeneous
// sensors sit on an outer arc; each modeled track flows inward, is FUSED by
// inverse-variance weighting, and passes a central Λ-GATE (Λ = Conjecture 1 —
// gray, NEVER green). Admitted tracks glow proof-teal, Λ-gated / inconsistent
// tracks stay grey. The gate core scales with the CAPPED trust (≤0.97). A compact
// HUD shows the fusion / energy / gate stats and the signed-fusion-receipt-per-
// write DESIGN (nothing minted on a read). Live snapshot:
//   /api/a11oy/v1/frontier/edgefusion
//
// This is an SZL CROSS-AXIS SYNTHESIS no published system ships together:
//   multi-sensor fusion (BEVFusion / TransFuser / VINS-Fusion) + energy-
//   proportional / carbon-aware inference (MLPerf Power / CarbonCall) + a
//   neuromorphic (SNN / Loihi) efficiency factor + the Λ trust gate + a signed
//   fusion-receipt-per-write chain.
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   BEVFusion — Liu et al. 2022, arXiv:2205.13542
//   TransFuser — Chitta et al. 2022, arXiv:2205.15997
//   VINS-Fusion — HKUST-Aerial-Robotics
//   MLPerf Power — Tschand et al. 2024, arXiv:2410.12032
//   CarbonCall — 2025, arXiv:2504.20348
//   snnTorch — Eshraghian et al. 2021, arXiv:2109.12894
//   Loihi — Davies et al. 2018, IEEE Micro
//
// HONESTY LABELS: MODELED (deterministic multi-sensor scene + inverse-variance
//   fusion + parametric joules model; read VERBATIM from JSON, never upgraded).
//   The SZL SYNTHESIS is CONJECTURE: Λ as a per-track trust gate is Λ = Conjecture
//   1 (gray, never green), and the signed-fusion-receipt-per-write chain is design-
//   only (RECEIPT-ON-WRITE — nothing minted or signed on this GET). Energy is
//   MODELED, NOT MEASURED (no NVML/RAPL/Loihi meter wired). Trust capped at 0.97.
// COLOURS: lattice-blue 0x5b8dee (sensors / track links), violet-blue 0x8a6bff
//   (Λ-gate ring), proof-teal 0x3af4c8 (admitted track / accent), greys (gated-out
//   / inconsistent / degraded). Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "edgefusion";
const TITLE = "EdgeFusion · Λ-Gated Energy-Proportional Sensor Fusion (live)";

// Served SAME-ORIGIN by szl_edgefusion.py — a deterministic governed-fusion model.
const EP = "/api/a11oy/v1/frontier/edgefusion?seed=42&n_tracks=48&n_sensors=4&horizon=64";

// data-viz hues — purple BANNED
const C_SENSOR = 0x5b8dee;  // lattice-blue (sensor emitter / track link)
const C_GATE   = 0x8a6bff;  // violet-blue (Λ-gate ring)
const C_ADMIT  = 0x3af4c8;  // proof-teal (admitted track / accent)
const C_GATED  = 0x5a6570;  // grey (Λ-gated-out / inconsistent)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// layout geometry
const SENSOR_R  = 7.0;   // radius of the outer sensor arc
const MAX_TRACK = 96;    // cap on track meshes rendered (matches backend _TRACK_CAP)
const MAX_SENS  = 6;     // cap on sensor emitters (matches backend _SENSOR_BANK)
const GATE_Y    = 0.7;   // height of the central Λ-gate core

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles
let _floor    = null;
let _sensMesh = [];   // Array<THREE.Mesh> — sensor emitters on the outer arc
let _gateRing = null; // THREE.LineLoop — Λ-gate ring
let _core     = null; // THREE.Mesh — central gate core (scales with trust)
let _trkMesh  = [];   // Array<THREE.Mesh> — fused-track particles
let _trkLine  = [];   // Array<THREE.Line> — track -> gate links

// live state
const S = {
  label: null,
  nTracks: null, nSensors: null, horizon: null,
  sensors: null,           // sensors[] {name, sigma, joules}
  tracks: null,            // tracks[] (per-track)
  admits: null, gatedOut: null,
  meanConf: null, meanAgree: null, consistencyRate: null,
  meanLambda: null, lambdaMax: null, admitThresh: null,
  trust: null, trustCap: null,
  joules: null, joulesIdle: null, neuro: null, neuroFactor: null,
  receiptSigned: null, receiptDigest: null,
  state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 10, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSensors();
  _buildGate();
  _buildTracks();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  // top-N sensor labels (billboarded) + hover tooltip via the shared helper.
  _show.attachSceneLabels({
    objects: () => _sensMesh.filter((m) => m.visible),
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.userData ? o.userData.weight : 0),
    topN: MAX_SENS,
    hover: true,
  });

  _polls.push(ctx.live.poll(EP, 5000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paint(); },
  }));
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(48, 48, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Sensor emitters: up to MAX_SENS nodes on the outer arc (front hemisphere), each
// a lattice-blue node; a lower-sigma (better) sensor is drawn larger + weighted
// higher for the top-N label ranking.
function _buildSensors() {
  const THREE = _THREE;
  const geo = new THREE.OctahedronGeometry(0.34, 0);
  for (let i = 0; i < MAX_SENS; i++) {
    const a = Math.PI * (0.15 + 0.7 * (i / Math.max(1, MAX_SENS - 1))); // front arc
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_SENSOR, emissive: C_SENSOR, emissiveIntensity: 0.25, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * SENSOR_R, 1.1, Math.sin(a) * SENSOR_R);
    mesh.visible = false;
    mesh.userData = { label: "", weight: 0 };
    _group.add(mesh);
    _sensMesh.push(mesh);
  }
}

// Central Λ-gate: an advisory ring + a core that scales with the CAPPED trust.
function _buildGate() {
  const THREE = _THREE;
  {
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * 1.9, GATE_Y, Math.sin(a) * 1.9));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const m = new THREE.LineBasicMaterial({ color: C_GATE, transparent: true, opacity: 0.45 });
    _gateRing = new THREE.LineLoop(g, m);
    _group.add(_gateRing);
  }
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.75, 1),
    new THREE.MeshStandardMaterial({ color: C_GATE, emissive: C_GATE, emissiveIntensity: 0.4, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _core.position.set(0, GATE_Y, 0);
  _group.add(_core);
}

// Fused-track particles: pre-allocated spheres arranged on a deterministic spiral
// between the sensor arc and the gate, each with a link line toward the gate core.
function _buildTracks() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.13, 8, 8);
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < MAX_TRACK; i++) {
    const t = (i + 1) / MAX_TRACK;
    const r = 2.6 + (SENSOR_R - 3.4) * Math.sqrt(t);
    const a = i * golden;
    const mesh = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_SENSOR, emissive: C_SENSOR, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    mesh.position.set(Math.cos(a) * r, 0.5 + 0.6 * Math.sin(t * 6.283), Math.sin(a) * r);
    mesh.visible = false;
    _group.add(mesh);
    _trkMesh.push(mesh);

    const lg = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), new THREE.Vector3(0, GATE_Y, 0)]);
    const lm = new THREE.LineBasicMaterial({ color: C_SENSOR, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(lg, lm);
    line.visible = false;
    _group.add(line);
    _trkLine.push(line);
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.nTracks  = typeof p.n_tracks  === "number" ? p.n_tracks  : null;
  S.nSensors = typeof p.n_sensors === "number" ? p.n_sensors : null;
  S.horizon  = typeof p.horizon   === "number" ? p.horizon   : null;
  S.sensors  = Array.isArray(p.sensors) ? p.sensors : null;
  S.tracks   = Array.isArray(p.tracks)  ? p.tracks  : null;

  const fus = (p && typeof p.fusion === "object") ? p.fusion : {};
  S.admits          = typeof fus.admitted === "number" ? fus.admitted : null;
  S.gatedOut        = typeof fus.gated_out === "number" ? fus.gated_out : null;
  S.meanConf        = typeof fus.mean_fused_confidence === "number" ? fus.mean_fused_confidence : null;
  S.meanAgree       = typeof fus.mean_sensor_agreement === "number" ? fus.mean_sensor_agreement : null;
  S.consistencyRate = typeof fus.consistency_rate === "number" ? fus.consistency_rate : null;

  const g = (p && typeof p.lambda_gate === "object") ? p.lambda_gate : {};
  S.meanLambda  = typeof g.mean_lambda_advisory === "number" ? g.mean_lambda_advisory : null;
  S.admitThresh = typeof g.admit_threshold === "number" ? g.admit_threshold : null;
  S.lambdaMax   = (g.bounds && typeof g.bounds.max === "number") ? g.bounds.max : null;
  S.trust       = typeof g.trust === "number" ? g.trust : null;
  S.trustCap    = typeof g.trust_cap === "number" ? g.trust_cap : null;

  const e = (p && typeof p.energy === "object") ? p.energy : {};
  S.joules      = typeof e.joules_per_inference === "number" ? e.joules_per_inference : null;
  S.joulesIdle  = typeof e.joules_idle_floor === "number" ? e.joules_idle_floor : null;
  S.neuro       = typeof e.neuromorphic === "boolean" ? e.neuromorphic : null;
  S.neuroFactor = typeof e.neuromorphic_factor === "number" ? e.neuromorphic_factor : null;

  const rd = (p && typeof p.receipt_design === "object") ? p.receipt_design : {};
  S.receiptSigned = typeof rd.signed === "boolean" ? rd.signed : null;
  S.receiptDigest = typeof rd.receipt_preview_digest === "string" ? rd.receipt_preview_digest : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";

  // gate ring degrades to grey when not live
  if (_gateRing) {
    _gateRing.material.color.setHex(live ? C_GATE : C_DIM);
    _gateRing.material.opacity = live ? 0.45 : 0.12;
  }

  // sensor emitters: light up the active sensor set; size ~ inverse sigma (better
  // sensor = larger), label = name + sigma, weight for the top-N ranking.
  const sens = live && S.sensors ? S.sensors : [];
  for (let i = 0; i < MAX_SENS; i++) {
    const mesh = _sensMesh[i];
    const s = i < sens.length ? sens[i] : null;
    if (!s) { mesh.visible = false; mesh.userData.label = ""; mesh.userData.weight = 0; continue; }
    mesh.visible = true;
    const sigma = typeof s.sigma === "number" ? s.sigma : 0.5;
    const w = 1 / Math.max(0.05, sigma);
    mesh.userData.label = (s.name || ("s" + i)) + " σ" + sigma.toFixed(2);
    mesh.userData.weight = w;
    mesh.material.color.setHex(live ? C_SENSOR : C_DIM);
    mesh.material.emissive.setHex(live ? C_SENSOR : C_DIM);
    mesh.material.emissiveIntensity = live ? 0.3 : 0.1;
    mesh.material.opacity = live ? 0.9 : 0.3;
    mesh.scale.setScalar(0.7 + Math.min(1.4, w * 0.28));
  }

  // fused tracks: colour by verdict — admitted proof-teal, Λ-gated/inconsistent
  // grey (the advisory verdict is always shown, never hidden). Size ~ fused conf.
  const trk = live && S.tracks ? S.tracks.slice(0, MAX_TRACK) : [];
  for (let i = 0; i < MAX_TRACK; i++) {
    const mesh = _trkMesh[i];
    const line = _trkLine[i];
    const t = i < trk.length ? trk[i] : null;
    if (!t) { mesh.visible = false; line.visible = false; continue; }
    mesh.visible = true; line.visible = true;
    const admitted = !!t.admitted;
    const conf = typeof t.fused_confidence === "number" ? t.fused_confidence : 0.5;
    const col = admitted ? C_ADMIT : C_GATED;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = admitted ? 0.6 : 0.12;
    mesh.material.opacity = admitted ? 0.95 : 0.4;
    mesh.scale.setScalar(0.7 + conf * 1.0);
    line.material.color.setHex(col);
    line.material.opacity = admitted ? 0.5 : 0.15;
  }

  // gate core: colour + size reflect the CAPPED trust (never green / never 1.0).
  if (_core) {
    if (live && S.trust != null) {
      _core.material.color.setHex(C_ADMIT);
      _core.material.emissive.setHex(C_ADMIT);
      _core.material.opacity = 0.85;
      _core.scale.setScalar(0.6 + S.trust * 1.0);
    } else {
      _core.material.color.setHex(C_DIM);
      _core.material.emissive.setHex(C_DIM);
      _core.material.opacity = 0.3;
      _core.scale.setScalar(0.6);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.12;
  if (_gateRing) _gateRing.rotation.y += 0.0015;
  if (_core) {
    _core.rotation.y += 0.02;
    _core.rotation.x += 0.008;
    const pulse = 1.0 + 0.1 * Math.sin(t * 0.0035);
    const base = (S.state === "live" && S.trust != null) ? (0.6 + S.trust * 1.0) : 0.6;
    _core.scale.setScalar(base * pulse);
  }
}

// =============================================================================
// showcase overlay (shared helper) — compact chrome + collapsible KPIs
// =============================================================================
function _buildShowcase(ctx) {
  _show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "MODELED", text: "fusion + energy", name: "ef" },
      { label: "STRUCTURAL-ONLY", text: "Λ=Conjecture 1 · receipt design", name: "syn" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>EdgeFusion.</b> Heterogeneous sensors (outer arc) feed MODELED tracks that are " +
      "fused by <b>inverse-variance weighting</b>, then pass a central <b>Λ-gate</b> " +
      "(Λ = Conjecture 1 — gray, NEVER green). Admitted tracks glow proof-teal, Λ-gated / " +
      "inconsistent tracks stay grey; the core scales with the capped trust (≤0.97). A " +
      "MODELED joules-per-inference readout scales with the active sensor+track workload " +
      "(energy-proportional; optional neuromorphic factor). Energy is <b>MODELED, not " +
      "MEASURED</b> — no NVML/RAPL/Loihi meter is wired.",
    citations:
      "BEVFusion arXiv:2205.13542 · TransFuser 2205.15997 · VINS-Fusion (HKUST) · " +
      "MLPerf Power 2410.12032 · CarbonCall 2504.20348 · snnTorch 2109.12894 · Loihi (IEEE Micro 2018). " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "Many different sensors (camera, lidar, radar, …) each see the world imperfectly. " +
        "EdgeFusion combines them so the good sensors count more — that's the inward flow to " +
        "the middle. A <b>trust gate</b> in the centre decides which combined tracks are " +
        "reliable enough to act on: teal = admitted, grey = held back. It also estimates the " +
        "<b>energy per decision</b> so an edge device can stay power-frugal. The gate is a " +
        "restraint idea we call Λ — an honest <b>conjecture</b>, so it's drawn grey and its " +
        "trust never hits 100%. Nothing is signed or saved just by looking at this page.",
    },
  });

  _f.workload = _show.addField("sensors / tracks", "workload");
  _f.conf     = _show.addField("mean fused confidence", "conf");
  _f.agree    = _show.addField("mean sensor agreement", "agree");
  _f.cons     = _show.addField("consistency rate", "cons");
  _f.lambda   = _show.addField("mean Λ advisory (gray)", "lambda");
  _f.gate     = _show.addField("Λ-gate admits / gated-out", "gate");
  _f.trust    = _show.addField("trust (capped ≤0.97)", "trust");
  _f.energy   = _show.addField("energy / inference (MODELED)", "energy");
  _f.receipt  = _show.addField("fusion receipt", "receipt");
  _f.label    = _show.addField("honesty label", "label");
  _paint();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function pct(v, d) { return typeof v === "number" ? (v * 100).toFixed(d) + "%" : "—"; }
function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(k, v) { if (_f[k]) _f[k].textContent = v; }

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("ef", S.label || "MODELED", { text: "fusion + energy" });

  _set("workload", t || (S.nSensors != null || S.nTracks != null
        ? (S.nSensors != null ? S.nSensors : "—") + " / " + (S.nTracks != null ? S.nTracks : "—") : "—"));
  _set("conf",  t || pct(S.meanConf, 1));
  _set("agree", t || pct(S.meanAgree, 1));
  _set("cons",  t || pct(S.consistencyRate, 1));
  _set("lambda", t || (S.meanLambda != null
        ? fx(S.meanLambda, 3) + (S.lambdaMax != null ? " (max " + S.lambdaMax + ")" : "") : "—"));
  _set("gate",  t || (S.admits != null || S.gatedOut != null
        ? (S.admits != null ? S.admits : "—") + " / " + (S.gatedOut != null ? S.gatedOut : "—") : "—"));
  _set("trust", t || (S.trust != null ? fx(S.trust, 3) + (S.trustCap != null ? " (≤" + S.trustCap + ")" : "") : "—"));
  _set("energy", t || (S.joules != null
        ? S.joules.toFixed(4) + " J" + (S.neuro ? " · neuro ×" + (S.neuroFactor != null ? S.neuroFactor : "?") : "")
        : "—"));
  _set("receipt", t || (S.receiptSigned === false
        ? "unsigned preview" + (S.receiptDigest ? " " + S.receiptDigest.slice(0, 10) + "…" : "")
        : (S.receiptDigest ? S.receiptDigest.slice(0, 10) + "…" : "—")));
  _set("label", t || (S.label || "MODELED"));
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
  _floor = null; _sensMesh = []; _gateRing = null; _core = null; _trkMesh = []; _trkLine = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.nTracks = S.nSensors = S.horizon = S.sensors = S.tracks = null;
  S.admits = S.gatedOut = S.meanConf = S.meanAgree = S.consistencyRate = null;
  S.meanLambda = S.lambdaMax = S.admitThresh = S.trust = S.trustCap = null;
  S.joules = S.joulesIdle = S.neuro = S.neuroFactor = null;
  S.receiptSigned = S.receiptDigest = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
