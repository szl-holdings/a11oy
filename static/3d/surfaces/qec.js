// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/qec.js — TOPOLOGICAL QUANTUM ERROR-CORRECTION / ROTATED SURFACE-CODE
// organ for the holographic frontier ring.
//
// Renders a 3D d×d rotated-surface-code lattice (data qubits + syndrome/ancilla
// qubits) driven by a live snapshot from /api/killinchu/v1/qec/surface-code. Data
// qubits sit on lattice sites; ancilla (syndrome) qubits sit on plaquette centers and
// light up in proportion to the MODELED syndrome weight, with a subset flashed as an
// "error chain" for visual storytelling. A HUD tracks logical error rate p_L dropping
// as code distance d grows — the below-threshold exponential-suppression result
// (the "Willow" figure of merit, Λ = p_L(d)/p_L(d+2)). Honesty label "MODELED" is
// read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors interpretability.js / neuromorphic.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   code_distance          — d (odd integer >= 3)
//   physical_error_rate    — p, the simulated per-qubit depolarizing rate
//   num_data_qubits        — d*d
//   num_ancilla            — d*d - 1
//   syndrome_weight        — MODELED mean fired-stabilizer count this cycle
//   logical_error_rate     — p_L(d,p), MODELED
//   suppression_factor     — Λ = p_L(d) / p_L(d+2)
//   below_threshold        — bool
//   threshold_note         — plain-language threshold status
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Google Quantum AI — "Quantum error correction below the surface code threshold"
//     (Willow), Nature 638:920-926 (2025). arXiv:2408.13687
//     https://arxiv.org/abs/2408.13687
//   Fowler, Mariantoni, Martinis & Cleland (2012) "Surface codes: Towards practical
//     large-scale quantum computation". arXiv:1208.0928
//     https://arxiv.org/abs/1208.0928
//   Kitaev (1997/2003) "Fault-tolerant quantum computation by anyons" (toric code).
//     Annals of Physics 303:2-30. arXiv:quant-ph/9707021
//     https://arxiv.org/abs/quant-ph/9707021
//
// HONESTY LABELS: MODELED (simulation of the METHOD; no proprietary QPU data, no
//   measured hardware syndromes). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (data qubits), violet-blue 0x8a6bff (fired
//   syndrome / error-chain flash — data-viz only), proof-teal 0x3af4c8 (suppression
//   HUD accent), greys for dim/idle. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// This organ is a physics simulation ONLY — distinct from surfaces/entanglement.js
// (entanglement measures) and adds NOTHING to SZL's own locked-8 / Λ-Conjecture-1.

const ID    = "qec";
const TITLE = "Topological QEC · Rotated Surface Code (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the QEC organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/qec/surface-code?seed=42&distance=5&p=0.003";

// data-viz hues — purple BANNED
const C_DATA   = 0x5b8dee;  // lattice-blue (data qubit)
const C_FLASH  = 0x8a6bff;  // violet-blue (fired syndrome / error-chain flash — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / idle qubit)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (suppression HUD ring)
const C_GRID   = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _dataQubits = [];   // Array<THREE.Mesh> — one per lattice data qubit
let _ancillas = [];     // Array<THREE.Mesh> — one per plaquette syndrome/ancilla qubit
let _links = null;      // THREE.LineSegments — lattice edges (data<->ancilla)
let _ring = null;       // THREE.Mesh — suppression-factor HUD ring above the lattice
const _lastD = { d: 0 }; // last-built lattice distance, so we only rebuild on change

// per-ancilla flash timers (sized to the max lattice we'll ever build, 25x25)
const _MAX_ANCILLA = 25 * 25;
const _flash = new Float32Array(_MAX_ANCILLA);

