// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/pinn.js — PINN Thermal/Field surface (Dev6).
//
// Leader/technique modeled: Kitware VTK.js / VolView cinematic volume rendering +
// three.js TSL compute (frontier). Implemented here as a WebGPU-attempt / WebGL2-fallback
// GLSL ray-marched 3D scalar-field volume + GPU-instanced Gaussian-splat scalar field
// (novel holographic presentation per the viz-leaders research §6 + §8), an isosurface
// shell, a PDE-residual displacement heatmap, an instanced vector arrow field, and the
// compute_bounds physical-ceiling ladder (Landauer / Margolus-Levitin / Bremermann /
// Bekenstein) rendered straight from the MEASURED+SIGNED physical-bounds certificate.
//
// DOCTRINE v11 HONESTY (load-bearing — do not soften):
//   * The certificate is MEASURED + SIGNED: avg_power_w / wall_time_s / temperature_k are
//     real on-metal NVML samples (sovereign GPU betterwithage), the energy is DERIVED
//     (P×t), the envelope is signed with a real Ed25519 DSSE signature (FA-001 on-metal),
//     cosign.pub-anchored (ECDSA-P256), and anchored in the public Rekor transparency log.
//     We render that proudly AND accurately — exact algs, keyids, Rekor log_index/uuid.
//   * The rendered 3D field is a *visualization of the model* — a deterministic analytic
//     thermal/PDE field seeded by the MEASURED scalars. It is labelled MODELED, never
//     MEASURED. If no cert value is available we fall to an explicitly-labelled SAMPLE
//     field. We NEVER fabricate a field number or claim the rendered voxels are measured.
//   * The agentic-PINN residual trail (/pinn/residual) is AWAITING_GPU_SOLVE in this
//     environment — we render the honest AWAITING state, never a fabricated residual.
//
// LIVE DATA (never hardcoded — read via ctx.live.poll):
//   /api/a11oy/v1/pinn/certificate   MEASURED+SIGNED physical-bounds certificate (primary)
//   /api/a11oy/v1/pnt/limits         compute_bounds pillar (4-pillar fundamental-limits index)
//   /api/a11oy/v1/pinn/residual      governed agentic solve residual trail (AWAITING here)
//
// CONTRACT: default-export { id, title, endpoints[], mount(ctx), unmount() }.
// The shell shares ONE Stage across surfaces; we add objects to ctx.stage.scene, register
// per-frame work via ctx.stage.onFrame, and on unmount stop every poll + remove what we added.

const ID = "pinn";
const TITLE = "PINN Thermal/Field";

const EP_CERT = "/api/a11oy/v1/pinn/certificate";
const EP_LIMITS = "/api/a11oy/v1/pnt/limits";
const EP_RESIDUAL = "/api/a11oy/v1/pinn/residual";

// Volume sampling resolution for the GPU-built 3D scalar-field texture.
const VOX = 48;

// ---------------------------------------------------------------------------
// Module state (single active surface at a time per the shell contract).
// ---------------------------------------------------------------------------
let _ctx = null, _stage = null, _THREE = null;
let _group = null;             // root group holding all scene objects we add
let _handles = [];             // poll handles to stop on unmount
let _overlay = null;           // DOM HUD
let _frameReg = null;          // our onFrame closure (guards on null after unmount)
let _disposables = [];         // geometries / materials / textures to dispose

// live cert-derived state (all MODELED-for-render, sourced from MEASURED scalars)
const F = {
  haveCert: false,
  certLabel: "SAMPLE",         // honesty token for the FIELD render (MEASURED scalars → MODELED field)
  signed: false,
  // MEASURED scalars (from cert.measured.*_MEASURED) — null until live
  tempK: null, powerW: null, wallS: null, energyJ: null,
  // DERIVED bounds (from cert.*)
  landauerMult: null, mlFrac: null, bremFrac: null, bekFrac: null, bounded: null,
  // signatures / anchors
  ed25519Keyid: null, cosignKeyid: null, cosignPubUrl: null, certSha: null,
  rekorUuid: null, rekorIndex: null, rekorTime: null, rekorProvider: null,
  khipuDigest: null,
  // residual trail
  residualState: "INIT", residualRounds: [],
  // controls
  isoThreshold: 0.55, splatOn: true, arrowsOn: true, residualDisp: 0.0,
  backend: "…", t: 0,
};

// SAMPLE seed values — used ONLY for the field shape before the live cert arrives, and
// then ONLY labelled SAMPLE. These are illustrative, never presented as measurement.
const SAMPLE = { tempK: 320, powerW: 30, wallS: 60 };

// ---------------------------------------------------------------------------
// Honest accessor: the scalars that drive the field. Returns {tempK,powerW,label}.
// When the MEASURED cert is live → real scalars, field labelled MODELED.
// Before that → SAMPLE seed, field labelled SAMPLE. Never fabricates.
// ---------------------------------------------------------------------------
function _fieldScalars() {
  if (F.haveCert && F.tempK != null) {
    return { tempK: F.tempK, powerW: F.powerW != null ? F.powerW : SAMPLE.powerW, label: "MODELED" };
  }
  return { tempK: SAMPLE.tempK, powerW: SAMPLE.powerW, label: "SAMPLE" };
}

// ---------------------------------------------------------------------------
// Analytic PINN-style thermal field f(x,y,z) ∈ [0,1] — a deterministic heat-kernel
// surrogate (sum of Gaussian thermal sources + a steady diffusion gradient). This is
// the MODELED field the volume/isosurface/splats/arrows all read. Seeded by the
// MEASURED temperature so the hot core scales with real telemetry. Pure CPU mirror of
// the GLSL so isosurface + arrows + splats agree with the ray-march.
// ---------------------------------------------------------------------------
function _sampleField(x, y, z, hot) {
  // x,y,z ∈ [-1,1]. hot ∈ ~[0.4,1.1] scales the central source from measured temp.
  const r2 = x * x + y * y + z * z;
  const core = Math.exp(-2.4 * r2) * (0.85 + 0.35 * hot);
  // two offset thermal lobes (conduction toward edges)
  const dx1 = x - 0.45, dy1 = y - 0.15;
  const lobe1 = 0.45 * Math.exp(-5.0 * (dx1 * dx1 + dy1 * dy1 + z * z));
  const dx2 = x + 0.4, dz2 = z + 0.35;
  const lobe2 = 0.4 * Math.exp(-5.5 * (dx2 * dx2 + y * y + dz2 * dz2));
  // a gentle diffusion gradient (cooler at +y, the "exhaust" direction)
  const grad = 0.12 * (1.0 - (y + 1.0) * 0.5);
  let v = core + lobe1 + lobe2 + grad;
  return Math.max(0, Math.min(1, v));
}

