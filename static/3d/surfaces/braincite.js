// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/braincite.js — BRAIN CITE · verifiable claim→source citations for brain answers.
// For a query it runs the SAME honest brain retrieval every sibling uses and binds each
// candidate claim term to the source node(s) whose title actually contains it. A claim with a
// real backing node is CITED; a claim with none is UNCITED and is NEVER given a fabricated
// citation — so an answer can never present an uncited claim as sourced. Pure knowledge-graph
// honesty; it advances NO detection / fusion / effector / targeting capability. NOT model
// training. NOT a sentience or consciousness claim.
//
// RENDER: one PILLAR per claim term in a ring — CITED pillars in proof-teal, UNCITED pillars
// in grey (drawn plainly, never dressed up as cited). A CORE orb carries the overall verdict
// FULLY-CITED / PARTIALLY-CITED / UNCITED-DOMINANT / NO-CITABLE-CLAIMS. The core is NEVER teal
// while any pillar is UNCITED and the verdict is not FULLY-CITED.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/cite (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, citation_coverage, cited_count, total_claims,
//   claims[]{ claim, status (CITED|UNCITED), sources[]{id,title,url,node_label} }.
//
// HONESTY LABEL: MODELED — a derived binding view over a real retrieval, never a MEASURED
//   quantity. citation_coverage null renders "—", never 0.0/1.0 by default. Trust ceiling 0.97,
//   never 100%. 0 RUNTIME CDN — vendored three.js via page importmap (ctx.THREE).

const ID = "braincite";
const TITLE = "Brain Cite · verifiable claim→source citations";
const EP = "/api/a11oy/v1/brain/cite";

// Approved hue palette only (lattice-blue, violet-blue, proof-teal + greys).
const C_TEAL = 0x3af4c8;   // CITED / FULLY-CITED
const C_VIOLET = 0x8a6bff; // partial / attention
const C_BLUE = 0x5b8dee;   // neutral accent
const C_GREY = 0x2a3138;   // UNCITED / stubs
const C_GREY_HI = 0x6b7580;

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _core = null, _pillars = [];
let _frameReg = false, _spin = 0;
const S = { label: null, verdict: null, coverage: null, cited: null, total: null, claims: [], state: "init" };

function _verdictColor(v) {
  if (v === "FULLY-CITED") return C_TEAL;
  if (v === "PARTIALLY-CITED") return C_VIOLET;
  if (v === "UNCITED-DOMINANT") return C_GREY_HI;
  return C_BLUE; // NO-CITABLE-CLAIMS or unknown — neutral, never teal
}

function _claimColor(status) {
  return status === "CITED" ? C_TEAL : C_GREY;
}

export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _buildFloor();
  _buildCore();
  _stage.scene.add(_group);
  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }
  _fetch();
}

function _buildFloor() {
  const THREE = _THREE;
  const g = new THREE.RingGeometry(2.2, 2.35, 64);
  const m = new THREE.MeshBasicMaterial({ color: C_BLUE, transparent: true, opacity: 0.18, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(g, m);
  ring.rotation.x = -Math.PI / 2;
  _group.add(ring);
}

function _buildCore() {
  const THREE = _THREE;
  const g = new THREE.IcosahedronGeometry(0.55, 1);
  const m = new THREE.MeshStandardMaterial({ color: C_BLUE, emissive: C_BLUE, emissiveIntensity: 0.35, roughness: 0.4, metalness: 0.1, transparent: true, opacity: 0.9 });
  _core = new THREE.Mesh(g, m);
  _group.add(_core);
}

function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();
  const claims = S.claims || [];
  const n = claims.length;
  if (!n) return;
  const R = 1.6;
  for (let i = 0; i < n; i++) {
    const c = claims[i];
    const cited = c.status === "CITED";
    const h = cited ? 1.1 : 0.5; // cited pillars taller; uncited plainly short (never inflated)
    const g = new THREE.BoxGeometry(0.16, h, 0.16);
    const col = _claimColor(c.status);
    const m = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: cited ? 0.3 : 0.08, roughness: 0.5, transparent: true, opacity: cited ? 0.92 : 0.55 });
    const mesh = new THREE.Mesh(g, m);
    const a = (i / n) * Math.PI * 2;
    mesh.position.set(Math.cos(a) * R, h / 2, Math.sin(a) * R);
    _group.add(mesh);
    _pillars.push(mesh);
  }
}

function _disposePillars() {
  const THREE = _THREE;
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
  S.label = j.label || "MODELED";
  S.verdict = j.verdict || null;
  // null coverage stays null — rendered "—", never 0.0 and never 1.0 by default.
  S.coverage = (typeof j.citation_coverage === "number") ? j.citation_coverage : null;
  S.cited = (typeof j.cited_count === "number") ? j.cited_count : null;
  S.total = (typeof j.total_claims === "number") ? j.total_claims : null;
  S.claims = Array.isArray(j.claims) ? j.claims : [];
  S.state = "ready";
  _buildPillars();
  if (_core && _core.material) {
    const col = _verdictColor(S.verdict);
    _core.material.color.setHex(col);
    _core.material.emissive.setHex(col);
  }
}

function _onFrame(dt) {
  _spin += (dt || 0.016) * 0.2;
  if (_group) _group.rotation.y = _spin;
  if (_core) _core.rotation.x = _spin * 0.7;
}

export function unmount() {
  try {
    if (_frameReg && _stage && _stage.offFrame) { _stage.offFrame(_onFrame); }
    _disposePillars();
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((mm) => mm.dispose && mm.dispose()); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _core = null; _pillars = [];
  _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.coverage = S.cited = S.total = null; S.claims = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
