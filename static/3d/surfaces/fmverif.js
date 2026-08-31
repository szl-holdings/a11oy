// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/fmverif.js — PROOF-CARRYING INFERENCE ("Machine-Checkable Certificates").
//
// The SZL SYNTHESIS surface: a governed inference that ships with ONE machine-checkable
// certificate binding four independent guarantees —
//   1. a FORMAL proof obligation (Lean/Coq proof-carrying code — Necula 1997),
//   2. a ZERO-KNOWLEDGE proof-of-inference (zkLLM),
//   3. the signed RECEIPT chain (Khipu),
//   4. a BFT QUORUM attestation over that receipt.
// The four component digests bind into a Merkle CERTIFICATE ROOT + a Fiat–Shamir transcript;
// a small trusted checker verifies the whole thing cheaply.
//
// DATA: live snapshot from the same-origin endpoint /api/a11oy/v1/frontier/fmverif:
//   label (MODELED, VERBATIM), claim (CONJECTURE), certificate_model{ components[] },
//   cost_model{ issuance_envelope, verify_side }, micro_artifact{ label, verify_ok,
//   certificate_root, component_digests }, doctrine{ trust_ceiling, lambda, khipu_bft }.
//
// VISUALIZES:
//   1. FOUR COMPONENT NODES (formal · zk · receipt · quorum) arranged around a central
//      CERTIFICATE glyph (the Merkle root). Each node colored by its verbatim label:
//      MODELED = lattice-blue, CONJECTURE (the BFT leg) = greyed (not proven).
//   2. BINDING LINKS — proof-teal beams from each component into the certificate root; a
//      packet travels each beam inward, "assembling" the certificate.
//   3. VERIFY PULSE — when the real in-process assembly→verify micro-artifact returns
//      MEASURED + verify_ok, ONE proof-teal pulse rings the certificate glyph; on
//      HONEST-STUB it is dim grey and labeled STUB. No green "1.0 / VERIFIED" state.
//
// PRIMARY SOURCES (cited verbatim on-surface; IDs only — 0 runtime CDN, no URL fetch):
//   Proof-Carrying Code · Necula DOI 10.1145/263699.263712 (POPL'97) · ATL verified tensor
//   compiler DOI 10.1145/3656390 (PLDI'24) · Marabou 2.0 arXiv:2401.14461 (CAV'24) ·
//   zkLLM arXiv:2404.16109 (CCS'24).
//
// HONESTY LABEL: MODELED — certificate structure + literature-parameterized cost, explicitly
//   NOT VERIFIED. The SZL synthesis (that the four legs compose end-to-end for a live LLM) is
//   CONJECTURE, never a theorem. The ONE narrowly MEASURED tile is the toy assembly→bind→
//   verify roundtrip (plumbing only; stand-in digests; not real proofs). Read VERBATIM from
//   JSON; never upgraded here. Trust ceiling 0.97, NEVER 100%.
// COLOURS: lattice-blue 0x5b8dee, violet-blue 0x8a6bff (data-viz marker), proof-teal
//   0x3af4c8 (binding beams / MEASURED pulse), greys (pending / CONJECTURE leg / STUB).
//   PURPLE BANNED. No green/1.0 verified state.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; BFT stays Conjecture 2; introduces no theorem. Degrades grey on
//   404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "fmverif";
const TITLE = "Proof-Carrying Inference · Machine-Checkable Certificates (live)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/frontier/fmverif";

// data-viz hues — purple BANNED, no green
const C_MODELED = 0x5b8dee;  // lattice-blue (MODELED component node)
const C_BEAM    = 0x3af4c8;  // proof-teal (binding beam / MEASURED pulse)
const C_CERT    = 0x8a6bff;  // violet-blue (central certificate glyph / marker)
const C_DIM     = 0x42505d;  // grey (pending / CONJECTURE leg / STUB / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// component order matches the backend certificate_model.components[]
const COMPS = [
  { key: "formal_proof_obligation", short: "formal" },
  { key: "zk_proof_of_inference",   short: "zk" },
  { key: "receipt_chain",           short: "receipt" },
  { key: "bft_quorum_attestation",  short: "quorum" },
];

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

// geometry handles
let _cert = null;        // THREE.Mesh — central certificate glyph (Merkle root)
let _nodes = [];         // Array<{ mesh, beam, packet, spec }>
let _floor = null;
let _pulseT = -1;        // >=0 while a verify pulse is animating

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,   // top honesty label VERBATIM (MODELED)
  claim:      null,   // CONJECTURE (synthesis)
  microLabel: null,   // MEASURED | HONEST-STUB
  verifyOk:   null,
  certRoot:   null,   // certificate Merkle root (hex)
  trustCeil:  null,
  lambda:     null,
  bft:        null,
  compLabels: {},     // key -> verbatim label (MODELED / CONJECTURE)
  envelope:   null,   // issuance-envelope formula (string)
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 15);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.6, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCertificate();
  _buildNodes();

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

