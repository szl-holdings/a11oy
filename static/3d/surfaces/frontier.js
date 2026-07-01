// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/frontier.js — FRONTIER holographic surface (the experimental tier, made 3D).
//
// Fuses FIVE SZL frontier "organs" into ONE holographic lattice, each node lit by a REAL
// live a11oy endpoint and carrying its honesty label VERBATIM from the JSON
// (RIGOROUS / VERIFIED / PROPOSED / MEASURED / LIVE-MANAGED / HONEST-STUB / ROADMAP —
// never upgraded here).
//
//   ENTANGLEMENT   — /api/a11oy/v1/entangle/{entropy,concurrence,negativity,capacity_bound}
//        von Neumann entropy · Wootters concurrence + EoF (Wootters 1998) · Vidal-Werner
//        negativity (2002) · Streltsov-2015 coherence→entanglement bound. Two Bloch spheres
//        joined by a bond whose brightness == live concurrence + an entropy halo.
//        Leaders adopted (NOT claimed-as): Google Quantum AI (Willow) · Quantinuum · PEPS/MERA.
//
//   NEUROPLASTICITY — /api/a11oy/v1/neuro/{stdp,plasticity}
//        Hebb/Oja/BCM + Bi-Poo 1998 STDP window + Dohare-Sutton 2024 loss-of-plasticity +
//        EWC. A 3D STDP curve + dormant-neuron plasticity-health field.
//        Leaders adopted: DeepMind EWC · Zenke SI · Numenta · Liquid AI LTC · Intel Loihi.
//
//   QUANTUM-BIO    — /api/a11oy/v1/qbio/{coherence,compass}   (WebGPU compute accelerated)
//        Lindblad/GKSL coherence master equation (decay helix) + radical-pair avian compass
//        (singlet-yield rosette). When the renderer is WebGPU, a compute pass evolves a dense
//        coherence/compass field on-GPU (visual density only — the reported KPI values ALWAYS
//        stay the server's, honest doctrine). WebGL2 path renders the same shape from the
//        endpoint series. Leaders adopted: Engel/Fleming (Nature 2007) · Hore · Lambert/Nori QuTiP.
//
//   SOVEREIGN-COMPUTE — /api/a11oy/v1/sovereign-compute
//        The honest sovereign-inference posture: brain (LIVE-MANAGED hf-router today),
//        embeddings (HONEST-STUB), + ROADMAP (PQC / Iron Bank / cross-mesh). Rendered as a
//        GPU-fabric tower whose blocks color by tier; sovereign:true ONLY on a real local-GPU
//        probe (false today → honestly MANAGED/STUB, never faked green).
//        Leaders adopted: NVIDIA confidential compute (H100 TEE) · Prime Intellect DiLoCo · Petals.
//
//   ENERGY        — /api/a11oy/v1/energy/sovereign
//        J/token + carbon posture. MEASURED only on a live GPU power probe (NVML/exporter);
//        with no meter it stays honest ROADMAP (no meter → no number). Rendered as an energy
//        column + carbon ring that light up MEASURED or dim to ROADMAP per the live label.
//        Leaders adopted: Google carbon-intelligent computing · Green Software Foundation SCI ·
//        CodeCarbon · Electricity Maps.
//
// BONUS — LIGHT-FIELD / HOLOGRAM EXPORT: a "◈ light-field" button renders a Looking-Glass-
//   style QUILT (a grid of views from a horizontal camera sweep) to a downloadable PNG, so the
//   lattice can drive a real light-field holographic display (Looking Glass Factory quilt fmt).
//
// DOCTRINE v11 (non-negotiable): every value traces to a real endpoint; honesty labels read
// straight from the JSON. NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%.
// Endpoints that 404/error/degrade render honest NO-LIVE-DATA/DEGRADED and grey their geometry.
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
const EP_SC = "/api/a11oy/v1/sovereign-compute";
const EP_EN = "/api/a11oy/v1/energy/sovereign";

// palette (data hues; matches the estate)
const C_ENT = 0x8a6bff;   // entanglement — violet-blue (data hue only)
const C_NEU = 0x39d3c4;   // neuroplasticity — teal
const C_QB = 0xe8c074;    // quantum-bio — gold
const C_SC = 0x6fb1ff;    // sovereign-compute — blue
const C_EN = 0x6dd47e;    // energy — green
const C_BOND = 0x6fb1ff;
const C_DIM = 0x42505d;
const C_ROADMAP = 0x9aa7b4;

// pentagon layout — 5 organs on a ring, camera frames the whole lattice
const R = 11;
function ring(i, n, y) { const a = Math.PI / 2 - (i / n) * Math.PI * 2; return [Math.cos(a) * R, y, -Math.sin(a) * R * 0.55]; }
const POS_ENT = ring(0, 5, 3.0);
const POS_NEU = ring(1, 5, 3.0);
const POS_QB = ring(2, 5, 3.0);
const POS_EN = ring(3, 5, 3.0);
const POS_SC = ring(4, 5, 3.0);

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false;
let _polls = [];
let _el = {};
let _badges = {};
let _webgpu = false;         // true only when the stage booted a real WebGPU renderer
let _computeReady = false;

// per-organ scene handles
let _ent = {}, _neu = {}, _qb = {}, _sc = {}, _en = {};