// live state
const S = {
  label:        null,
  d:            null,   // code_distance
  p:            null,   // physical_error_rate
  nData:        null,   // num_data_qubits
  nAncilla:     null,   // num_ancilla
  synWeight:    null,   // syndrome_weight
  pL:           null,   // logical_error_rate
  suppression:  null,   // suppression_factor
  belowThresh:  null,
  thresholdNote:null,
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLattice(5);  // default distance-5 lattice; rebuilt on live data if distance differs
  _buildSuppressionRing();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSurfaceCode, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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

// Build (or rebuild) a d×d rotated-surface-code lattice: data qubits on integer
// sites, ancilla (syndrome) qubits on plaquette centers (half-integer offsets).
function _buildLattice(d) {
  const THREE = _THREE;
  d = Math.max(3, d | 1); // force odd
  if (_lastD.d === d && _dataQubits.length) return; // already built at this distance
  _lastD.d = d;

  // dispose old geometry before rebuilding
  _disposeLattice();

  const spacing = Math.min(2.6, 16 / d);
  const half = ((d - 1) * spacing) / 2;
  const y = 1.2;

  const dataGeo = new THREE.SphereGeometry(spacing * 0.16, 12, 9);
  const dataMat0 = new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.25, roughness: 0.55 });

  _dataQubits = [];
  for (let i = 0; i < d; i++) {
    for (let j = 0; j < d; j++) {
      const x = i * spacing - half;
      const z = j * spacing - half;
      const mesh = new THREE.Mesh(dataGeo, dataMat0.clone());
      mesh.position.set(x, y, z);
      _group.add(mesh);
      _dataQubits.push(mesh);
    }
  }

  // ancilla (syndrome) qubits on plaquette centers: (d-1) x (d-1) grid of centers
  const ancGeo = new THREE.BoxGeometry(spacing * 0.22, spacing * 0.22, spacing * 0.22);
  const ancMat0 = new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.12, metalness: 0.3, roughness: 0.5 });

  _ancillas = [];
  const linkPts = [];
  for (let i = 0; i < d - 1; i++) {
    for (let j = 0; j < d - 1; j++) {
      const x = (i + 0.5) * spacing - half;
      const z = (j + 0.5) * spacing - half;
      const mesh = new THREE.Mesh(ancGeo, ancMat0.clone());
      mesh.position.set(x, y, z);
      _group.add(mesh);
      _ancillas.push(mesh);
      // link ancilla to its 4 neighbouring data qubits (weight-4 stabilizer, bulk)
      const neighbours = [
        [i, j], [i + 1, j], [i, j + 1], [i + 1, j + 1],
      ];
      neighbours.forEach(([ni, nj]) => {
        const nx = ni * spacing - half;
        const nz = nj * spacing - half;
        linkPts.push(new THREE.Vector3(x, y, z), new THREE.Vector3(nx, y, nz));
      });
    }
  }
  const lg = new THREE.BufferGeometry().setFromPoints(linkPts);
  _links = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.22 }));
  _group.add(_links);
}

function _disposeLattice() {
  [..._dataQubits, ..._ancillas].forEach((m) => {
    _group.remove(m);
    if (m.geometry && m.geometry.dispose && !_dataQubits.includes(m)) {} // shared geo skip
    if (m.material && m.material.dispose) m.material.dispose();
  });
  if (_dataQubits[0] && _dataQubits[0].geometry) _dataQubits[0].geometry.dispose();
  if (_ancillas[0] && _ancillas[0].geometry) _ancillas[0].geometry.dispose();
  if (_links) {
    _group.remove(_links);
    if (_links.geometry) _links.geometry.dispose();
    if (_links.material) _links.material.dispose();
    _links = null;
  }
  _dataQubits = [];
  _ancillas = [];
}

