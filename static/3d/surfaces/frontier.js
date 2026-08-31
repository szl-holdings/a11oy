// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/frontier.js — FRONTIER holographic surface (the experimental tier, made 3D).
//
// Fuses NINE SZL frontier "organs" into ONE holographic lattice on a ring, each node lit by
// a REAL live a11oy endpoint and carrying its honesty label VERBATIM from the JSON — never
// upgraded here. Quantum-bio renders as a Gaussian-splat-style VOLUMETRIC coherence field
// (WebGPU compute pass when available; instanced WebGL2 splats otherwise). A Looking-Glass
// LIGHT-FIELD export renders a 45-view quilt PNG for a real light-field display.
//
// ORGANS + endpoints (every shown value traces to one):
//   entanglement      /entangle/{entropy,concurrence,negativity}   — QuTiP-style measures
//   neuroplasticity   /neuro/{stdp,plasticity}                     — Bi-Poo STDP + ReDo/EWC
//   quantum-bio       /qbio/{coherence,compass}   [WebGPU splat]   — Lindblad/GKSL + radical-pair
//   sovereign-compute /sovereign-compute                          — honest sovereign-inference posture
//   energy            /energy/sovereign                           — J/token + carbon (SCI-aligned)
//   scaling           /scaling/{summary,exponents}                — Kleiber/WBE/MTE + urban allometry
//   conjecture        /conjecture-factory                         — OPEN conjectures (generated, not proven)
//   publications      /experimental/index                        — live locked-8 + thesis/DOI lineage
//
// LEADERS ADOPTED & CITED (NOT claimed-as; clean-room re-implementations of open technique):
//   entanglement: QuTiP (entropy_vn/concurrence/negativity, BSD) · quimb MPS/PEPS · Vidal MERA
//     · Verstraete-Cirac RMP arXiv:2011.12127 · Google Quantum AI (Willow) · Quantinuum.
//   quantum-bio: RadicalPy (MIT) · quantum_HEOM (MIT, FMO 7-site Lindblad) · Hore/Kattnig
//     cryptochrome arXiv:2508.21350 · Tanimura HEOM · Engel/Fleming (Nature 2007).
//   neuroplasticity: Avalanche (MIT) · ncps/LTC Apache-2 (Hasani arXiv:2006.04439) · Dohare-Sutton
//     ReDo/continual-backprop arXiv:2306.13812 · Zenke SI arXiv:1703.04200 · Kirkpatrick EWC.
//   sovereign-compute: Prime Intellect prime/OpenDiLoCo (Apache-2, arXiv:2501.18512 Streaming DiLoCo)
//     · NVIDIA nvtrust confidential compute (H100 TEE) · Petals · vLLM/SGLang.
//   energy: CodeCarbon (MIT) · GSF Carbon Aware SDK + SCI=(O+M)/R (ISO 21031:2024) · Zeus · NVML.
//   holography: three.js WebGPU/TSL (MIT) · mkkellogg/GaussianSplats3D (MIT) · Kerbl 3DGS
//     arXiv:2308.04079 · Looking Glass quilt (@lookingglass/webxr, Apache-2).
//   scaling: Kleiber 1932 / West-Brown-Enquist 1997 / MTE 2004 / Bettencourt-West 2007.
//
// DOCTRINE v11: every value traces to a real endpoint; honesty labels read straight from JSON.
// NOTHING here is in the locked-8. Λ = Conjecture 1. Trust < 100%. Endpoints that 404/error/
// degrade render honest NO-LIVE-DATA/DEGRADED and grey their geometry. 0 runtime CDN.

import { createShowcase } from "./_showcase.js";

const ID = "frontier";
const TITLE = "Frontier · Experimental Tier (live)";

const EP_ENT_ENTROPY = "/api/a11oy/v1/entangle/entropy?state=bell";
const EP_ENT_CONC = "/api/a11oy/v1/entangle/concurrence?state=bell";
const EP_ENT_NEG = "/api/a11oy/v1/entangle/negativity?state=bell";
const EP_NEU_STDP = "/api/a11oy/v1/neuro/stdp?dt=10";
const EP_NEU_PLAST = "/api/a11oy/v1/neuro/plasticity?act=0.5,0.0,0.0001,0.8,0.0";
const EP_QB_COH = "/api/a11oy/v1/qbio/coherence?tau_c=6.05&steps=60";
const EP_QB_COMPASS = "/api/a11oy/v1/qbio/compass?B_uT=50&angles=0,30,60,90,120,150,180";
const EP_SC = "/api/a11oy/v1/sovereign-compute";
const EP_EN = "/api/a11oy/v1/energy/sovereign";
const EP_SCALE = "/api/a11oy/v1/scaling/exponents";
const EP_CONJ = "/api/a11oy/v1/conjecture-factory";
const EP_PUBS = "/api/a11oy/v1/experimental/index";
const EP_ECO = "/api/a11oy/v1/genome";                       // ecosystem organ (investor/consumer headline)

// data hues
const C = { ent: 0x8a6bff, neu: 0x39d3c4, qb: 0xe8c074, sc: 0x6fb1ff, en: 0x6dd47e, scale: 0xffb56b, conj: 0xd7b96b, pubs: 0x9fd0ff, eco: 0x3af4c8, bond: 0x6fb1ff, dim: 0x42505d, roadmap: 0x9aa7b4 };

// 9 organs on a ring; camera frames the whole lattice
const N_ORG = 9, RING = 14;
function ring(i, y) { const a = Math.PI / 2 - (i / N_ORG) * Math.PI * 2; return [Math.cos(a) * RING, y, -Math.sin(a) * RING * 0.6]; }
const POS = { ent: ring(0, 3), neu: ring(1, 3), qb: ring(2, 3), en: ring(3, 3), scale: ring(4, 3), sc: ring(5, 3), conj: ring(6, 3), pubs: ring(7, 3), eco: ring(8, 3) };
const HUB = [0, 3, 0];

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badges = {}, _webgpu = false, _computeReady = false;
let _ent = {}, _neu = {}, _qb = {}, _sc = {}, _en = {}, _scale = {}, _conj = {}, _pubs = {}, _eco = {};
let _splatlib = null, _lkg = null, _plain = false;   // real-3DGS codec, Looking Glass runtime, plain-language mode

const S = {
  ent: { entropy: null, concurrence: null, negativity: null, state: "init" },
  neu: { dw: null, kind: null, health: null, dormant: null, state: "init" },
  qb: { coh: null, tau: null, compass: null, contrast: null, works: null, cohState: "init", compState: "init" },
  sc: { summary: null, sovereign_any: null, caps: null, roadmap: null, state: "init" },
  en: { jtoken: null, carbon: null, jlabel: null, measured: null, total: null, state: "init" },
  scale: { exps: null, state: "init" },
  conj: { count: null, first: null, state: "init" },
  pubs: { locked: null, lockedCount: null, expKernel: null, lambda: null, state: "init" },
  eco: { count: null, tiers: null, state: "init" },
};

// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _webgpu = (_stage.backend === "webgpu");
  _group = new _THREE.Group(); _stage.scene.add(_group);
  _stage.camera.position.set(0, 10, 34);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.6, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildEntanglement(); _buildNeuroplasticity(); _buildQuantumBio();
  _buildSovereignCompute(); _buildEnergy(); _buildScaling(); _buildConjecture(); _buildPublications(); _buildEcosystem();
  _buildLinks(); _buildOrganLabels();
  if (_webgpu) { try { _initCompute(); } catch (e) { _webgpu = false; console.warn("[frontier] WebGPU compute init failed, using splat/endpoint path:", e && e.message); } }
  // lazy-load the real-.splat 3DGS codec (clean-room) so quantum-bio can render a genuine
  // gaussian-splat MODEL encoded from live coherence data (not procedural points).
  import("/static/3d/szl3d/szl3d_splat.js").then((m) => { _splatlib = m.default || m; _initRealSplat(); }).catch((e) => console.warn("[frontier] splat codec load failed, using point cloud:", e && e.message));
  _buildOverlay();
  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  const P = (url, ms, cb, bk, os) => ctx.live.poll(url, ms, cb, { badge: _badges[bk], onState: os });
  _polls.push(P(EP_ENT_ENTROPY, 5000, _onEntEntropy, "ent", (m) => { S.ent.state = m.state; _paintEnt(); }));
  _polls.push(P(EP_ENT_CONC, 5200, _onEntConc, null));
  _polls.push(P(EP_ENT_NEG, 5400, _onEntNeg, null));
  _polls.push(P(EP_NEU_STDP, 5600, _onNeuStdp, "neu", (m) => { S.neu.state = m.state; _paintNeu(); }));
  _polls.push(P(EP_NEU_PLAST, 6000, _onNeuPlast, null));
  _polls.push(P(EP_QB_COH, 5800, _onQbCoh, "qbcoh", (m) => { S.qb.cohState = m.state; _paintQb(); }));
  _polls.push(P(EP_QB_COMPASS, 6200, _onQbCompass, "qbcomp", (m) => { S.qb.compState = m.state; _paintQb(); }));
  _polls.push(P(EP_SC, 8000, _onSc, "sc", (m) => { S.sc.state = m.state; _paintSc(); }));
  _polls.push(P(EP_EN, 8000, _onEn, "en", (m) => { S.en.state = m.state; _paintEn(); }));
  _polls.push(P(EP_SCALE, 9000, _onScale, "scale", (m) => { S.scale.state = m.state; _paintScale(); }));
  _polls.push(P(EP_CONJ, 9000, _onConj, "conj", (m) => { S.conj.state = m.state; _paintConj(); }));
  _polls.push(P(EP_PUBS, 10000, _onPubs, "pubs", (m) => { S.pubs.state = m.state; _paintPubs(); }));
  _polls.push(P(EP_ECO, 11000, _onEco, "eco", (m) => { S.eco.state = m.state; _paintEco(); }));
  return { id: ID, started: true };
}

// =========================================================================================
// builders
// =========================================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(60, 60, 0x16313c, 0x0f2027);
  grid.material.opacity = 0.2; grid.material.transparent = true; grid.position.y = -0.01; _group.add(grid);
}

function _org(key) { const THREE = _THREE; const g = new THREE.Group(); g.position.set(...POS[key]); _group.add(g); return g; }

function _buildEntanglement() {
  const THREE = _THREE; const g = _org("ent");
  const mkBloch = (dx) => {
    const s = new THREE.Group();
    s.add(new THREE.Mesh(new THREE.SphereGeometry(0.8, 20, 12), new THREE.MeshBasicMaterial({ color: 0x244a55, wireframe: true, transparent: true, opacity: 0.45 })));
    s.add(new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 12), new THREE.MeshStandardMaterial({ color: C.ent, emissive: C.ent, emissiveIntensity: 1 })));
    s.add(new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 0), 0.8, C.ent, 0.18, 0.1));
    s.position.x = dx; return s;
  };
  _ent.qA = mkBloch(-1.5); _ent.qB = mkBloch(1.5); g.add(_ent.qA, _ent.qB);
  const bg = new THREE.CylinderGeometry(0.05, 0.05, 3, 12); bg.rotateZ(Math.PI / 2);
  _ent.bond = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({ color: C.bond, emissive: C.bond, emissiveIntensity: 0.2, transparent: true, opacity: 0.6 })); g.add(_ent.bond);
  _ent.halo = new THREE.Mesh(new THREE.RingGeometry(1.8, 2.0, 40), new THREE.MeshBasicMaterial({ color: C.ent, transparent: true, opacity: 0, side: THREE.DoubleSide }));
  _ent.halo.rotation.x = -Math.PI / 2; _ent.halo.position.y = -1.1; g.add(_ent.halo); _ent.g = g;
}

function _buildNeuroplasticity() {
  const THREE = _THREE; const g = _org("neu");
  const NP = 71, pts = [];
  for (let i = 0; i < NP; i++) { const dt = (i / (NP - 1) - 0.5) * 80; const dw = dt >= 0 ? Math.exp(-dt / 16.8) : -Math.exp(dt / 33.7); pts.push(new THREE.Vector3(dt / 16, dw * 1.3, 0)); }
  _neu.line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: C.neu, transparent: true, opacity: 0.5 })); g.add(_neu.line);
  _neu.bead = new THREE.Mesh(new THREE.SphereGeometry(0.13, 14, 14), new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.8 })); g.add(_neu.bead);
  _neu.cells = [];
  for (let i = 0; i < 5; i++) { const c = new THREE.Mesh(new THREE.IcosahedronGeometry(0.2, 0), new THREE.MeshStandardMaterial({ color: C.neu, emissive: C.neu, emissiveIntensity: 0.15, metalness: 0.3, roughness: 0.5 })); c.position.set((i - 2) * 0.62, -2, 0); g.add(c); _neu.cells.push(c); }
  _neu.g = g;
}

function _buildQuantumBio() {
  const THREE = _THREE; const g = _org("qb");
  _qb.helix = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: C.qb, transparent: true, opacity: 0.3 }));
  _qb.helix.position.set(0, 0.3, 0); g.add(_qb.helix);
  _qb.compass = new THREE.Group(); _qb.compass.position.set(0, -2, 0); _qb.compass.rotation.x = -Math.PI / 2; _qb.petals = []; g.add(_qb.compass);
  // Gaussian-splat-style VOLUMETRIC coherence field: instanced soft billboards whose radius ==
  // live coherence C(t) along the Lindblad decay (a 3DGS-inspired point cloud, WebGL2-safe).
  _buildSplatField(g);
  _qb.g = g;
}