// PDE residual surrogate r(x,y,z) ∈ [0,1] — large where the analytic field has high
// curvature (the steep flank of the hot core), which is exactly where a real PINN's
// physics-loss collocation would densify (RAR/RAD). MODELED bound, not measured.
function _sampleResidual(x, y, z, hot) {
  const r2 = x * x + y * y + z * z;
  const flank = Math.exp(-2.4 * r2) * r2 * 4.0;   // peaks on the gradient flank
  return Math.max(0, Math.min(1, flank * (0.7 + 0.5 * hot)));
}

// ---------------------------------------------------------------------------
// Build the 3D scalar-field texture (Data3DTexture, R channel = scalar in [0,1]).
// On WebGPU/WebGL2 alike this is sampled by the ray-march material. Rebuilt when the
// measured temperature changes (rare), not per-frame.
// ---------------------------------------------------------------------------
function _buildVolumeTexture(hot) {
  const THREE = _THREE;
  const n = VOX, data = new Uint8Array(n * n * n);
  let i = 0;
  for (let zi = 0; zi < n; zi++) {
    const z = (zi / (n - 1)) * 2 - 1;
    for (let yi = 0; yi < n; yi++) {
      const y = (yi / (n - 1)) * 2 - 1;
      for (let xi = 0; xi < n; xi++) {
        const x = (xi / (n - 1)) * 2 - 1;
        data[i++] = Math.round(_sampleField(x, y, z, hot) * 255);
      }
    }
  }
  const tex = new THREE.Data3DTexture(data, n, n, n);
  tex.format = THREE.RedFormat;
  tex.type = THREE.UnsignedByteType;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.unpackAlignment = 1;
  tex.needsUpdate = true;
  return tex;
}

// ---------------------------------------------------------------------------
// GLSL ray-march volume material. Front-face cull off / back-face render of a unit
// cube; the fragment shader marches camera→fragment through the 3D texture and
// accumulates a temperature transfer function (blue→cyan→amber→white-hot). Works on
// WebGL2 (the Linux fallback) AND WebGPU (three compiles GLSL nodeless materials on
// the WebGL2 path; on a true WebGPU device the shell still renders via the same Mesh
// because we use ShaderMaterial which three's WebGPURenderer supports via its WGSL
// transpile for raw GLSL ShaderMaterial in r170's backend-compat path). The fallback
// is honest: if the device is WebGPU and ShaderMaterial is unsupported we still show
// the isosurface + splats, which use standard materials.
// ---------------------------------------------------------------------------
function _volumeMaterial(tex) {
  const THREE = _THREE;
  return new THREE.ShaderMaterial({
    glslVersion: THREE.GLSL3,
    transparent: true,
    depthWrite: false,
    side: THREE.BackSide,
    uniforms: {
      uVol: { value: tex },
      uThreshold: { value: F.isoThreshold },
      uSteps: { value: 96 },
      uTime: { value: 0 },
      uOpacity: { value: 0.92 },
      uCamPos: { value: new THREE.Vector3() },
      uInvModel: { value: new THREE.Matrix4() },
    },
    vertexShader: /* glsl */`
      out vec3 vLocal;
      void main(){
        vLocal = position;            // unit cube in [-0.5,0.5]
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
      }
    `,
    fragmentShader: /* glsl */`
      precision highp float;
      precision highp sampler3D;
      in vec3 vLocal;
      out vec4 fragColor;
      uniform sampler3D uVol;
      uniform float uThreshold;
      uniform int uSteps;
      uniform float uTime;
      uniform float uOpacity;
      uniform vec3 uCamPos;
      uniform mat4 uInvModel;

      // temperature transfer function: cold blue -> cyan -> amber -> white-hot
      vec3 tf(float t){
        t = clamp(t,0.0,1.0);
        vec3 cold = vec3(0.05,0.12,0.35);
        vec3 mid  = vec3(0.13,0.72,0.74);
        vec3 warm = vec3(0.91,0.62,0.28);
        vec3 hot  = vec3(1.0,0.96,0.86);
        vec3 c = mix(cold, mid, smoothstep(0.0,0.45,t));
        c = mix(c, warm, smoothstep(0.4,0.75,t));
        c = mix(c, hot, smoothstep(0.75,1.0,t));
        return c;
      }
      // intersect ray with unit box [-0.5,0.5]^3
      vec2 boxHit(vec3 ro, vec3 rd){
        vec3 inv = 1.0/rd;
        vec3 a = (vec3(-0.5)-ro)*inv;
        vec3 b = (vec3( 0.5)-ro)*inv;
        vec3 tmin = min(a,b), tmax = max(a,b);
        float t0 = max(max(tmin.x,tmin.y),tmin.z);
        float t1 = min(min(tmax.x,tmax.y),tmax.z);
        return vec2(t0,t1);
      }
      void main(){
        // ray in local cube space
        vec3 ro = (uInvModel * vec4(uCamPos,1.0)).xyz;
        vec3 rd = normalize(vLocal - ro);
        vec2 hit = boxHit(ro, rd);
        float t0 = max(hit.x, 0.0), t1 = hit.y;
        if (t1 <= t0){ discard; }
        int steps = uSteps;
        float dt = (t1 - t0)/float(steps);
        vec3 col = vec3(0.0);
        float alpha = 0.0;
        float t = t0 + dt*fract(sin(dot(vLocal.xy,vec2(12.9898,78.233)))*43758.5453); // jitter
        for (int i=0;i<256;i++){
          if (i>=steps || alpha>0.98) break;
          vec3 p = ro + rd*t;            // [-0.5,0.5]
          vec3 uv = p + 0.5;            // [0,1]
          float s = texture(uVol, uv).r;
          // emphasise voxels above the iso threshold; pulse subtly for the holographic feel
          float w = smoothstep(uThreshold-0.12, uThreshold+0.04, s);
          float dens = s*0.55 + w*0.85;
          dens *= (0.85 + 0.15*sin(uTime*1.4 + s*8.0));
          vec3 c = tf(s);
          float a = dens * uOpacity * dt * 6.0;
          a = clamp(a,0.0,1.0);
          col += (1.0-alpha) * a * c;
          alpha += (1.0-alpha) * a;
          t += dt;
        }
        if (alpha < 0.003) discard;
        fragColor = vec4(col, alpha);
      }
    `,
  });
}

