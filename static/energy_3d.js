// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11 LOCKED
//
// energy_3d.js — the /energy-3d "3D Holographic Energy View" ES module.
//
// Renders the a11oy sovereign compute mesh as glowing 3D nodes joined by energy-flow
// edges. Bound LIVE to GET /api/a11oy/v1/energy/mesh (polled ~2s):
//   - particle SPEED + DENSITY ∝ per-node live draw/watts (energy "flows" between nodes)
//   - node BRIGHTNESS ∝ live watts; DOWN nodes are dark (NEVER a fabricated glow)
//   - edge width/intensity ∝ joule flow between the two endpoints
// When the NVML meter is UNAVAILABLE the mesh STRUCTURE stays visible but all flow is
// frozen to zero — honest "posture-only, energy UNAVAILABLE" (no fabricated energy).
//
// TECHNIQUE (permissive patterns reimplemented in our OWN shaders — no code copied):
//   - GPGPU FBO ping-pong particle simulation  ← Three.js GPUComputationRenderer pattern (MIT)
//   - Vizceral-style node-edge traffic graph     ← Netflix Vizceral pattern (Apache-2.0)
// Three.js r160 (MIT) is vendored in-image at /hero/vendor3d (0 runtime CDN).
//
// prefers-reduced-motion -> a single static frame (no animation loop). No-WebGL ->
// the page's honest 2D fallback. Λ = Conjecture 1 (advisory). locked-proven kernel = 8.

import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const MESH_URL = "/api/a11oy/v1/energy/mesh";
const POLL_MS = 2000;
const MAX_EDGES = 28; // complete graph up to 8 nodes -> 28 edges (uniform-array cap)

const REDUCED = typeof matchMedia === "function"
  && matchMedia("(prefers-reduced-motion: reduce)").matches;
const COARSE = typeof matchMedia === "function"
  && matchMedia("(pointer: coarse)").matches;

// ---- tiny DOM helpers (HUD lives in energy-3d.html) -----------------------
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmtW = (w) => (typeof w === "number" && isFinite(w)) ? w.toFixed(1) : "—";
const fmtJ = (j) => (typeof j === "number" && isFinite(j))
  ? (Math.abs(j) >= 1000 ? Math.round(j).toLocaleString() : j.toFixed(1)) : "—";

function nodeColorHex(role) {
  const r = (role || "").toLowerCase();
  if (r === "glm") return 0x6a7bff;        // violet
  if (r === "blackwell") return 0x39d8c8;  // teal
  if (r === "anchor") return 0x5fe6d4;     // bright teal
  return 0x9fb2c9;                          // slate
}