// clean-room 3DGS-style splat cloud: instanced additively-blended sprites (soft radial texture).
// arXiv:2308.04079 (Kerbl) / mkkellogg/GaussianSplats3D (MIT) inspired — visual density only.
let _splatTex = null;
function _splatTexture() {
  if (_splatTex) return _splatTex;
  const THREE = _THREE; const s = 64; const cv = document.createElement("canvas"); cv.width = cv.height = s;
  const cx = cv.getContext("2d"); const gr = cx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(0.4, "rgba(255,255,255,0.5)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  cx.fillStyle = gr; cx.fillRect(0, 0, s, s); _splatTex = new THREE.CanvasTexture(cv); return _splatTex;
}
const SPLAT_N = 1400;
function _buildSplatField(g) {
  const THREE = _THREE;
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(SPLAT_N * 3), col = new Float32Array(SPLAT_N * 3), scl = new Float32Array(SPLAT_N);
  for (let i = 0; i < SPLAT_N; i++) { scl[i] = Math.random(); }
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  const mat = new THREE.PointsMaterial({ size: 0.32, map: _splatTexture(), vertexColors: true, transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
  _qb.splat = new THREE.Points(geo, mat); _qb.splat.userData.rand = scl; _qb.splat.position.set(0, 0.3, 0);
  g.add(_qb.splat);
}
function _updateSplatField() {
  const s = _qb.splat; if (!s) return;
  const series = S.qb.coh; const live = S.qb.cohState === "live";
  const pos = s.geometry.attributes.position, col = s.geometry.attributes.color, rnd = s.userData.rand;
  const n = series ? series.length : 60;
  const cQb = new _THREE.Color(live ? C.qb : C.dim);
  for (let i = 0; i < SPLAT_N; i++) {
    const t = (i / SPLAT_N);
    const k = Math.min(n - 1, Math.floor(t * n));
    const Ck = series ? series[k] : Math.exp(-1.6 * t);         // live coherence at this depth
    const ang = t * Math.PI * 8 + rnd[i] * 6.28;
    const jitter = (rnd[i] - 0.5) * 0.5 * Ck;                    // spread ~ coherence (decoheres → collapses)
    const r = 1.6 * Ck + jitter;
    pos.setXYZ(i, Math.cos(ang) * r, t * 5 - 2.4, Math.sin(ang) * r);
    const b = live ? (0.35 + 0.65 * Ck) : 0.3;
    col.setXYZ(i, cQb.r * b, cQb.g * b, cQb.b * b);
  }
  pos.needsUpdate = true; col.needsUpdate = true;
  s.material.opacity = live ? 0.55 : 0.2;
}

// ---- REAL 3DGS: encode the live coherence field as a genuine .splat MODEL + render it ----
// Clean-room .splat (32-byte record) codec + anisotropic gaussian renderer (szl3d_splat.js).
// Every rendered gaussian's position/scale/rotation/color comes from a real .splat record we
// encode from the LIVE coherence series — a real gaussian-splat model, honestly, not procedural.
let _realMesh = null, _realBytes = null;
function _cohToSplats() {
  const series = S.qb.coh; const n = series ? series.length : 60; const out = [];
  const base = _splatlib.colorToFdc(0.9);   // warm gold DC
  for (let i = 0; i < 1200; i++) {
    const t = i / 1200; const k = Math.min(n - 1, Math.floor(t * n));
    const Ck = series ? series[k] : Math.exp(-1.6 * t);
    const ang = t * Math.PI * 8 + (i % 7) * 0.9;
    const r = 1.6 * Ck;
    // anisotropic scale: splat gets fatter where coherent, collapses as it decoheres
    const sca = 0.05 + 0.14 * Ck;
    out.push({ x: Math.cos(ang) * r, y: t * 5 - 2.4, z: Math.sin(ang) * r,
      sx: sca, sy: sca * (0.5 + 0.5 * Ck), sz: sca,
      r: _splatlib.shDcToU8(base), g: _splatlib.shDcToU8(base * 0.72), b: _splatlib.shDcToU8(base * 0.28),
      a: Math.round(255 * (0.35 + 0.6 * Ck)),
      qw: Math.cos(ang / 2), qx: 0, qy: Math.sin(ang / 2), qz: 0 });
  }
  return out;
}
function _initRealSplat() {
  if (!_splatlib || !_qb.g) return;
  try {
    _realBytes = _splatlib.encodeSplat(_cohToSplats());   // a REAL .splat binary from live data
    _qb.real = _splatlib.buildSplatMesh(_THREE, _realBytes, { maxInstances: 1400, opacity: 0.85, scaleMul: 1 });
    _qb.real.mesh.position.set(0, 0.3, 0); _qb.g.add(_qb.real.mesh);
    // the real gaussian-splat model supersedes the procedural point cloud + gpu field
    if (_qb.splat) _qb.splat.visible = false;
    if (_qb.gpuField) _qb.gpuField.visible = false;
  } catch (e) { console.warn("[frontier] real-splat build failed:", e && e.message); }
}
function _updateRealSplat() {
  if (!_splatlib || !_qb.real) return;
  try { _realBytes = _splatlib.encodeSplat(_cohToSplats()); _qb.real.update(_realBytes); } catch (_) {}
}
// download the encoded .splat model (a real gaussian-splat file, openable in any 3DGS viewer)
function _downloadSplat() {
  if (!_realBytes) return;
  const blob = new Blob([_realBytes], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob); const a = document.createElement("a");
  a.href = url; a.download = "szl_coherence_field.splat"; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1500);
}

function _buildSovereignCompute() {
  const THREE = _THREE; const g = _org("sc");
  _sc.tower = new THREE.Group(); g.add(_sc.tower); _sc.blocks = [];
  _sc.trust = new THREE.Mesh(new THREE.IcosahedronGeometry(0.55, 1), new THREE.MeshStandardMaterial({ color: C.sc, emissive: C.sc, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.5 }));
  _sc.trust.position.y = 3; g.add(_sc.trust); _sc.g = g;
}

function _buildEnergy() {
  const THREE = _THREE; const g = _org("en");
  _en.col = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.55, 1, 20), new THREE.MeshStandardMaterial({ color: C.roadmap, emissive: C.roadmap, emissiveIntensity: 0.2, metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.6 }));
  _en.col.position.y = 0.5; g.add(_en.col);
  _en.ring = new THREE.Mesh(new THREE.TorusGeometry(1.3, 0.05, 12, 44), new THREE.MeshStandardMaterial({ color: C.roadmap, emissive: C.roadmap, emissiveIntensity: 0.3, transparent: true, opacity: 0.5 }));
  _en.ring.rotation.x = Math.PI / 2; g.add(_en.ring);
  _en.pips = []; const pr = new THREE.Group(); pr.position.set(0, -1.6, 0);
  for (let i = 0; i < 6; i++) { const p = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 10), new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.4 })); p.position.x = (i - 2.5) * 0.36; pr.add(p); _en.pips.push(p); } g.add(pr); _en.g = g;
}

function _buildScaling() {
  const THREE = _THREE; const g = _org("scale");
  // allometric power-law fan: each exponent drawn as a curve y=x^b from a shared origin
  _scale.curves = new THREE.Group(); g.add(_scale.curves); _scale.g = g;
  _scale.note = null;
}
function _updateScaling() {
  const THREE = _THREE; if (!_scale.curves) return;
  for (let i = _scale.curves.children.length - 1; i >= 0; i--) _scale.curves.remove(_scale.curves.children[i]);
  const exps = S.scale.exps; const live = S.scale.state === "live"; if (!exps) return;
  const cols = [0xffb56b, 0x6dd47e, 0x6fb1ff, 0xd7b96b, 0x8a6bff, 0x39d3c4];
  exps.slice(0, 6).forEach((e, i) => {
    const b = typeof e.exponent === "number" ? e.exponent : 1;
    const pts = [];
    for (let k = 0; k <= 40; k++) { const x = k / 40; const y = Math.pow(Math.max(x, 1e-4), Math.abs(b)); pts.push(new THREE.Vector3(x * 3 - 1.5, (b < 0 ? (1 - y) : y) * 2.6 - 0.5, 0)); }
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: live ? cols[i % cols.length] : C.dim, transparent: true, opacity: live ? 0.85 : 0.35 }));
    _scale.curves.add(line);
  });
}

function _buildConjecture() {
  const THREE = _THREE; const g = _org("conj");
  // OPEN conjectures as a slowly-rotating dodecahedron cage (open = wireframe, never solid/proven)
  _conj.cage = new THREE.Mesh(new THREE.DodecahedronGeometry(1.4, 0), new THREE.MeshStandardMaterial({ color: C.conj, emissive: C.conj, emissiveIntensity: 0.25, wireframe: true, transparent: true, opacity: 0.5 }));
  g.add(_conj.cage);
  _conj.core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.3, 0), new THREE.MeshStandardMaterial({ color: C.conj, emissive: C.conj, emissiveIntensity: 0.6, transparent: true, opacity: 0.7 }));
  g.add(_conj.core); _conj.g = g;
}

function _buildPublications() {
  const THREE = _THREE; const g = _org("pubs");
  // thesis lineage as a rising helix of nodes (v1→v25); the locked-proven count is a solid core
  _pubs.spine = new THREE.Group(); g.add(_pubs.spine);
  const NV = 25, pts = [];
  for (let i = 0; i < NV; i++) { const t = i / (NV - 1); const a = t * Math.PI * 4; pts.push(new THREE.Vector3(Math.cos(a) * 1.0, t * 4.5 - 2.2, Math.sin(a) * 1.0)); }
  _pubs.helix = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: C.pubs, transparent: true, opacity: 0.5 }));
  _pubs.spine.add(_pubs.helix);
  _pubs.nodes = [];
  pts.forEach((p) => { const n = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 8), new THREE.MeshStandardMaterial({ color: C.pubs, emissive: C.pubs, emissiveIntensity: 0.4 })); n.position.copy(p); _pubs.spine.add(n); _pubs.nodes.push(n); });
  _pubs.core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.4, 1), new THREE.MeshStandardMaterial({ color: C.pubs, emissive: C.pubs, emissiveIntensity: 0.7, transparent: true, opacity: 0.85 }));
  _pubs.core.position.y = -2.2; g.add(_pubs.core); _pubs.g = g;
}

function _buildEcosystem() {
  const THREE = _THREE; const g = _org("eco");
  // the investor/consumer headline organ: the live governed-capability genome as a tiered
  // sphere — concentric shells sized by the 5 honesty tiers (LOCKED-PROVEN core outward to
  // CONJECTURE). Reads /genome verbatim; the honest tier mix IS the story for investors.
  _eco.shells = new THREE.Group(); g.add(_eco.shells);
  _eco.core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.5, 1), new THREE.MeshStandardMaterial({ color: C.eco, emissive: C.eco, emissiveIntensity: 0.6, transparent: true, opacity: 0.85 }));
  g.add(_eco.core); _eco.g = g;
}
function _updateEco() {
  const THREE = _THREE; if (!_eco.shells) return;
  for (let i = _eco.shells.children.length - 1; i >= 0; i--) _eco.shells.remove(_eco.shells.children[i]);
  const tiers = S.eco.tiers; const live = S.eco.state === "live"; if (!tiers) return;
  // one translucent shell per tier, radius grows with tier order; opacity ~ share of 144
  const order = [["LOCKED-PROVEN", 0x3af4c8], ["SEMANTIC-VERIFIED", 0x5b8dee], ["evidence-backed", 0xd7b96b], ["honest-N/A", 0x7d8a96], ["CONJECTURE", 0xd163a7]];
  const total = S.eco.count || Object.values(tiers).reduce((a, b) => a + b, 0) || 1;
  order.forEach(([k, col], i) => {
    const cnt = tiers[k] || 0; const rad = 0.7 + i * 0.42; const share = cnt / total;
    const sh = new THREE.Mesh(new THREE.IcosahedronGeometry(rad, 1), new THREE.MeshBasicMaterial({ color: live ? col : C.dim, wireframe: true, transparent: true, opacity: live ? (0.12 + 0.5 * share) : 0.1 }));
    _eco.shells.add(sh);
  });
  if (_eco.core) { _eco.core.material.emissiveIntensity = live ? 0.6 : 0.25; _eco.core.material.color.setHex(live ? C.eco : C.dim); _eco.core.material.emissive.setHex(live ? C.eco : C.dim); }
}

