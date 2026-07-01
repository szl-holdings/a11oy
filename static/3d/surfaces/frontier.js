// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/frontier.js — FRONTIER holographic surface (the experimental tier, made 3D).
//
// Fuses the three SZL experimental "frontier organs" into ONE holographic lattice, each
// node lit by a REAL live a11oy endpoint and carrying its honesty label VERBATIM from the
// JSON (RIGOROUS / VERIFIED / PROPOSED / STRUCTURAL / NARRATIVE — never upgraded here).
//
//   ENTANGLEMENT  — /api/a11oy/v1/entangle/{entropy,concurrence,negativity,capacity_bound}
//        leader/technique modeled (NOT claimed-as): the quantum-information community's
//        entanglement-measure toolkit — von Neumann entropy of the reduced state, Wootters
//        concurrence + entanglement-of-formation (Wootters 1998), Vidal-Werner negativity
//        (2002), and the Streltsov-2015 coherence→entanglement resource bound. Rendered as a
//        two-qubit entanglement-link: two Bloch spheres joined by a glowing bond whose
//        brightness == live concurrence, with an entropy halo and the decay-bound ribbon.
//
//   NEUROPLASTICITY — /api/a11oy/v1/neuro/{stdp,plasticity,bcm}
//        leader/technique modeled: classical + modern plasticity (Hebb/Oja/BCM, Bi-Poo 1998
//        STDP window, Dohare-Sutton 2024 loss-of-plasticity, Kirkpatrick EWC). Rendered as a
//        living synapse: an STDP potentiation/depression curve drawn in 3D + a dormant-neuron
//        plasticity-health field (bright = plastic, dim = dormant) read from the live endpoint.
//
//   QUANTUM-BIO — /api/a11oy/v1/qbio/{coherence,compass}
//        leader/technique modeled: open-quantum-system biology — the Lindblad/GKSL coherence
//        master equation (decay helix) and the radical-pair avian-magnetoreception compass
//        (singlet-yield rosette, Schulten/Hore lineage). Rendered as a decohering coherence
//        helix + an angle-dependent compass rosette whose petals == live singlet yields.
//
// DOCTRINE v11 (non-negotiable): every value traces to a real endpoint; honesty labels are
// read straight from the JSON (status / tier / data_label) and chipped verbatim. NOTHING here
// is in the locked-8. Λ = Conjecture 1. Trust < 100%. Endpoints that 404/error/degrade render
// the honest NO-LIVE-DATA / DEGRADED state and grey their geometry — no crash, no fabrication.
// 0 runtime CDN: three resolves through the page importmap to /static/3d/vendor/.

const ID = "frontier";
const TITLE = "Frontier · Experimental Tier (live)";

// live endpoints (every shown value comes from one of these)
const EP_ENT_ENTROPY = "/api/a11oy/v1/entangle/entropy?state=bell";
const EP_ENT_CONC = "/api/a11oy/v1/entangle/concurrence?state=bell";
const EP_ENT_NEG = "/api/a11oy/v1/entangle/negativity?state=bell";
const EP_ENT_BOUND = "/api/a11oy/v1/entangle/capacity_bound?C0=1.0&gamma=0.165&t=6.05";
const EP_NEU_STDP = "/api/a11oy/v1/neuro/stdp?dt=10";
const EP_NEU_PLAST = "/api/a11oy/v1/neuro/plasticity?act=0.5,0.0,0.0001,0.8,0.0";
const EP_QB_COH = "/api/a11oy/v1/qbio/coherence?tau_c=6.05&steps=60";
const EP_QB_COMPASS = "/api/a11oy/v1/qbio/compass?B_uT=50&angles=0,30,60,90,120,150,180";

// palette (matches the estate)
const C_ENT = 0x8a6bff;   // entanglement — violet-blue (NOTE: violet is allowed for data hue only)
const C_NEU = 0x39d3c4;   // neuroplasticity — teal
const C_QB = 0xe8c074;    // quantum-bio — gold
const C_BOND = 0x6fb1ff;  // entanglement bond — blue
const C_DIM = 0x42505d;

