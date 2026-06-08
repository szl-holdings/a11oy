/* ============================================================================
 * a11oy_operator_organ.js — The OPERATOR organ: live 3D infrastructure topology.
 *
 * PROVENANCE: the real 3D infra-visualization capability was ingested from an
 * internal showpiece Space and re-homed here as the platform's Operator organ.
 * The orbiting-node / signal-wire / live-health-poll engine is that capability;
 * it has been re-themed to a11oy's sovereign-gold palette and reframed as an
 * honest infrastructure topology (the 5 governed SZL services + the Operator
 * core). No banned codenames are surfaced — this is the "Operator" organ.
 *
 * 0 RUNTIME CDN: Three.js r160 + OrbitControls are vendored locally and loaded
 * via the import map ("three" -> /hero/vendor3d/three.module.min.js). Glow is
 * additive-blend sprites (no postprocessing pass), so nothing un-vendored is
 * needed. Honest live/cached/pending states only — no fabricated telemetry.
 *
 * Doctrine v11: locked-proven = 5 {F1,F11,F12,F18,F19}; Λ = Conjecture 1.
 * Signed-off-by: Opus 4.8 (Dev3 — Operator-organ ingest). Apache-2.0.
 * ========================================================================== */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const GOLD = 0xc9b787, GOLD_BRIGHT = 0xd6c69a, LIVE = 0x5a8a6e, WARN = 0xc7a14a, DOWN = 0x9a4a4a;

// Infra topology source — fetched server-side from /operator-organ/topology.json
// (which reads the org infra manifest + probes the 5 governed services). The
// nodes below are the honest fallback skeleton used until topology.json loads.
const FALLBACK = {
  core: { id: 'operator', name: 'Operator Core', role: 'orchestrator' },
  nodes: [
    { id: 'gate',        name: 'Trust Gate',        role: 'heart',       pos: [13, 6, 2] },
    { id: 'reasoning',   name: 'Reasoning Cortex',  role: 'brain',       pos: [8, 12, -3] },
    { id: 'receipts',    name: 'Receipt Bus',       role: 'circulatory', pos: [-13, 7, 2] },
    { id: 'telemetry',   name: 'Telemetry Spans',   role: 'nervous',     pos: [12, -5, 3] },
    { id: 'mesh',        name: 'Service Mesh',      role: 'skeleton',    pos: [-12, -5, 3] },
    { id: 'fleet',       name: 'Fleet C2',          role: 'effector',    pos: [0, 6, -15] },
  ],
};

let scene, camera, renderer, controls, raycaster, pointer;
let coreGroup, coreMat, nodes = {}, wires = [], clock = new THREE.Clock();
let topo = FALLBACK, lastFpsTime = performance.now(), frameCount = 0, fps = 60;
let dataMode = 'pending'; // live | cached | pending
const CENTER = new THREE.Vector3(0, 6, 0);
const PARTICLE_GEO = new THREE.SphereGeometry(0.13, 8, 6);
const PER_WIRE = 5;

init();

async function init() {
  const wrap = document.getElementById('scene');
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0a0a);
  scene.fog = new THREE.FogExp2(0x0a0a0a, 0.012);

  camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 1000);
  camera.position.set(0, 7, 34);

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  wrap.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0x2a2a33, 0.7));
  const key = new THREE.DirectionalLight(0xffe6b8, 1.0); key.position.set(6, 16, 12); scene.add(key);
  const fill = new THREE.DirectionalLight(0xc9b787, 0.4); fill.position.set(-12, 4, 8); scene.add(fill);
  scene.add(new THREE.PointLight(0xd6c69a, 0.7, 60));

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.07;
  controls.minDistance = 10; controls.maxDistance = 90;
  controls.target.copy(CENTER);

  raycaster = new THREE.Raycaster(); pointer = new THREE.Vector2();

  buildStarfield();
  await loadTopology();   // sets `topo` + dataMode before building
  buildCore();
  buildNodes();
  buildWires();
  buildUI();

  addEventListener('resize', onResize);
  pollHealth();
  setInterval(pollHealth, 30000);
  setInterval(updateClock, 1000); updateClock();
  animate();
}

function buildStarfield() {
  const n = REDUCED ? 600 : 1500, pos = [], col = [];
  const c1 = new THREE.Color(0x2a2a33), c2 = new THREE.Color(GOLD);
  for (let i = 0; i < n; i++) {
    pos.push((Math.random() - 0.5) * 280, (Math.random() - 0.5) * 280, (Math.random() - 0.5) * 280);
    const c = c1.clone().lerp(c2, Math.random() * 0.5);
    col.push(c.r, c.g, c.b);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ size: 0.4, vertexColors: true, transparent: true, opacity: 0.5 })));
}