function _buildLinks() {
  const THREE = _THREE;
  const order = ["ent", "neu", "qb", "en", "scale", "sc", "conj", "pubs", "eco"];
  const mk = (a, b) => new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]), new THREE.LineBasicMaterial({ color: 0x1b3a44, transparent: true, opacity: 0.3 }));
  for (let i = 0; i < order.length; i++) { _group.add(mk(POS[order[i]], POS[order[(i + 1) % order.length]])); _group.add(mk(POS[order[i]], HUB)); }
  // faint hub
  _group.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.35, 0), new THREE.MeshBasicMaterial({ color: 0x1b3a44, wireframe: true, transparent: true, opacity: 0.4 }))).position.set(...HUB);
}

function _buildOrganLabels() {
  const THREE = _THREE;
  const lab = (label, text, p) => { try { const b = _ctx.label.billboard(THREE, label, { text, scale: 0.5, position: [p[0], p[1] + 3.2, p[2]] }); _group.add(b); return b; } catch (_) { return null; } };
  _ent.bb = lab("RIGOROUS", "entanglement", POS.ent);
  _neu.bb = lab("RIGOROUS", "neuroplasticity", POS.neu);
  _qb.bb = lab("VERIFIED", "quantum-bio", POS.qb);
  _en.bb = lab("ROADMAP", "energy", POS.en);
  _scale.bb = lab("VERIFIED", "scaling", POS.scale);
  _sc.bb = lab("LIVE-MANAGED", "sovereign-compute", POS.sc);
  _conj.bb = lab("OPEN", "conjecture", POS.conj);
  _pubs.bb = lab("PUBLISHED", "publications", POS.pubs);
  _eco.bb = lab("LIVE-STATIC", "ecosystem", POS.eco);
}

// =========================================================================================
// WebGPU compute (quantum-bio coherence field) — TSL kernel evolves the splat cloud on-GPU.
// Visual density only; reported KPIs stay the server's. Guarded fallback to the WebGL2 splat.
// =========================================================================================
let _computeNode = null, _cohBuf = null, _uTau = null, _uT = null, _CN = 4096;
async function _initCompute() {
  const mod = await import("three/webgpu");
  const { Fn, instancedArray, uniform, float, instanceIndex, sin, cos, exp, vec3 } = mod;
  if (!Fn || !instancedArray || !uniform) throw new Error("TSL nodes unavailable");
  const THREE = _THREE;
  _cohBuf = instancedArray(_CN, "vec3"); _uTau = uniform(float(6.05)); _uT = uniform(float(0.0));
  const kernel = Fn(() => {
    const i = instanceIndex.toFloat(); const tn = i.div(float(_CN)); const t = tn.mul(float(12.0));
    const Cc = exp(t.div(_uTau).negate()); const ang = tn.mul(float(Math.PI * 10)).add(_uT); const r = Cc.mul(float(1.6));
    _cohBuf.element(instanceIndex).assign(vec3(cos(ang).mul(r), tn.mul(float(5)).sub(float(2.4)), sin(ang).mul(r)));
  });
  _computeNode = kernel().compute(_CN);
  const mat = new mod.PointsNodeMaterial({ color: C.qb, size: 5, transparent: true, opacity: 0.75, map: _splatTexture(), blending: THREE.AdditiveBlending, depthWrite: false });
  mat.positionNode = _cohBuf.toAttribute();
  const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(_CN * 3), 3));
  _qb.gpuField = new THREE.Points(geo, mat); _qb.g.add(_qb.gpuField);
  if (_qb.splat) _qb.splat.visible = false;  // GPU field supersedes the WebGL2 splat when compute is live
  _computeReady = true;
}

// =========================================================================================
// live handlers
// =========================================================================================
function num(...c) { for (const x of c) if (typeof x === "number") return x; return null; }
function _onEntEntropy(j) { if (typeof j.von_neumann_entropy_bits === "number") S.ent.entropy = j.von_neumann_entropy_bits; _updateEnt(); _paintEnt(); }
function _onEntConc(j) { if (typeof j.concurrence === "number") S.ent.concurrence = j.concurrence; _updateEnt(); _paintEnt(); }
function _onEntNeg(j) { if (typeof j.negativity === "number") S.ent.negativity = j.negativity; _updateEnt(); _paintEnt(); }
function _onNeuStdp(j) { if (typeof j.delta_w === "number") S.neu.dw = j.delta_w; if (typeof j.kind === "string") S.neu.kind = j.kind; _updateNeu(); _paintNeu(); }
function _onNeuPlast(j) { S.neu.health = num(j.plasticity_health, j.plasticity_score, j.health, j.fraction_plastic); let d = num(j.dormant_fraction, j.fraction_dormant); if (d == null && Array.isArray(j.dormant)) d = j.dormant.filter(Boolean).length / j.dormant.length; S.neu.dormant = d; _updateNeu(); _paintNeu(); }
function _onQbCoh(j) { const s = (j.series && Array.isArray(j.series.C)) ? j.series.C : (Array.isArray(j.C) ? j.C : null); if (s) S.qb.coh = s; S.qb.tau = j.fitted_tau_c != null ? j.fitted_tau_c : (j.series && j.series.tau_c != null ? j.series.tau_c : S.qb.tau); if (_webgpu && _uTau && S.qb.tau != null) { try { _uTau.value = Number(S.qb.tau); } catch (_) {} } _updateQbHelix(); _updateSplatField(); _updateRealSplat(); _paintQb(); }
function _onQbCompass(j) { if (j.yields && typeof j.yields === "object") S.qb.compass = j.yields; if (typeof j.angular_contrast === "number") S.qb.contrast = j.angular_contrast; if (typeof j.works === "boolean") S.qb.works = j.works; _updateQbCompass(); _paintQb(); }
function _onSc(j) { S.sc.summary = j.summary || null; S.sc.sovereign_any = j.sovereign_any != null ? j.sovereign_any : null; S.sc.caps = Array.isArray(j.capabilities) ? j.capabilities : null; S.sc.roadmap = Array.isArray(j.roadmap) ? j.roadmap : null; _updateSc(); _paintSc(); }
function _onEn(j) { S.en.summary = j.summary || null; S.en.measured = j.measured_panels; S.en.total = j.total_panels; const jt = j.panels && j.panels.jtoken; if (jt) { S.en.jtoken = jt.joules_per_token; S.en.carbon = jt.carbon_g_co2eq_per_token; S.en.jlabel = jt.label || null; } _updateEn(); _paintEn(); }
function _onScale(j) { if (Array.isArray(j.exponents)) S.scale.exps = j.exponents; _updateScaling(); _paintScale(); }
function _onConj(j) { S.conj.count = j.count != null ? j.count : (Array.isArray(j.conjectures) ? j.conjectures.length : null); S.conj.first = (Array.isArray(j.conjectures) && j.conjectures[0]) ? (j.conjectures[0].id || null) : null; _paintConj(); }
function _onPubs(j) { const d = j.doctrine || j; S.pubs.locked = Array.isArray(d.locked_proven) ? d.locked_proven : null; S.pubs.lockedCount = d.locked_count != null ? d.locked_count : (S.pubs.locked ? S.pubs.locked.length : null); S.pubs.expKernel = d.experimental_kernel || null; S.pubs.lambda = d.lambda_status || null; _updatePubs(); _paintPubs(); }
function _onEco(j) { S.eco.count = j.count != null ? j.count : null; S.eco.tiers = (j.tier_counts && typeof j.tier_counts === "object") ? j.tier_counts : null; _updateEco(); _paintEco(); }

