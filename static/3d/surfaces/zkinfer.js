// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/zkinfer.js — zkML PROOF-OF-INFERENCE ("Cryptographic Receipts").
//
// The CRYPTOGRAPHIC-PROOF trust branch of verifiable inference — a prover (model host)
// emits a succinct zero-knowledge argument that a COMMITTED model produced a specific
// output, checkable against only a public weight commitment: no trusted hardware, no
// silicon vendor in the trust base. Orthogonal to the estate's TEE/hardware branch
// (ccattest, which trusts an enclave + vendor attestation service).
//
// DATA: live snapshot from the same-origin endpoint /api/a11oy/v1/frontier/zkinfer:
//   label (MODELED, VERBATIM), proof_cost_model{ anchor_points[], cost_frontier{grid} },
//   trust_model_matrix{ branches: crypto vs TEE }, micro_artifact{ label, verify_ok },
//   doctrine{ trust_ceiling, lambda }, sources{}.
//
// VISUALIZES:
//   1. a layerwise prover→verifier PROOF-PACKET TUNNEL — stacked model-layer planes; a
//      proof-teal packet travels layer-by-layer and collapses into a single small glyph at
//      the verifier, whose size is scaled to the MODELED proof size (kB) — "succinct".
//   2. a COST-FRONTIER RIBBON — x = model size, y = sequence length, z = prover time, from
//      the literature-parameterized grid; each cell MODELED (never a benchmark).
//   3. TRUST-BASE CONTRAST PILLARS — "cryptographic (this)" vs "TEE / ccattest"; the
//      silicon-vendor node on the crypto pillar is GREYED-OUT (outside the trust base).
//   4. a LIVE ROUNDTRIP PULSE — when the real commit→prove→verify micro-artifact returns
//      MEASURED, one proof-teal pulse fires prover→verifier; on HONEST-STUB it is dim grey
//      and labeled STUB. No green "1.0 / VERIFIED" state anywhere.
//
// PRIMARY SOURCES (cited verbatim on-surface; IDs only — 0 runtime CDN, no URL fetch):
//   zkLLM arXiv:2404.16109 (CCS'24) · Kang et al. arXiv:2210.08674 · ZKML EuroSys'24
//   DOI 10.1145/3627703.3650088 · South et al. arXiv:2402.02675 · Peng et al. survey
//   arXiv:2502.18535.
//
// HONESTY LABEL: MODELED — literature-parameterized cost model + trust matrix, explicitly
//   NOT VERIFIED; no live LLM-scale proof is produced. The ONE narrowly MEASURED tile is the
//   toy commit-verify roundtrip (plumbing only; reveals weights; not LLM-scale). Read
//   VERBATIM from JSON; never upgraded here. Trust ceiling 0.97, NEVER 100%.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff (data-viz marker), proof-teal
//   0x3af4c8 (packet / MEASURED pulse), greys (pending / TEE / greyed vendor / STUB).
//   PURPLE BANNED. No green/1.0 verified state.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "zkinfer";
const TITLE = "zkML Proof-of-Inference · Cryptographic Receipts (live)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/frontier/zkinfer";

// data-viz hues — purple BANNED, no green
const C_LAYER   = 0x5b8dee;  // lattice-blue (model-layer planes, tunnel body)
const C_PACKET  = 0x3af4c8;  // proof-teal (proof packet / MEASURED roundtrip pulse)
const C_MARKER  = 0x8a6bff;  // violet-blue (verifier glyph / data-viz marker)
const C_DIM     = 0x42505d;  // grey (pending / greyed vendor / STUB / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour
const C_RIBBON  = 0x5b8dee;  // lattice-blue (cost ribbon base)

// tunnel geometry
const N_LAYERS   = 7;        // stacked model-layer planes
const LAYER_GAP  = 1.4;      // world-units between layers along z
const LAYER_W    = 3.2;      // plane width/height

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _layers = [];       // Array<THREE.Mesh> — stacked layer planes (prover -> verifier)
let _packet = null;     // THREE.Mesh — traveling proof packet
let _verifier = null;   // THREE.Mesh — verifier glyph (collapses proof to a small object)
let _ribbon = null;     // THREE.Mesh — cost-frontier surface
let _pillars = [];      // Array<{ mesh, node }> — trust-base contrast pillars
let _floor = null;
let _pulseT = -1;       // >=0 while a roundtrip pulse is animating