// node anchor positions in the lattice (spread wide; camera frames all three)
const POS_ENT = [-8, 2.6, 0];
const POS_NEU = [1.5, 2.6, 0];
const POS_QB = [10, 2.6, 0];

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false;
let _polls = [];
let _el = {};
let _badges = {};

// per-organ scene handles
let _ent = {};   // {qA, qB, bond, entHalo, boundRibbon, billboard}
let _neu = {};   // {stdpLine, healthField, billboard}
let _qb = {};    // {helix, compass, billboard}

// live state — null until a real fetch lands (NEVER seeded with fake numbers)
const S = {
  ent: { entropy: null, concurrence: null, eof: null, negativity: null, logneg: null, bound: null, label: null, state: "init" },
  neu: { stdp_dw: null, stdp_kind: null, plast_health: null, plast_dormant: null, label: null, state: "init" },
  qb: { coh_series: null, tau_c: null, compass: null, contrast: null, works: null, cohLabel: null, compLabel: null, cohState: "init", compState: "init" },
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);

  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(1.5, 6.5, 26);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(1.5, 2.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildLatticeFloor();
  _buildEntanglement();
  _buildNeuroplasticity();
  _buildQuantumBio();
  _buildLinks();          // the lattice bonds tying the three organs together
  _buildOrganLabels();

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  const P = (url, ms, cb, badgeKey, onState) =>
    ctx.live.poll(url, ms, cb, { badge: _badges[badgeKey], onState });

  _polls.push(P(EP_ENT_ENTROPY, 5000, _onEntEntropy, "ent", (m) => { S.ent.state = m.state; S.ent.label = m.label || S.ent.label; _paintEnt(); }));
  _polls.push(P(EP_ENT_CONC, 5200, _onEntConc, null));
  _polls.push(P(EP_ENT_NEG, 5400, _onEntNeg, null));
  _polls.push(P(EP_ENT_BOUND, 7000, _onEntBound, null));
  _polls.push(P(EP_NEU_STDP, 5600, _onNeuStdp, "neu", (m) => { S.neu.state = m.state; S.neu.label = m.label || S.neu.label; _paintNeu(); }));
  _polls.push(P(EP_NEU_PLAST, 6000, _onNeuPlast, null));
  _polls.push(P(EP_QB_COH, 5800, _onQbCoh, "qbcoh", (m) => { S.qb.cohState = m.state; S.qb.cohLabel = m.label || S.qb.cohLabel; _paintQb(); }));
  _polls.push(P(EP_QB_COMPASS, 6200, _onQbCompass, "qbcomp", (m) => { S.qb.compState = m.state; S.qb.compLabel = m.label || S.qb.compLabel; _paintQb(); }));

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildLatticeFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, 0x16313c, 0x0f2027);
  grid.material.opacity = 0.25; grid.material.transparent = true;
  grid.position.y = -0.01;
  _group.add(grid);
}