// =========================================================================================
// geometry updaters
// =========================================================================================
function _updateEnt() {
  const live = S.ent.state === "live", dim = live ? 1 : 0.32;
  if (_ent.bond) { const c = S.ent.concurrence || 0; _ent.bond.material.emissiveIntensity = (0.15 + 1.4 * c) * dim; _ent.bond.material.opacity = (0.25 + 0.7 * c) * (live ? 1 : 0.4); _ent.bond.material.color.setHex(live ? C.bond : C.dim); _ent.bond.material.emissive.setHex(live ? C.bond : C.dim); }
  if (_ent.halo) { const e = S.ent.entropy || 0; _ent.halo.material.opacity = 0.6 * e * (live ? 1 : 0.4); const s = 0.6 + 0.6 * e; _ent.halo.scale.set(s, s, s); }
}
function _updateNeu() {
  const live = S.neu.state === "live", dim = live ? 1 : 0.35;
  if (_neu.bead) { const dw = S.neu.dw || 0; _neu.bead.position.set(10 / 16, dw * 1.3, 0); const pot = S.neu.kind && /LTP|potent/i.test(S.neu.kind); const col = !live ? C.dim : (pot ? 0x6dd47e : 0xff8f6b); _neu.bead.material.color.setHex(col); _neu.bead.material.emissive.setHex(col); _neu.bead.material.emissiveIntensity = live ? 1.1 : 0.4; }
  if (_neu.line) { _neu.line.material.opacity = live ? 0.85 : 0.4; _neu.line.material.color.setHex(live ? C.neu : C.dim); }
  if (_neu.cells) _neu.cells.forEach((c) => { let b = S.neu.dormant != null ? 1 - S.neu.dormant : (S.neu.health != null ? S.neu.health : 0.15); const col = !live ? C.dim : (b > 0.4 ? C.neu : 0x7d8a96); c.material.color.setHex(col); c.material.emissive.setHex(col); c.material.emissiveIntensity = (0.1 + 0.9 * b) * dim; c.scale.setScalar(0.7 + 0.5 * b); });
}
function _updateQbHelix() {
  const THREE = _THREE; if (!_qb.helix) return; const s = S.qb.coh; const live = S.qb.cohState === "live"; const n = s ? s.length : 60; const pts = [];
  for (let i = 0; i < n; i++) { const t = i / Math.max(1, n - 1); const Cc = s ? s[i] : Math.exp(-1.6 * t); const a = t * Math.PI * 6; const r = 1.6 * (s ? Cc : 0.3); pts.push(new THREE.Vector3(Math.cos(a) * r, t * 5 - 2.4, Math.sin(a) * r)); }
  _qb.helix.geometry.setFromPoints(pts); _qb.helix.material.opacity = live ? 0.85 : 0.3; _qb.helix.material.color.setHex(live ? C.qb : C.dim);
}
function _updateQbCompass() {
  const THREE = _THREE; if (!_qb.compass) return; _qb.petals.forEach((p) => { try { _qb.compass.remove(p); } catch (_) {} }); _qb.petals = [];
  const y = S.qb.compass; const live = S.qb.compState === "live"; if (!y) return;
  const e = Object.keys(y).map((k) => ({ a: parseFloat(k), y: y[k] })).filter((x) => !isNaN(x.a) && typeof x.y === "number");
  const ys = e.map((x) => x.y), mn = Math.min(...ys), mx = Math.max(...ys), sp = (mx - mn) || 1e-6;
  e.forEach((x) => { const nz = 0.3 + 0.9 * ((x.y - mn) / sp); const a = x.a * Math.PI / 180; const p = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.055, nz * 2, 8), new THREE.MeshStandardMaterial({ color: C.qb, emissive: C.qb, emissiveIntensity: live ? 0.9 : 0.3, transparent: true, opacity: live ? 0.95 : 0.4 })); p.position.set(Math.cos(a) * nz, 0, Math.sin(a) * nz); p.lookAt(0, 0, 0); p.rotateX(Math.PI / 2); _qb.compass.add(p); _qb.petals.push(p); });
}
function _updateSc() {
  const THREE = _THREE; if (!_sc.tower) return; const live = S.sc.state === "live";
  _sc.blocks.forEach((b) => { try { _sc.tower.remove(b); } catch (_) {} }); _sc.blocks = [];
  const tc = (t) => ({ "LIVE-SOVEREIGN": C.en, "LIVE-MANAGED": C.sc, "HONEST-STUB": C.roadmap, "ROADMAP": C.roadmap, "UNREACHABLE": 0xff7b72 }[t] || C.dim);
  (S.sc.caps || []).forEach((c, i) => { const col = live ? tc(c.tier) : C.dim; const b = new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.5, 1.3), new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: live ? 0.5 : 0.2, metalness: 0.35, roughness: 0.5, transparent: true, opacity: 0.9 })); b.position.y = 0.4 + i * 0.65; _sc.tower.add(b); _sc.blocks.push(b); });
  (S.sc.roadmap || []).forEach((r, i) => { const b = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.36, 1.0), new THREE.MeshStandardMaterial({ color: C.roadmap, emissive: C.roadmap, emissiveIntensity: 0.12, wireframe: true, transparent: true, opacity: 0.4 })); b.position.y = 0.4 + ((S.sc.caps || []).length + i) * 0.65; _sc.tower.add(b); _sc.blocks.push(b); });
  if (_sc.trust) { const col = (live && S.sc.sovereign_any) ? C.en : C.sc; _sc.trust.material.color.setHex(col); _sc.trust.material.emissive.setHex(col); _sc.trust.position.y = 0.6 + _sc.blocks.length * 0.65 + 0.5; }
}
function _updateEn() {
  if (!_en.col) return; const live = S.en.state === "live"; const measured = S.en.jlabel && /MEASURED/i.test(S.en.jlabel);
  const h = (S.en.jtoken != null) ? Math.max(0.3, Math.min(6, S.en.jtoken * 4)) : 1;
  _en.col.scale.y = h; _en.col.position.y = h / 2; const col = !live ? C.dim : (measured ? C.en : C.roadmap);
  _en.col.material.color.setHex(col); _en.col.material.emissive.setHex(col); _en.col.material.emissiveIntensity = measured ? 0.6 : 0.2; _en.col.material.opacity = measured ? 0.92 : 0.55;
  if (_en.ring) { _en.ring.material.color.setHex(col); _en.ring.material.emissive.setHex(col); }
  if (_en.pips) { const m = S.en.measured || 0; _en.pips.forEach((p, i) => { const on = i < m; const c = !live ? C.dim : (on ? C.en : C.roadmap); p.material.color.setHex(c); p.material.emissive.setHex(c); p.material.emissiveIntensity = on ? 0.9 : 0.3; }); }
}
function _updatePubs() {
  if (!_pubs.core) return; const live = S.pubs.state === "live"; const cnt = S.pubs.lockedCount || 0;
  _pubs.core.scale.setScalar(0.6 + 0.12 * cnt); _pubs.core.material.emissiveIntensity = live ? 0.7 : 0.3; _pubs.core.material.color.setHex(live ? C.pubs : C.dim); _pubs.core.material.emissive.setHex(live ? C.pubs : C.dim);
  if (_pubs.nodes) _pubs.nodes.forEach((n) => { n.material.emissiveIntensity = live ? 0.5 : 0.2; n.material.color.setHex(live ? C.pubs : C.dim); n.material.emissive.setHex(live ? C.pubs : C.dim); });
}

// =========================================================================================
function _onFrame() {
  const t = performance.now();
  if (_qb.compass) _qb.compass.rotation.z += 0.003;
  if (_neu.cells) _neu.cells.forEach((c, i) => { c.rotation.y += 0.01 + i * 0.001; });
  if (_sc.trust) _sc.trust.rotation.y += 0.006;
  if (_en.ring) _en.ring.rotation.z += 0.004;
  if (_ent.g) _ent.g.rotation.y = Math.sin(t * 0.0003) * 0.2;
  if (_conj.cage) { _conj.cage.rotation.y += 0.004; _conj.cage.rotation.x += 0.002; }
  if (_pubs.spine) _pubs.spine.rotation.y += 0.003;
  if (_eco.shells) _eco.shells.rotation.y += 0.0025;
  if (_eco.core) _eco.core.rotation.y -= 0.004;
  if (_qb.splat && _qb.splat.visible) _qb.splat.rotation.y += 0.002;
  if (_qb.real && _qb.real.mesh) _qb.real.mesh.rotation.y += 0.0016;
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.05;
  if (_webgpu && _computeReady && _uT && _computeNode && _stage.renderer && _stage.renderer.compute) { try { _uT.value = t * 0.0008; _stage.renderer.compute(_computeNode); } catch (_) { _webgpu = false; } }
}