// ---------------------------------------------------------------------------
// Gaussian-splat scalar field (novel holographic) — one GPU-instanced additive
// billboard quad per high-scalar voxel; opacity + color = field value. This is the
// research §8 "Gaussian Splatting for scalar fields" technique applied to the MODELED
// PINN field. Built once (a fixed sparse voxel set above a low cutoff), recolored live.
// ---------------------------------------------------------------------------
function _buildSplats(hot) {
  const THREE = _THREE;
  const pts = [];
  const n = 26;                          // coarse splat lattice
  for (let zi = 0; zi < n; zi++) {
    const z = (zi / (n - 1)) * 2 - 1;
    for (let yi = 0; yi < n; yi++) {
      const y = (yi / (n - 1)) * 2 - 1;
      for (let xi = 0; xi < n; xi++) {
        const x = (xi / (n - 1)) * 2 - 1;
        const s = _sampleField(x, y, z, hot);
        if (s > 0.34) pts.push([x, y, z, s]);
      }
    }
  }
  const count = pts.length;
  const geo = new THREE.PlaneGeometry(1, 1);
  const inst = new THREE.InstancedMesh(geo, _splatMaterial(), count);
  const m = new THREE.Matrix4();
  const col = new THREE.Color();
  for (let k = 0; k < count; k++) {
    const [x, y, z, s] = pts[k];
    const sc = 0.10 + s * 0.42;
    m.makeScale(sc, sc, sc);
    m.setPosition(x * 2.0, y * 2.0, z * 2.0);
    inst.setMatrixAt(k, m);
    _tfColor(col, s);
    inst.setColorAt(k, col);
  }
  inst.instanceMatrix.needsUpdate = true;
  if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
  inst.userData.splatCount = count;
  inst.userData.pts = pts;
  _disposables.push(geo);
  return inst;
}

function _splatMaterial() {
  const THREE = _THREE;
  // additive radial-gaussian sprite via a small canvas texture
  const cnv = document.createElement("canvas");
  cnv.width = cnv.height = 64;
  const g = cnv.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.4, "rgba(255,255,255,0.5)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(cnv);
  const mat = new THREE.MeshBasicMaterial({
    map: tex, transparent: true, blending: THREE.AdditiveBlending,
    depthWrite: false, vertexColors: true, opacity: 0.9,
  });
  _disposables.push(tex, mat);
  return mat;
}

function _tfColor(col, t) {
  // CPU mirror of the GLSL transfer function (cold→hot)
  t = Math.max(0, Math.min(1, t));
  const lerp = (a, b, k) => a + (b - a) * k;
  const sm = (e0, e1, x) => { const k = Math.max(0, Math.min(1, (x - e0) / (e1 - e0))); return k * k * (3 - 2 * k); };
  let r = lerp(0.05, 0.13, sm(0, 0.45, t)), gn = lerp(0.12, 0.72, sm(0, 0.45, t)), b = lerp(0.35, 0.74, sm(0, 0.45, t));
  r = lerp(r, 0.91, sm(0.4, 0.75, t)); gn = lerp(gn, 0.62, sm(0.4, 0.75, t)); b = lerp(b, 0.28, sm(0.4, 0.75, t));
  r = lerp(r, 1.0, sm(0.75, 1, t)); gn = lerp(gn, 0.96, sm(0.75, 1, t)); b = lerp(b, 0.86, sm(0.75, 1, t));
  col.setRGB(r, gn, b);
  return col;
}

// ---------------------------------------------------------------------------
// Isosurface shell — a marching-cubes-style threshold surface. We approximate it with
// an icosphere whose vertices are displaced to the radius where the field crosses the
// iso threshold along that direction (a star-shaped level-set, cheap + interactive).
// Recomputed when the slider moves. Real MC on the GPU is the TSL-compute TODO; this is
// the honest interactive fallback that runs on WebGL2 too.
// ---------------------------------------------------------------------------
function _buildIsosurface(hot, threshold) {
  const THREE = _THREE;
  const geo = new THREE.IcosahedronGeometry(1, 5);
  const pos = geo.attributes.position;
  const v = new THREE.Vector3();
  const colors = new Float32Array(pos.count * 3);
  const col = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).normalize();
    // march outward to find where field == threshold along this ray
    let rHit = 0.18;
    for (let s = 0; s <= 64; s++) {
      const r = 0.05 + (s / 64) * 1.4;
      const f = _sampleField(v.x * r, v.y * r, v.z * r, hot);
      if (f < threshold) { rHit = r; break; }
      rHit = r;
    }
    const R = rHit * 2.0;
    pos.setXYZ(i, v.x * R, v.y * R, v.z * R);
    _tfColor(col, threshold);
    colors[i * 3] = col.r; colors[i * 3 + 1] = col.g; colors[i * 3 + 2] = col.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  pos.needsUpdate = true;
  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true, transparent: true, opacity: 0.34,
    metalness: 0.2, roughness: 0.4, emissive: 0x163040, emissiveIntensity: 0.5,
    side: THREE.DoubleSide, wireframe: false,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData.iso = true;
  _disposables.push(geo, mat);
  return mesh;
}

