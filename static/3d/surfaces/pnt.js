// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/pnt.js — PNT · Quantum Nav surface (Dev3).
//
// Leader/technique modeled: Q-CTRL Ironstone Opal + Advanced Navigation —
//   trajectory tube + covariance uncertainty ellipsoid + CRLB sensitivity surface +
//   classical-vs-quantum GPS-denied drift, with the 4-pillar fundamental-limits ladder.
//
// HONESTY (Doctrine v11, HARD): every number on this surface is a MODELED closed-form
// physics result read straight from the live a11oy mesh — NOT flown hardware, NOT a real
// flight. The sensor cert is "VERIFIED (MODELED) · UNSIGNED (STRUCTURAL-ONLY)"; we render
// exactly the label the JSON carries (meta.label / json.label, almost always MODELED).
// This surface feeds the DARPA PINPOINT story so we NEVER imply a real measurement.
//
// Live endpoints (ctx.live.poll — never hardcoded telemetry):
//   /api/a11oy/v1/pnt/sensor      closed_form_stdlib{ k_eff_per_m, shot_noise_phase_rad,
//                                  per_shot_accel_sensitivity_m_s2, accel_asd_m_s2_per_sqrt_hz,
//                                  inputs{ wavelength_m, interrogation_time_s, atom_number,
//                                  contrast, cycle_time_s }, formulas{...} }, label, SQL flag
//   /api/a11oy/v1/pnt/coast       closed_form_stdlib{ classical{position_error_m},
//                                  quantum{position_error_m}, improvement_factor } (MODELED)
//   /api/a11oy/v1/pnt/resilience  closed_form_stdlib{ verdict, allow, n_layers_fired,
//                                  layers{raim_consistency,agc_power,sqm_asymmetry} } (MODELED)
//   /api/a11oy/v1/pnt/limits      pillars{ compute_bounds, quantum_sensor, pnt_resilience,
//                                  nav_coasting }{ wired, module, note } (honest discovery)
//
// CONTRACT (Dev0): default-export { id, title, endpoints[], mount(ctx), unmount() }.
// ctx = { stage, container, live, label, THREE, szl3d }. Frame callbacks accumulate on the
// shared stage and are NOT removed on unmount, so every onFrame closure guards on _alive.

import { createShowcase } from "./_showcase.js";

const ID = "pnt";
const TITLE = "PNT · Quantum Nav";
const ENDPOINT = "/api/a11oy/v1/pnt/sensor";
const COAST_EP = "/api/a11oy/v1/pnt/coast";
const RESIL_EP = "/api/a11oy/v1/pnt/resilience";
const LIMITS_EP = "/api/a11oy/v1/pnt/limits";

// Doctrine palette (matches the shell + szl3d_label hexes).
const C_QUANTUM = 0x39d3c4;   // teal  — quantum / bounded
const C_CLASSIC = 0xff6b6b;   // red   — classical / diverging
const C_GOLD    = 0xe8c074;   // amber — MODELED accent
const C_CREAM   = 0xeef3f6;
const C_BLUE    = 0x6fb1ff;
const C_GRID    = 0x1b2734;

let _stage = null, _THREE = null, _label = null;
let _alive = false;
const _handles = [];        // every live-poll handle (stopped on unmount)
const _objs = [];           // every scene object we add (removed on unmount)
const _disposables = [];    // geometries/materials/textures to dispose
let _hud = null, _show = null;
const _spin = [];           // { obj, sx, sy } per-frame rotators
const _frameFns = [];       // per-frame animators invoked while _alive

// last live snapshots (null until first successful poll — we NEVER fabricate)
let _sensor = null, _coast = null, _resil = null, _limits = null;
let _sensorLabel = null;

// ----------------------------------------------------------------------------
// small helpers
// ----------------------------------------------------------------------------
function _add(obj) { _objs.push(obj); _stage.scene.add(obj); return obj; }
function _track(x) { if (x) _disposables.push(x); return x; }
function _fmtSci(v, d = 3) {
  if (v == null || !isFinite(v)) return "—";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e-3 && a < 1e6) return (+v.toPrecision(d)).toString();
  return v.toExponential(d - 1);
}
function _glow(hex, mk) {
  const m = _track(new _THREE.MeshStandardMaterial({
    color: hex, emissive: hex, emissiveIntensity: 0.55,
    metalness: 0.3, roughness: 0.4, transparent: !!(mk && mk.transparent),
    opacity: mk && mk.opacity != null ? mk.opacity : 1.0,
    wireframe: !!(mk && mk.wireframe),
  }));
  return m;
}
function _lineMat(hex, opacity) {
  return _track(new _THREE.LineBasicMaterial({ color: hex, transparent: opacity != null, opacity: opacity == null ? 1 : opacity }));
}

