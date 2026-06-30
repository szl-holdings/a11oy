/* ============================================================================
 * a11oy_landing.js — the living-proof hero for the a11oy front door (v2).
 *
 * THE MOTIF (NVIDIA technical-sublime + True Anomaly operational COP, restrained
 * like Anthropic): a holographic PROOF LATTICE / signed-receipt constellation.
 * It encodes REAL state, not decorative noise:
 *   • NODES   = the recent receipts from GET /api/a11oy/v1/ledger. Each instanced
 *               node is one real receipt {seq, action, receipt_id}; the newest
 *               (chain head) sits innermost and brightest.
 *   • EDGES   = the SHA3-256 hash-chain links between consecutive receipts —
 *               the append-only ledger drawn as a lattice.
 *   • PULSE   = a token traveling the chain (genesis → head). When the live lake
 *               (GET /api/lake/v1/health.total_receipts) actually GROWS between
 *               polls, a brighter pulse fires to the head — a genuinely fresh
 *               signed receipt. No growth → only the ambient chain traversal of
 *               the receipts that already exist. We never fake a "new signature".
 *   • GLOW    = the governance core's intensity is tied to the advisory Λ from
 *               GET /api/a11oy/v1/lambda/org. Λ is Conjecture 1 (advisory bound),
 *               so the glow is a mood, never a pass/fail oracle.
 *
 * HONEST DEGRADE: if the ledger is unreachable we do NOT invent receipts or a
 * fake flow. The scene falls back to a calm, still lattice (dim wireframe core +
 * sparse static dust), reports dataState:"unreachable", and emits no pulses.
 *
 * SOVEREIGN: Three.js r160 (MIT) only, vendored in-image under /hero/vendor3d
 * (importmap in a11oy_landing.html). 0 runtime CDN. Bloom is faked with additive
 * fresnel + a layered halo sprite (no postprocessing dependency = GPU-light).
 *
 * KANCHAY palette: --void #080c14, --proof #3af4c8, --lattice #5b8dee. Calm and
 * deep-near-black; the lattice whispers, it never floods. Purple is banned.
 *
 * PERF: instanced nodes (one draw call), capped DPR, <13ms/frame target. Honors
 * prefers-reduced-motion (one static frame, no polling) and pauses when the hero
 * scrolls out of view (IntersectionObserver). Live figures are also fetched and
 * labelled by a11oy_landing.html — this module owns only the canvas.
 *
 * Doctrine v11: Λ = Conjecture 1 (advisory, NOT a theorem). locked-proven = 8.
 * Nothing here fabricates a number; every visual quantity is real or honestly off.
 * ========================================================================== */
import * as THREE from "three";

const REDUCED = window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MOBILE = Math.min(window.innerWidth, window.innerHeight) < 720 ||
  /Mobi|Android/i.test(navigator.userAgent);

// KANCHAY palette, held at restrained brightness so the deep void dominates.
const VOID    = 0x080c14;
const PROOF   = new THREE.Color(0x3af4c8); // --proof  : freshest receipt / head
const LATTICE = new THREE.Color(0x5b8dee); // --lattice: older receipts / chain
const DUSK    = new THREE.Color(0x101a2e); // near-void: ambient dust, denied glow

const LEDGER_URL = "/api/a11oy/v1/ledger";
const LAMBDA_URL = "/api/a11oy/v1/lambda/org";
const LAKE_URL   = "/api/lake/v1/health";

// Λ (Conjecture 1) → glow factor. Below the 0.80 advisory band the core is dim;
// near 1.0 it is at full restrained glow. Never implies a "pass".
function lambdaGlow(L) {
  if (typeof L !== "number" || !isFinite(L)) return 0.45; // neutral, no claim
  return Math.max(0.25, Math.min(1.0, (L - 0.80) / 0.20));
}