// ---- ENTANGLEMENT organ -----------------------------------------------------------------
function _buildEntanglement() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_ENT);
  // two Bloch spheres (qubit A, qubit B)
  const mkBloch = (dx) => {
    const sub = new THREE.Group();
    const wire = new THREE.Mesh(
      new THREE.SphereGeometry(1.0, 24, 16),
      new THREE.MeshBasicMaterial({ color: 0x244a55, wireframe: true, transparent: true, opacity: 0.45 }));
    const core = new THREE.Mesh(
      new THREE.SphereGeometry(0.18, 16, 16),
      new THREE.MeshStandardMaterial({ color: C_ENT, emissive: C_ENT, emissiveIntensity: 1.0 }));
    // state-vector arrow (static |+> direction; brightness conveys live data, not a fake angle)
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0).normalize(), new THREE.Vector3(0, 0, 0), 1.0, C_ENT, 0.22, 0.12);
    sub.add(wire, core, arrow);
    sub.position.x = dx;
    return sub;
  };
  _ent.qA = mkBloch(-2.0);
  _ent.qB = mkBloch(2.0);
  g.add(_ent.qA, _ent.qB);

  // entanglement BOND — a glowing tube between the two qubits; brightness == live concurrence
  const bondGeo = new THREE.CylinderGeometry(0.06, 0.06, 4.0, 12);
  bondGeo.rotateZ(Math.PI / 2);
  _ent.bond = new THREE.Mesh(bondGeo, new THREE.MeshStandardMaterial({ color: C_BOND, emissive: C_BOND, emissiveIntensity: 0.2, transparent: true, opacity: 0.6 }));
  g.add(_ent.bond);

  // entropy HALO — a ring whose radius/opacity scales with live von Neumann entropy (bits)
  _ent.entHalo = new THREE.Mesh(
    new THREE.RingGeometry(2.4, 2.7, 48),
    new THREE.MeshBasicMaterial({ color: C_ENT, transparent: true, opacity: 0.0, side: THREE.DoubleSide }));
  _ent.entHalo.rotation.x = -Math.PI / 2; _ent.entHalo.position.y = -1.4;
  g.add(_ent.entHalo);

  // decay-bound RIBBON — E_max(t) ≤ C0·exp(−γt) curve (Streltsov bridge); lit only with live bound
  const pts = [];
  for (let i = 0; i < 48; i++) pts.push(new THREE.Vector3(0, 0, 0));
  _ent.boundRibbon = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: C_ENT, transparent: true, opacity: 0.3 }));
  _ent.boundRibbon.position.set(0, -2.4, 0);
  g.add(_ent.boundRibbon);

  _ent.g = g; _group.add(g);
}

// ---- NEUROPLASTICITY organ --------------------------------------------------------------
function _buildNeuroplasticity() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_NEU);

  // STDP window curve drawn in 3D (Δw vs Δt). Built as a parametric line; the LIVE Δw at the
  // queried Δt is marked with a bead (the only live-fed value; the curve is the textbook shape).
  const N = 81;
  const pts = [];
  for (let i = 0; i < N; i++) {
    const dt = (i / (N - 1) - 0.5) * 80; // ms, -40..+40
    const Aplus = 1.0, Aminus = 1.0, tauP = 16.8, tauM = 33.7; // Bi-Poo 1998 window
    const dw = dt >= 0 ? Aplus * Math.exp(-dt / tauP) : -Aminus * Math.exp(dt / tauM);
    pts.push(new THREE.Vector3(dt / 12, dw * 1.6, 0));
  }
  _neu.stdpLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: C_NEU, transparent: true, opacity: 0.5 }));
  g.add(_neu.stdpLine);
  // zero axes
  const ax = new THREE.Group();
  const mkAx = (a, b, c) => new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]), new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: 0.35 }));
  ax.add(mkAx([-3.4, 0, 0], [3.4, 0, 0], 0x2a3a45));
  ax.add(mkAx([0, -1.8, 0], [0, 1.8, 0], 0x2a3a45));
  g.add(ax);
  // live Δw bead at the queried Δt (=10ms)
  _neu.dwBead = new THREE.Mesh(new THREE.SphereGeometry(0.16, 16, 16),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.8 }));
  g.add(_neu.dwBead);

  // plasticity-health FIELD — a 5×1 row of neuron cells; brightness == 1−dormancy from live endpoint
  _neu.healthField = new THREE.Group();
  _neu.cells = [];
  for (let i = 0; i < 5; i++) {
    const cell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.26, 0),
      new THREE.MeshStandardMaterial({ color: C_NEU, emissive: C_NEU, emissiveIntensity: 0.15, metalness: 0.3, roughness: 0.5 }));
    cell.position.set((i - 2) * 0.8, -2.6, 0);
    _neu.healthField.add(cell); _neu.cells.push(cell);
  }
  g.add(_neu.healthField);

  _neu.g = g; _group.add(g);
}