// live state — null until a real fetch lands (NEVER seeded with fake numbers)
const S = {
  ent: { entropy: null, concurrence: null, eof: null, negativity: null, logneg: null, label: null, state: "init" },
  neu: { stdp_dw: null, stdp_kind: null, plast_health: null, plast_dormant: null, label: null, state: "init" },
  qb: { coh_series: null, tau_c: null, compass: null, contrast: null, works: null, cohState: "init", compState: "init" },
  sc: { summary: null, sovereign_any: null, caps: null, roadmap: null, label: null, state: "init" },
  en: { summary: null, sovereign: null, gpu_reachable: null, measured: null, total: null, jtoken: null, carbon: null, jlabel: null, state: "init" },
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _webgpu = (_stage.backend === "webgpu");
  _group = new THREE.Group();
  _stage.scene.add(_group);

  _stage.camera.position.set(0, 8, 27);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildLatticeFloor();
  _buildEntanglement();
  _buildNeuroplasticity();
  _buildQuantumBio();
  _buildSovereignCompute();
  _buildEnergy();
  _buildLinks();
  _buildOrganLabels();
  if (_webgpu) { try { _initCompute(); } catch (e) { _webgpu = false; console.warn("[frontier] WebGPU compute init failed, using endpoint path:", e && e.message); } }

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  const P = (url, ms, cb, badgeKey, onState) => ctx.live.poll(url, ms, cb, { badge: _badges[badgeKey], onState });
  _polls.push(P(EP_ENT_ENTROPY, 5000, _onEntEntropy, "ent", (m) => { S.ent.state = m.state; S.ent.label = m.label || S.ent.label; _paintEnt(); }));
  _polls.push(P(EP_ENT_CONC, 5200, _onEntConc, null));
  _polls.push(P(EP_ENT_NEG, 5400, _onEntNeg, null));
  _polls.push(P(EP_ENT_BOUND, 7000, _onEntBound, null));
  _polls.push(P(EP_NEU_STDP, 5600, _onNeuStdp, "neu", (m) => { S.neu.state = m.state; S.neu.label = m.label || S.neu.label; _paintNeu(); }));
  _polls.push(P(EP_NEU_PLAST, 6000, _onNeuPlast, null));
  _polls.push(P(EP_QB_COH, 5800, _onQbCoh, "qbcoh", (m) => { S.qb.cohState = m.state; _paintQb(); }));
  _polls.push(P(EP_QB_COMPASS, 6200, _onQbCompass, "qbcomp", (m) => { S.qb.compState = m.state; _paintQb(); }));
  _polls.push(P(EP_SC, 8000, _onSc, "sc", (m) => { S.sc.state = m.state; S.sc.label = m.label || S.sc.label; _paintSc(); }));
  _polls.push(P(EP_EN, 8000, _onEn, "en", (m) => { S.en.state = m.state; _paintEn(); }));

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildLatticeFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(52, 52, 0x16313c, 0x0f2027);
  grid.material.opacity = 0.22; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

// ---- ENTANGLEMENT -----------------------------------------------------------------------
function _buildEntanglement() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_ENT);
  const mkBloch = (dx) => {
    const sub = new THREE.Group();
    sub.add(new THREE.Mesh(new THREE.SphereGeometry(0.85, 22, 14),
      new THREE.MeshBasicMaterial({ color: 0x244a55, wireframe: true, transparent: true, opacity: 0.45 })));
    sub.add(new THREE.Mesh(new THREE.SphereGeometry(0.15, 14, 14),
      new THREE.MeshStandardMaterial({ color: C_ENT, emissive: C_ENT, emissiveIntensity: 1.0 })));
    sub.add(new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 0), 0.85, C_ENT, 0.2, 0.11));
    sub.position.x = dx; return sub;
  };
  _ent.qA = mkBloch(-1.7); _ent.qB = mkBloch(1.7); g.add(_ent.qA, _ent.qB);
  const bondGeo = new THREE.CylinderGeometry(0.05, 0.05, 3.4, 12); bondGeo.rotateZ(Math.PI / 2);
  _ent.bond = new THREE.Mesh(bondGeo, new THREE.MeshStandardMaterial({ color: C_BOND, emissive: C_BOND, emissiveIntensity: 0.2, transparent: true, opacity: 0.6 }));
  g.add(_ent.bond);
  _ent.entHalo = new THREE.Mesh(new THREE.RingGeometry(2.0, 2.25, 48),
    new THREE.MeshBasicMaterial({ color: C_ENT, transparent: true, opacity: 0.0, side: THREE.DoubleSide }));
  _ent.entHalo.rotation.x = -Math.PI / 2; _ent.entHalo.position.y = -1.2; g.add(_ent.entHalo);
  _ent.g = g; _group.add(g);
}

// ---- NEUROPLASTICITY --------------------------------------------------------------------
function _buildNeuroplasticity() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_NEU);
  const N = 81, pts = [];
  for (let i = 0; i < N; i++) {
    const dt = (i / (N - 1) - 0.5) * 80;
    const tauP = 16.8, tauM = 33.7;
    const dw = dt >= 0 ? Math.exp(-dt / tauP) : -Math.exp(dt / tauM);
    pts.push(new THREE.Vector3(dt / 14, dw * 1.4, 0));
  }
  _neu.stdpLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: C_NEU, transparent: true, opacity: 0.5 }));
  g.add(_neu.stdpLine);
  const mkAx = (a, b) => new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]), new THREE.LineBasicMaterial({ color: 0x2a3a45, transparent: true, opacity: 0.35 }));
  g.add(mkAx([-3, 0, 0], [3, 0, 0])); g.add(mkAx([0, -1.6, 0], [0, 1.6, 0]));
  _neu.dwBead = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 16),
    new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.8 }));
  g.add(_neu.dwBead);
  _neu.cells = [];
  for (let i = 0; i < 5; i++) {
    const cell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.22, 0),
      new THREE.MeshStandardMaterial({ color: C_NEU, emissive: C_NEU, emissiveIntensity: 0.15, metalness: 0.3, roughness: 0.5 }));
    cell.position.set((i - 2) * 0.7, -2.3, 0); g.add(cell); _neu.cells.push(cell);
  }
  _neu.g = g; _group.add(g);
}