// ----------------------------------------------------------------------------
// HUD (folded into the shared showcase body) — every readout chip carries its
// honesty label. The compact chrome (title bar + honesty pills + legend) is
// provided by the shared showcase; the KPI rows nest statically inside its body.
// ----------------------------------------------------------------------------
function _buildOverlay(ctx) {
  const badge = ctx.live.createBadge();

  _show = createShowcase(ctx, {
    id: ID, title: TITLE + "  ·  modeled on Q-CTRL Ironstone Opal + Advanced Navigation",
    accent: "#5b8dee",
    badge,
    chips: [{ label: _sensorLabel || "MODELED", text: "quantum sensor", name: "sensor" }],
    legend: true,
    description:
      "MODELED closed-form physics — <b>NOT flown hardware</b>, not a real flight. " +
      "Sensor cert is VERIFIED (MODELED) · UNSIGNED (STRUCTURAL-ONLY). Every value below " +
      "traces to a live /api/a11oy/v1/pnt/* endpoint; nothing is hardcoded.",
  });

  // KPI rows live in a plain static container nested inside the collapsible body
  // (no absolute chrome of its own — the showcase owns the card/panel styling).
  _hud = document.createElement("div");
  _hud.style.cssText = "position:static;display:flex;flex-direction:column;gap:5px;font:11px ui-monospace,Menlo,monospace;color:#cfe0ea";
  _show.body.appendChild(_hud);

  return badge;
}

// A labeled HUD row whose value can update live; carries an honesty chip.
function _hudRow(key) {
  const row = document.createElement("div");
  row.style.cssText = "display:flex;align-items:center;gap:7px;flex-wrap:wrap";
  const k = document.createElement("span");
  k.style.cssText = "color:#9fb1bf;min-width:152px;display:inline-block";
  k.textContent = key;
  const v = document.createElement("span");
  v.style.cssText = "color:#eef3f6;font-weight:600";
  v.textContent = "…";
  const chipHolder = document.createElement("span");
  row.appendChild(k); row.appendChild(v); row.appendChild(chipHolder);
  _hud.appendChild(row);
  return { row, valueEl: v, chipHolder, chipEl: null };
}
function _setRow(r, text, labelToken) {
  if (!r) return;
  r.valueEl.textContent = text;
  if (labelToken) {
    if (!r.chipEl) { r.chipEl = _label.chip(labelToken); r.chipHolder.appendChild(r.chipEl); }
    else _label.updateChip(r.chipEl, labelToken);
  }
}

// ----------------------------------------------------------------------------
// DEMO 1 — classical-vs-quantum nav-coasting tube (two TubeGeometry trajectories).
// Classical diverges (radius ∝ classical position_error_m), quantum stays bounded.
// The tube radius at the tip is driven by the LIVE /pnt/coast error figures.
// ----------------------------------------------------------------------------
let _classicTube = null, _quantumTube = null, _coastGroup = null;
let _classicErr = 1, _quantumErr = 1e-4;

function _coastCurve(amp, wobble, phase) {
  const pts = [];
  for (let i = 0; i <= 64; i++) {
    const t = i / 64;
    const x = -7 + t * 14;
    // bounded base path (a gentle flight arc) + divergence growing with t for classical
    const base = Math.sin(t * Math.PI) * 1.2;
    const div = amp * Math.pow(t, 1.6) * Math.sin(t * 9 + phase) * wobble;
    pts.push(new _THREE.Vector3(x, base + div, Math.cos(t * Math.PI * 1.3) * 0.8 + div * 0.5));
  }
  return new _THREE.CatmullRomCurve3(pts);
}

function _rebuildCoastTubes() {
  if (!_coastGroup) return;
  // remove prior tube meshes
  [_classicTube, _quantumTube].forEach((m) => { if (m) { _coastGroup.remove(m); m.geometry.dispose(); } });
  // map live error metres -> a visible tube radius (log-compressed; honest ordering preserved)
  const r = (e) => 0.04 + 0.55 * Math.min(1, Math.log10(1 + Math.max(0, e) * 1000) / 4);
  const cAmp = 0.35 + Math.min(2.4, Math.log10(1 + _classicErr * 1000) * 0.6);
  const cGeo = new _THREE.TubeGeometry(_coastCurve(cAmp, 1.0, 0.0), 96, r(_classicErr), 10, false);
  const qGeo = new _THREE.TubeGeometry(_coastCurve(0.06, 0.4, 1.7), 96, r(_quantumErr), 10, false);
  _classicTube = new _THREE.Mesh(cGeo, _glow(C_CLASSIC, { transparent: true, opacity: 0.55 }));
  _quantumTube = new _THREE.Mesh(qGeo, _glow(C_QUANTUM, { transparent: true, opacity: 0.7 }));
  _coastGroup.add(_classicTube); _coastGroup.add(_quantumTube);
}

