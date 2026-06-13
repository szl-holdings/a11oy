/* ============================================================================
 * app.js — SZL Cathedral · Constellation · Khipu (sovereign 3D, vendored Three.js)
 * GENIUS ELEVATION — the flagship showpiece.
 *
 * RE-FACE rule honored: the only labelled bodies are
 *   - a11oy  (central brain / sun)
 *   - 3 a11oy-INTERNAL capabilities: reasoning / policy / operator  (NOT organs)
 *   - killinchu (field node)
 *   - a sovereign compute-fabric ring (real nodes from /compute-pool, honest tier)
 *   - Khipu receipt stars (anonymous receipt DAG, cord arcs)
 * No amaru / sentra / rosie node labels anywhere.
 *
 * HONESTY DOCTRINE v11 (machine-checked against live endpoints):
 *   Λ = Conjecture 1 (advisory, NOT a theorem, NOT "proven trust").
 *   Khipu BFT = Conjecture 2.  locked-proven kernel = EXACTLY 8.
 *   Trust = conformal (never 100%, NOT Hoeffding).  SLSA L1 honest / L2 roadmap.
 *   joules = MEASURED only via a real on-box NVML exporter; shown as SAMPLE/seed otherwise.
 *   organs = EXPERIMENTAL tier.  killinchu effectors = SIMULATED.
 *   Live data from real /healthz, /compute-pool, /lambda, /khipu/ledger.
 *   Honest SEED -> LIVE promotion; OFFLINE labelled loudly; no fabricated numbers.
 *
 * Sovereign: Three.js r160 (MIT) + OrbitControls vendored under ./vendor. NO CDN.
 * No external postprocessing — bloom is faked with additive layered sprites + fresnel
 * built only from vendored three primitives. System font stacks only.
 *
 * Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 * ========================================================================== */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

/* ---------- reduced-motion + perf posture ---------------------------------- */
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const IS_TOUCH = window.matchMedia('(pointer: coarse)').matches;

/* ---------- canonical content (the proven anatomy, surfaced honestly) ------- */
const CAPABILITIES = [
  {
    id: 'reasoning', title: 'Reasoning & Provenance',
    color: 0x5cc4bf, angle: 0,
    plain: 'Grounded reasoning, memory/recall and provenance over a signed knowledge base — an internal a11oy function.',
    functions: [
      'grounded ask (cites its source, refuses to fabricate)',
      '13-axis Trust Score (geometric-mean aggregate, floor 0.90)',
      'knowledge ontology (axioms → theorems → formulas)',
      'model router (5-tier, cost-aware)'
    ],
    proof: [
      'Trust-Score CI from CONFORMAL (W5-3 + W7-4) — distribution-free, anti-overconfidence floor (never 100%, NOT Hoeffding)',
      'Model-Router stability C20 + PAC-Bayes/router envelope W7-5 (min ≤ avg ≤ max)',
      'Ontology label-invariance: F-G2 / F-G4 / F-G6 / W7-1 (graph substrate, wave 6/7)'
    ]
  },
  {
    id: 'policy', title: 'Policy & Compliance',
    color: 0xd7b96b, angle: 2.094,
    plain: 'Deny-by-default safety gates and full ALLOW/DENY verdicts with signed receipts — an internal a11oy function.',
    functions: [
      '8 deny-by-default safety gates',
      'full verdict (ALLOW / DENY) with signals + receipt hash',
      '30-signature threat corpus (MITRE ATT&CK + CVSS)',
      'readiness / compliance (NIST / STIG / ISO)'
    ],
    proof: [
      'Gate-soundness P2 — no action without BOTH policy AND kernel/doctrine check; a single DENY is absorbing',
      'Agentic-loop P3 non-interference — poisoned input provably cannot flip a DENY into an ALLOW'
    ]
  },
  {
    id: 'operator', title: 'Operator · Ask / Act / Approvals',
    color: 0xe58e54, angle: 4.189,
    plain: 'The governed run loop: ask, act with approvals, and emit replayable signed receipts — an internal a11oy function.',
    functions: [
      'governed run loop P1–P6 (sign → gate → chain → memory → replay)',
      'human approvals gate for high-impact actions',
      'replayable, hash-chained receipts (Khipu)',
      'governed agentic coder (P1–P6), open-weight models'
    ],
    proof: [
      'Agentic-loop P1–P6 (PR #188): 28 kernel-verified theorems — run is auditable, gate-sound, injection-resistant end-to-end',
      'P5 replay-determinism gated only by declared hashFn_collision_resistant axiom (named, not a hardness proof)'
    ]
  }
];