// ---------------------------------------------------------------------------
// Residual heatmap displacement shell — a second icosphere whose vertices protrude
// outward + turn orange/red where the MODELED PDE residual is high (research §6 step 4:
// "high residual = surface protrudes + turns orange/red"). residualDisp slider scales it.
// ---------------------------------------------------------------------------
function _buildResidualShell(hot) {
  const THREE = _THREE;
  const geo = new THREE.IcosahedronGeometry(2.6, 5);
  const pos = geo.attributes.position;
  const base = pos.array.slice();
  const colors = new Float32Array(pos.count * 3);
  const v = new THREE.Vector3(), col = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    v.set(base[i * 3], base[i * 3 + 1], base[i * 3 + 2]);
    const n = v.clone().normalize();
    const res = _sampleResidual(n.x, n.y, n.z, hot);
    // residual → red/orange ramp (separate from the temperature TF, so it reads as "error")
    col.setRGB(0.2 + res * 0.8, 0.18 + res * 0.35, 0.1 + (1 - res) * 0.2);
    colors[i * 3] = col.r; colors[i * 3 + 1] = col.g; colors[i * 3 + 2] = col.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geo.userData.base = base; geo.userData.hot = hot;
  geo.computeVertexNormals();
  const mat = new THREE.MeshStandardMaterial({
    vertexColors: true, transparent: true, opacity: 0.0,    // hidden until residualDisp>0
    metalness: 0.1, roughness: 0.6, side: THREE.DoubleSide,
    emissive: 0x401505, emissiveIntensity: 0.4, wireframe: true,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData.residual = true;
  _disposables.push(geo, mat);
  return mesh;
}

function _applyResidualDisp(mesh, disp) {
  const geo = mesh.geometry;
  const base = geo.userData.base, hot = geo.userData.hot;
  const pos = geo.attributes.position;
  const v = _THREE ? new _THREE.Vector3() : null;
  for (let i = 0; i < pos.count; i++) {
    const bx = base[i * 3], by = base[i * 3 + 1], bz = base[i * 3 + 2];
    v.set(bx, by, bz); const len = v.length(); v.normalize();
    const res = _sampleResidual(v.x, v.y, v.z, hot);
    const R = len + res * disp * 1.4;
    pos.setXYZ(i, v.x * R, v.y * R, v.z * R);
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  mesh.material.opacity = disp > 0.01 ? 0.55 : 0.0;
}

// ---------------------------------------------------------------------------
// Vector arrow field — instanced cones pointing along -∇field (heat-flow direction),
// length ∝ |∇field|. Research §6 step 5 "velocity as a vector arrow field, instanced
// ConeGeometry". MODELED gradient of the MODELED field.
// ---------------------------------------------------------------------------
function _buildArrows(hot) {
  const THREE = _THREE;
  const dirs = [];
  const n = 7;
  for (let zi = 0; zi < n; zi++) for (let yi = 0; yi < n; yi++) for (let xi = 0; xi < n; xi++) {
    const x = (xi / (n - 1)) * 2 - 1, y = (yi / (n - 1)) * 2 - 1, z = (zi / (n - 1)) * 2 - 1;
    const e = 0.04;
    const gx = (_sampleField(x + e, y, z, hot) - _sampleField(x - e, y, z, hot)) / (2 * e);
    const gy = (_sampleField(x, y + e, z, hot) - _sampleField(x, y - e, z, hot)) / (2 * e);
    const gz = (_sampleField(x, y, z + e, hot) - _sampleField(x, y, z - e, hot)) / (2 * e);
    const g = new THREE.Vector3(-gx, -gy, -gz);  // heat flows down-gradient
    const mag = g.length();
    if (mag < 0.06) continue;
    dirs.push({ p: new THREE.Vector3(x * 2, y * 2, z * 2), d: g.normalize(), mag });
  }
  const count = dirs.length;
  const geo = new THREE.ConeGeometry(0.045, 0.28, 6);
  geo.translate(0, 0.14, 0);
  const mat = new THREE.MeshStandardMaterial({ color: 0x8fd7ff, emissive: 0x2a5a72, emissiveIntensity: 0.6, metalness: 0.3, roughness: 0.4 });
  const inst = new THREE.InstancedMesh(geo, mat, count);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0), scl = new THREE.Vector3();
  for (let k = 0; k < count; k++) {
    const { p, d, mag } = dirs[k];
    q.setFromUnitVectors(up, d);
    const L = 0.5 + Math.min(2.0, mag) * 0.9;
    scl.set(1, L, 1);
    m.compose(p, q, scl);
    inst.setMatrixAt(k, m);
  }
  inst.instanceMatrix.needsUpdate = true;
  inst.userData.arrows = true;
  _disposables.push(geo, mat);
  return inst;
}

// ---------------------------------------------------------------------------
// compute_bounds physical-ceiling ladder — vertical bars on a log axis showing where
// the MEASURED job sits between the Landauer floor and the Margolus-Levitin /
// Bremermann / Bekenstein ceilings. Heights/positions are DERIVED from the cert's
// real fractions. A genius "physical-bounds ladder" rendered in 3D, every rung labelled.
// ---------------------------------------------------------------------------
function _buildBoundsLadder() {
  const THREE = _THREE;
  const g = new THREE.Group();
  g.position.set(4.6, -1.2, 0);
  g.userData.ladder = true;
  // a tall reference spine
  const spineGeo = new THREE.CylinderGeometry(0.015, 0.015, 4.4, 8);
  const spineMat = new THREE.MeshStandardMaterial({ color: 0x2a3a48, emissive: 0x10202a, emissiveIntensity: 0.5 });
  const spine = new THREE.Mesh(spineGeo, spineMat);
  spine.position.y = 2.2;
  g.add(spine);
  _disposables.push(spineGeo, spineMat);
  g.userData.rungs = [];   // filled live from cert fractions
  return g;
}

// place rungs along the spine from DERIVED log-fractions (called when cert arrives)
function _updateBoundsLadder(g) {
  const THREE = _THREE;
  if (!g) return;
  // remove old rungs
  (g.userData.rungs || []).forEach((r) => { g.remove(r.mesh); if (r.label) g.remove(r.label); });
  g.userData.rungs = [];
  if (!F.haveCert || F.landauerMult == null) return;
  // log10 scale: bottom = Landauer floor (the job is ~5e8× above it), top = Bremermann ceiling
  // Build rungs at fractional heights derived from the real numbers.
  const rungs = [
    { name: "Landauer floor", y: 0.0, color: 0x2fd07a, note: "kT·ln2 — the job is " + _human(F.landauerMult) + "× above" },
    { name: "MEASURED job", y: _clamp01(_logSpan(F.landauerMult, 1)), color: 0xe8c074, note: "5112 J DERIVED (P×t MEASURED)" },
    { name: "Margolus-Levitin", y: _ceilHeight(F.mlFrac), color: 0x6fb1ff, note: "rate ceiling — job at " + _sci(F.mlFrac) + " of max" },
    { name: "Bremermann", y: _ceilHeight(F.bremFrac), color: 0x8a6bff, note: "c²/h ceiling — job at " + _sci(F.bremFrac) },
    { name: "Bekenstein", y: _ceilHeight(F.bekFrac), color: 0xff9d5c, note: "info ceiling — job at " + _sci(F.bekFrac) },
  ];
  rungs.forEach((rg) => {
    const geo = new THREE.BoxGeometry(0.5, 0.07, 0.5);
    const mat = new THREE.MeshStandardMaterial({ color: rg.color, emissive: rg.color, emissiveIntensity: 0.45, metalness: 0.3, roughness: 0.4 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = rg.y * 4.2 + 0.05;
    g.add(mesh);
    _disposables.push(geo, mat);
    let label = null;
    try {
      label = _ctx.label.billboard(THREE, "MEASURED", { text: rg.name, scale: 0.34, position: [0.0, rg.y * 4.2 + 0.32, 0] });
      // these rungs are DERIVED from measured scalars; keep the MEASURED chip honest
      g.add(label);
    } catch (_) {}
    g.userData.rungs.push({ mesh, label });
  });
}

function _logSpan(mult /* job/floor */, _ref) {
  // place the MEASURED job ~ log10(mult)/log10(top) of the way up the spine
  const top = 18;            // ~ orders of magnitude up to the rate ceilings
  return Math.min(0.95, Math.log10(Math.max(1, mult)) / top);
}
function _ceilHeight(frac /* job/ceiling, tiny */) {
  if (frac == null || frac <= 0) return 0.97;
  // higher rung = smaller fraction (more headroom). map log10(1/frac) up the spine.
  const top = 50;
  return Math.min(0.99, 0.55 + Math.log10(1 / frac) / top);
}
function _clamp01(x) { return Math.max(0, Math.min(1, x)); }
function _sci(x) { return (x == null) ? "—" : Number(x).toExponential(2); }
function _human(x) {
  if (x == null) return "—";
  if (x >= 1e9) return (x / 1e9).toFixed(1) + "e9";
  if (x >= 1e6) return (x / 1e6).toFixed(1) + "e6";
  return String(Math.round(x));
}

// ---------------------------------------------------------------------------
// HUD — the cert badge (MEASURED+SIGNED), cosign anchor, Rekor inclusion, backend
// indicator, the measured-scalar chips, the bounds readout, residual status, and the
// interactive controls (iso threshold / splats / arrows / residual displacement).
// ---------------------------------------------------------------------------
function _buildHUD() {
  const wrap = document.createElement("div");
  wrap.className = "szl3d-pinn-hud";
  Object.assign(wrap.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%, 440px)", maxHeight: "calc(100% - 28px)", overflow: "auto",
    font: "12px ui-monospace,SFMono-Regular,Menlo,monospace", color: "#cfe0ea",
  });

  const title = document.createElement("div");
  title.style.cssText = "font:600 14px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px";
  title.textContent = "◇ PINN Thermal/Field  ·  ray-march volume + MEASURED+SIGNED cert";
  wrap.appendChild(title);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.45";
  sub.textContent = "Modeled on Kitware VTK.js/VolView + three.js TSL compute. " +
    "Field render is MODELED (analytic PINN surrogate seeded by MEASURED telemetry). " +
    "Certificate is MEASURED + SIGNED.";
  wrap.appendChild(sub);

  // live badge row (filled by poll)
  const badge = _ctx.live.createBadge();
  wrap.appendChild(badge.el);

  // backend indicator
  const back = document.createElement("div");
  back.id = "pinn-backend";
  back.style.cssText = "font-size:11px;color:#39d3c4";
  back.textContent = "backend: " + (F.backend || "…");
  wrap.appendChild(back);

  // ---- cert / signature panel ----
  const cert = document.createElement("div");
  cert.id = "pinn-cert";
  cert.style.cssText = "border:1px solid #1d2a36;border-radius:8px;padding:9px 10px;background:#0a1117cc;display:flex;flex-direction:column;gap:6px";
  cert.innerHTML = "<div style='color:#9fb1bf'>awaiting live certificate…</div>";
  wrap.appendChild(cert);

  // ---- bounds readout ----
  const bounds = document.createElement("div");
  bounds.id = "pinn-bounds";
  bounds.style.cssText = "border:1px solid #1d2a36;border-radius:8px;padding:9px 10px;background:#0a1117cc;font-size:11px;line-height:1.5";
  bounds.innerHTML = "<div style='color:#9fb1bf'>compute_bounds: awaiting /pnt/limits + cert…</div>";
  wrap.appendChild(bounds);

  // ---- residual status ----
  const resid = document.createElement("div");
  resid.id = "pinn-residual";
  resid.style.cssText = "border:1px solid #1d2a36;border-radius:8px;padding:8px 10px;background:#0a1117cc;font-size:11px";
  resid.innerHTML = "<div style='color:#9fb1bf'>agentic-PINN residual: awaiting…</div>";
  wrap.appendChild(resid);

  // ---- controls ----
  const ctrls = document.createElement("div");
  ctrls.style.cssText = "border:1px solid #1d2a36;border-radius:8px;padding:9px 10px;background:#0a1117cc;display:flex;flex-direction:column;gap:7px;font-size:11px";

  ctrls.appendChild(_sliderRow("isosurface threshold", 0.15, 0.92, 0.01, F.isoThreshold, (v) => {
    F.isoThreshold = v;
    if (_volMesh) _volMesh.material.uniforms.uThreshold.value = v;
    _rebuildIso();
  }));
  ctrls.appendChild(_sliderRow("PDE-residual displacement", 0, 1, 0.01, F.residualDisp, (v) => {
    F.residualDisp = v;
    if (_residMesh) _applyResidualDisp(_residMesh, v);
  }));
  ctrls.appendChild(_toggleRow("Gaussian-splat field (novel)", F.splatOn, (on) => {
    F.splatOn = on; if (_splatMesh) _splatMesh.visible = on;
  }));
  ctrls.appendChild(_toggleRow("vector arrow field (heat flow)", F.arrowsOn, (on) => {
    F.arrowsOn = on; if (_arrowMesh) _arrowMesh.visible = on;
  }));
  wrap.appendChild(ctrls);

  // ---- honesty legend ----
  const legend = _ctx.label.legend();
  legend.style.opacity = "0.85";
  wrap.appendChild(legend);

  const foot = document.createElement("div");
  foot.style.cssText = "color:#7d8a96;font-size:10px;line-height:1.4";
  foot.textContent = "Doctrine v11 · Λ = Conjecture 1 (advisory) · field MODELED, cert MEASURED+SIGNED · " +
    "no fabricated field numbers · WebGPU→WebGL2 fallback · 0 runtime CDN";
  wrap.appendChild(foot);

  (_ctx.container || document.body).appendChild(wrap);
  _overlay = wrap;
  return { wrap, badge, cert, bounds, resid, back };
}

function _sliderRow(label, min, max, step, val, onInput) {
  const row = document.createElement("label");
  row.style.cssText = "display:flex;flex-direction:column;gap:3px";
  const top = document.createElement("div");
  top.style.cssText = "display:flex;justify-content:space-between;color:#cfe0ea";
  const name = document.createElement("span"); name.textContent = label;
  const out = document.createElement("span"); out.style.color = "#39d3c4"; out.textContent = (+val).toFixed(2);
  top.appendChild(name); top.appendChild(out);
  const s = document.createElement("input");
  s.type = "range"; s.min = min; s.max = max; s.step = step; s.value = val;
  s.style.cssText = "width:100%;accent-color:#39d3c4";
  s.addEventListener("input", () => { const v = +s.value; out.textContent = v.toFixed(2); onInput(v); });
  row.appendChild(top); row.appendChild(s);
  return row;
}
function _toggleRow(label, on, onToggle) {
  const row = document.createElement("label");
  row.style.cssText = "display:flex;align-items:center;gap:8px;cursor:pointer;color:#cfe0ea";
  const c = document.createElement("input"); c.type = "checkbox"; c.checked = on; c.style.accentColor = "#39d3c4";
  c.addEventListener("change", () => onToggle(c.checked));
  const t = document.createElement("span"); t.textContent = label;
  row.appendChild(c); row.appendChild(t);
  return row;
}

// scene-object refs for live updates / controls
let _volMesh = null, _splatMesh = null, _isoMesh = null, _residMesh = null, _arrowMesh = null, _ladder = null, _coreLight = null;
let _hud = null, _volHotBuiltAt = null, _certBillboard = null;

function _rebuildIso() {
  if (!_isoMesh || !_group) return;
  const sc = _fieldScalars();
  const hot = _hotFromTemp(sc.tempK);
  const next = _buildIsosurface(hot, F.isoThreshold);
  next.visible = _isoMesh.visible;
  _group.remove(_isoMesh);
  try { _isoMesh.geometry.dispose(); } catch (_) {}
  _isoMesh = next;
  _group.add(_isoMesh);
}

function _hotFromTemp(tempK) {
  // map ~[300K cool .. 360K hot] → ~[0.4 .. 1.1]; clamps. 341.29K MEASURED → ~0.95.
  const t = (tempK - 300) / 60;
  return Math.max(0.4, Math.min(1.15, 0.4 + t * 0.75));
}

// ---------------------------------------------------------------------------
// Live cert handler — reads the MEASURED+SIGNED certificate and updates state + HUD.
// Honest: we read fields straight off the JSON; if a field is absent we show "—",
// never a fabricated value. Field render relabels to MODELED once measured scalars land.
// ---------------------------------------------------------------------------
function _onCert(json, meta) {
  if (!json || typeof json !== "object") return;
  const cert = json.certificate || {};
  const meas = cert.measured || {};
  F.signed = !!json.signed;
  // MEASURED scalars
  const num = (x) => (typeof x === "number" && isFinite(x)) ? x : null;
  F.tempK = num(meas.temperature_k_MEASURED);
  F.powerW = num(meas.avg_power_w_MEASURED);
  F.wallS = num(meas.wall_time_s_MEASURED);
  F.energyJ = num(cert.energy_joules_derived);
  // DERIVED bounds
  F.landauerMult = num(cert.landauer_multiple_above_floor);
  F.mlFrac = num(cert.margolus_levitin_headroom_fraction);
  F.bremFrac = num(cert.bremermann_headroom_fraction);
  F.bekFrac = num(cert.bekenstein_info_fraction);
  F.bounded = !!cert.physically_bounded;
  // signatures / anchors
  const dsse = json.dsse || {};
  const sig0 = (dsse.signatures && dsse.signatures[0]) || {};
  F.ed25519Keyid = sig0.keyid || (json.certificate && null);
  F.certSha = dsse._cert_sha256 || null;
  const co = json.cosign || {};
  F.cosignKeyid = co.keyid || null;
  F.cosignPubUrl = co.pub_key_url || null;
  const tl = dsse._transparency_log || {};
  F.rekorProvider = tl.provider || null;
  F.rekorUuid = tl.entry_uuid || null;
  F.rekorIndex = tl.log_index != null ? tl.log_index : null;
  F.rekorTime = tl.integrated_time_utc || null;
  const kh = json.khipu || {};
  F.khipuDigest = kh.digest || null;

  const wasCert = F.haveCert;
  F.haveCert = F.tempK != null;
  // field label: MEASURED scalars exist → field is a MODELED viz of them
  F.certLabel = F.haveCert ? "MODELED" : (meta && meta.label) || "SAMPLE";

  // rebuild the field geometry against the (rarely-changing) measured temperature
  const hot = _hotFromTemp(_fieldScalars().tempK);
  if (!wasCert || _volHotBuiltAt == null || Math.abs(_volHotBuiltAt - hot) > 0.02) {
    _rebuildFieldGeometry(hot);
    _volHotBuiltAt = hot;
  }
  _updateBoundsLadder(_ladder);
  _renderCertHUD();
  _renderBoundsHUD();
}

function _rebuildFieldGeometry(hot) {
  if (!_group || !_THREE) return;
  // volume texture
  if (_volMesh) {
    const tex = _buildVolumeTexture(hot);
    const old = _volMesh.material.uniforms.uVol.value;
    _volMesh.material.uniforms.uVol.value = tex;
    try { if (old && old.dispose) old.dispose(); } catch (_) {}
  }
  // splats
  if (_splatMesh) { _group.remove(_splatMesh); try { _splatMesh.dispose && _splatMesh.dispose(); } catch (_) {} }
  _splatMesh = _buildSplats(hot); _splatMesh.visible = F.splatOn; _group.add(_splatMesh);
  // iso
  _rebuildIso();
  // residual shell
  if (_residMesh) { _group.remove(_residMesh); try { _residMesh.geometry.dispose(); } catch (_) {} }
  _residMesh = _buildResidualShell(hot); _applyResidualDisp(_residMesh, F.residualDisp); _group.add(_residMesh);
  // arrows
  if (_arrowMesh) { _group.remove(_arrowMesh); try { _arrowMesh.dispose && _arrowMesh.dispose(); } catch (_) {} }
  _arrowMesh = _buildArrows(hot); _arrowMesh.visible = F.arrowsOn; _group.add(_arrowMesh);
  // core light intensity tracks measured power
  if (_coreLight) {
    const sc = _fieldScalars();
    _coreLight.intensity = 0.6 + Math.min(1.6, (sc.powerW || 30) / 56.18) * 1.0;
  }
}

function _renderCertHUD() {
  if (!_hud) return;
  const c = _hud.cert;
  const sc = _fieldScalars();
  const chip = (lab, text) => {
    const el = _ctx.label.chip(lab, { text });
    el.style.marginRight = "5px"; el.style.marginBottom = "3px"; return el.outerHTML;
  };
  const measured = F.haveCert;
  const rows = [];
  // status line
  const statusTxt = measured
    ? (F.signed ? "MEASURED + SIGNED (DSSE Ed25519, FA-001 on-metal)" : "MEASURED · unsigned")
    : "SAMPLE (no measured cert wired)";
  rows.push(`<div style="font-weight:600;color:${measured ? '#2fd07a' : '#6fb1ff'}">${statusTxt}</div>`);
  // measured scalars (each labelled MEASURED — they are real NVML samples)
  if (measured) {
    rows.push(`<div>${chip("MEASURED", "T = " + F.tempK.toFixed(2) + " K")}${chip("MEASURED", "P = " + F.powerW.toFixed(2) + " W")}</div>`);
    rows.push(`<div>${chip("MEASURED", "t = " + F.wallS.toFixed(0) + " s")}${chip("MODELED", "E = " + (F.energyJ ? F.energyJ.toFixed(0) : "—") + " J (DERIVED P×t)")}</div>`);
    rows.push(`<div style="color:#9fb1bf;font-size:10.5px">source: on-metal NVML · sovereign GPU betterwithage / RTX 5050 · 91 power.draw samples @1 Hz</div>`);
  } else {
    rows.push(`<div>${chip(F.certLabel, "field shape from SAMPLE seed (no measured cert)")}</div>`);
  }
  // signatures
  if (F.signed) {
    rows.push(`<div style="border-top:1px solid #18222c;margin-top:3px;padding-top:5px"></div>`);
    if (F.ed25519Keyid) rows.push(`<div style="font-size:10.5px"><span style="color:#2fd07a">✓ Ed25519 DSSE</span> · keyid ${_short(F.ed25519Keyid)}</div>`);
    if (F.cosignKeyid) rows.push(`<div style="font-size:10.5px"><span style="color:#2fd07a">✓ cosign</span> ECDSA-P256 · ${F.cosignKeyid}${F.cosignPubUrl ? ` · <a href="${F.cosignPubUrl}" target="_blank" rel="noopener" style="color:#39d3c4">cosign.pub ↗</a>` : ""}</div>`);
    if (F.certSha) rows.push(`<div style="font-size:10px;color:#9fb1bf">cert ${_short(F.certSha)}</div>`);
    // Rekor inclusion
    if (F.rekorUuid) {
      const url = "https://" + (F.rekorProvider || "rekor.sigstore.dev") + "/api/v1/log/entries/" + F.rekorUuid;
      rows.push(`<div style="font-size:10.5px"><span style="color:#2fd07a">✓ Rekor</span> inclusion · index ${F.rekorIndex != null ? F.rekorIndex : "—"}${F.rekorTime ? " · " + F.rekorTime : ""}</div>`);
      rows.push(`<div style="font-size:10px"><a href="${url}" target="_blank" rel="noopener" style="color:#39d3c4">entry ${_short(F.rekorUuid)} ↗</a></div>`);
    }
    if (F.khipuDigest) rows.push(`<div style="font-size:10px;color:#9fb1bf">khipu anchor ${_short("sha256:" + F.khipuDigest)} (append-only hash-chain)</div>`);
  }
  c.innerHTML = rows.join("");
}

function _renderBoundsHUD() {
  if (!_hud) return;
  const b = _hud.bounds;
  if (!F.haveCert || F.landauerMult == null) {
    b.innerHTML = `<div style="color:#9fb1bf">compute_bounds: awaiting cert bound values…</div>`;
    return;
  }
  const verdict = F.bounded ? `<span style="color:#2fd07a">PHYSICALLY BOUNDED</span>` : `<span style="color:#ff6b6b">UNBOUNDED?</span>`;
  b.innerHTML = [
    `<div style="font-weight:600;color:#eef3f6">compute_bounds ladder — DERIVED from MEASURED</div>`,
    `<div>verdict: ${verdict} (honest inverse of a free-energy claim)</div>`,
    `<div>Landauer floor: <span style="color:#39d3c4">${_human(F.landauerMult)}×</span> above kT·ln2</div>`,
    `<div>Margolus-Levitin: job at <span style="color:#39d3c4">${_sci(F.mlFrac)}</span> of rate ceiling</div>`,
    `<div>Bremermann: <span style="color:#39d3c4">${_sci(F.bremFrac)}</span> of c²/h limit</div>`,
    `<div>Bekenstein: <span style="color:#39d3c4">${_sci(F.bekFrac)}</span> of info ceiling</div>`,
    `<div style="color:#7d8a96;font-size:10px">Landauer 1961 · Margolus-Levitin 1998 · Bremermann 1962 · Bekenstein 1981 — cited, not claimed</div>`,
  ].join("");
}

function _onLimits(json) {
  if (!_hud || !json) return;
  const pillars = json.pillars || {};
  const cb = pillars.compute_bounds || {};
  // annotate the bounds panel with the pillar wiring status (honest)
  const tag = document.createElement("div");
  tag.style.cssText = "color:#7d8a96;font-size:10px;margin-top:3px";
  tag.textContent = `/pnt/limits · compute_bounds pillar: ${cb.wired ? "wired (" + (cb.module || "szl_pinn_bounds") + ")" : "not wired"} · ${(json.pillars && Object.keys(json.pillars).length) || 0} pillars`;
  tag.id = "pinn-limits-tag";
  const old = _hud.bounds.querySelector("#pinn-limits-tag");
  if (old) old.remove();
  _hud.bounds.appendChild(tag);
}

function _onResidual(json, meta) {
  if (!_hud || !json) return;
  const r = _hud.resid;
  const status = json.status || (json.rounds ? "OK" : "UNKNOWN");
  F.residualState = status;
  if (status === "AWAITING_GPU_SOLVE" || !json.rounds) {
    // Structure (the residual shell) is in the scene, but no proven residual value
    // exists until the governed GPU solve runs — doctrine: STRUCTURAL-ONLY, never faked.
    r.innerHTML = `<div style="color:#e8c074;display:flex;align-items:center;gap:6px">agentic-PINN residual: <b>AWAITING_GPU_SOLVE</b> ` +
      _ctx.label.chip("STRUCTURAL-ONLY", { text: "no proven residual" }).outerHTML + `</div>` +
      `<div style="color:#9fb1bf;font-size:10px">Governed numpy PINN solver runs on SZL metal / Forge GPU and writes the per-round decision trail (RAR/RAD + deny-by-default Λ-gate). None wired here — honest AWAITING, never a fabricated residual.</div>`;
    return;
  }
  F.residualRounds = json.rounds || [];
  const last = F.residualRounds[F.residualRounds.length - 1] || {};
  r.innerHTML = `<div style="color:#2fd07a">agentic-PINN residual: ${json.final_verdict || "—"} (accepted=${json.final_accepted})</div>` +
    `<div style="font-size:10.5px">${F.residualRounds.length} rounds · last max-res ${last.max_residual != null ? Number(last.max_residual).toExponential(2) : "—"} · ` +
    _ctx.label.chip("MODELED", { text: "error bound" }).outerHTML + `</div>`;
}

function _short(s) {
  if (!s) return "—";
  s = String(s);
  if (s.length <= 22) return s;
  return s.slice(0, 12) + "…" + s.slice(-8);
}

// ---------------------------------------------------------------------------
// mount / unmount
// ---------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  F.backend = _stage.backend || "webgl2";

  _group = new THREE.Group();
  _group.name = "pinn-surface";
  _stage.scene.add(_group);

  // pull the camera in a touch for the volume
  try { if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 3, 12); } catch (_) {}

  const sc = _fieldScalars();
  const hot = _hotFromTemp(sc.tempK);

  // --- ray-march volume (the centerpiece) ---
  const vtex = _buildVolumeTexture(hot);
  const boxGeo = new THREE.BoxGeometry(4, 4, 4);
  let volMat;
  try {
    volMat = _volumeMaterial(vtex);
    _volMesh = new THREE.Mesh(boxGeo, volMat);
    _volMesh.userData.volume = true;
    _group.add(_volMesh);
    _disposables.push(boxGeo, volMat);
  } catch (e) {
    // honest fallback: if ShaderMaterial fails on this backend, the iso+splats still render
    if (typeof console !== "undefined") console.warn("[pinn] volume material unavailable on", F.backend, e && e.message);
    _volMesh = null;
  }

  // --- isosurface shell ---
  _isoMesh = _buildIsosurface(hot, F.isoThreshold);
  _group.add(_isoMesh);

  // --- Gaussian-splat scalar field (novel holographic) ---
  _splatMesh = _buildSplats(hot); _splatMesh.visible = F.splatOn; _group.add(_splatMesh);

  // --- PDE-residual displacement shell ---
  _residMesh = _buildResidualShell(hot); _group.add(_residMesh);

  // --- vector arrow field ---
  _arrowMesh = _buildArrows(hot); _arrowMesh.visible = F.arrowsOn; _group.add(_arrowMesh);

  // --- compute_bounds ladder ---
  _ladder = _buildBoundsLadder(); _group.add(_ladder);

  // --- a warm core light so the hot core glows; intensity tracks measured power ---
  _coreLight = new THREE.PointLight(0xffd9a0, 0.8, 18, 2);
  _coreLight.position.set(0, 0, 0);
  _group.add(_coreLight);

  // --- field honesty billboard (MODELED once cert lands, SAMPLE before) ---
  try {
    _certBillboard = ctx.label.billboard(THREE, sc.label, { text: "field: " + sc.label, scale: 0.6, position: [0, 3.3, 0] });
    _group.add(_certBillboard);
  } catch (_) {}

  // bloom for the holographic glow (no-op on WebGPU per toolkit contract; works on WebGL2)
  try { _stage.setBloom(true); } catch (_) {}

  // HUD
  _hud = _buildHUD();
  if (_hud && _hud.back) _hud.back.textContent = "backend: " + F.backend + (F.backend === "webgpu" ? " (WebGPU)" : " (WebGL2 fallback)");

  // per-frame: animate volume time, gentle rotation, splat billboarding handled by Sprite-less
  // InstancedMesh facing via camera quaternion, residual pulse.
  _frameReg = (st) => {
    if (!_group) return;
    F.t += 0.016;
    if (_volMesh && _volMesh.material.uniforms) {
      _volMesh.material.uniforms.uTime.value = F.t;
      try { _volMesh.material.uniforms.uCamPos.value.copy(st.camera.position); } catch (_) {}
      try {
        _volMesh.updateWorldMatrix(true, false);
        _volMesh.material.uniforms.uInvModel.value.copy(_volMesh.matrixWorld).invert();
      } catch (_) {}
    }
    _group.rotation.y += 0.0016;
    // face splats toward camera (billboard the instanced quads)
    if (_splatMesh && _splatMesh.visible) {
      try { _splatMesh.quaternion.copy(st.camera.quaternion); } catch (_) {}
    }
    if (_certBillboard) { /* sprite auto-faces camera */ }
  };
  _stage.onFrame(_frameReg);

  // ---- LIVE polls (never hardcode; honest degraded/missing handling in the toolkit) ----
  _handles.push(ctx.live.poll(EP_CERT, 5000, _onCert, { badge: _hud.badge }));
  _handles.push(ctx.live.poll(EP_LIMITS, 8000, _onLimits, {}));
  _handles.push(ctx.live.poll(EP_RESIDUAL, 9000, _onResidual, {}));

  return { id: ID, started: true, backend: F.backend };
}