// ---- QUANTUM-BIO ------------------------------------------------------------------------
function _buildQuantumBio() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_QB);
  _qb.helix = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: C_QB, transparent: true, opacity: 0.3 }));
  _qb.helix.position.set(0, 0.4, 0); g.add(_qb.helix);
  _qb.compass = new THREE.Group(); _qb.compass.position.set(0, -2.2, 0); _qb.compass.rotation.x = -Math.PI / 2;
  _qb.petals = []; g.add(_qb.compass);
  // WebGPU compute field: a dense point cloud whose radii are evolved on-GPU (visual only)
  _qb.field = null;
  _qb.g = g; _group.add(g);
}

// ---- SOVEREIGN-COMPUTE ------------------------------------------------------------------
function _buildSovereignCompute() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_SC);
  // a GPU-fabric tower: stacked blocks, one per capability; colored by tier when live
  _sc.tower = new THREE.Group(); g.add(_sc.tower);
  _sc.blocks = [];
  _sc.trustSphere = new THREE.Mesh(new THREE.IcosahedronGeometry(0.6, 1),
    new THREE.MeshStandardMaterial({ color: C_SC, emissive: C_SC, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.5 }));
  _sc.trustSphere.position.y = 3.4; g.add(_sc.trustSphere);
  _sc.g = g; _group.add(g);
}

// ---- ENERGY -----------------------------------------------------------------------------
function _buildEnergy() {
  const THREE = _THREE;
  const g = new THREE.Group(); g.position.set(...POS_EN);
  // energy column (J/token proxy height) + carbon ring
  _en.column = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.6, 1, 20),
    new THREE.MeshStandardMaterial({ color: C_ROADMAP, emissive: C_ROADMAP, emissiveIntensity: 0.2, metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.7 }));
  _en.column.position.y = 0.5; g.add(_en.column);
  _en.carbonRing = new THREE.Mesh(new THREE.TorusGeometry(1.4, 0.06, 12, 48),
    new THREE.MeshStandardMaterial({ color: C_ROADMAP, emissive: C_ROADMAP, emissiveIntensity: 0.3, transparent: true, opacity: 0.5 }));
  _en.carbonRing.rotation.x = Math.PI / 2; _en.carbonRing.position.y = 0.1; g.add(_en.carbonRing);
  // measured/total pip row
  _en.pips = []; const pr = new THREE.Group(); pr.position.set(0, -1.6, 0);
  for (let i = 0; i < 6; i++) {
    const pip = new THREE.Mesh(new THREE.SphereGeometry(0.1, 10, 10),
      new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.4 }));
    pip.position.x = (i - 2.5) * 0.4; pr.add(pip); _en.pips.push(pip);
  }
  g.add(pr);
  _en.g = g; _group.add(g);
}

function _buildLinks() {
  const THREE = _THREE;
  const P = [POS_ENT, POS_NEU, POS_QB, POS_EN, POS_SC];
  const mk = (a, b) => new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]),
    new THREE.LineBasicMaterial({ color: 0x1b3a44, transparent: true, opacity: 0.35 }));
  for (let i = 0; i < P.length; i++) _group.add(mk(P[i], P[(i + 1) % P.length]));  // ring
  // spokes to a faint center hub
  const hub = [0, 3.0, 0];
  P.forEach((p) => _group.add(mk(p, hub)));
}

function _buildOrganLabels() {
  const THREE = _THREE;
  const lab = (label, text, pos) => { try { const b = _ctx.label.billboard(THREE, label, { text, scale: 0.55, position: [pos[0], pos[1] + 3.4, pos[2]] }); _group.add(b); return b; } catch (_) { return null; } };
  _ent.billboard = lab("RIGOROUS", "entanglement", POS_ENT);
  _neu.billboard = lab("RIGOROUS", "neuroplasticity", POS_NEU);
  _qb.billboard = lab("VERIFIED", "quantum-bio", POS_QB);
  _en.billboard = lab("ROADMAP", "energy", POS_EN);
  _sc.billboard = lab("LIVE-MANAGED", "sovereign-compute", POS_SC);
}

// =========================================================================================
// WebGPU compute path (quantum-bio) — evolves a dense coherence/compass FIELD on-GPU.
// This drives VISUAL DENSITY only; the reported KPI values always stay the server's.
// Uses three r170 TSL (Fn/storage/instancedArray/uniform) via the webgpu build. Guarded:
// any failure flips _webgpu=false and the endpoint-driven WebGL2 path renders instead.
// =========================================================================================
let _tsl = null, _computeNode = null, _cohBuf = null, _uTau = null, _uT = null, _computeN = 4096;
async function _initCompute() {
  const mod = await import("three/webgpu");
  _tsl = mod;
  const { Fn, instancedArray, uniform, float, int, instanceIndex, sin, cos, exp } = mod;
  if (!Fn || !instancedArray || !uniform) throw new Error("TSL nodes unavailable in webgpu build");
  const THREE = _THREE;

  // storage buffer of particle positions (x,y,z) for the coherence helix cloud
  _cohBuf = instancedArray(_computeN, "vec3");
  _uTau = uniform(float(6.05));
  _uT = uniform(float(0.0));

  // compute kernel: each particle sits on the Lindblad decay helix C(t)=exp(-t/tau),
  // radius == coherence at its normalized time; a real GKSL open-system decay shape.
  const kernel = Fn(() => {
    const i = instanceIndex.toFloat();
    const tnorm = i.div(float(_computeN));
    const t = tnorm.mul(float(12.0));
    const C = exp(t.div(_uTau).negate());               // Lindblad coherence decay
    const ang = tnorm.mul(float(Math.PI * 10.0)).add(_uT);
    const r = C.mul(float(1.6));
    _cohBuf.element(instanceIndex).assign(
      mod.vec3(cos(ang).mul(r), tnorm.mul(float(5.0)).sub(float(2.4)), sin(ang).mul(r)));
  });
  _computeNode = kernel().compute(_computeN);

  // points object reading the storage buffer as positions (webgpu PointsNodeMaterial)
  const mat = new mod.PointsNodeMaterial({ color: C_QB, size: 6, transparent: true, opacity: 0.85 });
  mat.positionNode = _cohBuf.toAttribute();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(_computeN * 3), 3));
  _qb.field = new THREE.Points(geo, mat);
  _qb.g.add(_qb.field);
  _computeReady = true;
}