// live state (all read from JSON; nothing invented)
const S = {
  label:       null,   // top honesty label VERBATIM (MODELED)
  notVerified: null,
  microLabel:  null,   // MEASURED | HONEST-STUB
  verifyOk:    null,
  proofKb:     null,   // modeled proof size (kB)
  anchorTime:  null,   // zkLLM anchor prover time (s)
  trustCeil:   null,
  lambda:      null,
  grid:        null,   // prover_time_grid_s rows
  seqAxis:     null,
  paramsAxis:  null,
  cryptoTCB:   null,   // trusted_hardware_in_TCB for crypto branch (false)
  teeTCB:      null,   // trusted_hardware_in_TCB for TEE branch (true)
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(9, 6, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildTunnel();
  _buildRibbon();
  _buildPillars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 6000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Prover (z-) -> Verifier (z+): stacked translucent model-layer planes forming a tunnel,
// plus a traveling proof packet and the collapsing verifier glyph.
function _buildTunnel() {
  const THREE = _THREE;
  const planeGeo = new THREE.PlaneGeometry(LAYER_W, LAYER_W);
  const z0 = -((N_LAYERS - 1) * LAYER_GAP) / 2;

  for (let i = 0; i < N_LAYERS; i++) {
    const mat = new THREE.MeshStandardMaterial({
      color: C_LAYER, emissive: C_LAYER, emissiveIntensity: 0.12,
      transparent: true, opacity: 0.16, side: THREE.DoubleSide, wireframe: false,
    });
    const mesh = new THREE.Mesh(planeGeo, mat);
    mesh.position.set(-6, 1.6, z0 + i * LAYER_GAP);
    _group.add(mesh);
    // frame outline (wire) so layers read as discrete stages
    const wire = new THREE.Mesh(planeGeo, new THREE.MeshBasicMaterial({
      color: C_LAYER, transparent: true, opacity: 0.28, wireframe: true, side: THREE.DoubleSide,
    }));
    wire.position.copy(mesh.position);
    _group.add(wire);
    _layers.push(mesh);
  }

  // proof packet — small proof-teal octahedron traveling prover->verifier
  _packet = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.28, 0),
    new THREE.MeshStandardMaterial({ color: C_PACKET, emissive: C_PACKET, emissiveIntensity: 0.6, transparent: true, opacity: 0.95 }),
  );
  _packet.position.set(-6, 1.6, z0);
  _group.add(_packet);

  // verifier glyph — small violet-blue icosahedron at the +z end; its scale reflects the
  // MODELED proof size (succinct => small). Starts modest; updated from live data.
  _verifier = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.5, 0),
    new THREE.MeshStandardMaterial({ color: C_MARKER, emissive: C_MARKER, emissiveIntensity: 0.35, transparent: true, opacity: 0.9, wireframe: true }),
  );
  _verifier.position.set(-6, 1.6, z0 + (N_LAYERS - 1) * LAYER_GAP + 1.4);
  _group.add(_verifier);
}

// Cost-frontier ribbon: a plane whose vertices are displaced in Y by MODELED prover time
// over (model size × sequence length). Colored lattice-blue at low cost -> proof-teal high.
function _buildRibbon() {
  const THREE = _THREE;
  const segX = 5, segZ = 4;  // default until live grid arrives (6 params × 5 seq)
  const geo = new THREE.PlaneGeometry(7, 6, segX, segZ);
  geo.rotateX(-Math.PI / 2);
  const mat = new THREE.MeshStandardMaterial({
    color: C_RIBBON, emissive: C_RIBBON, emissiveIntensity: 0.18,
    transparent: true, opacity: 0.55, side: THREE.DoubleSide,
    wireframe: false, flatShading: true,
    vertexColors: true,
  });
  _ribbon = new THREE.Mesh(geo, mat);
  _ribbon.position.set(6.5, 1.2, 0);
  _group.add(_ribbon);

  // baseline vertex colors (lattice-blue); recolored when live grid arrives.
  const cnt = geo.attributes.position.count;
  const colors = new Float32Array(cnt * 3);
  const base = new THREE.Color(C_RIBBON);
  for (let i = 0; i < cnt; i++) { colors[i * 3] = base.r; colors[i * 3 + 1] = base.g; colors[i * 3 + 2] = base.b; }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
}