// central certificate glyph — a wire icosahedron (the Merkle root the four legs bind into).
function _buildCertificate() {
  const THREE = _THREE;
  _cert = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.95, 0),
    new THREE.MeshStandardMaterial({
      color: C_CERT, emissive: C_CERT, emissiveIntensity: 0.32,
      transparent: true, opacity: 0.85, wireframe: true,
    }),
  );
  _cert.position.set(0, 1.9, 0);
  _group.add(_cert);
}

// four component nodes on a ring, each with a beam + inbound packet toward the certificate.
function _buildNodes() {
  const THREE = _THREE;
  const R = 5.2;
  const nodeGeo = new THREE.OctahedronGeometry(0.5, 0);
  for (let i = 0; i < COMPS.length; i++) {
    const ang = (i / COMPS.length) * Math.PI * 2;
    const x = Math.cos(ang) * R, z = Math.sin(ang) * R;

    const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color: C_MODELED, emissive: C_MODELED, emissiveIntensity: 0.24,
      transparent: true, opacity: 0.9, wireframe: false,
    }));
    mesh.position.set(x, 1.9, z);
    mesh.userData.label = COMPS[i].short;
    _group.add(mesh);

    // binding beam: thin cylinder from node to certificate center.
    const from = new THREE.Vector3(x, 1.9, z);
    const to = new THREE.Vector3(0, 1.9, 0);
    const len = from.distanceTo(to);
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.02, 0.02, len, 6, 1, true),
      new THREE.MeshBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.28 }),
    );
    beam.position.copy(from.clone().add(to).multiplyScalar(0.5));
    beam.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize(),
    );
    _group.add(beam);

    // inbound packet — small proof-teal cube traveling node -> certificate.
    const packet = new THREE.Mesh(
      new THREE.BoxGeometry(0.16, 0.16, 0.16),
      new THREE.MeshStandardMaterial({ color: C_BEAM, emissive: C_BEAM, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }),
    );
    packet.position.copy(from);
    _group.add(packet);

    _nodes.push({ mesh, beam, packet, spec: COMPS[i], from, to });
  }
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label = (j.label || "MODELED").toUpperCase();
  S.claim = typeof j.claim === "string" ? j.claim.toUpperCase() : null;

  const cm = j.certificate_model || {};
  const comps = Array.isArray(cm.components) ? cm.components : [];
  S.compLabels = {};
  for (const c of comps) {
    if (c && typeof c.name === "string") S.compLabels[c.name] = (c.label || "").toUpperCase();
  }

  const cost = j.cost_model || {};
  S.envelope = cost.issuance_envelope && typeof cost.issuance_envelope.formula === "string"
    ? cost.issuance_envelope.formula : null;

  const ma = j.micro_artifact || {};
  S.microLabel = typeof ma.label === "string" ? ma.label.toUpperCase() : null;
  S.verifyOk   = typeof ma.verify_ok === "boolean" ? ma.verify_ok : null;
  S.certRoot   = typeof ma.certificate_root === "string" ? ma.certificate_root : null;

  const d = j.doctrine || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.bft       = typeof d.khipu_bft === "string" ? d.khipu_bft : null;

  _updateNodes();
  // fire a verify pulse only when the real micro-artifact actually reconciled.
  if (S.microLabel === "MEASURED" && S.verifyOk === true) _pulseT = 0;
  _paintOverlay();
}

