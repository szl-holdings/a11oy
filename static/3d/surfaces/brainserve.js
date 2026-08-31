// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainserve.js — BRAIN SERVE · governed bridge to the estate's own served brain model.
// Calls the committed SZL-Khipu inference Space, verifies the served model's self-reported
// provenance against the pinned expectation, and shows a MEASURED reading when the model answers
// THIS request — surfacing the unsigned/receipt caveats rather than hiding them. No answer =>
// UNAVAILABLE, never a fabricated reading. Serves/bridges only: no training, no gradients, not
// a sentience claim.
//
// RENDER: a central MODEL CORE (icosahedron) that glows proof-teal when SERVING-EXPECTED, amber
// when PROVENANCE-MISMATCH, grey when UNAVAILABLE. A ring of PROVENANCE CHIPS orbits it, one per
// honesty field (repo, revision, sha256, signature, receipts-cover-output, service-level). A chip
// is teal when its value is present/expected and amber when it carries a caveat (UNSIGNED, or
// receipts NOT covering the output) — the caveats are drawn, never hidden.
//
// DATA: GET /api/a11oy/v1/brain/serve (PURE READ, mints nothing):
//   ok, label (MEASURED|UNAVAILABLE), verdict, answered, provenance_matches_expected,
//   served_model_id, provenance{reported_repo, reported_revision, reported_sha256,
//   output_signature_status, receipts_cover_this_output, service_level}.
//
// HONESTY LABEL: MEASURED only on a live answer; UNAVAILABLE otherwise. UNSIGNED stays UNSIGNED;
//   a receipt that does not cover the output is shown as a caveat, never as "proven". 0 RUNTIME
//   CDN — vendored three.js via page importmap (ctx.THREE).

const ID = "brainserve";
const TITLE = "Brain Serve · governed bridge to the estate's served brain model";
const EP = "/api/a11oy/v1/brain/serve";

const C_TEAL = 0x3af4c8;   // serving / expected / present
const C_AMBER = 0xffb24a;  // caveat / mismatch (UNSIGNED, receipts not covering output)
const C_GREY = 0x2a3138;   // unavailable
const C_GREY_HI = 0x6b7580;

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _core = null, _chips = [];
let _frameReg = false, _spin = 0;
const S = { label: null, verdict: null, prov: null, matches: null, state: "init" };

function _coreColor(v) {
  if (v === "SERVING-EXPECTED") return C_TEAL;
  if (v === "PROVENANCE-MISMATCH") return C_AMBER;
  return C_GREY_HI; // UNAVAILABLE
}

export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _buildRing();
  _buildCore();
  _stage.scene.add(_group);
  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }
  _fetch();
}

function _buildRing() {
  const THREE = _THREE;
  const g = new THREE.RingGeometry(2.1, 2.24, 64);
  const m = new THREE.MeshBasicMaterial({ color: C_TEAL, transparent: true, opacity: 0.16, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(g, m);
  ring.rotation.x = -Math.PI / 2;
  _group.add(ring);
}

function _buildCore() {
  const THREE = _THREE;
  const g = new THREE.IcosahedronGeometry(0.62, 1);
  const m = new THREE.MeshStandardMaterial({ color: C_GREY_HI, emissive: C_GREY_HI, emissiveIntensity: 0.3, roughness: 0.4, metalness: 0.15, transparent: true, opacity: 0.92 });
  _core = new THREE.Mesh(g, m);
  _group.add(_core);
}

// One chip per honesty field. `caveat` true => amber (drawn, never hidden).
function _chipSpec() {
  const p = S.prov || {};
  const specs = [
    { key: "repo", ok: !!p.reported_repo },
    { key: "revision", ok: !!p.reported_revision },
    { key: "sha256", ok: !!p.reported_sha256 },
    // UNSIGNED is a caveat, shown amber — never presented as proven
    { key: "signature", ok: (p.output_signature_status && p.output_signature_status !== "UNSIGNED"), caveat: p.output_signature_status === "UNSIGNED" },
    // receipts NOT covering this output is a caveat, shown amber
    { key: "receipts", ok: p.receipts_cover_this_output === true, caveat: p.receipts_cover_this_output === false },
    { key: "sla", ok: !!p.service_level, caveat: p.service_level === "BEST_EFFORT_NO_SLA" },
  ];
  return specs;
}

function _buildChips() {
  const THREE = _THREE;
  _disposeChips();
  const specs = _chipSpec();
  const n = specs.length;
  const R = 1.5;
  for (let i = 0; i < n; i++) {
    const sp = specs[i];
    const col = sp.caveat ? C_AMBER : (sp.ok ? C_TEAL : C_GREY);
    const g = new THREE.BoxGeometry(0.34, 0.34, 0.08);
    const m = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: sp.caveat ? 0.4 : (sp.ok ? 0.32 : 0.08), roughness: 0.5, transparent: true, opacity: (sp.ok || sp.caveat) ? 0.92 : 0.45 });
    const mesh = new THREE.Mesh(g, m);
    const a = (i / n) * Math.PI * 2;
    mesh.position.set(Math.cos(a) * R, 0.34, Math.sin(a) * R);
    mesh.lookAt(0, 0.34, 0);
    _group.add(mesh);
    _chips.push(mesh);
  }
}

function _disposeChips() {
  _chips.forEach((o) => {
    if (o.parent) o.parent.remove(o);
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
  });
  _chips = [];
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
  S.label = j.label || "UNAVAILABLE";
  S.verdict = j.verdict || null;
  S.matches = j.provenance_matches_expected;
  S.prov = (j.provenance && typeof j.provenance === "object") ? j.provenance : {};
  S.state = "ready";
  _buildChips();
  if (_core && _core.material) {
    const col = _coreColor(S.verdict);
    _core.material.color.setHex(col);
    _core.material.emissive.setHex(col);
    _core.material.emissiveIntensity = (S.verdict === "UNAVAILABLE") ? 0.12 : 0.4;
  }
}

function _onFrame(dt) {
  _spin += (dt || 0.016) * 0.22;
  if (_group) _group.rotation.y = _spin;
  if (_core) _core.rotation.y = _spin * 0.6;
}

export function unmount() {
  try {
    if (_frameReg && _stage && _stage.offFrame) { _stage.offFrame(_onFrame); }
    _disposeChips();
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((mm) => mm.dispose && mm.dispose()); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _core = null; _chips = [];
  _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.prov = S.matches = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
