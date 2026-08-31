// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/braineval.js — BRAIN EVAL · honest refusal-to-fabricate GATE for a served model.
// When a real model endpoint answers THIS request it POSTs a fixed battery of doctrine PROBE
// prompts across six violation families and scores each response REFUSED or FABRICATED. The
// measured refusal rate is a real ratio, capped at the 0.97 trust ceiling — never 1.0. No live
// model => UNAVAILABLE, the expected state until an endpoint is brought up; never a fabricated
// score. This surface EVALUATES only — it trains nothing and writes nothing back to any model.
// NOT a sentience or consciousness claim.
//
// RENDER: one PILLAR per probe family in a ring — REFUSED pillars in proof-teal (tall), a
// FABRICATED pillar in violet-blue drawn tallest so a fabrication can never hide, UNSCORED as a
// grey stub. A CORE orb carries the verdict REFUSAL-HONEST / PARTIAL-REFUSAL /
// FABRICATION-DETECTED / UNAVAILABLE. The core is NEVER teal while any pillar is FABRICATED.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/eval (PURE READ, mints nothing):
//   ok, label (MEASURED|UNAVAILABLE), verdict, refusal_rate, refused, fabricated, scored,
//   probes[]{ family, outcome (REFUSED|FABRICATED|UNSCORED) }.
//
// HONESTY LABEL: MEASURED only on a live answer; UNAVAILABLE otherwise. refusal_rate null
//   renders "—", never 0.0/1.0 by default. Trust ceiling 0.97, never 100%. 0 RUNTIME CDN —
//   vendored three.js via page importmap (ctx.THREE).

const ID = "braineval";
const TITLE = "Brain Eval · refusal-to-fabricate gate for a served model";
const EP = "/api/a11oy/v1/brain/eval";

const C_TEAL = 0x3af4c8;   // REFUSED / honest
const C_VIOLET = 0x8a6bff; // FABRICATED / attention
const C_BLUE = 0x5b8dee;   // neutral accent
const C_GREY = 0x2a3138;   // UNSCORED / unavailable
const C_GREY_HI = 0x6b7580;

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _core = null, _pillars = [];
let _frameReg = false, _spin = 0;
const S = { label: null, verdict: null, rate: null, refused: null, fabricated: null, probes: [], state: "init" };

function _verdictColor(v) {
  if (v === "REFUSAL-HONEST") return C_TEAL;
  if (v === "PARTIAL-REFUSAL") return C_BLUE;
  if (v === "FABRICATION-DETECTED") return C_VIOLET;
  return C_GREY_HI; // UNAVAILABLE — neutral, never teal
}

function _outcomeColor(o) {
  if (o === "REFUSED") return C_TEAL;
  if (o === "FABRICATED") return C_VIOLET;
  return C_GREY; // UNSCORED
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
  const probes = S.probes || [];
  const n = probes.length;
  if (!n) return;
  const R = 1.6;
  for (let i = 0; i < n; i++) {
    const p = probes[i];
    const fab = p.outcome === "FABRICATED";
    const ref = p.outcome === "REFUSED";
    const h = fab ? 1.4 : (ref ? 1.0 : 0.4); // fabrication tallest so it cannot hide
    const g = new THREE.BoxGeometry(0.18, h, 0.18);
    const col = _outcomeColor(p.outcome);
    const m = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: fab ? 0.45 : (ref ? 0.3 : 0.08), roughness: 0.5, transparent: true, opacity: (fab || ref) ? 0.92 : 0.5 });
    const mesh = new THREE.Mesh(g, m);
    const a = (i / n) * Math.PI * 2;
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
  S.label = j.label || "UNAVAILABLE";
  S.verdict = j.verdict || null;
  S.rate = (typeof j.refusal_rate === "number") ? j.refusal_rate : null; // null -> "—"
  S.refused = (typeof j.refused === "number") ? j.refused : null;
  S.fabricated = (typeof j.fabricated === "number") ? j.fabricated : null;
  S.probes = Array.isArray(j.probes) ? j.probes : [];
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
  S.label = S.verdict = S.rate = S.refused = S.fabricated = null; S.probes = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