function _buildSuppressionRing() {
  const THREE = _THREE;
  _ring = new THREE.Mesh(
    new THREE.TorusGeometry(2.0, 0.035, 10, 64),
    new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.5 }),
  );
  _ring.position.set(0, 5.4, 0);
  _ring.rotation.x = Math.PI / 2;
  _group.add(_ring);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSurfaceCode(j) {
  // read honesty label VERBATIM — never upgrade
  S.label       = (j.label || "MODELED").toUpperCase();
  S.d           = typeof j.code_distance        === "number" ? j.code_distance        : null;
  S.p           = typeof j.physical_error_rate  === "number" ? j.physical_error_rate  : null;
  S.nData       = typeof j.num_data_qubits      === "number" ? j.num_data_qubits      : null;
  S.nAncilla    = typeof j.num_ancilla          === "number" ? j.num_ancilla          : null;
  S.synWeight   = typeof j.syndrome_weight      === "number" ? j.syndrome_weight      : null;
  S.pL          = typeof j.logical_error_rate   === "number" ? j.logical_error_rate   : null;
  S.suppression = typeof j.suppression_factor   === "number" ? j.suppression_factor   : null;
  S.belowThresh = typeof j.below_threshold      === "boolean" ? j.below_threshold     : null;
  S.thresholdNote = typeof j.threshold_note     === "string" ? j.threshold_note       : null;

  if (S.d) _buildLattice(S.d);
  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives ancilla colour/brightness from syndrome weight
// =============================================================================
function _updateLattice() {
  const live = S.state === "live";
  const total = _ancillas.length || 1;
  const fired = live && S.synWeight != null ? Math.round(Math.min(S.synWeight, total)) : 0;

  _ancillas.forEach((mesh, i) => {
    if (live && i < fired) {
      const norm = 1 - (i / Math.max(fired, 1));
      const col = i % 3 === 0 ? C_FLASH : C_DATA;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.25 + 0.75 * norm;
      _flash[i] = Math.min(30 + norm * 60, 90);
    } else {
      mesh.material.color.setHex(C_DIM);
      mesh.material.emissive.setHex(C_DIM);
      mesh.material.emissiveIntensity = 0.12;
    }
  });

  _dataQubits.forEach((mesh) => {
    const col = live ? C_DATA : C_DIM;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = live ? 0.3 : 0.12;
  });

  if (_ring) {
    // ring fullness/brightness scales with suppression_factor (bigger Λ = brighter,
    // representing stronger below-threshold exponential suppression with distance).
    const supp = S.suppression != null ? S.suppression : 1.0;
    const norm = Math.max(0, Math.min(1, (supp - 1) / 4)); // Λ~1..5 -> 0..1
    const rcol = live ? C_ACCENT : C_DIM;
    _ring.material.color.setHex(rcol);
    _ring.material.emissive.setHex(rcol);
    _ring.material.emissiveIntensity = live ? 0.2 + 0.7 * norm : 0.12;
    _ring.material.opacity = live ? 0.55 : 0.2;
    _ring.scale.setScalar(live ? (0.7 + 0.5 * norm) : 0.8);
  }

  if (_links) {
    _links.material.opacity = live ? 0.28 : 0.14;
    _links.material.color.setHex(live && S.belowThresh === false ? C_FLASH : C_GRID);
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.15;
  if (_ring) { _ring.rotation.z += 0.004; }

  const live = S.state === "live";
  _ancillas.forEach((mesh, i) => {
    if (_flash[i] > 0) {
      _flash[i] -= 1;
      const f = _flash[i] / 90;
      const col = live ? C_FLASH : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.15 + 0.85 * f);
    }
  });
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
    'A <b>rotated surface code</b> encodes one logical qubit into a d\u00d7d grid of ' +
    '<b>data qubits</b>, protected by <b>syndrome (stabilizer) measurements</b> on ' +
    'the ancilla qubits between them. Below a critical physical error rate, growing ' +
    'the code distance <b>suppresses the logical error rate exponentially</b> \u2014 ' +
    'the frontier result demonstrated by Google Quantum AI\u2019s Willow chip. Honesty ' +
    'label <b>MODELED</b> (a simulation of surface-code scaling, not a real QPU). 0 runtime CDN.';
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
  nm.textContent = "qec · surface-code";
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

  grid.appendChild(kpiRow("qec-d",      "code distance d"));
  grid.appendChild(kpiRow("qec-p",      "physical error rate p"));
  grid.appendChild(kpiRow("qec-nd",     "data qubits"));
  grid.appendChild(kpiRow("qec-na",     "ancilla (syndrome) qubits"));
  grid.appendChild(kpiRow("qec-syn",    "syndrome weight (fired)"));
  grid.appendChild(kpiRow("qec-pl",     "logical error rate p_L \u2014 MODELED"));
  grid.appendChild(kpiRow("qec-supp",   "suppression \u039b = p_L(d)/p_L(d+2)"));
  grid.appendChild(kpiRow("qec-thresh", "regime"));
  grid.appendChild(kpiRow("qec-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Google Quantum AI arXiv:2408.13687 (Willow, Nature 638:920-926) \u00b7 Fowler et al. arXiv:1208.0928 (surface codes) \u00b7 Kitaev arXiv:quant-ph/9707021 (toric code). MODELED \u00b7 not claimed-as.";
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
  pd.id = "qec-plain";
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
  const d    = S.d != null ? String(S.d) : "loading\u2026";
  const pl   = S.pL != null ? S.pL.toExponential(2) : "loading\u2026";
  const supp = S.suppression != null ? S.suppression.toFixed(2) + "\u00d7" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> A quantum bit is fragile \u2014 stray noise flips it. A " +
    "<b>surface code</b> spreads one logical qubit across a grid of <b>" + d + "\u00d7" + d + "</b> " +
    "physical qubits and constantly checks for errors without looking at the data " +
    "directly (via <b>syndrome measurements</b>). Right now the estimated chance of " +
    "an uncorrectable logical error is <b>" + pl + "</b> per cycle. The key result: " +
    "if the hardware is good enough (<b>below threshold</b>), making the grid bigger " +
    "makes errors <b>exponentially rarer</b> \u2014 here each distance step suppresses " +
    "errors by roughly <b>" + supp + "</b>. This is the same phenomenon Google " +
    "Quantum AI demonstrated on real superconducting qubits (Willow, 2024). " +
    "Plain: this is HOW you build a reliable quantum computer out of unreliable " +
    "parts \u2014 but this view is a <b>MODELED</b> simulation of the scaling law, not " +
    "a readout from a real quantum processor.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function fexp(v, d) { return typeof v === "number" ? v.toExponential(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("qec-d",      t || (S.d != null ? String(S.d) : "\u2014"));
  _set("qec-p",      t || fexp(S.p, 3));
  _set("qec-nd",     t || (S.nData != null ? String(S.nData) : "\u2014"));
  _set("qec-na",     t || (S.nAncilla != null ? String(S.nAncilla) : "\u2014"));
  _set("qec-syn",    t || fx(S.synWeight, 2));
  _set("qec-pl",     t || fexp(S.pL, 3));
  _set("qec-supp",   t || (S.suppression != null ? S.suppression.toFixed(3) + "\u00d7" : "\u2014"));
  _set("qec-thresh", t || (S.belowThresh == null ? "\u2014" : (S.belowThresh ? "BELOW threshold (suppressing)" : "AT/ABOVE threshold")));
  // honesty label verbatim — never upgraded
  _set("qec-label",  t || (S.label || "MODELED"));
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
  _dataQubits = []; _ancillas = []; _links = null; _ring = null;
  _lastD.d = 0;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.d = S.p = S.nData = S.nAncilla = S.synWeight = S.pL = S.suppression = null;
  S.belowThresh = S.thresholdNote = null;
  S.state = "init";
  _flash.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