// =====================================================================
// Public entry — called by the page boot script.
// =====================================================================
export function mountEnergy3D({ canvas, fallback } = {}) {
  if (!canvas) return { ok: false, reason: "no canvas" };

  // WebGL2 capability sniff — the GPGPU float-FBO path needs WebGL2.
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true,
      powerPreference: "high-performance" });
  } catch (e) {
    if (fallback) fallback();
    return { ok: false, reason: "webgl-unavailable" };
  }
  const gl = renderer.getContext();
  const isWebGL2 = (typeof WebGL2RenderingContext !== "undefined")
    && (gl instanceof WebGL2RenderingContext);
  // half-float color buffers are required to render INTO the simulation target.
  const canFloatFBO = isWebGL2 && !!gl.getExtension("EXT_color_buffer_float");

  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.setClearColor(0x00040f, 0); // transparent over the page's deep-space bg
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x00040f, 0.012);

  const camera = new THREE.PerspectiveCamera(52, 2, 0.1, 200);
  camera.position.set(0, 7.5, 20);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 9;
  controls.maxDistance = 44;
  controls.target.set(0, 0.5, 0);
  controls.autoRotate = !REDUCED;
  controls.autoRotateSpeed = 0.5;
  controls.enablePan = false;

  // ground reference grid — a faint holographic floor.
  const grid = new THREE.GridHelper(60, 40, 0x16324a, 0x0e2236);
  grid.position.y = -3.2;
  grid.material.transparent = true;
  grid.material.opacity = 0.28;
  scene.add(grid);

  // ----- particle counts (scale down on coarse/mobile pointers) -----
  const TEX_W = COARSE ? 64 : 160;
  const TEX_H = COARSE ? 48 : 100;
  const COUNT = TEX_W * TEX_H;

  // ----- shared GPU state, rebuilt when the mesh topology changes -----
  const state = {
    nodes: [],            // current node descriptors from /energy/mesh
    edges: [],            // {a,b} node-index pairs (complete graph)
    nodeMeshes: [],       // {core, halo, role, name}
    edgeMeshes: [],       // {mesh, a, b}
    sig: "",              // topology signature
    particles: null,      // {points, mat, sim, rtA, rtB, paramTex, paramData, ...}
    label: null,          // "MEASURED" | "UNAVAILABLE" | ...
    lastData: null,
  };

  // halo sprite texture (additive radial glow) — built once, reused.
  const haloTex = makeHaloTexture();

  // ===================================================================
  // GPGPU simulation scene (full-screen quad ping-pong) — OUR pattern.
  // The simulated state is the scalar progress t∈[0,1) of each particle
  // along its edge; t advances by a per-particle speed sampled from a
  // param texture (speed = 0 when its edge has no live draw -> frozen).
  // ===================================================================
  const simScene = new THREE.Scene();
  const simCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  function newStateRT() {
    return new THREE.WebGLRenderTarget(TEX_W, TEX_H, {
      type: THREE.HalfFloatType, format: THREE.RGBAFormat,
      minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter,
      depthBuffer: false, stencilBuffer: false,
    });
  }

  function buildParticles() {
    disposeParticles();

    const edgeCount = state.edges.length;
    // per-particle static attributes
    const ref = new Float32Array(COUNT * 2);   // uv into the state/param textures
    const edgeAttr = new Float32Array(COUNT);  // which edge (0..edgeCount-1)
    const seed = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) {
      const x = (i % TEX_W + 0.5) / TEX_W;
      const y = (Math.floor(i / TEX_W) + 0.5) / TEX_H;
      ref[i * 2] = x; ref[i * 2 + 1] = y;
      edgeAttr[i] = edgeCount > 0 ? (i % edgeCount) : 0;
      seed[i] = Math.random();
    }

    // initial state texture: r = random t, g/b/a spare
    const stateData = new Float32Array(COUNT * 4);
    for (let i = 0; i < COUNT; i++) stateData[i * 4] = Math.random();
    const stateTex = new THREE.DataTexture(stateData, TEX_W, TEX_H,
      THREE.RGBAFormat, THREE.FloatType);
    stateTex.needsUpdate = true;

    // param texture: r = speed, g = alpha/density, b = hot (color mix), a = spare.
    const paramData = new Float32Array(COUNT * 4);
    const paramTex = new THREE.DataTexture(paramData, TEX_W, TEX_H,
      THREE.RGBAFormat, THREE.FloatType);
    paramTex.needsUpdate = true;

    let rtA = null, rtB = null, sim = null;
    if (canFloatFBO && !REDUCED) {
      rtA = newStateRT(); rtB = newStateRT();
      // seed rtA from the initial DataTexture via a copy pass.
      sim = new THREE.ShaderMaterial({
        uniforms: {
          texState: { value: null },
          texParam: { value: paramTex },
          uDt: { value: 0.016 },
        },
        vertexShader: SIM_VERT,
        fragmentShader: SIM_FRAG,
        depthTest: false, depthWrite: false,
      });
      const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), sim);
      simScene.clear();
      simScene.add(quad);
      // prime rtA with the random initial state (one copy pass).
      const copyMat = new THREE.ShaderMaterial({
        uniforms: { texState: { value: stateTex }, texParam: { value: paramTex },
          uDt: { value: 0.0 } },
        vertexShader: SIM_VERT, fragmentShader: SIM_FRAG,
        depthTest: false, depthWrite: false,
      });
      quad.material = copyMat;
      renderer.setRenderTarget(rtA);
      renderer.render(simScene, simCam);
      renderer.setRenderTarget(null);
      copyMat.dispose();
      quad.material = sim;
      state._simQuad = quad;
    }

    // ---- render geometry (Points) ----
    const geo = new THREE.BufferGeometry();
    // dummy position attribute (real position computed in the vertex shader)
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    geo.setAttribute("aRef", new THREE.BufferAttribute(ref, 2));
    geo.setAttribute("aEdge", new THREE.BufferAttribute(edgeAttr, 1));
    geo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));

    const edgeA = new Array(MAX_EDGES).fill(0).map(() => new THREE.Vector3());
    const edgeB = new Array(MAX_EDGES).fill(0).map(() => new THREE.Vector3());

    const mat = new THREE.ShaderMaterial({
      uniforms: {
        texState: { value: canFloatFBO && !REDUCED ? rtA.texture : stateTex },
        texParam: { value: paramTex },
        uEdgeA: { value: edgeA },
        uEdgeB: { value: edgeB },
        uSize: { value: (COARSE ? 18.0 : 26.0) },
        uTime: { value: 0 },
        uColorCool: { value: new THREE.Color(0x39d8c8) },
        uColorHot: { value: new THREE.Color(0xff7a2a) },
      },
      vertexShader: RENDER_VERT,
      fragmentShader: RENDER_FRAG,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthTest: true,
      depthWrite: false,
    });

    const points = new THREE.Points(geo, mat);
    points.frustumCulled = false;
    scene.add(points);

    state.particles = {
      points, mat, sim, rtA, rtB, stateTex, paramTex, paramData,
      edgeA, edgeB, swap: false,
    };
  }

  function disposeParticles() {
    const p = state.particles;
    if (!p) return;
    scene.remove(p.points);
    p.points.geometry.dispose();
    p.mat.dispose();
    if (p.sim) p.sim.dispose();
    if (p.rtA) p.rtA.dispose();
    if (p.rtB) p.rtB.dispose();
    if (p.stateTex) p.stateTex.dispose();
    if (p.paramTex) p.paramTex.dispose();
    state.particles = null;
  }

  // ===================================================================
  // Topology (nodes + complete-graph edges) and the node/edge meshes.
  // ===================================================================
  function layoutPositions(n) {
    const out = [];
    if (n <= 0) return out;
    const R = Math.max(5, 3.2 + n * 0.9);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 - Math.PI / 2;
      // gentle vertical stagger so edges read in 3D
      const y = (i % 2 === 0 ? 0.8 : -0.8) + Math.sin(i * 1.7) * 0.4;
      out.push(new THREE.Vector3(Math.cos(a) * R, y, Math.sin(a) * R));
    }
    return out;
  }

  function rebuildTopology(nodes) {
    // tear down old node/edge meshes
    state.nodeMeshes.forEach((m) => {
      scene.remove(m.core); scene.remove(m.halo);
      m.core.geometry.dispose(); m.core.material.dispose(); m.halo.material.dispose();
    });
    state.edgeMeshes.forEach((e) => { scene.remove(e.mesh); e.mesh.geometry.dispose(); e.mesh.material.dispose(); });
    state.nodeMeshes = []; state.edgeMeshes = [];

    const pos = layoutPositions(nodes.length);

    // nodes: icosahedron core + additive halo sprite
    nodes.forEach((nd, i) => {
      const col = new THREE.Color(nodeColorHex(nd.role));
      const core = new THREE.Mesh(
        new THREE.IcosahedronGeometry(0.62, 2),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.92 })
      );
      core.position.copy(pos[i]);
      scene.add(core);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({
        map: haloTex, color: col, transparent: true, opacity: 0.0,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
      halo.position.copy(pos[i]);
      halo.scale.setScalar(3.0);
      scene.add(halo);
      state.nodeMeshes.push({ core, halo, role: nd.role, name: nd.name, pos: pos[i] });
    });

    // edges: complete graph, thin cylinders (radius ∝ flow, updated per poll)
    const edges = [];
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        if (edges.length >= MAX_EDGES) break;
        edges.push({ a, b });
      }
    }
    state.edges = edges;

    edges.forEach((e) => {
      const pa = pos[e.a], pb = pos[e.b];
      const len = pa.distanceTo(pb);
      const geo = new THREE.CylinderGeometry(1, 1, len, 8, 1, true);
      const mat = new THREE.MeshBasicMaterial({
        color: 0x39d8c8, transparent: true, opacity: 0.10,
        blending: THREE.AdditiveBlending, depthWrite: false,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pa).add(pb).multiplyScalar(0.5);
      mesh.quaternion.setFromUnitVectors(
        new THREE.Vector3(0, 1, 0),
        pb.clone().sub(pa).normalize()
      );
      mesh.scale.set(0.02, 1, 0.02);
      scene.add(mesh);
      state.edgeMeshes.push({ mesh, a: e.a, b: e.b });
    });

    // rebuild particles for the new edge set and push endpoint uniforms
    buildParticles();
    if (state.particles) {
      edges.forEach((e, i) => {
        state.particles.edgeA[i].copy(pos[e.a]);
        state.particles.edgeB[i].copy(pos[e.b]);
      });
    }
  }

  // ===================================================================
  // Per-poll visual binding: brightness, flow speed/density, edge width.
  // ===================================================================
  function applyData(data) {
    state.lastData = data;
    const nodes = Array.isArray(data.nodes) ? data.nodes.slice(0, 8) : [];
    const measured = (data.label === "MEASURED");
    state.label = data.label || "UNAVAILABLE";

    const sig = nodes.map((n) => (n.name || "") + ":" + (n.role || "")).join("|");
    if (sig !== state.sig) {
      state.sig = sig;
      rebuildTopology(nodes);
    }

    // per-node draw (0..1): MEASURED live watts only; never fabricated.
    const draws = nodes.map((n) => {
      if (!measured) return null;
      if (n.live !== true) return null;
      if (typeof n.draw === "number" && isFinite(n.draw)) return Math.max(0, Math.min(1, n.draw));
      return 0;
    });

    // ---- node brightness ∝ live watts (down = dark, NEVER a fake glow) ----
    state.nodeMeshes.forEach((m, i) => {
      const nd = nodes[i] || {};
      const down = nd.live === false;
      const unknown = nd.live == null;
      let bright = 0, haloOp = 0, coreOp = 0.5;
      if (down) {
        // honest dark: dim slate, no halo
        m.core.material.color.set(0x2a3550); coreOp = 0.55; bright = 0; haloOp = 0;
      } else if (!measured) {
        // posture-only: a live node gets a STEADY dim glow (liveness, not watts)
        m.core.material.color.set(nodeColorHex(nd.role));
        coreOp = unknown ? 0.45 : 0.8;
        haloOp = unknown ? 0.0 : 0.18; bright = unknown ? 0 : 0.25;
      } else {
        const d = draws[i] == null ? 0 : draws[i];
        const base = new THREE.Color(nodeColorHex(nd.role));
        // ramp toward white-hot as draw rises
        base.lerp(new THREE.Color(0xffffff), d * 0.5);
        m.core.material.color.copy(base);
        coreOp = 0.6 + 0.4 * d;
        haloOp = unknown ? 0.0 : (0.12 + 0.62 * d);
        bright = d;
      }
      m.core.material.opacity = coreOp;
      m.halo.material.opacity = haloOp;
      m.halo.scale.setScalar(2.4 + 2.6 * bright);
    });

    // ---- edge width/intensity ∝ joule flow between endpoints ----
    const edgeIntensity = state.edges.map((e) => {
      const da = draws[e.a], db = draws[e.b];
      if (da == null || db == null) return 0;       // not both live+measured -> no flow
      return Math.max(0, Math.min(1, (da + db) * 0.5));
    });
    state.edgeMeshes.forEach((em, i) => {
      const it = edgeIntensity[i] || 0;
      const r = 0.02 + 0.16 * it;                    // radius ∝ flow
      em.mesh.scale.set(r, 1, r);
      em.mesh.material.opacity = 0.07 + 0.5 * it;
      const c = new THREE.Color(0x39d8c8).lerp(new THREE.Color(0xff7a2a), it);
      em.mesh.material.color.copy(c);
    });

    // ---- particle flow: speed + density ∝ edge intensity (frozen when 0) ----
    const p = state.particles;
    if (p) {
      const edgeCount = state.edges.length;
      const data4 = p.paramData;
      for (let i = 0; i < COUNT; i++) {
        const ei = edgeCount > 0 ? (i % edgeCount) : 0;
        const it = edgeIntensity[ei] || 0;
        // speed ∝ intensity (0 -> frozen: no fabricated flow). small jitter for life.
        const jitter = 0.7 + 0.6 * ((i * 9301 + 49297) % 233280) / 233280;
        data4[i * 4 + 0] = it > 0 ? (0.06 + 0.5 * it) * jitter : 0.0;  // speed
        data4[i * 4 + 1] = it > 0 ? (0.18 + 0.82 * it) : 0.0;          // alpha/density
        data4[i * 4 + 2] = it;                                          // hot (color mix)
        data4[i * 4 + 3] = 0.0;
      }
      p.paramTex.needsUpdate = true;
    }

    updateHUD(data, nodes, draws, measured);
    if (REDUCED) renderOnce(); // static-frame mode: redraw after each poll
  }

  // ===================================================================
  // HUD (DOM) — honest chips + per-node cards + 2D fallback list.
  // ===================================================================
  function chip(kind, text) {
    return `<span class="chip ${kind}"><span class="dot"></span>${esc(text)}</span>`;
  }
  function liveChip(n, measured) {
    if (n.live === true) return chip("live", "LIVE");
    if (n.live === false) return chip("down", "DOWN");
    return chip("unknown", "UNKNOWN");
  }
  function updateHUD(data, nodes, draws, measured) {
    const sc = $("status-chip");
    if (sc) {
      if (measured) sc.outerHTML = chip("measured", "MEASURED").replace("chip ", "chip ").replace("<span", '<span id="status-chip"');
      else sc.outerHTML = chip("unavailable", "ENERGY UNAVAILABLE").replace("<span", '<span id="status-chip"');
    }
    const mc = $("mesh-chip");
    if (mc) {
      const live = (typeof data.live_count === "number") ? data.live_count : nodes.filter((n) => n.live === true).length;
      const tot = (typeof data.node_count === "number") ? data.node_count : nodes.length;
      mc.outerHTML = chip(live > 0 ? "live" : "down", `mesh ${live}/${tot}`).replace("<span", '<span id="mesh-chip"');
    }
    const tw = $("tot-watts"); if (tw) tw.textContent = measured ? fmtW(data.total_watts) : "—";
    const tj = $("tot-joules"); if (tj) tj.textContent = measured ? fmtJ(data.total_joules) : "—";

    const host = $("hud-nodes");
    if (host) {
      if (!nodes.length) {
        host.innerHTML = '<div class="panel"><div class="muted mono" style="font-size:12px">No mesh nodes reported.</div></div>';
      } else {
        host.innerHTML = nodes.map((n, i) => {
          const down = n.live === false;
          const col = "#" + nodeColorHex(n.role).toString(16).padStart(6, "0");
          const jl = (n.joules_label || (measured ? "MEASURED" : "UNAVAILABLE"));
          const jChipKind = (jl === "MEASURED") ? "measured" : "unavailable";
          const wattTxt = (measured && n.live === true && typeof n.watts === "number") ? fmtW(n.watts) : "—";
          const jouleTxt = (measured && typeof n.joules === "number") ? fmtJ(n.joules) : "—";
          const d = draws[i] == null ? 0 : draws[i];
          return `<div class="panel node-card ${down ? "down" : ""}">
            <div class="hd">
              <span class="swatch" style="color:${col};background:${col}"></span>
              <div><div class="nm">${esc(n.name || "node")}</div>
                <div class="role">${esc(n.role || "—")}</div></div>
              <div class="right">${liveChip(n, measured)}</div>
            </div>
            <div class="vals">
              <div class="v"><div class="k" style="color:var(--teal)">${wattTxt}</div><div class="l">watts</div></div>
              <div class="v"><div class="k">${jouleTxt}</div><div class="l">joules</div></div>
              <div class="v"><div class="k">${down ? "—" : Math.round(d * 100) + "%"}</div><div class="l">draw</div></div>
            </div>
            <div class="bar"><i style="width:${down ? 0 : Math.round(d * 100)}%"></i></div>
            <div style="margin-top:9px">${chip(jChipKind, "joules " + jl)}</div>
          </div>`;
        }).join("");
      }
    }

    // 2D fallback list (used only if WebGL failed — same honest labels)
    const fb = $("fb-nodes");
    if (fb && nodes.length) {
      fb.innerHTML = nodes.map((n) => {
        const wattTxt = (measured && n.live === true && typeof n.watts === "number") ? fmtW(n.watts) + " W" : "—";
        return `<div class="fb-node">${liveChip(n, measured)}
          <div><div class="nm">${esc(n.name || "node")}</div>
          <div class="role mono" style="font-size:11px;color:var(--ghost)">${esc(n.role || "—")} · ${wattTxt}</div></div></div>`;
      }).join("");
    }
  }

  function hudError(msg) {
    const sc = $("status-chip");
    if (sc) sc.outerHTML = chip("unavailable", "MESH UNREACHABLE").replace("<span", '<span id="status-chip"');
    const host = $("hud-nodes");
    if (host) host.innerHTML = `<div class="panel"><div class="mono" style="font-size:12px;color:var(--down)">
      ${esc(MESH_URL)} did not respond — no fabricated data.</div>
      <div class="muted mono" style="font-size:11px;margin-top:6px">${esc(msg || "")}</div></div>`;
    const fb = $("fb-nodes");
    if (fb) fb.innerHTML = '<div class="mono" style="color:var(--down)">mesh endpoint unreachable — no fabricated data.</div>';
  }

  // ===================================================================
  // Poll loop + render loop.
  // ===================================================================
  let stopped = false;
  async function poll() {
    try {
      const r = await fetch(MESH_URL, { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      applyData(data);
    } catch (e) {
      hudError(e && e.message);
    }
  }

  const clock = new THREE.Clock();
  function stepSim(dt) {
    const p = state.particles;
    if (!p || !p.sim || !p.rtA || !p.rtB) return;
    p.sim.uniforms.uDt.value = Math.min(0.05, dt);
    const src = p.swap ? p.rtB : p.rtA;
    const dst = p.swap ? p.rtA : p.rtB;
    p.sim.uniforms.texState.value = src.texture;
    state._simQuad.material = p.sim;
    renderer.setRenderTarget(dst);
    renderer.render(simScene, simCam);
    renderer.setRenderTarget(null);
    p.mat.uniforms.texState.value = dst.texture;
    p.swap = !p.swap;
  }

  function renderOnce() {
    controls.update();
    renderer.render(scene, camera);
  }

  function animate() {
    if (stopped) return;
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    if (state.particles) {
      state.particles.mat.uniforms.uTime.value += dt;
      stepSim(dt);
    }
    controls.update();
    renderer.render(scene, camera);
  }

  // ----- resize -----
  function resize() {
    const w = canvas.clientWidth || innerWidth;
    const h = canvas.clientHeight || innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    if (REDUCED) renderOnce();
  }
  addEventListener("resize", resize);
  resize();

  // ----- go -----
  poll();
  const pollTimer = setInterval(poll, POLL_MS);
  if (REDUCED) {
    renderOnce();                 // static frame; re-rendered after each poll
  } else {
    animate();
  }

  return {
    ok: true,
    webgl2: isWebGL2,
    gpgpu: canFloatFBO && !REDUCED,
    reducedMotion: REDUCED,
    dispose() {
      stopped = true;
      clearInterval(pollTimer);
      removeEventListener("resize", resize);
      controls.dispose();
      disposeParticles();
      renderer.dispose();
    },
  };
}

// =====================================================================
// Shaders (our own GLSL — reimplemented GPGPU + flow-field patterns).
// =====================================================================

// --- simulation: advance progress t per particle (FBO ping-pong) ---
const SIM_VERT = /* glsl */`
  varying vec2 vUv;
  void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;
const SIM_FRAG = /* glsl */`
  precision highp float;
  varying vec2 vUv;
  uniform sampler2D texState;
  uniform sampler2D texParam;
  uniform float uDt;
  void main(){
    vec4 s = texture2D(texState, vUv);
    float speed = texture2D(texParam, vUv).r;  // 0 -> frozen (honest no-flow)
    float t = fract(s.r + uDt * speed);
    gl_FragColor = vec4(t, s.g, s.b, 1.0);
  }
`;

// --- render: read t from FBO, place on edge, add flow-field turbulence ---
const RENDER_VERT = /* glsl */`
  precision highp float;
  attribute vec2 aRef;
  attribute float aEdge;
  attribute float aSeed;
  uniform sampler2D texState;
  uniform sampler2D texParam;
  uniform vec3 uEdgeA[${MAX_EDGES}];
  uniform vec3 uEdgeB[${MAX_EDGES}];
  uniform float uSize;
  uniform float uTime;
  varying float vAlpha;
  varying float vHot;
  void main(){
    float t = texture2D(texState, aRef).r;
    vec4 prm = texture2D(texParam, aRef);
    int idx = int(aEdge + 0.5);
    vec3 A = uEdgeA[idx];
    vec3 B = uEdgeB[idx];
    vec3 base = mix(A, B, t);
    // flow-field turbulence (small, seeded) — particles breathe along the edge
    float ph = aSeed * 6.2831853;
    vec3 wob = vec3(
      sin(t * 18.84 + ph) ,
      cos(t * 12.56 + ph * 1.7),
      sin(t * 15.70 + ph * 0.6)
    ) * 0.14 * (0.4 + prm.g);
    vec3 pos = base + wob;
    // taper density near the endpoints so flow reads as motion, not clutter
    float edgeFade = smoothstep(0.0, 0.12, t) * smoothstep(1.0, 0.88, t);
    vAlpha = prm.g * (0.25 + 0.75 * edgeFade);
    vHot = prm.b;
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = uSize * (0.5 + 0.9 * prm.g) / max(0.5, -mv.z);
  }
`;
const RENDER_FRAG = /* glsl */`
  precision highp float;
  uniform vec3 uColorCool;
  uniform vec3 uColorHot;
  varying float vAlpha;
  varying float vHot;
  void main(){
    if (vAlpha <= 0.01) discard;
    vec2 d = gl_PointCoord - vec2(0.5);
    float r = dot(d, d);
    if (r > 0.25) discard;
    float soft = smoothstep(0.25, 0.0, r);
    vec3 col = mix(uColorCool, uColorHot, clamp(vHot, 0.0, 1.0));
    gl_FragColor = vec4(col, vAlpha * soft);
  }
`;

// additive radial-glow sprite for node halos.
function makeHaloTexture() {
  const s = 128;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  g.addColorStop(0.0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.65)");
  g.addColorStop(1.0, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