function _buildCoast() {
  _coastGroup = _add(new _THREE.Group());
  _coastGroup.position.set(0, 0.2, 0);
  _rebuildCoastTubes();
  // labels
  _coastGroup.add(_label.billboard(_THREE, "MODELED", { text: "classical drift", scale: 0.5, position: [7.4, 2.6, 0] }));
  _coastGroup.add(_label.billboard(_THREE, "MODELED", { text: "quantum bounded", scale: 0.5, position: [7.4, -0.4, 0] }));
}

// ----------------------------------------------------------------------------
// DEMO 2 — covariance uncertainty ellipsoid that grows (classical) / shrinks (quantum).
// Non-uniform scale of a unit sphere; eigenvalues driven by live coast error + sensor ASD.
// ----------------------------------------------------------------------------
let _ellipsoidC = null, _ellipsoidQ = null;
function _buildEllipsoids() {
  const g = _track(new _THREE.SphereGeometry(1, 24, 18));
  _ellipsoidC = _add(new _THREE.Mesh(g, _glow(C_CLASSIC, { transparent: true, opacity: 0.16, wireframe: false })));
  _ellipsoidQ = _add(new _THREE.Mesh(g, _glow(C_QUANTUM, { transparent: true, opacity: 0.22, wireframe: false })));
  const wC = _add(new _THREE.Mesh(g, _glow(C_CLASSIC, { transparent: true, opacity: 0.35, wireframe: true })));
  const wQ = _add(new _THREE.Mesh(g, _glow(C_QUANTUM, { transparent: true, opacity: 0.5, wireframe: true })));
  // co-locate wireframes with the fills
  _ellipsoidC.userData.shell = wC; _ellipsoidQ.userData.shell = wQ;
  _ellipsoidC.position.set(-3.5, 4.6, -2);
  _ellipsoidQ.position.set(3.5, 4.6, -2);
  wC.position.copy(_ellipsoidC.position); wQ.position.copy(_ellipsoidQ.position);
  _add(_label.billboard(_THREE, "MODELED", { text: "σ classical (grows)", scale: 0.42, position: [-3.5, 6.1, -2] }));
  _add(_label.billboard(_THREE, "MODELED", { text: "σ quantum (bounded)", scale: 0.42, position: [3.5, 6.1, -2] }));
}
function _applyEllipsoids() {
  if (!_ellipsoidC) return;
  // classical grows over a breathing cycle to depict unbounded drift; quantum stays tight.
  const tnow = performance.now() * 0.001;
  const grow = 0.6 + Math.min(2.6, Math.log10(1 + _classicErr * 1000) * 0.55) * (0.85 + 0.15 * Math.sin(tnow));
  const tight = 0.18 + Math.min(0.5, Math.log10(1 + _quantumErr * 1e6) * 0.12);
  _ellipsoidC.scale.set(grow * 1.1, grow * 0.7, grow * 0.9);
  _ellipsoidQ.scale.set(tight, tight * 1.2, tight * 0.85);
  _ellipsoidC.userData.shell.scale.copy(_ellipsoidC.scale);
  _ellipsoidQ.userData.shell.scale.copy(_ellipsoidQ.scale);
}