function glowSprite(color, size, op) {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128;
  const g = cv.getContext('2d');
  const col = new THREE.Color(color);
  const rgb = `${(col.r*255)|0},${(col.g*255)|0},${(col.b*255)|0}`;
  const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, `rgba(${rgb},0.9)`); grd.addColorStop(0.4, `rgba(${rgb},0.35)`); grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, opacity: op, blending: THREE.AdditiveBlending, depthWrite: false }));
  s.scale.set(size, size, 1); return s;
}

// ---- central Operator core (orchestrator) ----
function buildCore() {
  coreGroup = new THREE.Group(); coreGroup.position.copy(CENTER);
  coreMat = new THREE.MeshStandardMaterial({ color: GOLD_BRIGHT, emissive: 0xb89a52, emissiveIntensity: 1.3, roughness: 0.4, metalness: 0.4, toneMapped: false });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(2.0, 2), coreMat);
  // gentle surface displacement for an organic governed-core look
  const p = core.geometry.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const v = new THREE.Vector3().fromBufferAttribute(p, i);
    const nn = 0.12 * Math.sin(v.x * 3) * Math.cos(v.y * 3) * Math.sin(v.z * 2.5);
    v.multiplyScalar(1 + nn); p.setXYZ(i, v.x, v.y, v.z);
  }
  core.geometry.computeVertexNormals();
  coreGroup.add(core);
  const cage = new THREE.Mesh(new THREE.IcosahedronGeometry(2.5, 1),
    new THREE.MeshBasicMaterial({ color: GOLD, wireframe: true, transparent: true, opacity: 0.35, toneMapped: false }));
  coreGroup.add(cage); coreGroup.userData.cage = cage;
  coreGroup.add(glowSprite(GOLD, 11, 0.5));
  coreGroup.add(makeLabel(topo.core.name || 'Operator Core', '#d6c69a', 1.05));
  coreGroup.children[coreGroup.children.length - 1].position.set(0, 3.4, 0);
  scene.add(coreGroup);
}

// ---- governed-service nodes orbiting the core ----
function buildNodes() {
  topo.nodes.forEach(nd => {
    const grp = new THREE.Group(); grp.position.set(...(nd.pos || [10, 0, 0]));
    const orb = new THREE.Mesh(new THREE.IcosahedronGeometry(0.85, 1),
      new THREE.MeshStandardMaterial({ color: 0x6a6a6a, emissive: 0x333333, emissiveIntensity: 0.6, metalness: 0.5, roughness: 0.35, toneMapped: false }));
    grp.add(orb);
    const halo = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.05, 8, 48),
      new THREE.MeshBasicMaterial({ color: 0x6a6a6a, transparent: true, opacity: 0.5, toneMapped: false }));
    grp.add(halo);
    grp.add(glowSprite(0x6a6a6a, 4.5, 0.35));
    const gl = grp.children[grp.children.length - 1];
    const label = makeLabel(nd.name, '#c9b787', 0.9); label.position.set(0, 1.9, 0); grp.add(label);
    scene.add(grp);
    nodes[nd.id] = { grp, orb, halo, glow: gl, label, data: nd, alive: null };
  });
}

// ---- signal wires from core to each node ----
function buildWires() {
  topo.nodes.forEach(nd => {
    const start = CENTER.clone();
    const end = new THREE.Vector3(...(nd.pos || [10, 0, 0]));
    const mid = start.clone().add(end).multiplyScalar(0.5).add(new THREE.Vector3((Math.random()-0.5)*2, 2.5, (Math.random()-0.5)*2));
    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    const grp = new THREE.Group();
    const pts = curve.getPoints(60);
    const dashed = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineDashedMaterial({ color: 0x6a6a6a, transparent: true, opacity: 0.5, dashSize: 0.4, gapSize: 0.3 }));
    dashed.computeLineDistances(); grp.add(dashed);
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.045, 8, false),
      new THREE.MeshStandardMaterial({ color: LIVE, emissive: LIVE, emissiveIntensity: 1.2, metalness: 0.3, roughness: 0.3, transparent: true, opacity: 0, toneMapped: false }));
    grp.add(tube);
    const particles = [];
    const pmat = new THREE.MeshBasicMaterial({ color: LIVE, toneMapped: false });
    for (let k = 0; k < PER_WIRE; k++) {
      const pp = new THREE.Mesh(PARTICLE_GEO, pmat.clone()); pp.userData = { t: k / PER_WIRE }; pp.visible = false;
      grp.add(pp); particles.push(pp);
    }
    scene.add(grp);
    wires.push({ id: nd.id, grp, dashed, tube, particles, curve, live: false });
  });
}