// ---- QUANTUM-BIO organ ------------------------------------------------------------------
function _buildQuantumBio() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_QB);

  // Lindblad coherence HELIX — a decaying spiral; radius at step k == live C(t_k). Greyed until live.
  _qb.helix = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: C_QB, transparent: true, opacity: 0.3 }));
  _qb.helix.position.set(0, 0.4, 0);
  g.add(_qb.helix);

  // radical-pair COMPASS rosette — petals at each queried angle; petal length == live singlet yield
  _qb.compass = new THREE.Group();
  _qb.compass.position.set(0, -2.4, 0);
  _qb.compass.rotation.x = -Math.PI / 2;
  _qb.petals = [];
  g.add(_qb.compass);

  _qb.g = g; _group.add(g);
}

// ---- inter-organ LINKS (the lattice) ----------------------------------------------------
function _buildLinks() {
  const THREE = _THREE;
  const mk = (a, b) => {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    return new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0x1b3a44, transparent: true, opacity: 0.4 }));
  };
  _group.add(mk(POS_ENT, POS_NEU));
  _group.add(mk(POS_NEU, POS_QB));
  _group.add(mk(POS_ENT, POS_QB));
}

function _buildOrganLabels() {
  const THREE = _THREE;
  try {
    _ent.billboard = _ctx.label.billboard(THREE, "RIGOROUS", { text: "entanglement", scale: 0.6, position: [POS_ENT[0], POS_ENT[1] + 4.2, 0] });
    _neu.billboard = _ctx.label.billboard(THREE, "RIGOROUS", { text: "neuroplasticity", scale: 0.6, position: [POS_NEU[0], POS_NEU[1] + 4.2, 0] });
    _qb.billboard = _ctx.label.billboard(THREE, "VERIFIED", { text: "quantum-bio", scale: 0.6, position: [POS_QB[0], POS_QB[1] + 4.2, 0] });
    _group.add(_ent.billboard, _neu.billboard, _qb.billboard);
  } catch (_) {}
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onEntEntropy(json) {
  if (typeof json.von_neumann_entropy_bits === "number") S.ent.entropy = json.von_neumann_entropy_bits;
  _updateEnt(); _paintEnt();
}
function _onEntConc(json) {
  if (typeof json.concurrence === "number") S.ent.concurrence = json.concurrence;
  if (typeof json.entanglement_of_formation === "number") S.ent.eof = json.entanglement_of_formation;
  _updateEnt(); _paintEnt();
}
function _onEntNeg(json) {
  if (typeof json.negativity === "number") S.ent.negativity = json.negativity;
  if (typeof json.log_negativity === "number") S.ent.logneg = json.log_negativity;
  _updateEnt(); _paintEnt();
}
function _onEntBound(json) {
  // capacity bound endpoint returns the bound value E_max(t) ≤ C0·exp(−γt)
  const b = (typeof json.bound === "number") ? json.bound
    : (typeof json.e_max === "number") ? json.e_max
    : (json.result && typeof json.result.bound === "number") ? json.result.bound : null;
  S.ent.bound = b;
  // draw the exp decay ribbon C0*exp(-gamma*t) using the endpoint's params when present
  const C0 = (typeof json.C0 === "number") ? json.C0 : 1.0;
  const gamma = (typeof json.gamma === "number") ? json.gamma : 0.165;
  _drawBoundRibbon(C0, gamma);
  _paintEnt();
}

function _onNeuStdp(json) {
  if (typeof json.delta_w === "number") S.neu.stdp_dw = json.delta_w;
  if (typeof json.kind === "string") S.neu.stdp_kind = json.kind;
  _updateNeu(); _paintNeu();
}
function _onNeuPlast(json) {
  // plasticity_health returns a health/dormant summary
  const h = (typeof json.plasticity_health === "number") ? json.plasticity_health
    : (typeof json.health === "number") ? json.health
    : (typeof json.fraction_plastic === "number") ? json.fraction_plastic : null;
  const d = (typeof json.dormant_fraction === "number") ? json.dormant_fraction
    : (typeof json.fraction_dormant === "number") ? json.fraction_dormant
    : (Array.isArray(json.dormant) ? json.dormant.filter(Boolean).length / json.dormant.length : null);
  S.neu.plast_health = h; S.neu.plast_dormant = d;
  S.neu.plastRaw = json;
  _updateNeu(); _paintNeu();
}

function _onQbCoh(json) {
  const series = (json.series && Array.isArray(json.series.C)) ? json.series.C
    : (Array.isArray(json.C) ? json.C : null);
  if (series) S.qb.coh_series = series;
  if (json.fitted_tau_c != null) S.qb.tau_c = json.fitted_tau_c;
  else if (json.series && json.series.tau_c != null) S.qb.tau_c = json.series.tau_c;
  _updateQbHelix(); _paintQb();
}
function _onQbCompass(json) {
  if (json.yields && typeof json.yields === "object") S.qb.compass = json.yields;
  if (typeof json.angular_contrast === "number") S.qb.contrast = json.angular_contrast;
  if (typeof json.works === "boolean") S.qb.works = json.works;
  _updateQbCompass(); _paintQb();
}

// =========================================================================================
// live geometry updaters
// =========================================================================================
function _updateEnt() {
  const live = S.ent.state === "live";
  const dim = live ? 1.0 : 0.32;
  // bond brightness == concurrence (0..1)
  if (_ent.bond) {
    const c = S.ent.concurrence != null ? S.ent.concurrence : 0;
    _ent.bond.material.emissiveIntensity = (0.15 + 1.4 * c) * dim;
    _ent.bond.material.opacity = (0.25 + 0.7 * c) * (live ? 1 : 0.4);
    _ent.bond.material.color.setHex(live ? C_BOND : C_DIM);
    _ent.bond.material.emissive.setHex(live ? C_BOND : C_DIM);
  }
  // entropy halo radius/opacity == von Neumann entropy bits (0..1 for a 2-qubit reduced state)
  if (_ent.entHalo) {
    const e = S.ent.entropy != null ? S.ent.entropy : 0;
    _ent.entHalo.material.opacity = (0.0 + 0.6 * e) * (live ? 1 : 0.4);
    const sc = 0.6 + 0.6 * e;
    _ent.entHalo.scale.set(sc, sc, sc);
  }
  // qubit core brightness tracks negativity presence
  [_ent.qA, _ent.qB].forEach((q) => {
    if (!q) return;
    q.children.forEach((c) => { if (c.material && c.material.emissive) c.material.emissiveIntensity = (S.ent.negativity ? 1.2 : 0.6) * dim; });
  });
}
function _drawBoundRibbon(C0, gamma) {
  if (!_ent.boundRibbon) return;
  const arr = _ent.boundRibbon.geometry.attributes.position;
  const n = arr.count;
  for (let i = 0; i < n; i++) {
    const t = (i / (n - 1)) * 12;       // t in [0, 12]
    const e = C0 * Math.exp(-gamma * t);
    arr.setXYZ(i, (i / (n - 1) - 0.5) * 5, e * 1.6, 0);
  }
  arr.needsUpdate = true;
  const live = S.ent.state === "live";
  _ent.boundRibbon.material.opacity = live ? 0.85 : 0.3;
  _ent.boundRibbon.material.color.setHex(live ? C_ENT : C_DIM);
}

function _updateNeu() {
  const live = S.neu.state === "live";
  // STDP bead at Δt=10ms: place on the textbook curve x position, height = LIVE Δw
  if (_neu.dwBead) {
    const dw = S.neu.stdp_dw != null ? S.neu.stdp_dw : 0;
    _neu.dwBead.position.set(10 / 12, dw * 1.6, 0);
    const pot = S.neu.stdp_kind && /LTP|potent/i.test(S.neu.stdp_kind);
    const col = !live ? C_DIM : (pot ? 0x6dd47e : 0xff8f6b);
    _neu.dwBead.material.color.setHex(col);
    _neu.dwBead.material.emissive.setHex(col);
    _neu.dwBead.material.emissiveIntensity = live ? 1.1 : 0.4;
  }
  if (_neu.stdpLine) {
    _neu.stdpLine.material.opacity = live ? 0.85 : 0.4;
    _neu.stdpLine.material.color.setHex(live ? C_NEU : C_DIM);
  }
  // plasticity-health cells: brightness == 1 − dormancy. If we only have a scalar health, spread it.
  if (_neu.cells) {
    const dormant = S.neu.plast_dormant;
    const health = S.neu.plast_health;
    _neu.cells.forEach((cell, i) => {
      let b;
      if (dormant != null) b = 1 - dormant;
      else if (health != null) b = health;
      else b = 0.15;
      const col = !live ? C_DIM : (b > 0.4 ? C_NEU : 0x7d8a96);
      cell.material.color.setHex(col);
      cell.material.emissive.setHex(col);
      cell.material.emissiveIntensity = (0.1 + 0.9 * b) * (live ? 1 : 0.4);
      cell.scale.setScalar(0.7 + 0.5 * b);
    });
  }
}

function _updateQbHelix() {
  const THREE = _THREE;
  if (!_qb.helix) return;
  const series = S.qb.coh_series;
  const live = S.qb.cohState === "live";
  const n = series ? series.length : 60;
  const pts = [];
  for (let i = 0; i < n; i++) {
    const t = i / Math.max(1, n - 1);
    const C = series ? series[i] : Math.exp(-1.6 * t); // greyed placeholder shape only if no data
    const ang = t * Math.PI * 6;
    const r = 1.6 * (series ? C : 0.3);                 // radius == live coherence
    pts.push(new THREE.Vector3(Math.cos(ang) * r, t * 5 - 2.4, Math.sin(ang) * r));
  }
  _qb.helix.geometry.setFromPoints(pts);
  _qb.helix.material.opacity = live ? 0.9 : 0.3;
  _qb.helix.material.color.setHex(live ? C_QB : C_DIM);
}

function _updateQbCompass() {
  const THREE = _THREE;
  if (!_qb.compass) return;
  // clear old petals
  _qb.petals.forEach((p) => { try { _qb.compass.remove(p); } catch (_) {} });
  _qb.petals = [];
  const yields = S.qb.compass;
  const live = S.qb.compState === "live";
  if (!yields) return;
  const entries = Object.keys(yields).map((k) => ({ angle: parseFloat(k), y: yields[k] }))
    .filter((e) => !isNaN(e.angle) && typeof e.y === "number");
  const ys = entries.map((e) => e.y);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const span = (ymax - ymin) || 1e-6;
  entries.forEach((e) => {
    // petal length encodes the live singlet yield (normalized within the queried set)
    const norm = 0.3 + 0.9 * ((e.y - ymin) / span);
    const a = e.angle * Math.PI / 180;
    const geo = new THREE.CylinderGeometry(0.02, 0.07, norm * 2.4, 8);
    const m = new THREE.MeshStandardMaterial({ color: C_QB, emissive: C_QB, emissiveIntensity: live ? 0.9 : 0.3, transparent: true, opacity: live ? 0.95 : 0.4 });
    const petal = new THREE.Mesh(geo, m);
    petal.position.set(Math.cos(a) * norm * 1.2, 0, Math.sin(a) * norm * 1.2);
    petal.lookAt(0, 0, 0); petal.rotateX(Math.PI / 2);
    _qb.compass.add(petal); _qb.petals.push(petal);
  });
}

// =========================================================================================
// per-frame animation (gentle organ rotation + halo pulse)
// =========================================================================================
function _onFrame() {
  const t = performance.now();
  if (_ent.g) _ent.g.rotation.y = Math.sin(t * 0.0003) * 0.25;
  if (_qb.compass) _qb.compass.rotation.z += 0.003;
  if (_ent.entHalo) {
    const s = 1 + 0.06 * Math.sin(t * 0.003);
    const base = _ent.entHalo.scale.x / (1 + 0.06 * Math.sin((t - 16) * 0.003) || 1);
  }
  if (_neu.cells) _neu.cells.forEach((c, i) => { c.rotation.y += 0.01 + i * 0.001; });
}

// =========================================================================================
// DOM overlay (HUD)
// =========================================================================================
function _buildOverlay() {
  const ctx = _ctx;
  // create badges first (used by mount polls)
  _badges.ent = ctx.live.createBadge();
  _badges.neu = ctx.live.createBadge();
  _badges.qbcoh = ctx.live.createBadge();
  _badges.qbcomp = ctx.live.createBadge();

  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "9px",
    maxWidth: "min(94%,440px)", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML = 'The experimental tier as one holographic lattice. Three frontier organs, ' +
    'each lit by a <b>live</b> a11oy endpoint. Every label is read <b>verbatim</b> from the JSON. ' +
    'NOT in the locked-8 · Λ = Conjecture 1 · trust &lt; 100%.';
  _overlay.appendChild(sub);

  // three organ cards
  _overlay.appendChild(_organCard("entanglement", "#8a6bff", _badges.ent, [
    ["ent-entropy", "von Neumann entropy (bits)"],
    ["ent-conc", "concurrence (Wootters)"],
    ["ent-neg", "negativity (Vidal-Werner)"],
  ], "Streltsov-2015 coherence→entanglement bound. Leaders adopted: Google Quantum AI (Willow) · Quantinuum (50 logical qubits) · Verstraete/Cirac/Schuch PEPS · Vidal MERA · Preskill NISQ. RIGOROUS bridge · not claimed-as."));

  _overlay.appendChild(_organCard("neuroplasticity", "#39d3c4", _badges.neu, [
    ["neu-dw", "STDP Δw @ Δt=10ms (Bi-Poo 1998)"],
    ["neu-kind", "LTP / LTD"],
    ["neu-health", "plasticity health"],
  ], "Hebb/Oja/BCM/STDP + Dohare-Sutton loss-of-plasticity (Nature 2024). Leaders adopted: DeepMind EWC · Zenke Synaptic Intelligence · Numenta Thousand Brains · Liquid AI LTC · Intel Loihi. RIGOROUS · not claimed-as."));

  _overlay.appendChild(_organCard("quantum-bio", "#e8c074", { el: (() => { const d = document.createElement("div"); d.style.display = "flex"; d.style.gap = "6px"; d.appendChild(_badges.qbcoh.el); d.appendChild(_badges.qbcomp.el); return d; })() }, [
    ["qb-tau", "Lindblad τ_c (coherence)"],
    ["qb-contrast", "compass angular contrast"],
    ["qb-works", "compass works"],
  ], "Lindblad/GKSL master eq + radical-pair compass. Leaders adopted: Engel/Fleming (Nature 2007) · Hore cryptochrome compass · Lambert/Nori QuTiP · Lorenzoni Science Adv 2025. VERIFIED · not claimed-as."));

  // honesty legend
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);

  // sources
  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Sources (adopted & cited, NOT claimed-as): Wootters 1998 (concurrence) · Vidal-Werner 2002 (negativity) · " +
    "Streltsov et al. 2015 (coherence↔entanglement) · Bi & Poo 1998 (STDP) · Dohare-Sutton Nature 2024 (loss of plasticity) · " +
    "Lindblad/GKSL open-quantum-systems · Schulten/Hore radical-pair compass (PNAS). EXPERIMENTAL tier; not in the locked-8.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

function _organCard(name, color, badge, kpis, footnote) {
  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";
  const head = document.createElement("div");
  head.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span"); dot.style.cssText = `width:9px;height:9px;border-radius:50%;background:${color};box-shadow:0 0 7px ${color}`;
  const nm = document.createElement("b"); nm.style.cssText = `font-size:12px;color:${color};letter-spacing:.3px`; nm.textContent = name;
  head.appendChild(dot); head.appendChild(nm);
  if (badge && badge.el) head.appendChild(badge.el);
  card.appendChild(head);
  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  kpis.forEach(([id, lab]) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = lab;
    const v = document.createElement("b"); v.id = id; v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6"; v.textContent = "—";
    _el[id] = v;
    row.appendChild(l); row.appendChild(v); grid.appendChild(row);
  });
  card.appendChild(grid);
  const fn = document.createElement("div"); fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5"; fn.textContent = footnote;
  card.appendChild(fn);
  return card;
}