// Trust-base contrast pillars: crypto (this surface) vs TEE (ccattest). The crypto pillar's
// silicon-vendor node is greyed-out to show it is OUTSIDE the trust base.
function _buildPillars() {
  const THREE = _THREE;
  const pillarGeo = new THREE.CylinderGeometry(0.55, 0.55, 3.4, 20, 1, true);
  const nodeGeo = new THREE.SphereGeometry(0.32, 16, 12);

  const specs = [
    { x: -1.4, color: C_PACKET, vendorGrey: true,  name: "crypto" },   // this surface
    { x:  1.4, color: C_LAYER,  vendorGrey: false, name: "tee" },      // ccattest
  ];
  for (const sp of specs) {
    const mesh = new THREE.Mesh(pillarGeo, new THREE.MeshStandardMaterial({
      color: sp.color, emissive: sp.color, emissiveIntensity: 0.14,
      transparent: true, opacity: 0.28, side: THREE.DoubleSide, wireframe: true,
    }));
    mesh.position.set(sp.x, 1.9, 7.5);
    _group.add(mesh);
    // "silicon-vendor node" at pillar top — greyed on the crypto pillar (not in TCB).
    const nodeColor = sp.vendorGrey ? C_DIM : C_MARKER;
    const node = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color: nodeColor, emissive: nodeColor,
      emissiveIntensity: sp.vendorGrey ? 0.08 : 0.4,
      transparent: true, opacity: sp.vendorGrey ? 0.35 : 0.9,
    }));
    node.position.set(sp.x, 3.9, 7.5);
    _group.add(node);
    _pillars.push({ mesh, node });
  }
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label       = (j.label || "MODELED").toUpperCase();
  S.notVerified = j.not_verified === true;

  const pcm = j.proof_cost_model || {};
  const cf  = pcm.cost_frontier || {};
  S.grid    = Array.isArray(cf.prover_time_grid_s) ? cf.prover_time_grid_s : null;
  S.seqAxis = cf.axes && Array.isArray(cf.axes.seq_len) ? cf.axes.seq_len : null;
  S.paramsAxis = cf.axes && Array.isArray(cf.axes.params_b) ? cf.axes.params_b : null;
  S.proofKb = cf.proof_size_kb_modeled && typeof cf.proof_size_kb_modeled.value === "number"
    ? cf.proof_size_kb_modeled.value : null;
  S.anchorTime = cf.anchor && typeof cf.anchor.prover_time_s === "number"
    ? cf.anchor.prover_time_s : null;

  const ma = j.micro_artifact || {};
  S.microLabel = typeof ma.label === "string" ? ma.label.toUpperCase() : null;
  S.verifyOk   = typeof ma.verify_ok === "boolean" ? ma.verify_ok : null;

  const d = j.doctrine || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;

  const br = (j.trust_model_matrix || {}).branches || {};
  const crypto = br["cryptographic_zkml (this surface)"] || {};
  const tee    = br["tee_attestation (ccattest)"] || {};
  S.cryptoTCB = typeof crypto.trusted_hardware_in_TCB === "boolean" ? crypto.trusted_hardware_in_TCB : null;
  S.teeTCB    = typeof tee.trusted_hardware_in_TCB === "boolean" ? tee.trusted_hardware_in_TCB : null;

  _updateVerifier();
  _updateRibbon();
  _updatePillars();
  // fire a roundtrip pulse only when the real micro-artifact actually reconciled.
  if (S.microLabel === "MEASURED" && S.verifyOk === true) _pulseT = 0;
  _paintOverlay();
}

// verifier glyph scale reflects MODELED proof size (succinct => small).
function _updateVerifier() {
  if (!_verifier) return;
  const live = S.state === "live";
  if (live && S.proofKb != null) {
    // map ~200 kB -> small glyph; keep it visibly "succinct".
    const s = Math.max(0.3, Math.min(0.9, 0.3 + (S.proofKb / 200) * 0.4));
    _verifier.scale.setScalar(s);
    _verifier.material.color.setHex(C_MARKER);
    _verifier.material.emissive.setHex(C_MARKER);
    _verifier.material.opacity = 0.9;
  } else {
    _verifier.scale.setScalar(0.5);
    _verifier.material.color.setHex(C_DIM);
    _verifier.material.emissive.setHex(C_DIM);
    _verifier.material.opacity = 0.3;
  }
}