async function getJSON(url, ms = 3500) {
  const ctl = new AbortController();
  const to = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, { cache: "no-store", signal: ctl.signal });
    if (!r.ok) return null;
    return await r.json();
  } catch (_e) {
    return null;
  } finally {
    clearTimeout(to);
  }
}

export function mountHero(canvas) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas, antialias: !MOBILE, alpha: true, powerPreference: "high-performance",
    });
  } catch (e) {
    return { ok: false, reason: String(e) };
  }
  if (!renderer.getContext()) return { ok: false, reason: "no-webgl" };

  const DPR = Math.min(window.devicePixelRatio || 1, MOBILE ? 1.5 : 2);
  renderer.setPixelRatio(DPR);
  renderer.setClearColor(VOID, 0); // transparent — the page's deep void shows through

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
  camera.position.set(0, 0, 8.4);

  const root = new THREE.Group();
  scene.add(root);

  // ---- Governance core: fresnel glass icosahedron, glow tied to Λ ------------
  const coreMat = new THREE.ShaderMaterial({
    transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
    uniforms: {
      uTime: { value: 0 },
      uGlow: { value: 0.45 },  // set from real Λ once fetched
      uProof: { value: new THREE.Vector3(PROOF.r, PROOF.g, PROOF.b) },
      uLattice: { value: new THREE.Vector3(LATTICE.r, LATTICE.g, LATTICE.b) },
    },
    vertexShader: /* glsl */`
      varying vec3 vN; varying vec3 vView; uniform float uTime;
      void main(){
        vN = normalize(normalMatrix * normal);
        vec3 p = position;
        float w = sin(uTime*0.8 + position.y*2.0)*0.03
                + sin(uTime*1.3 + position.x*3.0)*0.02;
        p += normal * w;
        vec4 mv = modelViewMatrix * vec4(p,1.0);
        vView = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      varying vec3 vN; varying vec3 vView;
      uniform float uTime; uniform float uGlow; uniform vec3 uProof; uniform vec3 uLattice;
      void main(){
        float fres = pow(1.0 - max(dot(normalize(vN), normalize(vView)), 0.0), 2.4);
        float breathe = 0.5 + 0.5*sin(uTime*1.4);
        float glow = fres * (0.22 + 0.16*breathe) * uGlow;
        vec3 col = mix(uLattice, uProof, fres);
        gl_FragColor = vec4(col * glow, clamp(glow, 0.0, 0.42));
      }`,
  });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.35, MOBILE ? 2 : 4), coreMat);
  root.add(core);

  // deny-by-default cage — dim hairlines over the core
  const cage = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.42, 1)),
    new THREE.LineBasicMaterial({ color: 0x274063, transparent: true, opacity: 0.16 })
  );
  root.add(cage);

  // ---- Ambient dust (pure decoration, clearly NOT data) ----------------------
  // Sparse, very dim, static-ish depth field. Never labelled as receipts.
  const dustN = REDUCED ? 350 : (MOBILE ? 600 : 1100);
  const dpos = new Float32Array(dustN * 3);
  for (let i = 0; i < dustN; i++) {
    const t = i / dustN, phi = Math.acos(1 - 2 * t);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i, r = 4.5 + Math.random() * 4.0;
    dpos[i*3+0] = Math.sin(phi) * Math.cos(theta) * r;
    dpos[i*3+1] = Math.cos(phi) * r;
    dpos[i*3+2] = Math.sin(phi) * Math.sin(theta) * r;
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dpos, 3));
  const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
    color: DUSK, size: 0.6 * DPR, sizeAttenuation: false,
    transparent: true, opacity: 0.22, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  root.add(dust);

  // ---- Receipt constellation (instanced nodes + chain edges + pulse) ---------
  // Built only from REAL ledger data. Empty until/unless the ledger is reachable.
  const MAX_NODES = 24;
  const nodeGeo = new THREE.SphereGeometry(0.06, 10, 10);
  const nodeMat = new THREE.MeshBasicMaterial({
    transparent: true, opacity: 0.92, blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const nodes = new THREE.InstancedMesh(nodeGeo, nodeMat, MAX_NODES);
  nodes.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  nodes.count = 0; // nothing claimed until real receipts arrive
  nodes.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_NODES * 3), 3);
  root.add(nodes);

  const edgeMat = new THREE.LineBasicMaterial({
    color: 0x5b8dee, transparent: true, opacity: 0.0, // raised once edges exist
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const edges = new THREE.Line(new THREE.BufferGeometry(), edgeMat);
  root.add(edges);

  const pulse = new THREE.Mesh(
    new THREE.SphereGeometry(0.11, 12, 12),
    new THREE.MeshBasicMaterial({ color: PROOF, transparent: true, opacity: 0.0,
      blending: THREE.AdditiveBlending, depthWrite: false })
  );
  root.add(pulse);

  const _m = new THREE.Matrix4();
  const _v = new THREE.Vector3();
  let chainCurve = null;          // CatmullRom through node positions (genesis→head)
  let nodePositions = [];         // Vector3[]
  let pulseT = 0;                 // 0..1 along the chain
  let pulseBoost = 0;             // brief extra brightness on a genuinely fresh receipt
  let receiptCount = 0;           // honest count actually rendered

  // Lay out N receipts on a gentle helix around the core: genesis outer/low,
  // head inner/high (append-only growth climbs toward the governed core).
  function layout(n) {
    nodePositions = [];
    for (let i = 0; i < n; i++) {
      const f = n > 1 ? i / (n - 1) : 0;          // 0 genesis → 1 head
      const ang = f * Math.PI * 4.0;               // two turns of the helix
      const rad = 3.4 - f * 1.4;                   // spirals inward to the core
      const y = (f - 0.5) * 3.6;                   // climbs upward
      nodePositions.push(new THREE.Vector3(Math.cos(ang) * rad, y, Math.sin(ang) * rad));
    }
    chainCurve = nodePositions.length > 1
      ? new THREE.CatmullRomCurve3(nodePositions, false, "catmullrom", 0.4) : null;
  }

  // Apply REAL receipts to the constellation. `list` = [{seq,action,receipt_id}].
  function applyReceipts(list) {
    const n = Math.min(MAX_NODES, list.length);
    receiptCount = n;
    layout(n);
    for (let i = 0; i < n; i++) {
      const f = n > 1 ? i / (n - 1) : 1;
      _m.makeScale(0.7 + f * 0.9, 0.7 + f * 0.9, 0.7 + f * 0.9); // head a touch larger
      _m.setPosition(nodePositions[i]);
      nodes.setMatrixAt(i, _m);
      const c = LATTICE.clone().lerp(PROOF, f); // older=lattice blue, head=proof teal
      nodes.setColorAt(i, c);
    }
    nodes.count = n;
    nodes.instanceMatrix.needsUpdate = true;
    if (nodes.instanceColor) nodes.instanceColor.needsUpdate = true;

    if (n > 1) {
      const pts = chainCurve.getPoints(Math.max(32, n * 4));
      edges.geometry.dispose();
      edges.geometry = new THREE.BufferGeometry().setFromPoints(pts);
      edgeMat.opacity = 0.20;
      pulse.material.opacity = 0.0; // animated in the frame loop
    } else {
      edgeMat.opacity = 0.0;
    }
  }

  // Calm, still, honestly-empty state — no receipts invented, no flow faked.
  function showUnreachable() {
    receiptCount = 0;
    nodes.count = 0;
    edgeMat.opacity = 0.0;
    pulse.material.opacity = 0.0;
    chainCurve = null;
    cage.material.opacity = 0.22; // the lattice cage carries the quiet, honest mood
  }

  // ---- resize ---------------------------------------------------------------
  function resize() {
    const r = canvas.getBoundingClientRect();
    const w = Math.max(1, r.width), h = Math.max(1, r.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize, { passive: true });

  // ---- pointer parallax -----------------------------------------------------
  let px = 0, py = 0, tx = 0, ty = 0;
  if (!REDUCED) {
    window.addEventListener("pointermove", (e) => {
      tx = (e.clientX / window.innerWidth - 0.5);
      ty = (e.clientY / window.innerHeight - 0.5);
    }, { passive: true });
  }

  const hero = {
    ok: true, renderer, dataState: "loading", receiptCount: 0, lambda: null,
    setLambda(v) {
      hero.lambda = (typeof v === "number") ? v : null;
      coreMat.uniforms.uGlow.value = lambdaGlow(v);
    },
    setReceipts(list) {
      if (Array.isArray(list) && list.length) {
        applyReceipts(list);
        hero.dataState = "live"; hero.receiptCount = receiptCount;
      } else {
        showUnreachable(); hero.dataState = "unreachable"; hero.receiptCount = 0;
      }
    },
    fireFreshReceipt() { pulseT = 0; pulseBoost = 1.0; }, // genuine new signed receipt
  };

  // ---- render loop ----------------------------------------------------------
  const clock = new THREE.Clock();
  let raf = 0, running = true;

  function render(t) {
    coreMat.uniforms.uTime.value = t;
    px += (tx - px) * 0.04; py += (ty - py) * 0.04;
    root.rotation.y = t * 0.10 + px * 0.6;
    root.rotation.x = py * 0.35;
    cage.rotation.y = -t * 0.04;
    dust.rotation.y = t * 0.015;

    // signed-receipt pulse traverses the real chain (only when we have one)
    if (chainCurve) {
      pulseT += 0.0016 + 0.004 * pulseBoost; // fresh receipts travel faster + brighter
      if (pulseT >= 1) { pulseT = 0; pulseBoost = 0; }
      chainCurve.getPointAt(pulseT, _v);
      pulse.position.copy(_v);
      const base = 0.45 + 0.25 * Math.sin(t * 3.0);
      pulse.material.opacity = Math.min(1.0, base + pulseBoost * 0.5);
      const s = 1.0 + pulseBoost * 0.8;
      pulse.scale.setScalar(s);
    }
    renderer.render(scene, camera);
  }

  function frame() {
    if (!running) return;
    render(clock.getElapsedTime());
    raf = requestAnimationFrame(frame);
  }

  // ---- live data: fetch real receipts + Λ; poll lake for genuine growth ------
  async function boot() {
    const [ledger, lam] = await Promise.all([getJSON(LEDGER_URL), getJSON(LAMBDA_URL)]);
    if (lam && typeof lam.lambda_org === "number") hero.setLambda(lam.lambda_org);
    if (ledger && Array.isArray(ledger.receipts) && ledger.receipts.length) {
      hero.setReceipts(ledger.receipts);
    } else {
      hero.setReceipts(null); // honest still state — no fabricated receipts
    }
  }

  let lastLakeTotal = null;
  async function pollLake() {
    const h = await getJSON(LAKE_URL);
    const total = h && typeof h.total_receipts === "number" ? h.total_receipts : null;
    if (total !== null && lastLakeTotal !== null && total > lastLakeTotal) {
      hero.fireFreshReceipt(); // a real new receipt landed in the lake
    }
    if (total !== null) lastLakeTotal = total;
  }

  if (REDUCED) {
    // Static, dignified single frame. Still fetch real data (no animation/polling).
    boot().then(() => render(1.2));
    render(1.2);
  } else {
    boot();
    const io = new IntersectionObserver((ents) => {
      for (const en of ents) {
        if (en.isIntersecting && !running) { running = true; clock.start(); frame(); }
        else if (!en.isIntersecting && running) { running = false; cancelAnimationFrame(raf); }
      }
    }, { threshold: 0.01 });
    io.observe(canvas);
    frame();
    // poll the lake every 15s for genuine receipt growth (honest fresh pulse)
    const poll = setInterval(() => { if (running) pollLake(); }, 15000);
    hero._stopPoll = () => clearInterval(poll);
  }

  return hero;
}