function makeLabel(text, color, scale) {
  const cv = document.createElement('canvas'); cv.width = 320; cv.height = 64;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = 'rgba(10,10,10,0.72)'; roundRect(ctx, 4, 8, 312, 48, 12); ctx.fill();
  ctx.font = 'bold 28px "Space Grotesk", Georgia, sans-serif'; ctx.fillStyle = color || '#f5f5f5';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, 160, 34);
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false }));
  spr.scale.set(4.2 * (scale || 1), 0.84 * (scale || 1), 1); return spr;
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

// ============================================================
// TOPOLOGY + LIVE HEALTH — server-side fetched, honest degrade
// ============================================================
async function loadTopology() {
  try {
    const r = await fetch('/operator-organ/topology.json', { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    if (r.ok) {
      const j = await r.json();
      if (j && Array.isArray(j.nodes) && j.nodes.length) { topo = j; dataMode = j.source === 'live' ? 'live' : 'cached'; }
    }
  } catch { dataMode = 'pending'; }
  setModeBadge();
}

async function pollHealth() {
  let alive = 0;
  for (const nd of topo.nodes) {
    let up = (typeof nd.healthy === 'boolean') ? nd.healthy : null;
    const n = nodes[nd.id]; if (!n) continue;
    if (up) alive++;
    const c = new THREE.Color(up === true ? LIVE : (up === false ? DOWN : WARN));
    n.orb.material.color.copy(c); n.orb.material.emissive.copy(c);
    n.halo.material.color.copy(c); n.glow.material.color.copy(c);
    const w = wires.find(x => x.id === nd.id);
    if (w) {
      w.live = up === true;
      w.dashed.visible = up !== true;
      w.tube.material.opacity = up === true ? 0.8 : 0;
      w.tube.material.color.copy(c); w.tube.material.emissive.copy(c);
      w.particles.forEach(p => { p.visible = up === true; p.material.color.copy(c); });
    }
  }
  // refresh topology (which carries live healthy flags) on each poll cycle
  await loadTopology();
  renderHUD(alive);
}

function setModeBadge() {
  const el = document.getElementById('opMode'); if (!el) return;
  const map = { live: ['LIVE', '#5a8a6e'], cached: ['CACHED', '#c7a14a'], pending: ['PENDING', '#9a4a4a'] };
  const [txt, col] = map[dataMode] || map.pending;
  el.textContent = txt; el.style.color = col;
}

function renderHUD(alive) {
  const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
  set('opNodes', topo.nodes.length);
  set('opAlive', `${alive}/${topo.nodes.length}`);
  const ul = document.getElementById('opList');
  if (ul) ul.innerHTML = topo.nodes.map(nd => {
    const st = nd.healthy === true ? 'up' : (nd.healthy === false ? 'down' : 'warn');
    const tag = nd.healthy === true ? 'live' : (nd.healthy === false ? 'down' : 'unmeasured');
    return `<div class="orow"><span class="od ${st}"></span>${nd.name}<span class="ot">${tag}</span></div>`;
  }).join('');
  setModeBadge();
}

function updateClock() { const el = document.getElementById('opClock'); if (el) el.textContent = new Date().toISOString().substring(11, 19) + 'Z'; }

function buildUI() {
  const reset = document.getElementById('btnReset');
  if (reset) reset.onclick = () => { controls.reset(); camera.position.set(0, 7, 34); };
}

function onResize() {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  if (coreGroup) {
    const b = 1 + Math.sin(t * 2.0) * 0.04;
    coreGroup.scale.setScalar(b);
    if (!REDUCED) { coreGroup.userData.cage.rotation.y += 0.004; coreGroup.userData.cage.rotation.x += 0.0025; }
    coreMat.emissiveIntensity = 1.2 + Math.sin(t * 2.6) * 0.3;
  }
  Object.values(nodes).forEach(n => { n.orb.rotation.y += 0.01; n.halo.rotation.z += 0.012; });
  wires.forEach(w => { if (w.live) w.particles.forEach(p => { p.userData.t = (p.userData.t + 0.007) % 1; p.position.copy(w.curve.getPoint(p.userData.t)); }); });
  controls.update();
  if (!document.hidden) renderer.render(scene, camera);
  frameCount++;
  const now = performance.now();
  if (now - lastFpsTime >= 1000) { fps = frameCount; frameCount = 0; lastFpsTime = now; const el = document.getElementById('opFps'); if (el) el.textContent = fps; }
}