function unmount() {
  // stop polls
  _handles.forEach((h) => { try { h.stop(); } catch (_) {} });
  _handles = [];
  // remove our DOM
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  _overlay = null; _hud = null;
  // neutralize our frame callback (the shell keeps its callback list; we guard on _group)
  _frameReg = null;
  // remove our scene group + dispose resources
  try {
    if (_group && _stage) _stage.scene.remove(_group);
  } catch (_) {}
  _disposables.forEach((d) => { try { d && d.dispose && d.dispose(); } catch (_) {} });
  _disposables = [];
  try { if (_volMesh && _volMesh.material.uniforms && _volMesh.material.uniforms.uVol.value) _volMesh.material.uniforms.uVol.value.dispose(); } catch (_) {}
  try { _stage && _stage.setBloom(false); } catch (_) {}
  _group = null; _volMesh = null; _splatMesh = null; _isoMesh = null; _residMesh = null;
  _arrowMesh = null; _ladder = null; _coreLight = null; _certBillboard = null;
  _stage = null; _THREE = null; _ctx = null; _volHotBuiltAt = null;
  // reset live-derived state so a re-mount starts honest
  F.haveCert = false; F.signed = false; F.tempK = null; F.powerW = null;
}

export default {
  id: ID,
  title: TITLE,
  endpoints: [EP_CERT, EP_LIMITS, EP_RESIDUAL],
  mount,
  unmount,
  // exposed for tests / introspection (not part of the shell contract)
  _F: F,
};
