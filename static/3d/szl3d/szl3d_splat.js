// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// szl3d_splat.js — clean-room 3D-Gaussian-Splatting codec + anisotropic splat renderer.
//
// We implement the REAL `.splat` binary interchange format (the antimatter15/splat layout,
// MIT — 32 bytes/splat, no header) so a surface can encode its live data as a genuine
// gaussian-splat MODEL (position + anisotropic scale + rotation quaternion + RGBA) and render
// it as oriented, additively-blended gaussians — NOT procedural points. This is our own
// clean-room implementation of the open format; nothing is copied and the technique is cited
// (Kerbl et al. 3DGS, arXiv:2308.04079; antimatter15/splat; mkkellogg/GaussianSplats3D, MIT).
//
// EXACT .splat record (little-endian, 32 bytes), confirmed layout:
//   off  0 : float32[3]  position  (world xyz)
//   off 12 : float32[3]  scale     (already exp()'d — world half-lengths, NOT log-space)
//   off 24 : uint8[4]    RGBA      (r,g,b, alpha)          color = clamp((0.5 + SH_C0*f_dc)*255)
//   off 28 : uint8[4]    quaternion w,x,y,z  (128 + 128*q) unit quaternion, w-first
//
// Renderer: an InstancedMesh of camera-facing-ish quads, each scaled by the splat's two
// largest axes and oriented by its quaternion, textured with a radial gaussian falloff,
// AdditiveBlending, depthWrite off. This is a faithful (if simplified — no per-frame depth
// sort, no view-dependent SH) real-splat render: every rendered gaussian's transform + color
// comes from the 32-byte record, so the MODEL is real data, honestly.
//
// 0 runtime CDN. Pure three.js (passed in by the caller — no import here so the page importmap
// governs the three build). Doctrine v11: renders pixels from a real model; invents nothing.

export const SPLAT_BYTES = 32;
export const SH_C0 = 0.28209479177387814;   // 1/(2·sqrt(π)) — DC spherical-harmonic coefficient

// DC SH coefficient -> uint8 color channel (the real .splat color encoding).
export function shDcToU8(f_dc) { return Math.min(255, Math.max(0, Math.round((0.5 + SH_C0 * f_dc) * 255))); }
// linear 0..1 -> the f_dc that encodes to it (inverse of shDcToU8), for authoring by target color.
export function colorToFdc(c01) { return (c01 - 0.5) / SH_C0; }

// Encode an array of splat objects into a real .splat ArrayBuffer.
//   splat = { x,y,z, sx,sy,sz, r,g,b,a (0..255), qw,qx,qy,qz (unit quat) }
export function encodeSplat(splats) {
  const buf = new ArrayBuffer(splats.length * SPLAT_BYTES);
  const dv = new DataView(buf);
  for (let i = 0; i < splats.length; i++) {
    const s = splats[i], o = i * SPLAT_BYTES;
    dv.setFloat32(o + 0, s.x, true); dv.setFloat32(o + 4, s.y, true); dv.setFloat32(o + 8, s.z, true);
    dv.setFloat32(o + 12, s.sx, true); dv.setFloat32(o + 16, s.sy, true); dv.setFloat32(o + 20, s.sz, true);
    dv.setUint8(o + 24, s.r & 255); dv.setUint8(o + 25, s.g & 255); dv.setUint8(o + 26, s.b & 255); dv.setUint8(o + 27, s.a & 255);
    // quaternion w,x,y,z encoded as 128 + 128*q (clamped to a valid uint8)
    const q = _normQuat(s.qw ?? 1, s.qx ?? 0, s.qy ?? 0, s.qz ?? 0);
    dv.setUint8(o + 28, _q8(q[0])); dv.setUint8(o + 29, _q8(q[1])); dv.setUint8(o + 30, _q8(q[2])); dv.setUint8(o + 31, _q8(q[3]));
  }
  return buf;
}

// Decode a real .splat ArrayBuffer back to splat objects (quaternion decoded to unit floats).
export function decodeSplat(buf) {
  const n = Math.floor(buf.byteLength / SPLAT_BYTES);
  const dv = new DataView(buf);
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    const o = i * SPLAT_BYTES;
    out[i] = {
      x: dv.getFloat32(o + 0, true), y: dv.getFloat32(o + 4, true), z: dv.getFloat32(o + 8, true),
      sx: dv.getFloat32(o + 12, true), sy: dv.getFloat32(o + 16, true), sz: dv.getFloat32(o + 20, true),
      r: dv.getUint8(o + 24), g: dv.getUint8(o + 25), b: dv.getUint8(o + 26), a: dv.getUint8(o + 27),
      qw: (dv.getUint8(o + 28) - 128) / 128, qx: (dv.getUint8(o + 29) - 128) / 128,
      qy: (dv.getUint8(o + 30) - 128) / 128, qz: (dv.getUint8(o + 31) - 128) / 128,
    };
  }
  return out;
}