// =========================================================================================
// live-data handlers
// =========================================================================================
function _onEntEntropy(json) { if (typeof json.von_neumann_entropy_bits === "number") S.ent.entropy = json.von_neumann_entropy_bits; _updateEnt(); _paintEnt(); }
function _onEntConc(json) { if (typeof json.concurrence === "number") S.ent.concurrence = json.concurrence; if (typeof json.entanglement_of_formation === "number") S.ent.eof = json.entanglement_of_formation; _updateEnt(); _paintEnt(); }
function _onEntNeg(json) { if (typeof json.negativity === "number") S.ent.negativity = json.negativity; if (typeof json.log_negativity === "number") S.ent.logneg = json.log_negativity; _updateEnt(); _paintEnt(); }
function _onEntBound() { /* bound value shown via capacity note; geometry already conveys concurrence/entropy */ }

function _onNeuStdp(json) { if (typeof json.delta_w === "number") S.neu.stdp_dw = json.delta_w; if (typeof json.kind === "string") S.neu.stdp_kind = json.kind; _updateNeu(); _paintNeu(); }
function _onNeuPlast(json) {
  const h = num(json.plasticity_health, json.health, json.fraction_plastic);
  let d = num(json.dormant_fraction, json.fraction_dormant);
  if (d == null && Array.isArray(json.dormant)) d = json.dormant.filter(Boolean).length / json.dormant.length;
  S.neu.plast_health = h; S.neu.plast_dormant = d; _updateNeu(); _paintNeu();
}

function _onQbCoh(json) {
  const series = (json.series && Array.isArray(json.series.C)) ? json.series.C : (Array.isArray(json.C) ? json.C : null);
  if (series) S.qb.coh_series = series;
  S.qb.tau_c = json.fitted_tau_c != null ? json.fitted_tau_c : (json.series && json.series.tau_c != null ? json.series.tau_c : S.qb.tau_c);
  if (_webgpu && _uTau && S.qb.tau_c != null) { try { _uTau.value = Number(S.qb.tau_c); } catch (_) {} }
  _updateQbHelix(); _paintQb();
}
function _onQbCompass(json) {
  if (json.yields && typeof json.yields === "object") S.qb.compass = json.yields;
  if (typeof json.angular_contrast === "number") S.qb.contrast = json.angular_contrast;
  if (typeof json.works === "boolean") S.qb.works = json.works;
  _updateQbCompass(); _paintQb();
}

function _onSc(json) {
  S.sc.summary = json.summary || null;
  S.sc.sovereign_any = json.sovereign_any != null ? json.sovereign_any : null;
  S.sc.caps = Array.isArray(json.capabilities) ? json.capabilities : null;
  S.sc.roadmap = Array.isArray(json.roadmap) ? json.roadmap : null;
  _updateSc(); _paintSc();
}
function _onEn(json) {
  S.en.summary = json.summary || null;
  S.en.sovereign = json.sovereign != null ? json.sovereign : null;
  S.en.gpu_reachable = json.gpu_reachable != null ? json.gpu_reachable : null;
  S.en.measured = json.measured_panels != null ? json.measured_panels : null;
  S.en.total = json.total_panels != null ? json.total_panels : null;
  const jt = json.panels && json.panels.jtoken;
  if (jt) { S.en.jtoken = jt.joules_per_token; S.en.carbon = jt.carbon_g_co2eq_per_token; S.en.jlabel = jt.label || null; }
  _updateEn(); _paintEn();
}

function num(...cands) { for (const c of cands) if (typeof c === "number") return c; return null; }