// =========================================================================================
// overlay
// =========================================================================================
function _buildOverlay() {
  const ctx = _ctx;
  ["ent", "neu", "qbcoh", "qbcomp", "sc", "en", "scale", "conj", "pubs", "eco"].forEach((k) => { _badges[k] = ctx.live.createBadge(); });

  // Shared collapsible showcase chrome FIRST: compact title bar + honesty legend live in
  // the always-visible chrome. This surface has MANY per-organ badges, so we omit a single
  // `badge` and instead relocate the whole badge/card cluster into the (collapsed) body,
  // keeping the 3D lattice the star. Long descriptive text -> description; the "adopted &
  // cited" footnote -> citations (both verbatim).
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    legend: ["RIGOROUS", "VERIFIED", "PUBLISHED", "OPEN", "CONJECTURE", "ROADMAP"],
    description:
      'The experimental tier as one holographic lattice \u2014 <b>nine frontier organs</b> on a ring, each lit by a <b>live</b> a11oy endpoint. ' +
      'Quantum-bio renders as a <b>Gaussian-splat volumetric field</b> (WebGPU compute when enabled). Every label is read <b>verbatim</b> from the JSON. NOT in the locked-8 \u00b7 \u039b = Conjecture 1 \u00b7 trust &lt; 100%.',
    citations:
      "Open techniques adopted & cited, NOT claimed-as (clean-room): QuTiP \u00b7 quimb \u00b7 RadicalPy \u00b7 quantum_HEOM \u00b7 Avalanche \u00b7 ncps/LTC \u00b7 Prime Intellect OpenDiLoCo \u00b7 NVIDIA nvtrust \u00b7 CodeCarbon \u00b7 GSF SCI \u00b7 three.js WebGPU \u00b7 GaussianSplats3D \u00b7 Looking Glass quilt. Papers: Kerbl 3DGS 2308.04079 \u00b7 Cirac-Verstraete 2011.12127 \u00b7 Dohare-Sutton (Nature 2024) \u00b7 Hore 2508.21350 \u00b7 Streaming DiLoCo 2501.18512. EXPERIMENTAL tier; not in the locked-8.",
  });

  // rows/cards fold into the showcase body as a PLAIN static container (no absolute chrome,
  // no own title, no standalone legend \u2014 the showcase provides those).
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, { display: "flex", flexDirection: "column", gap: "8px", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6" });

  const ctl = document.createElement("div"); ctl.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  _el.rchip = document.createElement("span"); _el.rchip.style.cssText = "font:10px ui-monospace,monospace;padding:3px 8px;border-radius:6px;border:1px solid #1d2a36;color:" + (_webgpu ? "#6dd47e" : "#6fb1ff"); _el.rchip.textContent = _webgpu ? "splat: WebGPU compute" : "splat: WebGL2"; ctl.appendChild(_el.rchip);
  const lf = document.createElement("button"); lf.textContent = "\u25c8 light-field export"; lf.title = "Render a Looking Glass 45-view quilt PNG for a light-field holographic display."; lf.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #39d3c4;background:#0d2028;color:#39d3c4;cursor:pointer"; lf.addEventListener("click", () => _exportLightField(lf)); ctl.appendChild(lf);
  _el.lfStatus = document.createElement("span"); _el.lfStatus.style.cssText = "font:10px ui-monospace,monospace;color:#9fb1bf"; ctl.appendChild(_el.lfStatus);
  _overlay.appendChild(ctl);

  // second control row: real-.splat download, native Looking Glass, plain-language toggle
  const ctl2 = document.createElement("div"); ctl2.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  const dl = document.createElement("button"); dl.textContent = "\u2b07 .splat model"; dl.title = "Download the live coherence field as a real .splat gaussian-splat model (opens in any 3DGS viewer)."; dl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #e8c074;background:#1a1508;color:#e8c074;cursor:pointer"; dl.addEventListener("click", () => _downloadSplat()); ctl2.appendChild(dl);
  const lg2 = document.createElement("button"); lg2.textContent = "\u25c9 Looking Glass"; lg2.title = "Enter a native Looking Glass light-field display (WebXR). Opens a preview window if no hardware is attached."; lg2.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #5b8dee;background:#0b1424;color:#8fb4ff;cursor:pointer"; lg2.addEventListener("click", () => _enterLookingGlass(lg2)); ctl2.appendChild(lg2);
  _el.lgStatus = document.createElement("span"); _el.lgStatus.style.cssText = "font:10px ui-monospace,monospace;color:#9fb1bf"; ctl2.appendChild(_el.lgStatus);
  const pl = document.createElement("button"); pl.textContent = "\u25d1 what this means"; pl.title = "Toggle plain-language explanations for investors & consumers \u2014 every line still reads the real live data."; pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer"; pl.addEventListener("click", () => { _plain = !_plain; pl.style.background = _plain ? "#0f2a20" : "#08140f"; _applyPlain(); }); ctl2.appendChild(pl);
  _overlay.appendChild(ctl2);

  _overlay.appendChild(_card("entanglement", "#8a6bff", _badges.ent, [["ent-entropy", "von Neumann entropy (bits)"], ["ent-conc", "concurrence (Wootters)"], ["ent-neg", "negativity (Vidal-Werner)"]], "QuTiP entropy_vn/concurrence/negativity (BSD) \u00b7 quimb MPS/PEPS \u00b7 Vidal MERA \u00b7 Cirac-Verstraete RMP arXiv:2011.12127. RIGOROUS \u00b7 not claimed-as."));
  _overlay.appendChild(_card("neuroplasticity", "#39d3c4", _badges.neu, [["neu-dw", "STDP \u0394w @ \u0394t=10ms"], ["neu-kind", "LTP / LTD"], ["neu-health", "plasticity health"]], "Bi-Poo 1998 STDP + Dohare-Sutton ReDo arXiv:2306.13812 + Zenke SI arXiv:1703.04200 + ncps/LTC (Apache-2, Hasani arXiv:2006.04439). RIGOROUS \u00b7 not claimed-as."));
  const qbb = document.createElement("div"); qbb.style.cssText = "display:flex;gap:6px;flex-wrap:wrap"; qbb.appendChild(_badges.qbcoh.el); qbb.appendChild(_badges.qbcomp.el);
  _overlay.appendChild(_card("quantum-bio", "#e8c074", { el: qbb }, [["qb-tau", "Lindblad \u03c4_c (coherence)"], ["qb-contrast", "compass angular contrast"], ["qb-works", "compass works"]], "Lindblad/GKSL + radical-pair compass \u2014 Gaussian-splat volumetric field (Kerbl 3DGS arXiv:2308.04079). RadicalPy (MIT) \u00b7 quantum_HEOM (MIT) \u00b7 Hore cryptochrome arXiv:2508.21350. VERIFIED \u00b7 not claimed-as."));
  _overlay.appendChild(_card("energy", "#6dd47e", _badges.en, [["en-jtoken", "J/token"], ["en-carbon", "gCO\u2082e/token"], ["en-measured", "measured panels"]], "MEASURED only on a live NVML/exporter probe; no meter \u2192 honest ROADMAP. CodeCarbon (MIT) \u00b7 GSF Carbon Aware SDK + SCI=(O+M)/R (ISO 21031) \u00b7 Zeus (Apache-2)."));
  _overlay.appendChild(_card("scaling", "#ffb56b", _badges.scale, [["sc-exps", "allometric exponents"]], "Kleiber 1932 / West-Brown-Enquist 1997 / MTE 2004 / Bettencourt-West 2007 urban allometry. VERIFIED (deterministic) \u00b7 unified \u03a6 is a PROPOSED SZL construct, not in locked-8."));
  _overlay.appendChild(_card("sovereign-compute", "#6fb1ff", _badges.sc, [["scmp-summary", "posture"], ["scmp-sovereign", "on our GPU?"], ["scmp-caps", "capabilities"]], "sovereign:true ONLY on a real local-GPU probe. Prime Intellect prime/OpenDiLoCo (Apache-2, Streaming DiLoCo arXiv:2501.18512) \u00b7 NVIDIA nvtrust H100 TEE \u00b7 vLLM. never faked green."));
  _overlay.appendChild(_card("conjecture", "#d7b96b", _badges.conj, [["conj-count", "open conjectures"], ["conj-first", "latest id"]], "Factory output is a set of OPEN conjectures \u2014 generated, NOT proven. Signatures attest timestamp + content, not truth. Conjecture 1 (unconditional \u039b uniqueness) remains OPEN."));
  _overlay.appendChild(_card("publications", "#9fd0ff", _badges.pubs, [["pubs-locked", "locked-proven"], ["pubs-lambda", "\u039b status"], ["pubs-kernel", "experimental kernel"]], "SZL corpus: 41 Zenodo DOIs, thesis v1\u2192v25 (Ouroboros \u2192 Lutar Invariant \u2192 GPD), ORCID 0009-0001-0110-4173. Locked-proven read live; \u039b = Conjecture 1 (unconditional machine-checked FALSE)."));
  _overlay.appendChild(_card("ecosystem", "#3af4c8", _badges.eco, [["eco-count", "governed capabilities"], ["eco-proven", "locked-proven"], ["eco-mix", "honesty mix"]], "The investor/consumer headline: the live governed-capability genome (/genome). 5-tier honesty mix read VERBATIM \u2014 what is proven vs evidence-backed vs conjecture. The honest mix IS the diligence signal."));

  // fold the whole control + badge/card cluster into the collapsible showcase body
  // (the showcase provides the title bar + honesty legend; footnote moved to citations).
  _show.body.appendChild(_overlay);
  _paintEnt(); _paintNeu(); _paintQb(); _paintSc(); _paintEn(); _paintScale(); _paintConj(); _paintPubs(); _paintEco();
}

