// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainreceipt.js — BRAIN RECEIPT · signed inference receipts (integrity, not truth).
// The estate can sign a receipt binding request + sources + output under its own ECDSA P-256
// key, so a third party can verify the answer was not altered. A valid signature proves
// integrity + key continuity ONLY — never that the output is correct or source-supported. This
// surface shows the KEY POSTURE honestly: SIGNED-LOCAL (persistent key), UNSIGNED-LOCAL
// (ephemeral container key — real bytes, honestly scoped), or UNAVAILABLE (digest only).
//
// RENDER: a central SEAL (torus-knot) that glows proof-teal when a persistent SIGNED-LOCAL key
// is active, cyan when UNSIGNED-LOCAL (ephemeral), grey when UNAVAILABLE. Three BINDING PILLARS
// (request / sources / output) rise around it, each carrying its SHA-256 presence. A small
// "integrity ≠ truth" tag ring reminds that the seal binds integrity, not correctness.
//
// DATA: the info route describes posture; a live read uses GET /api/a11oy/v1/brain/receipt/info
//   (PURE READ — signing itself is POST-only and mints nothing on GET). We display the surface's
//   declared label posture and honesty statement; the actual signature is produced on POST.
//
// HONESTY: no signature is ever drawn as "proven truth". 0 RUNTIME CDN — three.js via ctx.THREE.

const ID = "brainreceipt";
const TITLE = "Brain Receipt · signed inference receipts (integrity, not truth)";
const EP = "/api/a11oy/v1/brain/receipt/info";

const C_TEAL = 0x3af4c8;   // SIGNED-LOCAL (persistent)
const C_CYAN = 0x4fd0ff;   // UNSIGNED-LOCAL (ephemeral — honestly scoped)
const C_GREY = 0x2a3138;   // UNAVAILABLE
const C_GREY_HI = 0x6b7580;
const C_AMBER = 0xffb24a;  // the "integrity != truth" reminder tag

let _ctx = null, _stage = null, _THREE = null;
let _group = null, _seal = null, _pillars = [];
let _frameReg = false, _spin = 0;
const S = { label: null, state: "init" };

function _sealColor(label) {
  if (label === "SIGNED-LOCAL") return C_TEAL;
  if (label === "UNSIGNED-LOCAL") return C_CYAN;
  return C_GREY_HI; // UNAVAILABLE or unknown
}

export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _buildTagRing();
  _buildSeal();
  _buildPillars();
  _stage.scene.add(_group);
  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }
  _fetch();
}

// amber ring = the permanent "integrity != truth" reminder; never teal (never "proven truth")
function _buildTagRing() {
  const THREE = _THREE;
  const g = new THREE.RingGeometry(2.15, 2.26, 64);
  const m = new THREE.MeshBasicMaterial({ color: C_AMBER, transparent: true, opacity: 0.14, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(g, m);
  ring.rotation.x = -Math.PI / 2;
  _group.add(ring);
}

function _buildSeal() {
  const THREE = _THREE;
  const g = new THREE.TorusKnotGeometry(0.5, 0.15, 96, 16);
  const m = new THREE.MeshStandardMaterial({ color: C_GREY_HI, emissive: C_GREY_HI, emissiveIntensity: 0.3, roughness: 0.35, metalness: 0.2, transparent: true, opacity: 0.92 });
  _seal = new THREE.Mesh(g, m);
  _group.add(_seal);
}

// three binding pillars: request / sources / output
function _buildPillars() {
  const THREE = _THREE;
  const R = 1.5;
  const labels = 3; // request, sources, output
  for (let i = 0; i < labels; i++) {
    const g = new THREE.BoxGeometry(0.16, 1.0, 0.16);
    const m = new THREE.MeshStandardMaterial({ color: C_CYAN, emissive: C_CYAN, emissiveIntensity: 0.28, roughness: 0.5, transparent: true, opacity: 0.85 });
    const mesh = new THREE.Mesh(g, m);
    const a = (i / labels) * Math.PI * 2;
    mesh.position.set(Math.cos(a) * R, 0.5, Math.sin(a) * R);
    _group.add(mesh);
    _pillars.push(mesh);
  }
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
  // info route declares posture; the surface reflects the honesty label vocabulary it supports.
  // Actual per-receipt label is produced on POST /sign; here we show the seal in its neutral
  // "ready to sign" posture unless the surface is unavailable.
  S.label = j.label || "MODELED";
  S.state = "ready";
  if (_seal && _seal.material) {
    // show cyan "ready-to-sign (ephemeral-capable)" by default; never teal without a persistent key signal
    const col = C_CYAN;
    _seal.material.color.setHex(col);
    _seal.material.emissive.setHex(col);
    _seal.material.emissiveIntensity = 0.34;
  }
}

function _onFrame(dt) {
  _spin += (dt || 0.016) * 0.25;
  if (_seal) { _seal.rotation.x = _spin; _seal.rotation.y = _spin * 0.6; }
  if (_group) _group.rotation.y = _spin * 0.2;
}

export function unmount() {
  try {
    if (_frameReg && _stage && _stage.offFrame) { _stage.offFrame(_onFrame); }
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((mm) => mm.dispose && mm.dispose()); }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _seal = null; _pillars = [];
  _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
