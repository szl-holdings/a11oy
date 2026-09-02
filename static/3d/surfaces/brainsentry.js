// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainsentry.js — BRAIN SENTRY · defensive-cyber signal triage (blue-team).
// Scores and ranks raw security signals (log lines, alerts, indicators) by transparent,
// auditable defensive rules so an analyst reviews the riskiest first. RANKS and EXPLAINS only —
// takes no action, blocks nothing, attacks nothing. Defensive posture, not offensive, not
// counter-UAS. A score is a MODELED sum of transparent rule weights; no signals => UNAVAILABLE.
//
// RENDER: a triage TOWER of stacked signal bars, tallest/most-saturated = highest review
// priority. Bar color = priority (red-orange CRITICAL, amber HIGH, cyan MEDIUM, teal LOW, grey
// INFORMATIONAL). A base plate shows the defensive posture. Because the info route lists the rule
// families (not live signals), the surface renders the rule-family lattice as its resting state
// and a legend of priority buckets.
//
// DATA: GET /api/a11oy/v1/brain/sentry/info (PURE READ, mints nothing) — rule families +
// priorities. Live triage is POST /sentry/triage with a signals[] batch (not called from the
// passive 3D view). HONESTY: never claims malice; human adjudicates. 0 RUNTIME CDN via ctx.THREE.

const ID = "brainsentry";
const TITLE = "Brain Sentry · defensive-cyber signal triage (blue-team)";
const EP = "/api/a11oy/v1/brain/sentry/info";

const C_CRIT = 0xff6a3d;   // REVIEW-CRITICAL
const C_HIGH = 0xffb24a;   // REVIEW-HIGH
const C_MED = 0x4fd0ff;    // REVIEW-MEDIUM
const C_LOW = 0x3af4c8;    // REVIEW-LOW
const C_INFO = 0x6b7580;   // INFORMATIONAL
const C_BASE = 0x2a3138;

const PRI_COLORS = [C_CRIT, C_HIGH, C_MED, C_LOW, C_INFO];

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _bars = [], _base = null;
let _frameReg = false, _spin = 0;
const S = { rules: null, state: "init" };

export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _buildBase();
  _stage.scene.add(_group);
  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }
  _fetch();
}

function _buildBase() {
  const THREE = _THREE;
  const g = new THREE.CylinderGeometry(2.0, 2.1, 0.12, 48);
  const m = new THREE.MeshStandardMaterial({ color: C_BASE, emissive: C_LOW, emissiveIntensity: 0.06, roughness: 0.6, transparent: true, opacity: 0.85 });
  _base = new THREE.Mesh(g, m);
  _base.position.y = -0.06;
  _group.add(_base);
}

// one bar per rule family, arranged in a ring; height = rule weight (transparent, auditable)
function _buildBars(rules) {
  const THREE = _THREE;
  _disposeBars();
  const n = rules.length;
  if (!n) return;
  const R = 1.45;
  for (let i = 0; i < n; i++) {
    const w = Math.max(1, Number(rules[i].weight) || 1);
    const h = 0.35 + w * 0.22; // weight -> height (higher weight = more severe family)
    // color by weight bucket (mirrors priority thresholds)
    const col = w >= 5 ? C_CRIT : (w >= 4 ? C_HIGH : (w >= 3 ? C_MED : C_LOW));
    const g = new THREE.BoxGeometry(0.2, h, 0.2);
    const m = new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: 0.3, roughness: 0.5, transparent: true, opacity: 0.9 });
    const bar = new THREE.Mesh(g, m);
    const a = (i / n) * Math.PI * 2;
    bar.position.set(Math.cos(a) * R, h / 2, Math.sin(a) * R);
    _group.add(bar);
    _bars.push(bar);
  }
}

function _disposeBars() {
  _bars.forEach((o) => {
    if (o.parent) o.parent.remove(o);
    if (o.geometry && o.geometry.dispose) o.geometry.dispose();
    if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
  });
  _bars = [];
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
  S.rules = Array.isArray(j.rule_families) ? j.rule_families : [];
  S.state = "ready";
  _buildBars(S.rules);
}

function _onFrame(dt) {
  _spin += (dt || 0.016) * 0.2;
  if (_group) _group.rotation.y = _spin;
}

export function unmount() {
  try {
    if (_frameReg && _stage && _stage.offFrame) { _stage.offFrame(_onFrame); }
    _disposeBars();
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((mm) => mm.dispose && mm.dispose()); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _base = null; _bars = [];
  _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.rules = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