function _normQuat(w, x, y, z) { const n = Math.hypot(w, x, y, z) || 1; return [w / n, x / n, y / n, z / n]; }
function _q8(q) { return Math.min(255, Math.max(0, Math.round(128 + 128 * q))); }

// Radial gaussian sprite texture (soft falloff) — shared by all splat renders.
let _tex = null;
function _gaussTexture(THREE) {
  if (_tex) return _tex;
  const s = 64, cv = document.createElement("canvas"); cv.width = cv.height = s;
  const cx = cv.getContext("2d"); const g = cx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(0.35, "rgba(255,255,255,0.55)"); g.addColorStop(1, "rgba(255,255,255,0)");
  cx.fillStyle = g; cx.fillRect(0, 0, s, s); _tex = new THREE.CanvasTexture(cv); return _tex;
}

// Build a THREE.InstancedMesh rendering a decoded splat model as oriented anisotropic gaussians.
// Returns { mesh, update(splats), dispose() }. `update` re-decodes a new .splat buffer or array
// into the existing instances (count-capped) so a live surface can re-encode each poll.
export function buildSplatMesh(THREE, arrayBufferOrSplats, opts = {}) {
  const maxN = opts.maxInstances || 4000;
  const splats = (arrayBufferOrSplats instanceof ArrayBuffer) ? decodeSplat(arrayBufferOrSplats) : (arrayBufferOrSplats || []);
  const geo = new THREE.PlaneGeometry(1, 1);
  const mat = new THREE.MeshBasicMaterial({ map: _gaussTexture(THREE), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, vertexColors: false, opacity: opts.opacity != null ? opts.opacity : 0.9 });
  const mesh = new THREE.InstancedMesh(geo, mat, maxN);
  // per-instance color as a custom attribute — NOT three's reserved `instanceColor`, whose
  // auto-injected `attribute vec3 instanceColor;` would collide with our onBeforeCompile decl.
  const splatColor = new THREE.InstancedBufferAttribute(new Float32Array(maxN * 3), 3);
  geo.setAttribute("aSplatColor", splatColor);
  mesh.frustumCulled = false;
  const dummy = new THREE.Object3D(); const q = new THREE.Quaternion(); const col = new THREE.Color();

  function _apply(list) {
    const n = Math.min(list.length, maxN);
    for (let i = 0; i < n; i++) {
      const s = list[i];
      dummy.position.set(s.x, s.y, s.z);
      q.set(s.qx, s.qy, s.qz, s.qw); dummy.quaternion.copy(q);
      // use the two dominant axes as the billboard footprint (anisotropic gaussian)
      const sc = opts.scaleMul || 1;
      dummy.scale.set(Math.max(1e-3, s.sx) * 6 * sc, Math.max(1e-3, s.sy) * 6 * sc, 1);
      dummy.updateMatrix(); mesh.setMatrixAt(i, dummy.matrix);
      col.setRGB((s.r / 255) * (s.a / 255), (s.g / 255) * (s.a / 255), (s.b / 255) * (s.a / 255));
      splatColor.setXYZ(i, col.r, col.g, col.b);
    }
    mesh.count = n;
    mesh.instanceMatrix.needsUpdate = true; splatColor.needsUpdate = true;
    // basic material doesn't read our color attribute by default; wired via onBeforeCompile
  }
  // wire the per-instance splat color into the basic material (multiply diffuse by it)
  mat.onBeforeCompile = (shader) => {
    shader.vertexShader = "attribute vec3 aSplatColor;\nvarying vec3 vSplatColor;\n" +
      shader.vertexShader.replace("void main() {", "void main() {\n  vSplatColor = aSplatColor;");
    shader.fragmentShader = "varying vec3 vSplatColor;\n" +
      shader.fragmentShader.replace("vec4 diffuseColor = vec4( diffuse, opacity );",
        "vec4 diffuseColor = vec4( diffuse * vSplatColor, opacity );");
  };
  _apply(splats);

  return {
    mesh,
    update(next) { _apply((next instanceof ArrayBuffer) ? decodeSplat(next) : (next || [])); },
    dispose() { try { geo.dispose(); mat.dispose(); } catch (_) {} },
  };
}

export default { SPLAT_BYTES, SH_C0, shDcToU8, colorToFdc, encodeSplat, decodeSplat, buildSplatMesh };