// recolor + displace the ribbon from the live MODELED prover-time grid.
function _updateRibbon() {
  if (!_ribbon || !_ribbon.geometry) return;
  const THREE = _THREE;
  const geo = _ribbon.geometry;
  const pos = geo.attributes.position;
  const col = geo.attributes.color;
  const live = S.state === "live" && S.grid && S.grid.length;

  if (!live) {
    // flat + dim grey when no live data
    for (let i = 0; i < pos.count; i++) {
      pos.setY(i, 0);
      col.setXYZ(i, 0.26, 0.31, 0.36);
    }
    pos.needsUpdate = true; col.needsUpdate = true; geo.computeVertexNormals();
    return;
  }

  // grid rows = params (X), cols = seq (Z). PlaneGeometry has (segX+1)*(segZ+1) verts.
  const rows = S.grid;                     // [{params_b, prover_time_s:[...]}]
  const nX = rows.length;                  // params count
  const nZ = rows[0].prover_time_s.length; // seq count
  // find max for normalization
  let mx = 1;
  for (const r of rows) for (const v of r.prover_time_s) if (v > mx) mx = v;

  const lo = new THREE.Color(C_RIBBON);    // lattice-blue (low cost)
  const hi = new THREE.Color(C_PACKET);    // proof-teal (high cost)
  const segX = geo.parameters.widthSegments;
  const segZ = geo.parameters.heightSegments;

  for (let ix = 0; ix <= segX; ix++) {
    for (let iz = 0; iz <= segZ; iz++) {
      const vi = ix * (segZ + 1) + iz;
      const gx = Math.min(nX - 1, Math.round((ix / segX) * (nX - 1)));
      const gz = Math.min(nZ - 1, Math.round((iz / segZ) * (nZ - 1)));
      const t = rows[gx].prover_time_s[gz] / mx;      // 0..1 normalized cost
      pos.setY(vi, t * 2.4);                            // z = prover time (height)
      const c = lo.clone().lerp(hi, t);
      col.setXYZ(vi, c.r, c.g, c.b);
    }
  }
  pos.needsUpdate = true; col.needsUpdate = true; geo.computeVertexNormals();
}