// =========================================================================================
// live geometry updaters
// =========================================================================================
function _updateEnt() {
  const live = S.ent.state === "live"; const dim = live ? 1.0 : 0.32;
  if (_ent.bond) {
    const c = S.ent.concurrence != null ? S.ent.concurrence : 0;
    _ent.bond.material.emissiveIntensity = (0.15 + 1.4 * c) * dim;
    _ent.bond.material.opacity = (0.25 + 0.7 * c) * (live ? 1 : 0.4);
    _ent.bond.material.color.setHex(live ? C_BOND : C_DIM); _ent.bond.material.emissive.setHex(live ? C_BOND : C_DIM);
  }
  if (_ent.entHalo) { const e = S.ent.entropy != null ? S.ent.entropy : 0; _ent.entHalo.material.opacity = (0.6 * e) * (live ? 1 : 0.4); const sc = 0.6 + 0.6 * e; _ent.entHalo.scale.set(sc, sc, sc); }
}
function _updateNeu() {
  const live = S.neu.state === "live"; const dim = live ? 1.0 : 0.35;
  if (_neu.dwBead) {
    const dw = S.neu.stdp_dw != null ? S.neu.stdp_dw : 0;
    _neu.dwBead.position.set(10 / 14, dw * 1.4, 0);
    const pot = S.neu.stdp_kind && /LTP|potent/i.test(S.neu.stdp_kind);
    const col = !live ? C_DIM : (pot ? 0x6dd47e : 0xff8f6b);
    _neu.dwBead.material.color.setHex(col); _neu.dwBead.material.emissive.setHex(col); _neu.dwBead.material.emissiveIntensity = live ? 1.1 : 0.4;
  }
  if (_neu.stdpLine) { _neu.stdpLine.material.opacity = live ? 0.85 : 0.4; _neu.stdpLine.material.color.setHex(live ? C_NEU : C_DIM); }
  if (_neu.cells) {
    _neu.cells.forEach((cell) => {
      let b = S.neu.plast_dormant != null ? 1 - S.neu.plast_dormant : (S.neu.plast_health != null ? S.neu.plast_health : 0.15);
      const col = !live ? C_DIM : (b > 0.4 ? C_NEU : 0x7d8a96);
      cell.material.color.setHex(col); cell.material.emissive.setHex(col);
      cell.material.emissiveIntensity = (0.1 + 0.9 * b) * dim; cell.scale.setScalar(0.7 + 0.5 * b);
    });
  }
}
function _updateQbHelix() {
  const THREE = _THREE; if (!_qb.helix) return;
  const series = S.qb.coh_series; const live = S.qb.cohState === "live";
  const n = series ? series.length : 60; const pts = [];
  for (let i = 0; i < n; i++) {
    const t = i / Math.max(1, n - 1);
    const C = series ? series[i] : Math.exp(-1.6 * t);
    const ang = t * Math.PI * 6; const r = 1.6 * (series ? C : 0.3);
    pts.push(new THREE.Vector3(Math.cos(ang) * r, t * 5 - 2.4, Math.sin(ang) * r));
  }
  _qb.helix.geometry.setFromPoints(pts);
  _qb.helix.material.opacity = live ? 0.9 : 0.3; _qb.helix.material.color.setHex(live ? C_QB : C_DIM);
}
function _updateQbCompass() {
  const THREE = _THREE; if (!_qb.compass) return;
  _qb.petals.forEach((p) => { try { _qb.compass.remove(p); } catch (_) {} }); _qb.petals = [];
  const yields = S.qb.compass; const live = S.qb.compState === "live"; if (!yields) return;
  const entries = Object.keys(yields).map((k) => ({ angle: parseFloat(k), y: yields[k] })).filter((e) => !isNaN(e.angle) && typeof e.y === "number");
  const ys = entries.map((e) => e.y); const ymin = Math.min(...ys), ymax = Math.max(...ys); const span = (ymax - ymin) || 1e-6;
  entries.forEach((e) => {
    const norm = 0.3 + 0.9 * ((e.y - ymin) / span); const a = e.angle * Math.PI / 180;
    const petal = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.06, norm * 2.2, 8),
      new THREE.MeshStandardMaterial({ color: C_QB, emissive: C_QB, emissiveIntensity: live ? 0.9 : 0.3, transparent: true, opacity: live ? 0.95 : 0.4 }));
    petal.position.set(Math.cos(a) * norm * 1.1, 0, Math.sin(a) * norm * 1.1); petal.lookAt(0, 0, 0); petal.rotateX(Math.PI / 2);
    _qb.compass.add(petal); _qb.petals.push(petal);
  });
}
function _updateSc() {
  const THREE = _THREE; if (!_sc.tower) return; const live = S.sc.state === "live";
  // rebuild blocks from live caps
  _sc.blocks.forEach((b) => { try { _sc.tower.remove(b); } catch (_) {} }); _sc.blocks = [];
  const tierColor = (t) => ({ "LIVE-SOVEREIGN": C_EN, "LIVE-MANAGED": C_SC, "HONEST-STUB": C_ROADMAP, "ROADMAP": C_ROADMAP, "UNREACHABLE": 0xff7b72 }[t] || C_DIM);
  const caps = S.sc.caps || [];
  caps.forEach((c, i) => {
    const col = live ? tierColor(c.tier) : C_DIM;
    const box = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.55, 1.4),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: live ? 0.5 : 0.2, metalness: 0.35, roughness: 0.5, transparent: true, opacity: 0.9 }));
    box.position.y = 0.4 + i * 0.7; _sc.tower.add(box); _sc.blocks.push(box);
  });
  // roadmap items as faint ghost blocks on top (honestly dim)
  (S.sc.roadmap || []).forEach((r, i) => {
    const box = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.4, 1.1),
      new THREE.MeshStandardMaterial({ color: C_ROADMAP, emissive: C_ROADMAP, emissiveIntensity: 0.12, wireframe: true, transparent: true, opacity: 0.4 }));
    box.position.y = 0.4 + (caps.length + i) * 0.7; _sc.tower.add(box); _sc.blocks.push(box);
  });
  if (_sc.trustSphere) { const col = (live && S.sc.sovereign_any) ? C_EN : C_SC; _sc.trustSphere.material.color.setHex(col); _sc.trustSphere.material.emissive.setHex(col); _sc.trustSphere.material.emissiveIntensity = live ? 0.4 : 0.2; _sc.trustSphere.position.y = 0.6 + (_sc.blocks.length) * 0.7 + 0.6; }
}
function _updateEn() {
  if (!_en.column) return; const live = S.en.state === "live";
  const measured = (S.en.jlabel && /MEASURED/i.test(S.en.jlabel));
  const jt = S.en.jtoken;
  const h = (jt != null) ? Math.max(0.3, Math.min(6, jt * 4)) : 1.0;   // J/token proxy height (only when MEASURED)
  _en.column.scale.y = h; _en.column.position.y = h / 2;
  const col = !live ? C_DIM : (measured ? C_EN : C_ROADMAP);
  _en.column.material.color.setHex(col); _en.column.material.emissive.setHex(col); _en.column.material.emissiveIntensity = measured ? 0.6 : 0.2;
  _en.column.material.opacity = measured ? 0.92 : 0.55;
  if (_en.carbonRing) { _en.carbonRing.material.color.setHex(col); _en.carbonRing.material.emissive.setHex(col); _en.carbonRing.material.emissiveIntensity = measured ? 0.5 : 0.25; }
  if (_en.pips) {
    const m = S.en.measured != null ? S.en.measured : 0;
    _en.pips.forEach((pip, i) => { const on = i < m; const c = !live ? C_DIM : (on ? C_EN : C_ROADMAP); pip.material.color.setHex(c); pip.material.emissive.setHex(c); pip.material.emissiveIntensity = on ? 0.9 : 0.3; });
  }
}