const A11OY = {
  id: 'a11oy', title: 'a11oy — Command Platform (the brain)',
  plain: 'The orchestrating governance substrate: one brain coordinating reasoning, policy and operator capabilities. Every result carries a signed provenance receipt. Live: /healthz · /lambda.',
  functions: [
    'command center + five superpowers + 25-demo Warhacker board (5×5 live)',
    'a11oy Code (governed agentic coder, P1–P6, open-weight router)',
    'one governance substrate (capabilities are internal, no service split)',
    '13-axis Trust Score aggregate (yuyay_v3, geometric mean, floor 0.90)',
    '/proven: wave 9/10 formula cards (several with live runtime checks)',
    'signed Khipu receipts for every governed action'
  ],
  proof: [
    'Locked proven kernel = 8 @ c7c0ba17 (749 decl / 14 unique axioms / 163 sorries) — machine-enforced count, never moves',
    'Experimental tier (kernel 7885fd9, Lean v4.18.0): 1304 declarations, 36 CI-green theorems (Wave5-8 + agentic P1-P6 + airtight Λ + coder) — kernel-verified but NOT folded into the locked 8',
    'Λ-Aggregator uniqueness (F23) = Conjecture 1 — NOT a theorem (open CAUCHY_ND sorry + missing symmetry axiom; unconditional uniqueness machine-checked FALSE)',
    'Λ proven CONDITIONAL on slice-multiplicativity (separability) under {A1,A2,A3,A5}, axiom-free — CUT-2 (PR #202); Byzantine BFT safety stays Conjecture 2'
  ],
  url: 'https://szlholdings-a11oy.hf.space'
};

const KILLINCHU = {
  id: 'killinchu', title: 'killinchu — Field Node (drones & vessels)',
  plain: 'Counter-UAS drone & vessel intelligence at the tactical edge — the deployed field node of the substrate. Effectors are SIMULATED. Live: /healthz.',
  functions: [
    'maritime + drone C2 — vessels consolidated into killinchu (/elite fleet group)',
    'OpenDroneID / ASTM F3411 · ADS-B Mode-S 1090ES · MAVLink v1/v2 decoders',
    'counter-UAS A-gate + 13-axis edge Λ verdict · tactical routing · threat ranking (effectors SIMULATED)',
    '/wave910: wave 9/10 edge formula cards · Q2 Gershgorin spectral bound',
    'signed Khipu receipts (ECDSA-P256 DSSE when the signing key is present; else UNSIGNED, labelled)'
  ],
  proof: [
    'Edge verdict bound by proven formulas: C20/W7-5 router, W5-3/W7-4 conformal (never 100%)',
    'Experimental frontier (Wave 12 CF-13 DEQ input-Lipschitz, CF-17 fp-summation stability; Wave 14 CF-19 Reed–Solomon MDS bound) — never folded into the locked 8',
    'Same doctrine lock 749/14/163 @ c7c0ba17 · Λ = Conjecture 1 · Khipu BFT = Conjecture 2 · SLSA L1 honest / L2 roadmap'
  ],
  url: 'https://szlholdings-killinchu.hf.space'
};

/* compute-fabric inspector content is built live from /compute-pool (honest tiers). */
const FABRIC = {
  id: 'fabric', title: 'Sovereign compute fabric',
  plain: 'A real multi-node compute pool. Sovereign = owned self-hosted hardware (the box + the RTX). Hosted APIs and cloud GPUs are fallback only — labelled NON-sovereign. No energy/joule claim made here.',
  functions: ['live node roster loads from /api/a11oy/v1/compute-pool'],
  proof: ['No node fabricated · reachable=true only on a real probe this poll · Λ = Conjecture 1, not one of the locked 8'],
  url: 'https://a11oy.net/api/a11oy/v1/compute-pool'
};

/* ---------- live endpoints (real /healthz + live data; CORS open) ----------- */
const ENDPOINTS = {
  a11oy: {
    health: 'https://szlholdings-a11oy.hf.space/healthz',
    lambda: 'https://szlholdings-a11oy.hf.space/api/a11oy/v1/lambda'
  },
  killinchu: {
    health: 'https://szlholdings-killinchu.hf.space/healthz',
    ledger: 'https://szlholdings-killinchu.hf.space/api/killinchu/v1/khipu/ledger'
  },
  fabric: 'https://a11oy.net/api/a11oy/v1/compute-pool'
};

/* ---------- renderer / scene / camera --------------------------------------- */
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // perf: cap DPR
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.18;

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x070815, 0.0018);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 6000);
camera.position.set(0, 90, 380);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.minDistance = 90;
controls.maxDistance = 1400;
controls.enablePan = false;
controls.autoRotate = !REDUCED;            // cinematic idle orbit (off under reduced-motion)
controls.autoRotateSpeed = 0.40;
controls.target.set(0, 0, 0);