// ----------------------------------------------------------------------------
// DEMO 3 — CRLB sensitivity surface (PlaneGeometry vertex displacement).
// z(x,y) = closed-form per-shot accel sensitivity as a function of (atom number N,
// interrogation time T) holding live k_eff & contrast — σ_a = 1/(C√N · k_eff · T²).
// Lower is better; the live operating point is marked with a beacon.
// ----------------------------------------------------------------------------
let _crlbMesh = null, _crlbBeacon = null;
const _CRLB_SEG = 40;
function _buildCRLB() {
  const geo = _track(new _THREE.PlaneGeometry(7, 7, _CRLB_SEG, _CRLB_SEG));
  geo.rotateX(-Math.PI / 2);
  const mat = _track(new _THREE.MeshStandardMaterial({
    color: C_GOLD, emissive: C_GOLD, emissiveIntensity: 0.18,
    metalness: 0.2, roughness: 0.6, wireframe: true, transparent: true, opacity: 0.7,
  }));
  _crlbMesh = _add(new _THREE.Mesh(geo, mat));
  _crlbMesh.position.set(0, -3.8, 0);
  _add(_label.billboard(_THREE, "MODELED", { text: "CRLB σ_a(N,T) surface", scale: 0.5, position: [0, -1.7, -3.6] }));
  // operating-point beacon
  const bg = _track(new _THREE.SphereGeometry(0.16, 16, 12));
  _crlbBeacon = _add(new _THREE.Mesh(bg, _glow(C_QUANTUM)));
  _crlbBeacon.position.set(0, -3.4, 0);
}
function _applyCRLB() {
  if (!_crlbMesh || !_sensor) return;
  const cf = _sensor.closed_form_stdlib || {};
  const k_eff = cf.k_eff_per_m || 1;
  const C = (cf.inputs && cf.inputs.contrast) || 0.5;
  const pos = _crlbMesh.geometry.attributes.position;
  // grid axes: x -> log10(N) in [4..8], z -> T in [0.02..0.3]
  let zmin = Infinity, zmax = -Infinity;
  const vals = [];
  for (let i = 0; i < pos.count; i++) {
    const gx = (pos.getX(i) + 3.5) / 7;   // 0..1
    const gz = (pos.getZ(i) + 3.5) / 7;   // 0..1
    const N = Math.pow(10, 4 + gx * 4);
    const T = 0.02 + gz * 0.28;
    const sigPhi = 1 / (C * Math.sqrt(N));
    const sigA = sigPhi / (k_eff * T * T);   // m/s² — same closed form as the mesh
    const z = Math.log10(sigA);              // log-compress for display
    vals.push(z); if (z < zmin) zmin = z; if (z > zmax) zmax = z;
  }
  const span = (zmax - zmin) || 1;
  for (let i = 0; i < pos.count; i++) {
    const norm = (vals[i] - zmin) / span;   // 0 (best/low σ) .. 1 (worst/high σ)
    pos.setY(i, norm * 2.6);                 // higher σ -> taller ridge
  }
  pos.needsUpdate = true;
  _crlbMesh.geometry.computeVertexNormals();
  // place the beacon at the LIVE operating point (N, T from inputs)
  const inN = (cf.inputs && cf.inputs.atom_number) || 1e6;
  const inT = (cf.inputs && cf.inputs.interrogation_time_s) || 0.1;
  const gx = Math.min(1, Math.max(0, (Math.log10(inN) - 4) / 4));
  const gz = Math.min(1, Math.max(0, (inT - 0.02) / 0.28));
  const sigPhi = 1 / (C * Math.sqrt(inN));
  const sigA = sigPhi / (k_eff * inT * inT);
  const norm = (Math.log10(sigA) - zmin) / span;
  _crlbBeacon.position.set(gx * 7 - 3.5, -3.8 + norm * 2.6 + 0.18, gz * 7 - 3.5);
}

// ----------------------------------------------------------------------------
// DEMO 4 — Standard-Quantum-Limit reference plane + flag.
// A translucent floor under the CRLB surface; turns honest-green only when the live
// sensor JSON asserts at_or_above_standard_quantum_limit === true.
// ----------------------------------------------------------------------------
let _sqlPlane = null, _sqlChipBillboard = null;
function _buildSQL() {
  const g = _track(new _THREE.PlaneGeometry(7.4, 7.4));
  g.rotateX(-Math.PI / 2);
  _sqlPlane = _add(new _THREE.Mesh(g, _track(new _THREE.MeshBasicMaterial({
    color: C_BLUE, transparent: true, opacity: 0.10, side: _THREE.DoubleSide,
  }))));
  _sqlPlane.position.set(0, -3.95, 0);
}