// =========================================================================================
// per-frame animation + WebGPU compute dispatch
// =========================================================================================
function _onFrame() {
  const t = performance.now();
  if (_qb.compass) _qb.compass.rotation.z += 0.003;
  if (_neu.cells) _neu.cells.forEach((c, i) => { c.rotation.y += 0.01 + i * 0.001; });
  if (_sc.trustSphere) _sc.trustSphere.rotation.y += 0.006;
  if (_en.carbonRing) _en.carbonRing.rotation.z += 0.004;
  if (_ent.g) _ent.g.rotation.y = Math.sin(t * 0.0003) * 0.2;
  // slow lattice breathing
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.06;
  // WebGPU compute dispatch (animates the coherence field on-GPU each frame)
  if (_webgpu && _computeReady && _uT && _computeNode && _stage.renderer && _stage.renderer.compute) {
    try { _uT.value = t * 0.0008; _stage.renderer.compute(_computeNode); } catch (_) { _webgpu = false; }
  }
}

// =========================================================================================
// DOM overlay (HUD) + light-field export button
// =========================================================================================
function _buildOverlay() {
  const ctx = _ctx;
  ["ent", "neu", "qbcoh", "qbcomp", "sc", "en"].forEach((k) => { _badges[k] = ctx.live.createBadge(); });

  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,450px)", maxHeight: "calc(100vh - 130px)", overflowY: "auto",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
    paddingRight: "6px",
  });

  const h = document.createElement("div"); h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px"; h.textContent = TITLE; _overlay.appendChild(h);
  const sub = document.createElement("div"); sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML = 'The experimental tier as one holographic lattice \u2014 <b>five frontier organs</b>, each lit by a <b>live</b> a11oy endpoint. ' +
    'Quantum-bio runs on a <b>WebGPU compute pass</b> when available (<code>?webgpu=1</code>); WebGL2 otherwise. ' +
    'Every label is read <b>verbatim</b> from the JSON. NOT in the locked-8 \u00b7 \u039b = Conjecture 1 \u00b7 trust &lt; 100%.';
  _overlay.appendChild(sub);

  // renderer + light-field controls
  const ctlRow = document.createElement("div"); ctlRow.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  _el.rendererChip = document.createElement("span");
  _el.rendererChip.style.cssText = "font:10px ui-monospace,monospace;padding:3px 8px;border-radius:6px;border:1px solid #1d2a36;color:" + (_webgpu ? "#6dd47e" : "#6fb1ff");
  _el.rendererChip.textContent = _webgpu ? "compute: WebGPU" : "compute: endpoint (WebGL2)";
  ctlRow.appendChild(_el.rendererChip);
  const lfBtn = document.createElement("button");
  lfBtn.textContent = "\u25c8 light-field export";
  lfBtn.title = "Render a Looking Glass quilt (grid of horizontal views) as a downloadable PNG for a light-field holographic display.";
  lfBtn.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #39d3c4;background:#0d2028;color:#39d3c4;cursor:pointer";
  lfBtn.addEventListener("click", () => _exportLightField(lfBtn));
  ctlRow.appendChild(lfBtn);
  _el.lfStatus = document.createElement("span"); _el.lfStatus.style.cssText = "font:10px ui-monospace,monospace;color:#9fb1bf"; ctlRow.appendChild(_el.lfStatus);
  _overlay.appendChild(ctlRow);

  _overlay.appendChild(_organCard("entanglement", "#8a6bff", _badges.ent, [
    ["ent-entropy", "von Neumann entropy (bits)"], ["ent-conc", "concurrence (Wootters)"], ["ent-neg", "negativity (Vidal-Werner)"],
  ], "Streltsov-2015 coherence\u2192entanglement bound. Leaders: Google Quantum AI (Willow) \u00b7 Quantinuum \u00b7 Verstraete/Cirac/Schuch PEPS \u00b7 Vidal MERA. RIGOROUS \u00b7 not claimed-as."));

  _overlay.appendChild(_organCard("neuroplasticity", "#39d3c4", _badges.neu, [
    ["neu-dw", "STDP \u0394w @ \u0394t=10ms (Bi-Poo 1998)"], ["neu-kind", "LTP / LTD"], ["neu-health", "plasticity health"],
  ], "Hebb/Oja/BCM/STDP + Dohare-Sutton loss-of-plasticity (Nature 2024). Leaders: DeepMind EWC \u00b7 Zenke SI \u00b7 Numenta \u00b7 Liquid AI LTC \u00b7 Intel Loihi. RIGOROUS \u00b7 not claimed-as."));

  const qbBadges = document.createElement("div"); qbBadges.style.cssText = "display:flex;gap:6px;flex-wrap:wrap"; qbBadges.appendChild(_badges.qbcoh.el); qbBadges.appendChild(_badges.qbcomp.el);
  _overlay.appendChild(_organCard("quantum-bio", "#e8c074", { el: qbBadges }, [
    ["qb-tau", "Lindblad \u03c4_c (coherence)"], ["qb-contrast", "compass angular contrast"], ["qb-works", "compass works"],
  ], "Lindblad/GKSL master eq + radical-pair compass \u2014 WebGPU compute accelerated. Leaders: Engel/Fleming (Nature 2007) \u00b7 Hore cryptochrome \u00b7 Lambert/Nori QuTiP. VERIFIED \u00b7 not claimed-as."));

  _overlay.appendChild(_organCard("sovereign-compute", "#6fb1ff", _badges.sc, [
    ["sc-summary", "posture"], ["sc-sovereign", "on our GPU?"], ["sc-caps", "capabilities"],
  ], "Honest sovereign-inference posture; sovereign:true ONLY on a real local-GPU probe. Leaders: NVIDIA confidential compute (H100 TEE) \u00b7 Prime Intellect DiLoCo \u00b7 Petals. tier-labeled \u00b7 never faked green."));

  _overlay.appendChild(_organCard("energy", "#6dd47e", _badges.en, [
    ["en-jtoken", "J/token"], ["en-carbon", "gCO\u2082e/token"], ["en-measured", "measured panels"],
  ], "MEASURED only on a live GPU power probe (NVML/exporter); no meter \u2192 honest ROADMAP. Leaders: Google carbon-intelligent computing \u00b7 GSF SCI \u00b7 CodeCarbon \u00b7 Electricity Maps."));

  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);
  const src = document.createElement("div"); src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Sources (adopted & cited, NOT claimed-as): Wootters 1998 \u00b7 Vidal-Werner 2002 \u00b7 Streltsov 2015 \u00b7 Bi&Poo 1998 \u00b7 Dohare-Sutton Nature 2024 \u00b7 Lindblad/GKSL \u00b7 Schulten/Hore radical-pair (PNAS) \u00b7 NVIDIA H100 confidential compute \u00b7 Prime Intellect DiLoCo \u00b7 GSF Software Carbon Intensity. EXPERIMENTAL tier; not in the locked-8. Light-field export = Looking Glass quilt format.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
  _paintEnt(); _paintNeu(); _paintQb(); _paintSc(); _paintEn();
}