// recolor component nodes + beams from the verbatim per-component labels.
function _updateNodes() {
  const live = S.state === "live";
  for (const n of _nodes) {
    const lbl = S.compLabels[n.spec.key];
    // CONJECTURE leg (BFT) greyed; MODELED legs lattice-blue; unknown/no-data dim.
    const isConj = lbl === "CONJECTURE";
    const known = !!lbl;
    const col = !live || !known ? C_DIM : (isConj ? C_DIM : C_MODELED);
    n.mesh.material.color.setHex(col);
    n.mesh.material.emissive.setHex(col);
    n.mesh.material.emissiveIntensity = (!live || !known) ? 0.1 : (isConj ? 0.12 : 0.24);
    n.mesh.material.opacity = (!live || !known) ? 0.4 : (isConj ? 0.55 : 0.9);
    // beam lights proof-teal only when live + this leg has a known label.
    const beamLit = live && known;
    n.beam.material.color.setHex(beamLit ? C_BEAM : C_DIM);
    n.beam.material.opacity = beamLit ? 0.4 : 0.16;
  }
  // certificate glyph dims when not live.
  if (_cert) {
    _cert.material.color.setHex(live ? C_CERT : C_DIM);
    _cert.material.emissive.setHex(live ? C_CERT : C_DIM);
    _cert.material.opacity = live ? 0.85 : 0.35;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.12;
  if (_cert) { _cert.rotation.y += 0.01; _cert.rotation.x += 0.004; }

  const live = S.state === "live";
  // inbound packets travel node -> certificate, looping (assembling the certificate).
  const phase = (t * 0.0004) % 1;
  for (const n of _nodes) {
    if (!n.packet) continue;
    n.packet.position.lerpVectors(n.from, n.to, phase);
    n.packet.rotation.y += 0.06;
    const known = !!S.compLabels[n.spec.key];
    const lit = live && known;
    n.packet.material.color.setHex(lit ? C_BEAM : C_DIM);
    n.packet.material.emissive.setHex(lit ? C_BEAM : C_DIM);
    n.packet.material.opacity = lit ? 0.9 : 0.3;
  }

  // verify pulse: a single proof-teal (MEASURED) or dim-grey (STUB) ring on the certificate
  // glyph when the real micro-artifact returns. NEVER a green/1.0 state.
  if (_pulseT >= 0 && _cert) {
    _pulseT += 0.02;
    const measured = S.microLabel === "MEASURED" && S.verifyOk === true;
    const c = measured ? C_BEAM : C_DIM;
    _cert.material.emissive.setHex(c);
    _cert.material.emissiveIntensity = 0.32 + 0.5 * Math.max(0, Math.sin(_pulseT * Math.PI));
    if (_pulseT >= 1) { _pulseT = -1; _cert.material.emissiveIntensity = 0.32; }
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [
      { label: "MODELED", text: "certificate", name: "lbl" },
      { label: "CONJECTURE", text: "synthesis", name: "syn" },
    ],
    legend: ["MODELED", "CONJECTURE"],
  });
  const host = _show.body;

  // in-scene labels for the four component nodes (billboarded, hover + always-on top-4).
  try {
    _show.attachSceneLabels({
      objects: () => _nodes.map((n) => n.mesh),
      text: (o) => o.userData.label,
      weight: () => 1, topN: 4, hover: true,
    });
  } catch (_) {}

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A governed inference that ships with <b>one machine-checkable certificate</b> binding ' +
    'four guarantees: a <b>formal</b> proof obligation (Lean/Coq PCC), a <b>zero-knowledge</b> ' +
    'proof-of-inference, the signed <b>receipt</b> chain, and a <b>BFT quorum</b> attestation. ' +
    'Honesty label <b>MODELED</b>; the SZL synthesis (that the four compose end-to-end for a ' +
    'live LLM) is <b>CONJECTURE</b> — <b>not a theorem, NOT VERIFIED</b>. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "fmverif";
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
  grid.appendChild(kpiRow("fm-legs",   "certificate legs (MODELED / CONJECTURE)"));
  grid.appendChild(kpiRow("fm-micro",  "assembly→verify roundtrip"));
  grid.appendChild(kpiRow("fm-root",   "certificate root (Merkle)"));
  grid.appendChild(kpiRow("fm-bft",    "BFT quorum leg"));
  grid.appendChild(kpiRow("fm-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("fm-lambda", "Λ"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent =
    "Sources: Necula PCC DOI 10.1145/263699.263712 (POPL’97) · ATL verified compiler " +
    "DOI 10.1145/3656390 (PLDI’24) · Marabou 2.0 arXiv:2401.14461 (CAV’24) · zkLLM " +
    "arXiv:2404.16109 (CCS’24). MODELED · synthesis CONJECTURE · not verified.";
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
  pd.id = "fm-plain";
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
    "<b>What this means:</b> imagine an AI answer that arrives with a tamper-proof " +
    "<b>receipt anyone can check</b> — proving the model met a stated rule, that a " +
    "<b>specific committed model</b> produced it, that its history was sealed, and that a " +
    "group of independent validators agreed to admit it. That bundle is a " +
    "<b>proof-carrying inference certificate</b>. This tab shows its <b>shape</b> and " +
    "<b>MODELED</b> costs read from four real papers — it is <b>NOT a live proof</b> and never " +
    "shows a “verified/1.0” state. The idea that all four legs snap together end-to-end for a " +
    "big model is our <b>CONJECTURE</b>, not a proven theorem (the BFT leg in particular is " +
    "Conjecture 2). The one genuinely-run piece is a tiny <b>assemble→bind→verify</b> " +
    "roundtrip on the server (it " + micro + "); it proves the <b>plumbing</b> is real, not " +
    "that it scales. Plain: honest blueprint + one real toy check, clearly labeled, no overclaim.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _legsSummary() {
  const labels = COMPS.map((c) => S.compLabels[c.key]).filter(Boolean);
  if (!labels.length) return "—";
  const nMod = labels.filter((l) => l === "MODELED").length;
  const nConj = labels.filter((l) => l === "CONJECTURE").length;
  return nMod + " MODELED · " + nConj + " CONJECTURE";
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "certificate" });
    _show.setChip("syn", S.claim || "CONJECTURE", { text: "synthesis" });
  }
  _set("fm-legs",   t || _legsSummary());
  _set("fm-micro",  t || (S.microLabel ? (S.microLabel + (S.verifyOk === true ? " · verify_ok" : "")) : "—"));
  _set("fm-root",   t || (S.certRoot ? (S.certRoot.slice(0, 12) + "…") : "—"));
  _set("fm-bft",    t || (S.bft || "—"));
  _set("fm-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("fm-lambda", t || (S.lambda || "—"));
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
  _cert = null; _nodes = []; _floor = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _pulseT = -1;
  _stage = _THREE = _ctx = null;
  S.label = S.claim = S.microLabel = S.verifyOk = S.certRoot = null;
  S.trustCeil = S.lambda = S.bft = S.envelope = null; S.compLabels = {};
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