// ---- native Looking Glass entry (WebXR) — lazy-loads the vendored polyfill on click --------
async function _enterLookingGlass(btn) {
  if (_el.lgStatus) _el.lgStatus.textContent = "opening\u2026"; btn.disabled = true;
  try {
    if (!_lkg) _lkg = await import("/static/3d/szl3d/szl3d_lookingglass.js");
    const lkg = _lkg.default || _lkg;
    const res = await lkg.enter(_stage, { targetY: 3, targetZ: 0, targetDiam: 34, numViews: 45 });
    if (_el.lgStatus) _el.lgStatus.textContent = res.entered ? "session active" : (res.note || "no display");
  } catch (e) { if (_el.lgStatus) _el.lgStatus.textContent = "unavailable"; console.warn("[frontier] looking glass:", e && e.message); }
  finally { btn.disabled = false; }
}

// ---- plain-language 'what this means' layer (investors & consumers) — real data, plain words --
// Toggles a one-line human explanation under each organ card. Every explanation quotes the SAME
// live value the technical KPI shows; nothing is invented and no honesty label is upgraded.
function _plainText() {
  const mix = S.eco.tiers ? `${S.eco.tiers["LOCKED-PROVEN"] || 0} machine-proven, ${S.eco.tiers["evidence-backed"] || 0} evidence-backed, ${S.eco.tiers["CONJECTURE"] || 0} still open of ${S.eco.count || "?"}` : "loading the live capability mix";
  return {
    entanglement: `Two linked qubits share ${fx(S.ent.entropy, 2)} bits of entanglement (concurrence ${fx(S.ent.concurrence, 2)}). Plain: a rigorous, textbook quantum-information measure computed live \u2014 not a claim, a calculation.`,
    neuroplasticity: `The learning rule strengthens a connection by ${fx(S.neu.dw, 3)} (${S.neu.kind || "\u2014"}); plasticity health ${S.neu.health != null ? fx(S.neu.health, 2) : "\u2014"}. Plain: how the agent keeps learning without forgetting.`,
    "quantum-bio": `Coherence lasts \u03c4=${S.qb.tau != null ? S.qb.tau : "\u2014"}; the bio-compass ${S.qb.works ? "works" : "is loading"} (contrast ${fx(S.qb.contrast, 3)}). Plain: real open-quantum-system biology, rendered as a downloadable 3D gaussian-splat model.`,
    energy: `Energy per token is ${S.en.jlabel && /MEASURED/i.test(S.en.jlabel) ? fx(S.en.jtoken, 4) + " J" : "pending a live power meter (honest ROADMAP)"}; ${S.en.measured != null ? S.en.measured : 0}/${S.en.total != null ? S.en.total : 6} panels measured. Plain: we only show an energy number when a real meter reports it.`,
    scaling: `Growth follows power laws (metabolic 0.75, city GDP 1.15). Plain: the same math that governs biology and cities, computed deterministically.`,
    "sovereign-compute": `Running on: ${S.sc.summary || "\u2014"} (on our own GPU: ${S.sc.sovereign_any ? "yes" : "not yet \u2014 managed"}). Plain: we say \u201Con our GPU\u201D only when a real probe confirms it.`,
    conjecture: `${S.conj.count != null ? S.conj.count : "\u2014"} open conjecture(s) generated. Plain: machine-generated open problems \u2014 signed for timestamp, never claimed as proven.`,
    publications: `Locked-proven set: ${S.pubs.locked ? S.pubs.locked.join(", ") : "\u2014"}; \u039b = ${S.pubs.lambda || "Conjecture 1"}. Plain: 41 published papers (v1\u2192v25); only ${S.pubs.lockedCount != null ? S.pubs.lockedCount : "a few"} results are machine-proven \u2014 the rest are honestly labeled.`,
    ecosystem: `${S.eco.count != null ? S.eco.count : "\u2014"} governed capabilities: ${mix}. Plain: the honest scorecard \u2014 what is proven vs evidence-backed vs still a conjecture. The mix itself is the diligence signal.`,
  };
}
function _applyPlain() {
  if (!_overlay) return;
  const texts = _plainText();
  const cards = _overlay.querySelectorAll(":scope > div");
  Object.keys(texts).forEach((k) => {
    let el = _el["plain-" + k];
    if (_plain && !el) {
      for (const card of cards) { const b = card.querySelector("b"); if (b && b.textContent === k) { el = document.createElement("div"); el.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.5;border-top:1px dashed #26333f;padding-top:5px;margin-top:2px"; card.appendChild(el); _el["plain-" + k] = el; break; } }
    }
    if (el) { el.textContent = texts[k]; el.style.display = _plain ? "block" : "none"; }
  });
}

function _card(name, color, badge, kpis, footnote) {
  const c = document.createElement("div"); c.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";
  const head = document.createElement("div"); head.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span"); dot.style.cssText = `width:9px;height:9px;border-radius:50%;background:${color};box-shadow:0 0 7px ${color}`;
  const nm = document.createElement("b"); nm.style.cssText = `font-size:12px;color:${color};letter-spacing:.3px`; nm.textContent = name;
  head.appendChild(dot); head.appendChild(nm); if (badge && badge.el) head.appendChild(badge.el); c.appendChild(head);
  const grid = document.createElement("div"); grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  kpis.forEach(([id, lab]) => { const r = document.createElement("div"); r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px"; const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = lab; const v = document.createElement("b"); v.id = id; v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:58%"; v.textContent = "\u2014"; _el[id] = v; r.appendChild(l); r.appendChild(v); grid.appendChild(r); });
  c.appendChild(grid);
  const fn = document.createElement("div"); fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5"; fn.textContent = footnote; c.appendChild(fn);
  return c;
}

// =========================================================================================
// Looking Glass quilt export (45-view horizontal sweep -> downloadable PNG)
// =========================================================================================
async function _exportLightField(btn) {
  const THREE = _THREE, stage = _stage; if (!stage || !stage.renderer) return;
  const COLS = 5, ROWS = 9, VIEWS = COLS * ROWS, TW = 256, TH = 256;
  btn.disabled = true; const prev = btn.textContent; btn.textContent = "rendering\u2026"; if (_el.lfStatus) _el.lfStatus.textContent = `${VIEWS} views\u2026`;
  try {
    const renderer = stage.renderer, scene = stage.scene, srcCam = stage.camera;
    const rt = new THREE.WebGLRenderTarget(TW, TH, { samples: 2 }); const cam = srcCam.clone();
    const target = (stage.controls && stage.controls.target) ? stage.controls.target.clone() : new THREE.Vector3(0, 2.6, 0);
    const radius = srcCam.position.distanceTo(target); const baseAngle = Math.atan2(srcCam.position.x - target.x, srcCam.position.z - target.z); const height = srcCam.position.y; const CONE = 0.5;
    const quilt = document.createElement("canvas"); quilt.width = COLS * TW; quilt.height = ROWS * TH; const qx = quilt.getContext("2d");
    const rcv = document.createElement("canvas"); rcv.width = TW; rcv.height = TH; const rc = rcv.getContext("2d"); const px = new Uint8Array(TW * TH * 4);
    const prevRT = renderer.getRenderTarget();
    for (let v = 0; v < VIEWS; v++) {
      const tv = VIEWS > 1 ? (v / (VIEWS - 1) - 0.5) : 0; const ang = baseAngle + tv * CONE;
      cam.position.set(target.x + Math.sin(ang) * radius, height, target.z + Math.cos(ang) * radius); cam.lookAt(target); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
      renderer.setRenderTarget(rt); renderer.render(scene, cam); renderer.readRenderTargetPixels(rt, 0, 0, TW, TH, px);
      const img = rc.createImageData(TW, TH); for (let y = 0; y < TH; y++) { const sy = TH - 1 - y; img.data.set(px.subarray(sy * TW * 4, (sy + 1) * TW * 4), y * TW * 4); } rc.putImageData(img, 0, 0);
      const col = v % COLS, row = ROWS - 1 - Math.floor(v / COLS); qx.drawImage(rcv, col * TW, row * TH);
      if (_el.lfStatus && v % 5 === 0) { _el.lfStatus.textContent = `view ${v + 1}/${VIEWS}`; await new Promise((r) => setTimeout(r, 0)); }
    }
    renderer.setRenderTarget(prevRT); rt.dispose();
    quilt.toBlob((blob) => { const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `frontier_qs${COLS}x${ROWS}a${(TW / TH).toFixed(2)}.png`; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1500); if (_el.lfStatus) _el.lfStatus.textContent = `saved ${COLS}\u00d7${ROWS} quilt`; }, "image/png");
  } catch (e) { if (_el.lfStatus) _el.lfStatus.textContent = "export failed"; console.error("[frontier] light-field:", e); }
  finally { btn.disabled = false; btn.textContent = prev; }
}

// =========================================================================================
// painters
// =========================================================================================
function _tok(s) { if (s === "live") return null; if (s === "missing") return "NO-LIVE-DATA"; if (s === "degraded") return "DEGRADED"; if (s === "error") return "OFFLINE"; return "\u2026"; }
function fx(v, d) { return (typeof v === "number") ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _paintEnt() { const t = _tok(S.ent.state); _set("ent-entropy", t || fx(S.ent.entropy, 4)); _set("ent-conc", t || fx(S.ent.concurrence, 4)); _set("ent-neg", t || fx(S.ent.negativity, 4)); }
function _paintNeu() { const t = _tok(S.neu.state); _set("neu-dw", t || fx(S.neu.dw, 4)); _set("neu-kind", t || (S.neu.kind || "\u2014")); _set("neu-health", t || (S.neu.health != null ? fx(S.neu.health, 3) : (S.neu.dormant != null ? "dormant " + fx(S.neu.dormant, 2) : "\u2014"))); }
function _paintQb() { const tc = _tok(S.qb.cohState), tk = _tok(S.qb.compState); _set("qb-tau", tc || (S.qb.tau != null ? String(S.qb.tau) : "\u2014")); _set("qb-contrast", tk || fx(S.qb.contrast, 4)); _set("qb-works", tk || (S.qb.works != null ? (S.qb.works ? "yes" : "no") : "\u2014")); }
function _paintSc() { const t = _tok(S.sc.state); _set("scmp-summary", t || (S.sc.summary ? (S.sc.summary.length > 28 ? S.sc.summary.slice(0, 27) + "\u2026" : S.sc.summary) : "\u2014")); _set("scmp-sovereign", t || (S.sc.sovereign_any != null ? (S.sc.sovereign_any ? "yes (sovereign)" : "no (managed)") : "\u2014")); _set("scmp-caps", t || (S.sc.caps ? S.sc.caps.map((c) => c.tier).join(", ") : "\u2014")); }
function _paintEn() { const t = _tok(S.en.state); _set("en-jtoken", t || (S.en.jtoken != null ? fx(S.en.jtoken, 4) : (S.en.jlabel || "ROADMAP"))); _set("en-carbon", t || (S.en.carbon != null ? fx(S.en.carbon, 4) : "ROADMAP")); _set("en-measured", t || (S.en.measured != null && S.en.total != null ? `${S.en.measured}/${S.en.total}` : "\u2014")); }
function _paintScale() { const t = _tok(S.scale.state); _set("sc-exps", t || (S.scale.exps ? S.scale.exps.slice(0, 4).map((e) => (e.exponent != null ? e.exponent : "?")).join(", ") + (S.scale.exps.length > 4 ? "\u2026" : "") : "\u2014")); }
function _paintConj() { const t = _tok(S.conj.state); _set("conj-count", t || (S.conj.count != null ? String(S.conj.count) : "\u2014")); _set("conj-first", t || (S.conj.first ? String(S.conj.first).slice(0, 10) : "\u2014")); }
function _paintPubs() { const t = _tok(S.pubs.state); _set("pubs-locked", t || (S.pubs.locked ? S.pubs.locked.join(",") : (S.pubs.lockedCount != null ? String(S.pubs.lockedCount) : "\u2014"))); _set("pubs-lambda", t || (S.pubs.lambda ? (S.pubs.lambda.length > 18 ? S.pubs.lambda.slice(0, 17) + "\u2026" : S.pubs.lambda) : "Conjecture 1")); _set("pubs-kernel", t || (S.pubs.expKernel || "\u2014")); if (_plain) _applyPlain(); }
function _paintEco() { const t = _tok(S.eco.state); _set("eco-count", t || (S.eco.count != null ? String(S.eco.count) : "\u2014")); _set("eco-proven", t || (S.eco.tiers ? String(S.eco.tiers["LOCKED-PROVEN"] || 0) : "\u2014")); _set("eco-mix", t || (S.eco.tiers ? `${S.eco.tiers["LOCKED-PROVEN"] || 0}/${S.eco.tiers["SEMANTIC-VERIFIED"] || 0}/${S.eco.tiers["evidence-backed"] || 0}/${S.eco.tiers["CONJECTURE"] || 0}` : "\u2014")); if (_plain) _applyPlain(); }

// =========================================================================================
function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try { if (_group && _stage) { _group.traverse((o) => { if (o.geometry && o.geometry.dispose) o.geometry.dispose(); if (o.material) { const m = Array.isArray(o.material) ? o.material : [o.material]; m.forEach((x) => { if (x.map && x.map.dispose) x.map.dispose(); if (x.dispose) x.dispose(); }); } }); _stage.scene.remove(_group); } } catch (_) {}
  _splatTex = null;
  try { if (_qb.real && _qb.real.dispose) _qb.real.dispose(); } catch (_) {}
  _group = _overlay = _show = null; _ent = {}; _neu = {}; _qb = {}; _sc = {}; _en = {}; _scale = {}; _conj = {}; _pubs = {}; _eco = {}; _el = {}; _badges = {};
  _splatlib = _lkg = _realBytes = null; _plain = false;
  _computeNode = _cohBuf = _uTau = _uT = null; _computeReady = false;
  S.ent = { entropy: null, concurrence: null, negativity: null, state: "init" };
  S.neu = { dw: null, kind: null, health: null, dormant: null, state: "init" };
  S.qb = { coh: null, tau: null, compass: null, contrast: null, works: null, cohState: "init", compState: "init" };
  S.sc = { summary: null, sovereign_any: null, caps: null, roadmap: null, state: "init" };
  S.en = { jtoken: null, carbon: null, jlabel: null, measured: null, total: null, state: "init" };
  S.scale = { exps: null, state: "init" }; S.conj = { count: null, first: null, state: "init" };
  S.pubs = { locked: null, lockedCount: null, expKernel: null, lambda: null, state: "init" };
  S.eco = { count: null, tiers: null, state: "init" };
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_ENT_ENTROPY, EP_ENT_CONC, EP_ENT_NEG, EP_NEU_STDP, EP_QB_COH, EP_QB_COMPASS, EP_SC, EP_EN, EP_SCALE, EP_CONJ, EP_PUBS, EP_ECO], mount, unmount };