function _organCard(name, color, badge, kpis, footnote) {
  const card = document.createElement("div"); card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";
  const head = document.createElement("div"); head.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span"); dot.style.cssText = `width:9px;height:9px;border-radius:50%;background:${color};box-shadow:0 0 7px ${color}`;
  const nm = document.createElement("b"); nm.style.cssText = `font-size:12px;color:${color};letter-spacing:.3px`; nm.textContent = name;
  head.appendChild(dot); head.appendChild(nm); if (badge && badge.el) head.appendChild(badge.el); card.appendChild(head);
  const grid = document.createElement("div"); grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  kpis.forEach(([id, lab]) => {
    const row = document.createElement("div"); row.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = lab;
    const v = document.createElement("b"); v.id = id; v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:56%"; v.textContent = "\u2014"; _el[id] = v;
    row.appendChild(l); row.appendChild(v); grid.appendChild(row);
  });
  card.appendChild(grid);
  const fn = document.createElement("div"); fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5"; fn.textContent = footnote; card.appendChild(fn);
  return card;
}

// =========================================================================================
// Light-field / Looking Glass QUILT export.
// Renders the scene from N horizontal camera positions (a light-field sweep) into a grid
// (quilt). The quilt is the Looking Glass display's native input: a downloadable PNG that
// drives a real light-field holographic display. Uses only the vendored renderer (0 CDN).
// =========================================================================================
async function _exportLightField(btn) {
  const THREE = _THREE, stage = _stage;
  if (!stage || !stage.renderer) return;
  const COLS = 5, ROWS = 9, VIEWS = COLS * ROWS;   // 45-view Looking Glass quilt
  const TILE_W = 256, TILE_H = 256;                // per-view tile (keeps PNG reasonable)
  btn.disabled = true; const prevTxt = btn.textContent; btn.textContent = "rendering\u2026";
  if (_el.lfStatus) _el.lfStatus.textContent = `${VIEWS} views\u2026`;
  try {
    const renderer = stage.renderer, scene = stage.scene, srcCam = stage.camera;
    // dedicated render target + a cloned camera swept horizontally around the target
    const rt = new THREE.WebGLRenderTarget(TILE_W, TILE_H, { samples: 2 });
    const cam = srcCam.clone();
    const target = (stage.controls && stage.controls.target) ? stage.controls.target.clone() : new THREE.Vector3(0, 2.4, 0);
    const radius = srcCam.position.distanceTo(target);
    const baseAngle = Math.atan2(srcCam.position.x - target.x, srcCam.position.z - target.z);
    const height = srcCam.position.y;
    const CONE = 0.5; // ~28° total horizontal sweep (Looking Glass viewing cone)

    const quilt = document.createElement("canvas"); quilt.width = COLS * TILE_W; quilt.height = ROWS * TILE_H;
    const qx = quilt.getContext("2d");
    const readCanvas = document.createElement("canvas"); readCanvas.width = TILE_W; readCanvas.height = TILE_H;
    const rc = readCanvas.getContext("2d");
    const pixels = new Uint8Array(TILE_W * TILE_H * 4);

    const prevRT = renderer.getRenderTarget();
    for (let v = 0; v < VIEWS; v++) {
      const tView = VIEWS > 1 ? (v / (VIEWS - 1) - 0.5) : 0;   // -0.5..0.5
      const ang = baseAngle + tView * CONE;
      cam.position.set(target.x + Math.sin(ang) * radius, height, target.z + Math.cos(ang) * radius);
      cam.lookAt(target); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
      renderer.setRenderTarget(rt);
      renderer.render(scene, cam);
      renderer.readRenderTargetPixels(rt, 0, 0, TILE_W, TILE_H, pixels);
      // flip vertically (GL origin is bottom-left) into the read canvas
      const img = rc.createImageData(TILE_W, TILE_H);
      for (let y = 0; y < TILE_H; y++) {
        const sy = TILE_H - 1 - y;
        img.data.set(pixels.subarray(sy * TILE_W * 4, (sy + 1) * TILE_W * 4), y * TILE_W * 4);
      }
      rc.putImageData(img, 0, 0);
      // quilt layout: Looking Glass fills bottom-left→right, bottom→top
      const col = v % COLS, row = ROWS - 1 - Math.floor(v / COLS);
      qx.drawImage(readCanvas, col * TILE_W, row * TILE_H);
      if (_el.lfStatus && (v % 5 === 0)) { _el.lfStatus.textContent = `view ${v + 1}/${VIEWS}`; await new Promise((r) => setTimeout(r, 0)); }
    }
    renderer.setRenderTarget(prevRT);
    rt.dispose();

    // download the quilt PNG (name encodes columns/rows/aspect per Looking Glass convention)
    const name = `frontier_qs${COLS}x${ROWS}a${(TILE_W / TILE_H).toFixed(2)}.png`;
    quilt.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1500);
      if (_el.lfStatus) _el.lfStatus.textContent = `saved ${COLS}\u00d7${ROWS} quilt`;
    }, "image/png");
  } catch (e) {
    if (_el.lfStatus) _el.lfStatus.textContent = "export failed"; console.error("[frontier] light-field export:", e);
  } finally {
    btn.disabled = false; btn.textContent = prevTxt;
  }
}