function _updatePillars() {
  if (_pillars.length < 2) return;
  const live = S.state === "live";
  // crypto pillar[0]: vendor node greyed iff crypto TCB has NO trusted hardware (expected).
  const cryptoGrey = S.cryptoTCB === false || S.cryptoTCB == null;
  const cNode = _pillars[0].node;
  cNode.material.color.setHex(cryptoGrey ? C_DIM : C_MARKER);
  cNode.material.emissive.setHex(cryptoGrey ? C_DIM : C_MARKER);
  cNode.material.emissiveIntensity = cryptoGrey ? 0.08 : 0.4;
  cNode.material.opacity = cryptoGrey ? 0.35 : 0.9;
  // TEE pillar[1]: vendor node lit iff TEE TCB includes trusted hardware (expected true).
  const teeLit = S.teeTCB === true;
  const tNode = _pillars[1].node;
  tNode.material.color.setHex(teeLit ? C_MARKER : C_DIM);
  tNode.material.emissive.setHex(teeLit ? C_MARKER : C_DIM);
  tNode.material.emissiveIntensity = teeLit ? 0.4 : 0.1;
  tNode.material.opacity = teeLit ? 0.9 : 0.4;
  if (!live) {
    _pillars.forEach((p) => { p.mesh.material.opacity = 0.14; });
  } else {
    _pillars.forEach((p) => { p.mesh.material.opacity = 0.28; });
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.10;
  if (_verifier) { _verifier.rotation.y += 0.02; _verifier.rotation.x += 0.006; }

  // proof packet travels prover -> verifier along the tunnel, looping.
  if (_packet && _layers.length) {
    const z0 = _layers[0].position.z;
    const z1 = _verifier ? _verifier.position.z : _layers[_layers.length - 1].position.z;
    const phase = (t * 0.00035) % 1;
    _packet.position.z = z0 + (z1 - z0) * phase;
    _packet.rotation.y += 0.05;
    const live = S.state === "live";
    _packet.material.color.setHex(live ? C_PACKET : C_DIM);
    _packet.material.emissive.setHex(live ? C_PACKET : C_DIM);
    _packet.material.opacity = live ? 0.95 : 0.35;
    // light the layer the packet is currently passing through
    for (let i = 0; i < _layers.length; i++) {
      const near = Math.abs(_layers[i].position.z - _packet.position.z) < LAYER_GAP * 0.6;
      _layers[i].material.opacity = live ? (near ? 0.4 : 0.16) : 0.1;
    }
  }

  // live roundtrip pulse: a single proof-teal (MEASURED) or dim-grey (STUB) surge on the
  // verifier glyph when the real micro-artifact returns. NEVER a green/1.0 state.
  if (_pulseT >= 0 && _verifier) {
    _pulseT += 0.02;
    const measured = S.microLabel === "MEASURED" && S.verifyOk === true;
    const c = measured ? C_PACKET : C_DIM;
    _verifier.material.emissive.setHex(c);
    _verifier.material.emissiveIntensity = 0.35 + 0.5 * Math.max(0, Math.sin(_pulseT * Math.PI));
    if (_pulseT >= 1) { _pulseT = -1; _verifier.material.emissiveIntensity = 0.35; }
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "zkML proof", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The <b>cryptographic-proof</b> trust branch of verifiable inference: a succinct ' +
    '<b>zero-knowledge</b> argument that a <b>committed</b> model produced a specific output, ' +
    'checkable against only a public weight commitment — <b>no trusted hardware, no ' +
    'vendor in the trust base</b>. Orthogonal to the estate’s TEE branch (ccattest). ' +
    'Honesty label <b>MODELED</b> — literature-parameterized cost model, explicitly ' +
    '<b>NOT VERIFIED</b>; no live LLM-scale proof is produced. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "zkinfer";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("zk-anchor", "prover time · zkLLM 13B (MODELED)"));
  grid.appendChild(kpiRow("zk-proof",  "proof size (MODELED, succinct)"));
  grid.appendChild(kpiRow("zk-micro",  "commit→verify roundtrip"));
  grid.appendChild(kpiRow("zk-tcb",    "trusted hardware in TCB (crypto)"));
  grid.appendChild(kpiRow("zk-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("zk-lambda", "Λ"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent =
    "Sources: zkLLM arXiv:2404.16109 (CCS’24) · Kang et al. arXiv:2210.08674 · " +
    "ZKML EuroSys’24 DOI 10.1145/3627703.3650088 · South et al. arXiv:2402.02675 · " +
    "Peng et al. survey arXiv:2502.18535. MODELED · not verified.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "zk-plain";
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
  const micro = S.microLabel === "MEASURED" && S.verifyOk === true
    ? "really ran and reconciled just now"
    : (S.microLabel === "HONEST-STUB" ? "is an honest stub (did not run)" : "loading…");
  pd.innerHTML =
    "<b>What this means:</b> zkML lets a model host prove — with a small math object " +
    "anyone can check — that a <b>specific committed model</b> produced a given output, " +
    "<b>without revealing the weights</b> and <b>without the checker re-running the model</b>. " +
    "That is the cryptographic cousin of a hardware attestation (the estate’s ccattest " +
    "tab): instead of trusting a chip vendor, you trust <b>standard math assumptions</b>. " +
    "This tab shows <b>MODELED</b> costs read from five real papers (prover time, proof size, " +
    "verify time) — it is <b>NOT a live proof</b> and never shows a “verified/1.0” " +
    "state. The one genuinely-run piece is a tiny <b>commit→prove→verify roundtrip</b> " +
    "computed on the server (it " + micro + "); it proves the <b>plumbing</b> is real, not " +
    "that it scales to an LLM. Plain: honest cost map + trust contrast + one real toy check, " +
    "clearly labeled, no overclaim.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _fmtTime(s) { return s == null ? "—" : (s >= 60 ? (s / 60).toFixed(1) + " min" : s + " s"); }

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "zkML proof" });
  _set("zk-anchor", t || (S.anchorTime != null ? "< " + _fmtTime(S.anchorTime) : "—"));
  _set("zk-proof",  t || (S.proofKb != null ? "< " + S.proofKb + " kB" : "—"));
  _set("zk-micro",  t || (S.microLabel ? (S.microLabel + (S.verifyOk === true ? " · verify_ok" : "")) : "—"));
  _set("zk-tcb",    t || (S.cryptoTCB === false ? "false (none)" : (S.cryptoTCB === true ? "true" : "—")));
  _set("zk-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("zk-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — dispose everything; must not affect other organs
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
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _layers = []; _packet = null; _verifier = null; _ribbon = null; _pillars = []; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _pulseT = -1;
  _stage = _THREE = _ctx = null;
  S.label = S.notVerified = S.microLabel = S.verifyOk = S.proofKb = S.anchorTime = null;
  S.trustCeil = S.lambda = S.grid = S.seqAxis = S.paramsAxis = S.cryptoTCB = S.teeTCB = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