/* ---------- lighting --------------------------------------------------------- */
scene.add(new THREE.AmbientLight(0x33304a, 0.9));
const keyLight = new THREE.PointLight(0xffe6a8, 2.6, 2000, 1.4); // the sun emits warm gold
scene.add(keyLight);
const rim = new THREE.DirectionalLight(0x5c8fd1, 0.55); rim.position.set(-220, 130, -160); scene.add(rim);

/* ---------- deep star backdrop (depth, not data) ---------------------------- */
const disposables = [];
(function backdrop() {
  const N = 2600, pos = new Float32Array(N * 3), siz = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const r = 1500 + Math.random() * 1900;
    const t = Math.random() * Math.PI * 2, p = Math.acos(2 * Math.random() - 1);
    pos[i*3] = r*Math.sin(p)*Math.cos(t); pos[i*3+1] = r*Math.cos(p); pos[i*3+2] = r*Math.sin(p)*Math.sin(t);
    siz[i] = Math.random() < 0.08 ? 2.6 : 1.2;
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('size', new THREE.BufferAttribute(siz, 1));
  disposables.push(g);
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0x8a90c0, size: 1.5, sizeAttenuation: true, transparent: true, opacity: 0.55 })));
})();

/* ---------- soft radial glow sprite texture (sovereign, procedural) --------- */
function glowTexture(inner, outer) {
  const s = 128, c = document.createElement('canvas'); c.width = c.height = s;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(s/2, s/2, 0, s/2, s/2, s/2);
  g.addColorStop(0.0, inner);
  g.addColorStop(0.35, outer);
  g.addColorStop(1.0, 'rgba(0,0,0,0)');
  ctx.fillStyle = g; ctx.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c); tex.anisotropy = 2;
  return tex;
}
const GLOW_TEX = glowTexture('rgba(255,231,168,0.95)', 'rgba(216,154,46,0.35)');

/* ---------- interactable registry ------------------------------------------- */
const interactables = []; // meshes with userData.inspect + userData.focus
function registerBody(mesh, data, focusGetter) {
  mesh.userData.inspect = data;
  mesh.userData.focus = focusGetter; // () => {target:Vector3, dist:Number}
  interactables.push(mesh);
}

/* ---------- a11oy — the brain / sun (fresnel rim + layered additive bloom) -- */
const sunGroup = new THREE.Group(); scene.add(sunGroup);

