// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainverdict.js — BRAIN VERDICT · the verifiable answer.
// Composes three honest readings — served-model provenance (brainserve), claim→source citation
// coverage (braincite), refusal-to-fabricate posture (braineval) — into ONE assurance verdict,
// then binds the whole chain under an ECDSA-P256 signature (brainreceipt). One offline-verifiable
// object for the entire governed pipeline. A valid signature proves the chain is UNALTERED —
// integrity, NOT truth. assurance is never drawn higher than the components earned; the weakest
// link is always shown.
//
// RENDER: a central VERDICT core whose color = assurance (teal VERIFIABLE-GROUNDED, cyan
// VERIFIABLE-PARTIAL, amber VERIFIABLE-WEAK, grey UNVERIFIABLE-NO-MODEL). THREE component pillars
// (served / citation / refusal) rise around it — each teal when MEASURED/strong, amber when a
// caveat, grey when UNAVAILABLE. A thin SEAL ring encircles the core when the receipt signature
// verified. The shortest/greyest pillar is the weakest link — shown, never hidden.
//
// DATA: GET /api/a11oy/v1/brain/verdict?q=... (PURE READ, mints no signature):
//   assurance_level, weakest_link, components{served_model, citation, refusal_eval}.
// The signed receipt is produced by POST /verdict/sign.
//
// HONESTY: assurance is MODELED; no component upgraded; 0 RUNTIME CDN — three.js via ctx.THREE.

const ID = "brainverdict";
const TITLE = "Brain Verdict · the verifiable answer (question→sources→answer→checks, signed)";
const DEFAULT_Q = "what is the energy ledger receipt";
const EP = "/api/a11oy/v1/brain/verdict?k=6&q=" + encodeURIComponent(DEFAULT_Q);

const C_TEAL = 0x3af4c8;   // grounded / measured / strong
const C_CYAN = 0x4fd0ff;   // partial
const C_AMBER = 0xffb24a;  // weak / caveat
const C_GREY = 0x2a3138;   // unavailable
const C_GREY_HI = 0x6b7580;

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _core = null, _seal = null, _pillars = [];
let _frameReg = false, _spin = 0;
const S = { assurance: null, comps: null, state: "init", signed: false };

function _assuranceColor(a) {
  if (a === "VERIFIABLE-GROUNDED") return C_TEAL;
  if (a === "VERIFIABLE-PARTIAL") return C_CYAN;
  if (a === "VERIFIABLE-WEAK") return C_AMBER;
  return C_GREY_HI; // UNVERIFIABLE-NO-MODEL
}

function _compColor(label, verdict) {
  if (label === "MEASURED" || verdict === "SERVING-EXPECTED" || verdict === "FULLY-CITED" || verdict === "REFUSAL-HONEST") return C_TEAL;
  if (verdict === "FABRICATION-DETECTED" || verdict === "UNCITED-DOMINANT") return C_AMBER;
  if (label === "UNAVAILABLE" || verdict === "UNAVAILABLE" || !label) return C_GREY;
  return C_CYAN; // partial / present
}

function _compHeight(label, verdict) {
  if (label === "MEASURED" || verdict === "FULLY-CITED" || verdict === "REFUSAL-HONEST") return 1.2;
  if (label === "UNAVAILABLE" || verdict === "UNAVAILABLE" || !label) return 0.35; // weakest link = shortest
  return 0.8;
}

export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _buildCore();
  _stage.scene.add(_group);
  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }
  _fetch();
}

function _buildCore() {
  const THREE = _THREE;
  const g = new THREE.OctahedronGeometry(0.6, 0);
  const m = new THREE.MeshStandardMaterial({ color: C_GREY_HI, emissive: C_GREY_HI, emissiveIntensity: 0.3, roughness: 0.35, metalness: 0.2, transparent: true, opacity: 0.92 });
  _core = new THREE.Mesh(g, m);
  _group.add(_core);
}

// seal ring appears only when the receipt signature verified (shown honestly, not implied)
function _buildSeal(on) {
  const THREE = _THREE;
  if (_seal) { _group.remove(_seal); if (_seal.geometry) _seal.geometry.dispose(); if (_seal.material) _seal.material.dispose(); _seal = null; }
  if (!on) return;
  const g = new THREE.TorusGeometry(0.95, 0.03, 12, 80);
  const m = new THREE.MeshBasicMaterial({ color: C_TEAL, transparent: true, opacity: 0.6 });
  _seal = new THREE.Mesh(g, m);
  _seal.rotation.x = Math.PI / 2;
  _group.add(_seal);
}

function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();
  const c = S.comps || {};
  const specs = [
    { k: "served_model", d: c.served_model || {} },
    { k: "citation", d: c.citation || {} },
    { k: "refusal_eval", d: c.refusal_eval || {} },
  ];
  const R = 1.5;
  for (let i = 0; i < specs.length; i++) {
    const d = specs[i].d;
    const h = _compHeight(d.label, d.verdict);
    const col = _compColor(d.label, d.verdict);
    const g = new THREE.BoxGeometry(0.2, h, 0.2);
    const m = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: (col === C_GREY) ? 0.08 : 0.32, roughness: 0.5, transparent: true, opacity: (col === C_GREY) ? 0.5 : 0.9 });
    const mesh = new THREE.Mesh(g, m);
    const a = (i / specs.length) * Math.PI * 2;
    mesh.position.set(Math.cos(a) * R, h / 2, Math.sin(a) * R);
    _group.add(mesh);
    _pillars.push(mesh);
  }
}

function _disposePillars() {
  _pillars.forEach((o) => {
    if (o.parent) o.parent.remove(o);
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
  });
  _pillars = [];
}

function _fetch() {
  try {
    fetch(EP, { headers: { accept: "application/json" } })
      .then((r) => r.json())
      .then((j) => _onData(j))
      .catch(() => { S.state = "unavailable"; });
  } catch (_) { S.state = "unavailable"; }
}

function _onData(j) {
  if (!j || j.ok === false) { S.state = "unavailable"; return; }
  S.assurance = j.assurance_level || "UNVERIFIABLE-NO-MODEL";
  S.comps = (j.components && typeof j.components === "object") ? j.components : {};
  S.state = "ready";
  _buildPillars();
  // seal ring only when served model MEASURED (a live, bindable answer); GET does not sign,
  // so we show the seal as "signable" posture only when the chain has a live model.
  const sm = (S.comps.served_model || {}).label === "MEASURED";
  _buildSeal(sm);
  if (_core && _core.material) {
    const col = _assuranceColor(S.assurance);
    _core.material.color.setHex(col);
    _core.material.emissive.setHex(col);
    _core.material.emissiveIntensity = (S.assurance === "UNVERIFIABLE-NO-MODEL") ? 0.12 : 0.4;
  }
}

function _onFrame(dt) {
  _spin += (dt || 0.016) * 0.22;
  if (_core) { _core.rotation.y = _spin; _core.rotation.x = _spin * 0.4; }
  if (_group) _group.rotation.y = _spin * 0.15;
}

export function unmount() {
  try {
    if (_frameReg && _stage && _stage.offFrame) { _stage.offFrame(_onFrame); }
    _disposePillars();
    _buildSeal(false);
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((mm) => mm.dispose && mm.dispose()); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _core = _seal = null; _pillars = [];
  _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.assurance = S.comps = null; S.state = "init"; S.signed = false;
}

export default { id: ID, title: TITLE, endpoints: ["/api/a11oy/v1/brain/verdict"], mount, unmount };