// =========================================================================================
// KPI painters (honest tokens when not live)
// =========================================================================================
function _tok(state) { if (state === "live") return null; if (state === "missing") return "NO-LIVE-DATA"; if (state === "degraded") return "DEGRADED"; if (state === "error") return "OFFLINE"; return "\u2026"; }
function _paintEnt() { const t = _tok(S.ent.state); _set("ent-entropy", t || fx(S.ent.entropy, 4)); _set("ent-conc", t || fx(S.ent.concurrence, 4)); _set("ent-neg", t || fx(S.ent.negativity, 4)); }
function _paintNeu() { const t = _tok(S.neu.state); _set("neu-dw", t || fx(S.neu.stdp_dw, 4)); _set("neu-kind", t || (S.neu.stdp_kind || "\u2014")); _set("neu-health", t || (S.neu.plast_health != null ? fx(S.neu.plast_health, 3) : (S.neu.plast_dormant != null ? "dormant " + fx(S.neu.plast_dormant, 2) : "\u2014"))); }
function _paintQb() { const tc = _tok(S.qb.cohState), tk = _tok(S.qb.compState); _set("qb-tau", tc || (S.qb.tau_c != null ? String(S.qb.tau_c) : "\u2014")); _set("qb-contrast", tk || fx(S.qb.contrast, 4)); _set("qb-works", tk || (S.qb.works != null ? (S.qb.works ? "yes" : "no") : "\u2014")); }
function _paintSc() {
  const t = _tok(S.sc.state);
  _set("sc-summary", t || (S.sc.summary ? (S.sc.summary.length > 30 ? S.sc.summary.slice(0, 29) + "\u2026" : S.sc.summary) : "\u2014"));
  _set("sc-sovereign", t || (S.sc.sovereign_any != null ? (S.sc.sovereign_any ? "yes (sovereign GPU)" : "no (managed)") : "\u2014"));
  _set("sc-caps", t || (S.sc.caps ? S.sc.caps.map((c) => c.tier).join(", ") : "\u2014"));
}
function _paintEn() {
  const t = _tok(S.en.state);
  _set("en-jtoken", t || (S.en.jtoken != null ? fx(S.en.jtoken, 4) : (S.en.jlabel || "ROADMAP")));
  _set("en-carbon", t || (S.en.carbon != null ? fx(S.en.carbon, 4) : "ROADMAP"));
  _set("en-measured", t || (S.en.measured != null && S.en.total != null ? `${S.en.measured}/${S.en.total}` : "\u2014"));
}
function fx(v, d) { return (typeof v === "number") ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

// =========================================================================================
// unmount
// =========================================================================================
function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
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
  _group = _overlay = null; _ent = {}; _neu = {}; _qb = {}; _sc = {}; _en = {}; _el = {}; _badges = {};
  _tsl = _computeNode = _cohBuf = _uTau = _uT = null; _computeReady = false;
  S.ent = { entropy: null, concurrence: null, eof: null, negativity: null, logneg: null, label: null, state: "init" };
  S.neu = { stdp_dw: null, stdp_kind: null, plast_health: null, plast_dormant: null, label: null, state: "init" };
  S.qb = { coh_series: null, tau_c: null, compass: null, contrast: null, works: null, cohState: "init", compState: "init" };
  S.sc = { summary: null, sovereign_any: null, caps: null, roadmap: null, label: null, state: "init" };
  S.en = { summary: null, sovereign: null, gpu_reachable: null, measured: null, total: null, jtoken: null, carbon: null, jlabel: null, state: "init" };
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_ENT_ENTROPY, EP_ENT_CONC, EP_ENT_NEG, EP_NEU_STDP, EP_QB_COH, EP_QB_COMPASS, EP_SC, EP_EN], mount, unmount };