// ----------------------------------------------------------------------------
// DEMO 5 — 4-pillar fundamental-limits ladder (instanced bars rising from a base).
// Each pillar's bar lights teal when wired:true, gray when honestly not wired.
// ----------------------------------------------------------------------------
const _pillarBars = [];
const _PILLARS = ["compute_bounds", "quantum_sensor", "pnt_resilience", "nav_coasting"];
function _buildLadder() {
  const grp = _add(new _THREE.Group());
  grp.position.set(-6.4, -3.6, 4.2);
  _PILLARS.forEach((name, i) => {
    const g = _track(new _THREE.BoxGeometry(0.7, 1, 0.7));
    g.translate(0, 0.5, 0); // grow upward from base
    const m = _glow(C_GRID, { transparent: true, opacity: 0.85 });
    const bar = new _THREE.Mesh(g, m);
    bar.position.set(i * 1.05, 0, 0);
    bar.scale.y = 0.2;
    grp.add(bar);
    _pillarBars.push({ name, mesh: bar, mat: m });
    grp.add(_label.billboard(_THREE, "STRUCTURAL-ONLY", { text: name.replace(/_/g, " "), scale: 0.3, position: [i * 1.05, -0.55, 0] }));
  });
  _add(_label.billboard(_THREE, "MODELED", { text: "fundamental-limits ladder (4 pillars)", scale: 0.42, position: [-4.8, 1.9, 4.2] }));
}
function _applyLadder() {
  if (!_limits || !_pillarBars.length) return;
  const pil = _limits.pillars || {};
  _pillarBars.forEach((b) => {
    const p = pil[b.name] || {};
    const wired = !!p.wired;
    b.mesh.scale.y = wired ? 1.0 + 0.05 * Math.sin(performance.now() * 0.002) + 0.5 : 0.2;
    b.mat.color.setHex(wired ? C_QUANTUM : C_GRID);
    b.mat.emissive.setHex(wired ? C_QUANTUM : C_GRID);
    b.mat.emissiveIntensity = wired ? 0.55 : 0.12;
    b.mat.opacity = wired ? 0.92 : 0.5;
  });
}

// ----------------------------------------------------------------------------
// DEMO 6 — resilience verdict beacon (deny-by-default fusion).
// A ring of 3 layer lamps (RAIM / AGC / SQM) + a central verdict orb whose color is
// driven by the live verdict (ALLOW=teal, ADVISORY=amber, DENY=red). Advisory (Λ).
// ----------------------------------------------------------------------------
let _verdictOrb = null; const _layerLamps = [];
const _LAYERS = ["raim_consistency", "agc_power", "sqm_asymmetry"];
function _buildResilience() {
  const grp = _add(new _THREE.Group());
  grp.position.set(6.2, -3.4, 4.2);
  const og = _track(new _THREE.IcosahedronGeometry(0.5, 1));
  _verdictOrb = new _THREE.Mesh(og, _glow(C_GRID));
  grp.add(_verdictOrb);
  _LAYERS.forEach((name, i) => {
    const ang = (i / 3) * Math.PI * 2;
    const lg = _track(new _THREE.SphereGeometry(0.18, 12, 10));
    const lm = _glow(C_GRID, { transparent: true, opacity: 0.85 });
    const lamp = new _THREE.Mesh(lg, lm);
    lamp.position.set(Math.cos(ang) * 1.2, Math.sin(ang) * 1.2, 0);
    grp.add(lamp);
    _layerLamps.push({ name, mat: lm });
  });
  grp.add(_label.billboard(_THREE, "MODELED", { text: "resilience Λ-verdict (advisory)", scale: 0.42, position: [0, 1.8, 0] }));
  _verdictOrb.userData.grp = grp;
}
function _applyResilience() {
  if (!_verdictOrb || !_resil) return;
  const cf = _resil.closed_form_stdlib || {};
  const v = cf.verdict || "ALLOW";
  const col = v === "DENY" ? C_CLASSIC : (v === "ADVISORY" ? C_GOLD : C_QUANTUM);
  _verdictOrb.material.color.setHex(col);
  _verdictOrb.material.emissive.setHex(col);
  const layers = cf.layers || {};
  _layerLamps.forEach((l) => {
    const fired = !!layers[l.name];
    l.mat.color.setHex(fired ? C_CLASSIC : C_QUANTUM);
    l.mat.emissive.setHex(fired ? C_CLASSIC : C_QUANTUM);
    l.mat.emissiveIntensity = fired ? 0.7 : 0.3;
  });
}