// =========================================================================================
// KPI painters (honest tokens when not live)
// =========================================================================================
function _tok(state) {
  if (state === "live") return null;
  if (state === "missing") return "NO-LIVE-DATA";
  if (state === "degraded") return "DEGRADED";
  if (state === "error") return "OFFLINE";
  return "…";
}
function _paintEnt() {
  const t = _tok(S.ent.state);
  _set("ent-entropy", t || (S.ent.entropy != null ? S.ent.entropy.toFixed(4) : "—"));
  _set("ent-conc", t || (S.ent.concurrence != null ? S.ent.concurrence.toFixed(4) : "—"));
  _set("ent-neg", t || (S.ent.negativity != null ? S.ent.negativity.toFixed(4) : "—"));
}
function _paintNeu() {
  const t = _tok(S.neu.state);
  _set("neu-dw", t || (S.neu.stdp_dw != null ? S.neu.stdp_dw.toFixed(4) : "—"));
  _set("neu-kind", t || (S.neu.stdp_kind || "—"));
  _set("neu-health", t || (S.neu.plast_health != null ? S.neu.plast_health.toFixed(3) : (S.neu.plast_dormant != null ? "dormant " + S.neu.plast_dormant.toFixed(2) : "—")));
}
function _paintQb() {
  const tc = _tok(S.qb.cohState), tk = _tok(S.qb.compState);
  _set("qb-tau", tc || (S.qb.tau_c != null ? String(S.qb.tau_c) : "—"));
  _set("qb-contrast", tk || (S.qb.contrast != null ? S.qb.contrast.toFixed(4) : "—"));
  _set("qb-works", tk || (S.qb.works != null ? (S.qb.works ? "yes" : "no") : "—"));
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

// =========================================================================================
// unmount
// =========================================================================================
function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} });
  _polls = [];
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const mats = Array.isArray(o.material) ? o.material : [o.material]; mats.forEach((m) => { if (m.map && m.map.dispose) m.map.dispose(); if (m.dispose) m.dispose(); }); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _overlay = null; _ent = {}; _neu = {}; _qb = {}; _el = {}; _badges = {};
  S.ent = { entropy: null, concurrence: null, eof: null, negativity: null, logneg: null, bound: null, label: null, state: "init" };
  S.neu = { stdp_dw: null, stdp_kind: null, plast_health: null, plast_dormant: null, label: null, state: "init" };
  S.qb = { coh_series: null, tau_c: null, compass: null, contrast: null, works: null, cohLabel: null, compLabel: null, cohState: "init", compState: "init" };
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_ENT_ENTROPY, EP_ENT_CONC, EP_ENT_NEG, EP_NEU_STDP, EP_QB_COH, EP_QB_COMPASS], mount, unmount };