// fresnel rim shader (vendored three ShaderMaterial only — no postprocessing CDN)
const sunCoreGeo = new THREE.IcosahedronGeometry(34, 5);
const sunMat = new THREE.ShaderMaterial({
  uniforms: {
    uTime: { value: 0 },
    uColorHot: { value: new THREE.Color(0xfff0c2) },
    uColorCore: { value: new THREE.Color(0xd79a2e) },
    uPulse: { value: 0.0 }      // breathing, tied to live healthz
  },
  vertexShader: `
    varying vec3 vN; varying vec3 vView;
    void main(){
      vec3 p = position;
      vN = normalize(normalMatrix * normal);
      vec4 mv = modelViewMatrix * vec4(p,1.0);
      vView = normalize(-mv.xyz);
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: `
    uniform float uTime; uniform vec3 uColorHot; uniform vec3 uColorCore; uniform float uPulse;
    varying vec3 vN; varying vec3 vView;
    void main(){
      float fres = pow(1.0 - max(dot(vN, vView), 0.0), 2.2);
      float shimmer = 0.5 + 0.5*sin(uTime*1.4 + vN.y*6.0);
      vec3 col = mix(uColorCore, uColorHot, fres*0.85 + 0.15*shimmer);
      float glow = (0.55 + 0.45*uPulse);
      gl_FragColor = vec4(col * (1.15 + fres*1.6) * glow, 1.0);
    }`
});
const sunCore = new THREE.Mesh(sunCoreGeo, sunMat);
sunGroup.add(sunCore);
registerBody(sunCore, A11OY, () => ({ target: sunGroup.position.clone(), dist: 170 }));
disposables.push(sunCoreGeo);

// layered additive bloom sprites (fake bloom, sovereign)
const bloomSprites = [];
[ {s: 150, o: 0.42}, {s: 250, o: 0.26}, {s: 400, o: 0.14} ].forEach(L => {
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({
    map: GLOW_TEX, color: 0xffd98a, transparent: true, opacity: L.o,
    blending: THREE.AdditiveBlending, depthWrite: false
  }));
  spr.scale.set(L.s, L.s, 1);
  sunGroup.add(spr); bloomSprites.push({ spr, base: L.o, size: L.s });
});

// inner translucent glow shell
const sunGlowGeo = new THREE.SphereGeometry(48, 32, 32);
const sunGlow = new THREE.Mesh(sunGlowGeo, new THREE.MeshBasicMaterial({ color: 0xffd98a, transparent: true, opacity: 0.10, side: THREE.BackSide }));
sunGroup.add(sunGlow); disposables.push(sunGlowGeo);

// "brain" wireframe lattice (the orchestrating brain motif)
const brainGeo = new THREE.IcosahedronGeometry(42, 2);
const brainLattice = new THREE.Mesh(brainGeo, new THREE.MeshBasicMaterial({ color: 0xffe6a8, wireframe: true, transparent: true, opacity: 0.20 }));
sunGroup.add(brainLattice); disposables.push(brainGeo);
sunGroup.add(makeLabel('a11oy', 0xffe6a8, 64));

/* ---------- 3 internal capabilities orbiting the sun ------------------------ */
const ORBIT_R = 158;
const capBodies = [];
CAPABILITIES.forEach((cap) => {
  const grp = new THREE.Group();
  const geo = new THREE.IcosahedronGeometry(15, 2);
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: cap.color, emissive: cap.color, emissiveIntensity: 0.6, roughness: 0.5, metalness: 0.2 }));
  grp.add(mesh); disposables.push(geo);
  const ringGeo = new THREE.TorusGeometry(22, 0.7, 8, 64);
  const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: cap.color, transparent: true, opacity: 0.35 }));
  ring.rotation.x = Math.PI / 2; grp.add(ring); disposables.push(ringGeo);
  // soft glow halo per capability
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW_TEX, color: cap.color, transparent: true, opacity: 0.30, blending: THREE.AdditiveBlending, depthWrite: false }));
  halo.scale.set(70, 70, 1); grp.add(halo);
  grp.add(makeLabel(cap.title.split(/[ &·]/)[0], cap.color, 30));
  scene.add(grp);
  const entry = { grp, mesh, cap, baseAngle: cap.angle };
  registerBody(mesh, cap, () => ({ target: grp.position.clone(), dist: 95 }));
  capBodies.push(entry);
  const tether = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: cap.color, transparent: true, opacity: 0.28 })
  );
  scene.add(tether); entry.tether = tether;
});

/* ---------- sovereign compute fabric ring (real nodes, honest tier) --------- */
const fabricGroup = new THREE.Group(); scene.add(fabricGroup);
let fabricNodes = []; // {mesh, sovereign, reachable}
const FABRIC_R = 240;
function colorForNode(n){
  if (!n.reachable) return 0x6b6f86;          // unreachable = grey
  if (n.sovereign)  return 0x4fd18b;           // owned, live = teal/green
  return 0x9b8cff;                              // reachable but hosted/non-sovereign = violet
}
function renderFabric(nodes){
  // dispose old
  fabricNodes.forEach(o => { fabricGroup.remove(o.mesh); o.mesh.geometry.dispose(); });
  fabricNodes = [];
  if (!nodes || !nodes.length) return;
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2;
    const geo = n.kind && n.kind.includes('gpu')
      ? new THREE.OctahedronGeometry(7, 0)
      : new THREE.BoxGeometry(9, 9, 9);
    const col = colorForNode(n);
    const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: col, emissive: col, emissiveIntensity: n.reachable ? 0.7 : 0.15,
      roughness: 0.5, metalness: 0.3, transparent: true, opacity: n.reachable ? 0.95 : 0.5
    }));
    m.position.set(Math.cos(a) * FABRIC_R, Math.sin(a * 1.7) * 30 - 70, Math.sin(a) * FABRIC_R);
    m.userData.inspect = { ...FABRIC, title: 'Compute node · ' + (n.name || 'node'),
      plain: (n.sovereign ? 'SOVEREIGN (owned self-hosted hardware). ' : 'NON-sovereign — hosted/cloud fallback, not owned compute. ')
             + (n.reachable ? 'Reachable on this poll. ' : 'NOT reachable this poll. ')
             + (n.detail || ''),
      functions: [ 'kind: ' + (n.kind || '—'), 'endpoint: ' + (n.endpoint || '—'),
                   'capabilities: ' + ((n.capabilities||[]).join(', ') || '—'),
                   (n.models && n.models.length ? 'models: ' + n.models.join(', ') : 'models: —') ],
      proof: [ n.source || 'live /compute-pool', 'No energy/joule claim. Λ = Conjecture 1, not one of the locked 8.' ],
      url: FABRIC.url };
    m.userData.focus = () => ({ target: m.getWorldPosition(new THREE.Vector3()), dist: 70 });
    fabricGroup.add(m); interactables.push(m);
    fabricNodes.push({ mesh: m, sovereign: n.sovereign, reachable: n.reachable });
  });
}

/* ---------- killinchu — the field node (offset, deployed at the edge) ------- */
const fieldGroup = new THREE.Group();
fieldGroup.position.set(380, -50, -130);
const fieldGeo = new THREE.OctahedronGeometry(20, 0);
const fieldNode = new THREE.Mesh(fieldGeo, new THREE.MeshStandardMaterial({ color: 0x5c8fd1, emissive: 0x2c5f9e, emissiveIntensity: 0.65, roughness: 0.45, metalness: 0.3 }));
fieldGroup.add(fieldNode); disposables.push(fieldGeo);
const fieldRingGeo = new THREE.TorusGeometry(30, 0.8, 8, 80);
const fieldRing = new THREE.Mesh(fieldRingGeo, new THREE.MeshBasicMaterial({ color: 0x5c8fd1, transparent: true, opacity: 0.4 }));
fieldRing.rotation.x = Math.PI / 2.4; fieldGroup.add(fieldRing); disposables.push(fieldRingGeo);
const fieldHalo = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW_TEX, color: 0x5c8fd1, transparent: true, opacity: 0.28, blending: THREE.AdditiveBlending, depthWrite: false }));
fieldHalo.scale.set(95, 95, 1); fieldGroup.add(fieldHalo);
fieldGroup.add(makeLabel('killinchu', 0x8fb6e6, 40));
scene.add(fieldGroup);
registerBody(fieldNode, KILLINCHU, () => ({ target: fieldGroup.position.clone(), dist: 120 }));
// Wire D — traceparent link sun ↔ field node (the substrate reaches the edge)
const fieldWire = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0), fieldGroup.position.clone()]),
  new THREE.LineBasicMaterial({ color: 0x9b8cff, transparent: true, opacity: 0.4 })
);
scene.add(fieldWire);

/* ---------- Khipu constellation: receipt stars + cord arcs (DAG) ------------ */
const khipuGroup = new THREE.Group(); scene.add(khipuGroup);
let receiptPoints = null, cordLines = null, receiptData = [];
let cordPulse = 0; // 0..1 pulse spike when a new receipt streams in
const VERDICT_COLOR = { allow: 0x4fd18b, advisory: 0xd7b96b, deny: 0xc0392b };
function verdictOf(l){ return l >= 0.9 ? 'allow' : (l >= 0.5 ? 'advisory' : 'deny'); }

// deterministic hash → unit sphere position (reproducible across reloads)
function seededVec(seed, radius){
  let h = 2166136261 >>> 0;
  for (let i=0;i<seed.length;i++){ h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  const a = (h % 10000)/10000 * Math.PI*2;
  const b = Math.acos(2*(((h>>>13)%10000)/10000)-1);
  const r = radius * (0.55 + 0.45*(((h>>>7)%10000)/10000));
  return new THREE.Vector3(r*Math.sin(b)*Math.cos(a), r*Math.cos(b), r*Math.sin(b)*Math.sin(a));
}

// Build a deterministic SEED constellation (clearly labelled SEED until live answers).
function seedConstellation(){
  const arr = [];
  for (let i=0;i<64;i++){
    const id = 'seed-'+i.toString(16).padStart(4,'0');
    // honest spread of seed verdicts: mostly allow, a few advisory, rare deny
    const roll = ((i*2654435761)>>>0)%100;
    const l = roll < 80 ? 0.90 + (roll%10)/100 : (roll < 95 ? 0.62 + (roll%30)/100 : 0.30 + (roll%20)/100);
    arr.push({ id, prev: i>0 && (i%5!==0) ? 'seed-'+(i-1).toString(16).padStart(4,'0') : null,
               lambda: Math.min(0.999, l), source: 'SEED' });
  }
  return arr;
}

function renderConstellation(nodes, isNew){
  receiptData = nodes;
  if (receiptPoints){ khipuGroup.remove(receiptPoints); receiptPoints.geometry.dispose(); receiptPoints.material.dispose(); }
  if (cordLines){ khipuGroup.remove(cordLines); cordLines.geometry.dispose(); cordLines.material.dispose(); }
  const pos = new Float32Array(nodes.length*3), col = new Float32Array(nodes.length*3);
  const byId = {};
  nodes.forEach((n,i)=>{
    const v = seededVec(n.id, 250); n._v = v; byId[n.id] = v;
    pos[i*3]=v.x; pos[i*3+1]=v.y; pos[i*3+2]=v.z;
    const c = new THREE.Color(VERDICT_COLOR[verdictOf(n.lambda)] || 0x888888);
    col[i*3]=c.r; col[i*3+1]=c.g; col[i*3+2]=c.b;
  });
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos,3));
  g.setAttribute('color', new THREE.BufferAttribute(col,3));
  receiptPoints = new THREE.Points(g, new THREE.PointsMaterial({ size: 5.0, vertexColors:true, transparent:true, opacity:0.94, sizeAttenuation:true, map: GLOW_TEX, blending: THREE.AdditiveBlending, depthWrite:false }));
  khipuGroup.add(receiptPoints);
  // cord arcs: prev → cur (the receipt DAG cords / quipu), coloured by child verdict
  const linePos = [], lineCol = [];
  nodes.forEach((n)=>{ if (n.prev && byId[n.prev]){ const a=byId[n.prev], b=n._v;
    const mid = a.clone().add(b).multiplyScalar(0.5).multiplyScalar(1.18);
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(10);
    const cc = new THREE.Color(VERDICT_COLOR[verdictOf(n.lambda)] || 0xc08f2f);
    for (let k=0;k<curve.length-1;k++){
      linePos.push(curve[k].x,curve[k].y,curve[k].z, curve[k+1].x,curve[k+1].y,curve[k+1].z);
      lineCol.push(cc.r,cc.g,cc.b, cc.r,cc.g,cc.b);
    }
  }});
  const lg = new THREE.BufferGeometry();
  lg.setAttribute('position', new THREE.Float32BufferAttribute(linePos,3));
  lg.setAttribute('color', new THREE.Float32BufferAttribute(lineCol,3));
  cordLines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ vertexColors:true, transparent:true, opacity:0.34 }));
  khipuGroup.add(cordLines);
  if (isNew && !REDUCED) cordPulse = 1.0; // spike a pulse when a new receipt set streams in
}

/* ---------- floating text label sprites (canvas texture) -------------------- */
function makeLabel(text, color, size){
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const ctx = c.getContext('2d');
  ctx.font = '700 34px ui-monospace, Menlo, Consolas, monospace';
  ctx.fillStyle = '#'+new THREE.Color(color).getHexString();
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(0,0,0,0.85)'; ctx.shadowBlur = 8;
  ctx.fillText(text, 128, 34);
  const tex = new THREE.CanvasTexture(c); tex.anisotropy = 4;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
  spr.scale.set(size*2, size*0.5, 1);
  spr.position.y = size*0.9;
  spr.userData.isLabel = true;
  return spr;
}

/* ---------- camera fly-to choreography -------------------------------------- */
let flying = null; // {fromPos, toPos, fromTgt, toTgt, t, dur}
function flyTo(target, dist){
  controls.autoRotate = false;
  const dir = camera.position.clone().sub(controls.target).normalize();
  const toPos = target.clone().add(dir.multiplyScalar(dist));
  flying = { fromPos: camera.position.clone(), toPos,
             fromTgt: controls.target.clone(), toTgt: target.clone(),
             t: 0, dur: REDUCED ? 0.001 : 1.05 };
}
function easeInOut(x){ return x < 0.5 ? 4*x*x*x : 1 - Math.pow(-2*x+2,3)/2; }

/* ---------- raycasting (click to inspect + fly) ----------------------------- */
const ray = new THREE.Raycaster(); ray.params.Points.threshold = 6;
const ptr = new THREE.Vector2();
let downXY = null;
function ptrFromEvent(e){
  const r = canvas.getBoundingClientRect();
  const cx = e.clientX ?? (e.touches && e.touches[0].clientX);
  const cy = e.clientY ?? (e.touches && e.touches[0].clientY);
  ptr.x = ((cx-r.left)/r.width)*2-1; ptr.y = -((cy-r.top)/r.height)*2+1;
  return { cx, cy };
}
canvas.addEventListener('pointerdown', (e)=>{ downXY = { x: e.clientX, y: e.clientY }; });
canvas.addEventListener('pointerup', (e)=>{
  if (!downXY) return;
  const moved = Math.hypot(e.clientX-downXY.x, e.clientY-downXY.y);
  downXY = null;
  if (moved > 6) return; // it was a drag/orbit, not a click
  ptrFromEvent(e);
  ray.setFromCamera(ptr, camera);
  const hits = ray.intersectObjects(interactables, false);
  if (hits.length){
    const o = hits[0].object;
    openInspector(o.userData.inspect);
    if (o.userData.focus){ const f = o.userData.focus(); flyTo(f.target, f.dist); }
  }
});

/* ---------- inspector panel ------------------------------------------------- */
const insp = document.getElementById('inspector');
document.getElementById('insp-close').addEventListener('click', ()=>{ insp.classList.remove('show'); controls.autoRotate = !REDUCED; });
function openInspector(d){
  if (!d) return;
  document.getElementById('insp-title').textContent = d.title;
  document.getElementById('insp-plain').textContent = d.plain;
  let html = '<div class="ih">Functions</div><ul>' + d.functions.map(f=>`<li>${esc(f)}</li>`).join('') + '</ul>';
  if (d.proof){ html += '<div class="ih">Proof support (honest)</div><ul>' + d.proof.map(p=>`<li class="proof">${esc(p)}</li>`).join('') + '</ul>'; }
  if (d.url){ html += `<div class="ih">Live</div><ul><li><a href="${esc(d.url)}" target="_blank" rel="noopener" style="color:#7fe0db">${esc(d.url)} ↗</a></li></ul>`; }
  document.getElementById('insp-body').innerHTML = html;
  insp.classList.add('show');
}
function esc(s){ return String(s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

/* ---------- live polling + honest SEED→LIVE promotion ----------------------- */
let liveState = { a11oy:'…', killinchu:'…' }, fabricCounts = null;
let feedSource = 'SEED', lastLambda = null, sunPulseTarget = 0.5;
const ticker = []; // recent receipt-feed lines

async function getJSON(url, ms){
  const ctrl = new AbortController(); const t = setTimeout(()=>ctrl.abort(), ms||7000);
  try { const r = await fetch(url, { signal: ctrl.signal, headers:{accept:'application/json'} });
    if (!r.ok) throw new Error('HTTP '+r.status); return await r.json(); }
  finally { clearTimeout(t); }
}
function pushTicker(line){ ticker.unshift(line); if (ticker.length > 4) ticker.pop(); paintTicker(); }

let prevReceiptIds = '';
async function poll(){
  // 1) health (drives status dots + sun breathing target)
  let healthy = 0;
  await Promise.all(['a11oy','killinchu'].map(async k=>{
    try { const h = await getJSON(ENDPOINTS[k].health, 7000); const ok = h && h.status==='ok'; liveState[k] = ok ? 'LIVE' : 'DEGRADED'; if (ok) healthy++; }
    catch(_) { liveState[k] = 'OFFLINE'; }
  }));
  sunPulseTarget = 0.30 + 0.35*healthy; // 0.30..1.0 brighter when both live

  // 2) sovereign compute fabric (real nodes)
  try {
    const cp = await getJSON(ENDPOINTS.fabric, 8000);
    if (cp && Array.isArray(cp.nodes)){
      renderFabric(cp.nodes); fabricCounts = cp.counts || null;
    }
  } catch(_) { /* keep last fabric render; honest */ }

  // 3) live constellation: prefer killinchu real ledger; else colour SEED with live a11oy Λ; else SEED
  let nodes = null, src = 'SEED · deterministic (no live receipts yet)';
  try {
    const led = await getJSON(ENDPOINTS.killinchu.ledger, 7000);
    if (led && Array.isArray(led.nodes) && led.nodes.length){
      nodes = led.nodes.map((n,i)=>({ id: (n.digest||('k'+i)).slice(0,16), prev: (n.parents&&n.parents[0])?String(n.parents[0]).slice(0,16):null,
        lambda: typeof n.lambda==='number' ? n.lambda : (n.signed?0.92:0.40), source:'LIVE' }));
      src = 'LIVE · killinchu khipu ledger ('+nodes.length+' receipts · '+(led.slsa||'SLSA L1')+')';
    } else if (led && Array.isArray(led.nodes)) {
      // ledger reachable but EMPTY — honest: ledger is in-memory per Space, non-persistent
      src = 'LIVE ledger reachable · 0 receipts (in-memory, non-persistent) · showing SEED';
    }
  } catch(_) {}
  if (!nodes){
    try {
      const lam = await getJSON(ENDPOINTS.a11oy.lambda, 7000);
      if (lam && typeof lam.lambda==='number'){
        lastLambda = lam.lambda;
        nodes = seedConstellation().map(n=>({ ...n, lambda: lam.lambda, source:'SEED+liveΛ' }));
        src = 'SEED positions · LIVE a11oy Λ='+lam.lambda.toFixed(3)+' (13-axis Trust Score, floor '+(lam.lambda_floor??0.9)+')';
      }
    } catch(_) {}
  }
  if (!nodes) nodes = seedConstellation();
  feedSource = src;

  const ids = nodes.map(n=>n.id).join('|');
  const isNew = ids !== prevReceiptIds && prevReceiptIds !== '';
  renderConstellation(nodes, isNew);
  if (isNew){
    const top = nodes[0];
    pushTicker((top.source.startsWith('LIVE')?'◆ LIVE':'◇ seed') + ' ' + (top.id||'').slice(0,10) + ' · Λ ' + (top.lambda||0).toFixed(2) + ' · ' + verdictOf(top.lambda).toUpperCase());
  }
  prevReceiptIds = ids;
  paintHUD();
}

function paintHUD(){
  const rows = [
    { label:'a11oy · brain', s:liveState.a11oy },
    { label:'killinchu · field', s:liveState.killinchu }
  ];
  let html = rows.map(r=>{
    const cls = r.s==='LIVE' ? 'live' : (r.s==='OFFLINE' ? 'off' : 'seed');
    return `<div class="row"><span class="dot ${cls}"></span><span>${r.label}</span><span class="meta">${r.s}</span></div>`;
  }).join('');
  if (fabricCounts){
    html += `<div class="row"><span class="dot live"></span><span>compute fabric</span><span class="meta">${fabricCounts.nodes_reachable}/${fabricCounts.nodes_total} up · ${fabricCounts.gpu_nodes_reachable} GPU</span></div>`;
  }
  document.getElementById('status-rows').innerHTML = html;
  document.getElementById('feed-src').textContent = feedSource;
}
function paintTicker(){
  const el = document.getElementById('ticker-lines'); if (!el) return;
  el.innerHTML = ticker.length ? ticker.map(t=>`<div class="tk">${esc(t)}</div>`).join('') : '<div class="tk dim">awaiting receipt stream…</div>';
}

/* ---------- animation loop (delta-clamped, perf-safe) ----------------------- */
const clock = new THREE.Clock();
let acc = 0;
function animate(){
  requestAnimationFrame(animate);
  let dt = clock.getDelta(); if (dt > 0.05) dt = 0.05; // clamp after tab-switch
  acc += dt;
  const t = acc;

  // sun: shader time + breathing pulse toward live target
  sunMat.uniforms.uTime.value = t;
  const pulse = REDUCED ? sunPulseTarget : (0.5*sunPulseTarget + 0.5*(sunPulseTarget*(0.85+0.15*Math.sin(t*1.6))));
  sunMat.uniforms.uPulse.value += (pulse - sunMat.uniforms.uPulse.value) * 0.05;
  const bp = sunMat.uniforms.uPulse.value;
  keyLight.intensity = 1.8 + 1.4*bp;
  bloomSprites.forEach((b,i)=>{ b.spr.material.opacity = b.base * (0.7 + 0.6*bp); if(!REDUCED){ const s=b.size*(1+0.03*Math.sin(t*1.3+i)); b.spr.scale.set(s,s,1);} });

  if (!REDUCED){
    sunCore.rotation.y += 0.0015*dt*60; brainLattice.rotation.y -= 0.0011*dt*60; brainLattice.rotation.x += 0.0006*dt*60;
    sunGlow.material.opacity = 0.08 + 0.04*Math.sin(t*2);
    capBodies.forEach((cb,i)=>{
      const a = cb.baseAngle + t*0.55;
      const x = Math.cos(a)*ORBIT_R, z = Math.sin(a)*ORBIT_R, y = Math.sin(a*1.3+i)*24;
      cb.grp.position.set(x,y,z); cb.mesh.rotation.y += 0.01;
      cb.tether.geometry.setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(x,y,z)]);
      cb.tether.geometry.attributes.position.needsUpdate = true;
    });
    fieldNode.rotation.y += 0.008; fieldRing.rotation.z += 0.004;
    khipuGroup.rotation.y += 0.0006*dt*60;
    fabricGroup.rotation.y -= 0.0004*dt*60;
    fabricNodes.forEach((o,i)=>{ o.mesh.rotation.x += 0.01; o.mesh.rotation.y += 0.008; });
  } else {
    // reduced-motion: place capabilities statically along their base angle
    capBodies.forEach((cb,i)=>{ const a=cb.baseAngle; const x=Math.cos(a)*ORBIT_R, z=Math.sin(a)*ORBIT_R, y=Math.sin(a*1.3+i)*24;
      cb.grp.position.set(x,y,z); cb.tether.geometry.setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(x,y,z)]); cb.tether.geometry.attributes.position.needsUpdate = true; });
  }

  // cord pulse decay → brighten cords briefly when a new receipt streams in
  if (cordPulse > 0){ cordPulse = Math.max(0, cordPulse - dt*0.8);
    if (cordLines) cordLines.material.opacity = 0.34 + 0.5*cordPulse;
    if (receiptPoints) receiptPoints.material.opacity = 0.94 + 0.06*cordPulse;
  }

  // camera fly-to choreography
  if (flying){
    flying.t += dt / flying.dur;
    const k = easeInOut(Math.min(1, flying.t));
    camera.position.lerpVectors(flying.fromPos, flying.toPos, k);
    controls.target.lerpVectors(flying.fromTgt, flying.toTgt, k);
    if (flying.t >= 1) flying = null;
  }

  controls.update();
  renderer.render(scene, camera);
}

/* ---------- boot ------------------------------------------------------------ */
window.addEventListener('resize', ()=>{
  camera.aspect = window.innerWidth/window.innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
});

renderConstellation(seedConstellation(), false); // immediate honest SEED paint
paintHUD(); paintTicker();
animate();
requestAnimationFrame(()=> document.getElementById('boot').classList.add('hide'));
poll();
setInterval(poll, 8000);

// yield cinematic auto-orbit the moment the user grabs the scene
controls.addEventListener('start', ()=>{ controls.autoRotate = false; });