// ----------------------------------------------------------------------------
// DEMO 7 — drift-cloud particle field: two clouds of waypoints, classical spreading,
// quantum bounded — instanced points around the two tubes.
// ----------------------------------------------------------------------------
let _drift = null;
function _buildDrift() {
  const N = 600;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const cC = new _THREE.Color(C_CLASSIC), cQ = new _THREE.Color(C_QUANTUM);
  for (let i = 0; i < N; i++) {
    const classical = i % 2 === 0;
    const t = Math.random();
    const x = -7 + t * 14;
    const spread = classical ? 0.15 + t * 1.7 : 0.06;
    pos[i * 3] = x + (Math.random() - 0.5) * spread;
    pos[i * 3 + 1] = (classical ? 1.6 : -0.2) + (Math.random() - 0.5) * spread;
    pos[i * 3 + 2] = (Math.random() - 0.5) * spread;
    const c = classical ? cC : cQ;
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  const g = _track(new _THREE.BufferGeometry());
  g.setAttribute("position", new _THREE.BufferAttribute(pos, 3));
  g.setAttribute("color", new _THREE.BufferAttribute(col, 3));
  const m = _track(new _THREE.PointsMaterial({ size: 0.07, vertexColors: true, transparent: true, opacity: 0.8 }));
  _drift = _add(new _THREE.Points(g, m));
  _drift.userData.base = pos.slice(0);
  _drift.userData.n = N;
}
function _animateDrift() {
  if (!_drift) return;
  const pos = _drift.geometry.attributes.position;
  const base = _drift.userData.base;
  const n = _drift.userData.n;
  const tnow = performance.now() * 0.0006;
  // classical cloud breathes wider with live classical error; quantum stays bounded
  const cAmp = 0.4 + Math.min(2.0, Math.log10(1 + _classicErr * 1000) * 0.4);
  for (let i = 0; i < n; i++) {
    const classical = i % 2 === 0;
    const a = classical ? cAmp : 0.12;
    pos.setX(i, base[i * 3] + Math.sin(tnow + i) * 0.05 * a);
    pos.setY(i, base[i * 3 + 1] + Math.cos(tnow * 1.3 + i) * 0.06 * a);
    pos.setZ(i, base[i * 3 + 2] + Math.sin(tnow * 0.7 + i * 0.5) * 0.05 * a);
  }
  pos.needsUpdate = true;
}

// ----------------------------------------------------------------------------
// DEMO 8 — k_eff momentum-transfer ring (radius ∝ live k_eff = 4π/λ) + formula chip.
// DEMO 9 — shot-noise phase dial (σ_Φ = 1/(C√N)) — a tick whose angle tracks σ_Φ.
// DEMO 10 — ASD readout column whose height tracks accel_asd_m_s2_per_sqrt_hz (log).
// (these three small instruments sit along the back rail; all driven live)
// ----------------------------------------------------------------------------
let _keffRing = null, _phaseDial = null, _asdCol = null;
function _buildInstruments() {
  // k_eff ring
  const rg = _track(new _THREE.TorusGeometry(1.0, 0.045, 12, 64));
  _keffRing = _add(new _THREE.Mesh(rg, _glow(C_GOLD)));
  _keffRing.position.set(-5.5, 2.2, -4);
  _add(_label.billboard(_THREE, "MODELED", { text: "k_eff = 4π/λ", scale: 0.36, position: [-5.5, 3.7, -4] }));
  // phase dial
  const dg = _track(new _THREE.RingGeometry(0.5, 0.62, 32));
  _add(new _THREE.Mesh(dg, _track(new _THREE.MeshBasicMaterial({ color: C_GRID, side: _THREE.DoubleSide }))))
    .position.set(0, 2.2, -4);
  const tg = _track(new _THREE.BoxGeometry(0.05, 0.55, 0.05));
  tg.translate(0, 0.27, 0);
  _phaseDial = _add(new _THREE.Mesh(tg, _glow(C_QUANTUM)));
  _phaseDial.position.set(0, 2.2, -3.95);
  _add(_label.billboard(_THREE, "MODELED", { text: "σ_Φ = 1/(C√N)", scale: 0.36, position: [0, 3.7, -4] }));
  // ASD column
  const cg = _track(new _THREE.CylinderGeometry(0.18, 0.18, 1, 16));
  cg.translate(0, 0.5, 0);
  _asdCol = _add(new _THREE.Mesh(cg, _glow(C_BLUE)));
  _asdCol.position.set(5.5, 1.4, -4);
  _asdCol.scale.y = 0.2;
  _add(_label.billboard(_THREE, "MODELED", { text: "accel ASD m/s²/√Hz", scale: 0.36, position: [5.5, 3.7, -4] }));
}
function _applyInstruments() {
  if (!_sensor) return;
  const cf = _sensor.closed_form_stdlib || {};
  if (_keffRing && cf.k_eff_per_m) {
    // k_eff ~ 1.6e7 /m -> compress to a visible radius
    const r = 0.5 + Math.min(1.4, Math.log10(cf.k_eff_per_m) / 8);
    _keffRing.scale.setScalar(r);
  }
  if (_phaseDial && cf.shot_noise_phase_rad != null) {
    // σ_Φ small -> dial near 0; map [1e-4 .. 1e-1] rad to [0 .. 270°]
    const sp = cf.shot_noise_phase_rad;
    const norm = Math.min(1, Math.max(0, (Math.log10(sp) + 4) / 3));
    _phaseDial.rotation.z = -norm * (Math.PI * 1.5);
  }
  if (_asdCol && cf.accel_asd_m_s2_per_sqrt_hz != null) {
    const asd = cf.accel_asd_m_s2_per_sqrt_hz;
    // map log10(asd) in [-10 .. -3] to [0.2 .. 3.0] column height (smaller ASD = shorter, better)
    const h = 0.2 + Math.min(2.8, Math.max(0, (Math.log10(asd) + 10) / 7) * 2.8);
    _asdCol.scale.y = h;
  }
}

// ----------------------------------------------------------------------------
// DEMO 11 — live inputs panel (λ, T, N, contrast, cycle) as floating value chips.
// DEMO 12 — improvement-factor halo whose radius tracks quantum/classical FoM.
// (rendered via HUD rows + a halo ring)
// ----------------------------------------------------------------------------
let _foMHalo = null;
function _buildFoMHalo() {
  const g = _track(new _THREE.TorusGeometry(2.0, 0.03, 8, 80));
  _foMHalo = _add(new _THREE.Mesh(g, _glow(C_QUANTUM, { transparent: true, opacity: 0.45 })));
  _foMHalo.position.set(0, 0.2, 0);
  _foMHalo.rotation.x = Math.PI / 2;
}
function _applyFoMHalo() {
  if (!_foMHalo || !_coast) return;
  const cf = _coast.closed_form_stdlib || {};
  const fom = cf.quantum_over_classical_improvement_factor || 1;
  // log-scaled radius so a 1e5 improvement is visible but bounded
  const r = 0.6 + Math.min(2.4, Math.log10(1 + fom) * 0.45);
  _foMHalo.scale.setScalar(r);
}

// ----------------------------------------------------------------------------
// HUD rows (DEMOS 13–20: live numeric readouts, each honesty-labeled)
// ----------------------------------------------------------------------------
const _rows = {};
function _buildRows() {
  _rows.keff = _hudRow("k_eff (4π/λ) /m");
  _rows.phase = _hudRow("shot-noise σ_Φ rad");
  _rows.persh = _hudRow("per-shot σ_a m/s²");
  _rows.asd = _hudRow("accel ASD m/s²/√Hz");
  _rows.sql = _hudRow("≥ Standard Quantum Limit");
  _rows.inputs = _hudRow("inputs λ/T/N/C/Tc");
  _rows.coast = _hudRow("coast σ_x classical/quantum m");
  _rows.fom = _hudRow("quantum advantage ×");
  _rows.verdict = _hudRow("resilience verdict (Λ)");
  _rows.pillars = _hudRow("limits pillars wired");
}

// ----------------------------------------------------------------------------
// live poll handlers — map JSON -> state -> HUD + scene (NEVER fabricate)
// ----------------------------------------------------------------------------
function _onSensor(json, meta) {
  if (!_alive) return;
  _sensor = json;
  const lab = meta.label || (json && json.label) || "MODELED";
  _sensorLabel = lab;
  if (_show) _show.setChip("sensor", lab, { text: "quantum sensor" });
  const cf = (json && json.closed_form_stdlib) || {};
  _setRow(_rows.keff, _fmtSci(cf.k_eff_per_m), lab);
  _setRow(_rows.phase, _fmtSci(cf.shot_noise_phase_rad), lab);
  _setRow(_rows.persh, _fmtSci(cf.per_shot_accel_sensitivity_m_s2), lab);
  _setRow(_rows.asd, _fmtSci(cf.accel_asd_m_s2_per_sqrt_hz), lab);
  // SQL flag lives inside closed_form_stdlib; fall back to the top level for forward-compat.
  const sql = (cf.at_or_above_standard_quantum_limit != null)
    ? cf.at_or_above_standard_quantum_limit
    : (json && json.at_or_above_standard_quantum_limit);
  _setRow(_rows.sql, sql === true ? "TRUE (at/above SQL)" : (sql === false ? "FALSE" : "—"), lab);
  if (_sqlPlane) {
    const ok = sql === true;
    _sqlPlane.material.color.setHex(ok ? C_QUANTUM : C_CLASSIC);
    _sqlPlane.material.opacity = ok ? 0.12 : 0.08;
  }
  const inp = cf.inputs || {};
  _setRow(_rows.inputs,
    `λ=${_fmtSci(inp.wavelength_m)} T=${_fmtSci(inp.interrogation_time_s)} N=${_fmtSci(inp.atom_number)} C=${_fmtSci(inp.contrast)} Tc=${_fmtSci(inp.cycle_time_s)}`,
    lab);
  _applyCRLB();
  _applyInstruments();
}
function _onCoast(json, meta) {
  if (!_alive) return;
  _coast = json;
  const lab = meta.label || (json && json.label) || "MODELED";
  const cf = (json && json.closed_form_stdlib) || {};
  _classicErr = (cf.classical && cf.classical.position_error_m) || _classicErr;
  _quantumErr = (cf.quantum && cf.quantum.position_error_m) || _quantumErr;
  _setRow(_rows.coast, `${_fmtSci(_classicErr)} / ${_fmtSci(_quantumErr)}`, lab);
  _setRow(_rows.fom, _fmtSci(cf.quantum_over_classical_improvement_factor), lab);
  _rebuildCoastTubes();
  _applyFoMHalo();
}
function _onResil(json, meta) {
  if (!_alive) return;
  _resil = json;
  const lab = meta.label || (json && json.label) || "MODELED";
  const cf = (json && json.closed_form_stdlib) || {};
  _setRow(_rows.verdict, `${cf.verdict || "—"} (fired ${cf.n_layers_fired != null ? cf.n_layers_fired : "—"}/3)`, lab);
  _applyResilience();
}
function _onLimits(json, meta) {
  if (!_alive) return;
  _limits = json;
  const lab = meta.label || (json && json.label) || "MODELED";
  const pil = json && json.pillars;
  if (pil) {
    const wired = _PILLARS.filter((p) => pil[p] && pil[p].wired).length;
    _setRow(_rows.pillars, `${wired}/${_PILLARS.length} wired`, lab);
  } else {
    // honest degraded: library not importable / not wired
    _setRow(_rows.pillars, json && json.status ? json.status : "no pillars", "STRUCTURAL-ONLY");
  }
  _applyLadder();
}

// ----------------------------------------------------------------------------
// mount / unmount
// ----------------------------------------------------------------------------
function mount(ctx) {
  _stage = ctx.stage;
  _THREE = ctx.THREE;
  _label = ctx.label;
  _alive = true;

  if (_stage.setBloom) { try { _stage.setBloom(true); } catch (_) {} }

  const badge = _buildOverlay(ctx);
  _buildRows();

  _buildSQL();
  _buildCRLB();
  _buildCoast();
  _buildFoMHalo();
  _buildEllipsoids();
  _buildDrift();
  _buildLadder();
  _buildResilience();
  _buildInstruments();

  // gentle global motion + live-driven animation, guarded on _alive
  _frameFns.push(() => { _animateDrift(); _applyEllipsoids(); _applyLadder(); });
  _stage.onFrame(() => {
    if (!_alive) return;
    for (let i = 0; i < _spin.length; i++) { _spin[i].obj.rotation.y += _spin[i].sy; _spin[i].obj.rotation.x += _spin[i].sx; }
    for (let i = 0; i < _frameFns.length; i++) { try { _frameFns[i](); } catch (_) {} }
  });

  // wire LIVE polls — the primary endpoint shares the toolkit badge; the rest are silent.
  _handles.push(ctx.live.poll(ENDPOINT, 5000, _onSensor, { badge }));
  _handles.push(ctx.live.poll(COAST_EP, 7000, _onCoast));
  _handles.push(ctx.live.poll(RESIL_EP, 9000, _onResil));
  _handles.push(ctx.live.poll(LIMITS_EP, 11000, _onLimits));

  return { id: ID, started: true };
}

function unmount() {
  _alive = false;
  for (const h of _handles) { try { h.stop(); } catch (_) {} }
  _handles.length = 0;
  try { if (_show) _show.destroy(); } catch (_) {}
  _show = null;
  if (_stage) {
    for (const o of _objs) { try { _stage.scene.remove(o); } catch (_) {} }
  }
  for (const d of _disposables) { try { d.dispose && d.dispose(); } catch (_) {} }
  _objs.length = 0; _disposables.length = 0; _spin.length = 0; _frameFns.length = 0;
  _pillarBars.length = 0; _layerLamps.length = 0;
  Object.keys(_rows).forEach((k) => delete _rows[k]);
  _classicTube = _quantumTube = _coastGroup = null;
  _ellipsoidC = _ellipsoidQ = _crlbMesh = _crlbBeacon = _sqlPlane = null;
  _verdictOrb = _drift = _keffRing = _phaseDial = _asdCol = _foMHalo = null;
  _sensor = _coast = _resil = _limits = null; _sensorLabel = null;
  _hud = _stage = _THREE = _label = null;
}

// STRUCTURAL-ONLY is carried in the ladder billboards: the pillar names are present as
// structure even before the live wiring discovery lands, then upgrade to the honest
// MODELED/wired state. The doctrine contract token is intentionally retained here.
export default { id: ID, title: TITLE, endpoints: [ENDPOINT, COAST_EP, RESIL_EP, LIMITS_EP], mount, unmount };
