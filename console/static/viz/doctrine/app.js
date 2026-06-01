// Doctrine Cathedral — SZL Holdings
// First-person walkthrough of Doctrine v11 rendered as architecture.
// LOCKED v11 numbers shown verbatim: 749 declarations, 14 axioms, 163 sorries, 13-axis yuyay_v3.
// Metaphor is architectural (pillars / tiles / windows / dim-spots) — not religious.
// Three.js r171, WebGPURenderer baseline + WebGL2 fallback, PointerLockControls (WASD + mouse).

import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
// SZL canonical mobile layer (additive — desktop WASD/pointer-lock untouched).
import { SZLMobileControls } from './szl-mobile-controls.js';

// ---- LOCKED v11 constants (verbatim, do not change) ----
const N_DECLARATIONS = 749;
const N_AXIOMS = 14;
const N_SORRIES = 163;
const N_AXES = 13;
const GH = 'https://github.com/szl-holdings/lutar-lean/blob/main/';
const HONEST_EP = 'https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest';

// 14 axioms — names + Lean-style type signatures (A2=IsHomogeneous, A4=IsBounded per charter LOCK).
const AXIOMS = [
  ['A0_Receipted',     'axiom receipted : ∀ (a : Act), ∃ r : Khipu, Emits a r'],
  ['A1_ChainVerified', 'axiom chain_verified : ∀ r : Khipu, ChainVerified r → r.prev.ChainVerified'],
  ['A2_IsHomogeneous', 'axiom A2_IsHomogeneous : IsHomogeneous (Λ : Ctx → ℝ≥0)            -- positive-homogeneous'],
  ['A3_Monotone',      'axiom A3_monotone : Monotone (Λ : Ctx → ℝ≥0)'],
  ['A4_IsBounded',     'axiom A4_IsBounded : IsBounded (Λ : Ctx → ℝ≥0)                    -- Λ bounded'],
  ['A5_Conjunctive',   'axiom A5_conjunctive : Yuyay13 a = ∏ i, gate (axis i a) (floor i)'],
  ['A6_SacredFloor',   'axiom A6_sacred : ∀ i ∈ Sacred, axis i a ≥ 0.95'],
  ['A7_StructFloor',   'axiom A7_struct : ∀ i ∈ Structural, axis i a ≥ 0.90'],
  ['A8_HuklaPenalty',  'axiom A8_hukla : U a = base a * Real.exp (-β * (huklaCount a : ℝ))'],
  ['A9_HaltOnT01',     'axiom A9_halt : huklaTripwire a = T01 → U a = 0'],
  ['A10_Bekenstein',   'axiom A10_bekenstein : (𝒜.card : ℝ) ≤ BekensteinBound ctx'],
  ['A11_CostMono',     'axiom A11_cost_mono : ¬ silentUpshift (route req)'],
  ['A12_ReplayHash',   'axiom A12_replay : replayHash doctrine = 0xbacf5443…631fc5'],
  ['A13_SLSA',         'axiom A13_slsa : provenance doctrine ⊒ SLSA.L1'],
];

// 13 axes (yuyay_v3) — 2 sacred (≥0.95) + 7 structural (≥0.90) + 4 introspection (↔ HUKLLA T03/T04/T09/T10).
// Names follow the doctrine category structure (numbers are LOCKED; these descriptive labels are the v3 taxonomy).
const AXES = [
  ['Chiqap',   'sacred',        'truthfulness ≥ 0.95'],
  ['Hampiq',   'sacred',        'non-harm ≥ 0.95'],
  ['Allinkay', 'structural',    'integrity ≥ 0.90'],
  ['Sumaq',    'structural',    'coherence ≥ 0.90'],
  ['Kawsay',   'structural',    'robustness ≥ 0.90'],
  ['Ayni',     'structural',    'reciprocity ≥ 0.90'],
  ['Yanantin', 'structural',    'balance ≥ 0.90'],
  ['Chanin',   'structural',    'proportion ≥ 0.90'],
  ['Tinkuy',   'structural',    'convergence ≥ 0.90'],
  ['Yuyay',    'introspection', 'reflection ↔ HUKLLA T03'],
  ['Qhaway',   'introspection', 'self-monitor ↔ HUKLLA T04'],
  ['Willay',   'introspection', 'disclosure ↔ HUKLLA T09'],
  ['Amawta',   'introspection', 'meta-wisdom ↔ HUKLLA T10'],
];

const MASTER_FORMULA = 'P(x,t) = argmax_{a∈𝒜} [ Λ(x) · Yuyay₁₃(a) · exp(−β·HUKLLA(a)) · ∏_i Khipu_i(a) ]';

// ---------- renderer (WebGPU baseline, WebGL2 fallback) ----------
let renderer, BACKEND='webgl2';
async function makeRenderer(){
  if(navigator.gpu){
    try{ const m=await import('three/webgpu'); const r=new m.WebGPURenderer({antialias:true}); await r.init(); BACKEND='webgpu'; return r; }
    catch(e){ console.warn('WebGPU fallback',e); }
  }
  // Mobile (incl. iOS Safari): low-power, antialias off for battery + perf.
  const H = SZLMobileControls.rendererHints();
  return new THREE.WebGLRenderer({antialias:H.antialias, powerPreference:H.powerPreference});
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0f1e);
scene.fog = new THREE.Fog(0x0a0f1e, 30, 165);

const camera = new THREE.PerspectiveCamera(70, innerWidth/innerHeight, 0.1, 600);
camera.position.set(0, 4.2, 64);

// ---- hall dimensions ----
const HALL_W = 44, HALL_L = 150, WALL_H = 34;

// lights: cool ambient + warm altar light + window light shafts
scene.add(new THREE.AmbientLight(0x2a3a48, 0.9));
const altarLight = new THREE.PointLight(0xcda64a, 3.2, 120, 1.4); altarLight.position.set(0, 16, -64); scene.add(altarLight);
const hemi = new THREE.HemisphereLight(0x8fb6ff, 0x10151c, 0.55); scene.add(hemi);

// ---- floor: 749 declaration tiles (instanced grid) ----
const tileGeo = new THREE.BoxGeometry(2.0, 0.18, 2.0);
const tileMat = new THREE.MeshStandardMaterial({ color:0x14463f, emissive:0x0c2c28, emissiveIntensity:0.5, roughness:0.7, metalness:0.05 });
const tiles = new THREE.InstancedMesh(tileGeo, tileMat, N_DECLARATIONS);
const cols = 17;                                  // 17 * 44 = 748 ≈ 749 -> 17x44 grid then +1
const rows = Math.ceil(N_DECLARATIONS/cols);      // 44
const dummy = new THREE.Object3D(); const col = new THREE.Color();
let placed=0;
for(let r=0; r<rows && placed<N_DECLARATIONS; r++){
  for(let c=0; c<cols && placed<N_DECLARATIONS; c++){
    const x = (c-(cols-1)/2)*2.3;
    const z = 60 - r*3.0;                          // run from entrance (+z) to altar (−z)
    dummy.position.set(x, 0.09, z);
    dummy.scale.set(1,1,1); dummy.updateMatrix();
    tiles.setMatrixAt(placed, dummy.matrix);
    const shade = 0.7 + ((placed*1117)%100)/300;   // subtle deterministic variation
    col.setHex(0x168f89).multiplyScalar(shade);
    tiles.setColorAt(placed, col);
    placed++;
  }
}
tiles.count = placed; // === 749
scene.add(tiles);

// floor base slab
scene.add(new THREE.Mesh(new THREE.BoxGeometry(HALL_W, 0.3, HALL_L),
  new THREE.MeshStandardMaterial({ color:0x0c1118, roughness:1 })).translateY(-0.16).translateZ(-12));

// ---- walls ----
const wallMat = new THREE.MeshStandardMaterial({ color:0x1b222c, roughness:0.95 });
function wall(w,h,d,x,y,z){ const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d), wallMat); m.position.set(x,y,z); scene.add(m); return m; }
wall(2, WALL_H, HALL_L, -HALL_W/2, WALL_H/2-0.16, -12);  // left
wall(2, WALL_H, HALL_L,  HALL_W/2, WALL_H/2-0.16, -12);  // right
wall(HALL_W, WALL_H, 2, 0, WALL_H/2-0.16, -88);          // altar wall

// ---- 14 axiom pillars (clickable) ----
const PILLARS = [];
const pillarMat = () => new THREE.MeshStandardMaterial({ color:0x6b5224, emissive:0xcda64a, emissiveIntensity:0.22, roughness:0.6, metalness:0.25 });
for(let i=0;i<N_AXIOMS;i++){
  const side = i<7 ? -1 : 1;
  const idx = i%7;
  const z = 44 - idx*16;
  const x = side*(HALL_W/2-4.2);
  const h = 22;
  const g = new THREE.CylinderGeometry(1.5,1.8,h,18);
  const mesh = new THREE.Mesh(g, pillarMat());
  mesh.position.set(x, h/2, z);
  mesh.userData = { type:'axiom', i };
  // capital
  const cap = new THREE.Mesh(new THREE.BoxGeometry(4.2,1.2,4.2), pillarMat());
  cap.position.set(x, h+0.6, z); scene.add(cap);
  scene.add(mesh); PILLARS.push(mesh);
}

// ---- 163 sorry dim-spots (clickable) -> GitHub line links ----
let SORRY_DATA = [];
const SORRIES = [];
const sorryGeo = new THREE.SphereGeometry(0.5, 12, 12);
function placeSorries(){
  for(let i=0;i<N_SORRIES;i++){
    const ang = (i/N_SORRIES)*Math.PI*2*3.2;        // spiral across the floor
    const rad = 3 + (i/N_SORRIES)*16;
    const x = Math.cos(ang)*rad;
    const z = 30 - (i/N_SORRIES)*78;
    const mat = new THREE.MeshStandardMaterial({ color:0x222a33, emissive:0x3c4757, emissiveIntensity:0.25, roughness:1 });
    const m = new THREE.Mesh(sorryGeo, mat);
    m.position.set(x, 1.4, z);
    m.userData = { type:'sorry', i };
    scene.add(m); SORRIES.push(m);
  }
}

// ---- 13 stained-glass clerestory windows ----
const WINDOWS = [];
for(let i=0;i<N_AXES;i++){
  const side = i<7 ? -1 : 1;                          // 7 left, 6 right
  const idx = i<7 ? i : i-7;
  const z = 40 - idx*18;
  const x = side*(HALL_W/2-1.1);
  const cat = AXES[i][1];
  const hue = cat==='sacred' ? 0xcda64a : cat==='introspection' ? 0x8fb6ff : 0x34aaa4;
  const mat = new THREE.MeshStandardMaterial({ color:hue, emissive:hue, emissiveIntensity:1.1, transparent:true, opacity:0.82, side:THREE.DoubleSide });
  const m = new THREE.Mesh(new THREE.PlaneGeometry(5.5, 9), mat);
  m.position.set(x, WALL_H-9, z);
  m.rotation.y = side<0 ? Math.PI/2 : -Math.PI/2;
  m.userData = { type:'axis', i };
  scene.add(m); WINDOWS.push(m);
  // shaft of light into the hall
  const shaft = new THREE.PointLight(hue, 0.7, 40, 2); shaft.position.set(x*0.6, WALL_H-12, z); scene.add(shaft);
}

// ---- master formula floating above the altar ----
const altar = new THREE.Mesh(new THREE.BoxGeometry(10,2.4,6),
  new THREE.MeshStandardMaterial({ color:0x2a3340, emissive:0xc08f2f, emissiveIntensity:0.2, roughness:0.5 }));
altar.position.set(0, 1.2, -64); scene.add(altar);

function formulaSprite(){
  const c = document.createElement('canvas'); c.width=2048; c.height=256;
  const g = c.getContext('2d');
  g.fillStyle='rgba(10,15,30,0.0)'; g.fillRect(0,0,c.width,c.height);
  g.font='44px "IBM Plex Mono", monospace'; g.textAlign='center'; g.textBaseline='middle';
  g.shadowColor='#cda64a'; g.shadowBlur=24; g.fillStyle='#f5f7fa';
  g.fillText(MASTER_FORMULA, c.width/2, c.height/2);
  const tex = new THREE.CanvasTexture(c); tex.anisotropy=8;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map:tex, transparent:true }));
  spr.scale.set(40,5,1); spr.position.set(0, 18, -62);
  return spr;
}
scene.add(formulaSprite());

// ---- PointerLockControls (WASD + mouse) ----
const controls = new PointerLockControls(camera, document.body);
scene.add(controls.object || camera);
const enterOverlay = document.getElementById('enterOverlay');
document.getElementById('enterBtn').onclick = ()=> { if(!MC.isMobile) controls.lock(); else MC.enter(); };
controls.addEventListener('lock', ()=> enterOverlay.style.display='none');
controls.addEventListener('unlock', ()=> { if(!MC.isMobile) enterOverlay.style.display='flex'; });

// ---- MOBILE: virtual joystick + drag-look + pinch-zoom, NO pointer lock (iOS) ----
const mEuler = new THREE.Euler(0,0,0,'YXZ');
let mPitch = 0, mYaw = 0;
const MC = new SZLMobileControls({
  enterLabel: 'Enter (touch)',
  onEnter(){ enterOverlay.style.display='none'; mEuler.setFromQuaternion(camera.quaternion); mYaw = mEuler.y; mPitch = mEuler.x; },
  onExit(){ enterOverlay.style.display='flex'; }
});
if(MC.isMobile){
  const eb = document.getElementById('enterBtn');
  if(eb){ eb.textContent = 'Enter (touch — joystick + drag)'; eb.setAttribute('aria-label','Enter cathedral with touch controls'); }
  const ft = document.querySelector('#hud footer span'); if(ft) ft.innerHTML = '<b>Joystick</b> walk · <b>drag right</b> look · <b>pinch</b> zoom · <b>tap</b> inspect';
}

const keys = {};
addEventListener('keydown', e=>{ keys[e.code]=true; });
addEventListener('keyup',   e=>{ keys[e.code]=false; });
const vel = new THREE.Vector3();

// ---- picking on click (axiom -> Lean sig; sorry -> GitHub line) ----
const ray = new THREE.Raycaster(); const center = new THREE.Vector2(0,0);
const inspect = document.getElementById('inspect');
const inspectBody = document.getElementById('inspectBody');
document.getElementById('closeInspect').onclick = ()=> inspect.hidden=true;

function clickPick(){
  ray.setFromCamera(center, camera);
  const targets = [...PILLARS, ...SORRIES, ...WINDOWS];
  const hit = ray.intersectObjects(targets, false);
  if(!hit.length) return;
  const ud = hit[0].object.userData;
  if(ud.type==='axiom'){
    const [name,sig] = AXIOMS[ud.i];
    inspectBody.innerHTML = `<h2>Axiom ${ud.i+1}/14 — ${name}</h2><span class="k">Lean type signature</span><pre>${sig}</pre>`;
    inspect.hidden=false;
  } else if(ud.type==='sorry'){
    const s = SORRY_DATA[ud.i];
    if(s){
      const file = s.file, line = s.line;
      const url = GH + file + '#L' + line;
      inspectBody.innerHTML = `<h2>Sorry ${ud.i+1}/163</h2><span class="k">file · line (real)</span><pre>${file}:${line}</pre>`+
        `<span class="k">source line</span><pre>${(s.note||'sorry').slice(0,200)}</pre>`+
        `<a href="${url}" target="_blank" rel="noopener">${url}</a>`;
    } else {
      inspectBody.innerHTML = `<h2>Sorry ${ud.i+1}/163</h2>`+
        `<span class="k">status</span><pre>LOCKED count 163; ${SORRY_DATA.length} mapped to live GitHub lines. This dim spot is part of the locked tally; its line was not in the last enumeration.</pre>`+
        `<a href="https://github.com/szl-holdings/lutar-lean/search?q=sorry" target="_blank" rel="noopener">browse all sorries on GitHub</a>`;
    }
    inspect.hidden=false;
  } else if(ud.type==='axis'){
    const [name,cat,floor] = AXES[ud.i];
    inspectBody.innerHTML = `<h2>Axis ${ud.i+1}/13 — ${name}</h2><span class="k">category</span><pre>${cat}</pre>`+
      `<span class="k">gate</span><pre>${floor}</pre><span class="k">role</span><pre>yuyay_v3 conjunctive AND — score 0 unless all 13 axes clear floor</pre>`;
    inspect.hidden=false;
  }
}
document.addEventListener('click', ()=>{ if(controls.isLocked) clickPick(); });
if(MC.isMobile){
  let tStart=0, tx=0, ty=0;
  document.addEventListener('touchstart', e=>{ if(MC.active){ const t=e.changedTouches[0]; tStart=Date.now(); tx=t.clientX; ty=t.clientY; } }, {passive:true});
  document.addEventListener('touchend', e=>{
    if(!MC.active) return; const t=e.changedTouches[0];
    const moved = Math.hypot(t.clientX-tx, t.clientY-ty);
    if(Date.now()-tStart < 300 && moved < 14){
      const ndc = new THREE.Vector2((t.clientX/innerWidth)*2-1, -(t.clientY/innerHeight)*2+1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects([...PILLARS,...SORRIES,...WINDOWS], false);
      if(hit.length){ mobilePick(hit[0].object.userData); }
    }
  }, {passive:true});
}
function mobilePick(ud){
  if(ud.type==='axiom'){ const [name,sig]=AXIOMS[ud.i]; inspectBody.innerHTML=`<h2>Axiom ${ud.i+1}/14 — ${name}</h2><span class="k">Lean type signature</span><pre>${sig}</pre>`; inspect.hidden=false; }
  else if(ud.type==='sorry'){ const s=SORRY_DATA[ud.i]; if(s){ const url=GH+s.file+'#L'+s.line; inspectBody.innerHTML=`<h2>Sorry ${ud.i+1}/163</h2><pre>${s.file}:${s.line}</pre><a href="${url}" target="_blank" rel="noopener">${url}</a>`; } else { inspectBody.innerHTML=`<h2>Sorry ${ud.i+1}/163</h2><pre>LOCKED count 163.</pre>`; } inspect.hidden=false; }
  else if(ud.type==='axis'){ const [name,cat,floor]=AXES[ud.i]; inspectBody.innerHTML=`<h2>Axis ${ud.i+1}/13 — ${name}</h2><span class="k">category</span><pre>${cat}</pre><span class="k">gate</span><pre>${floor}</pre>`; inspect.hidden=false; }
}

// ---- load real sorry data + honest endpoint ----
async function loadData(){
  try{
    const res = await fetch('real_sorries.json', {cache:'no-store'});
    SORRY_DATA = await res.json();
  }catch(e){ SORRY_DATA = []; }
  placeSorries();
  // honest endpoint: live counts cross-check (never overwrites LOCKED numbers; only reports liveness)
  const pill = document.getElementById('dataPill');
  try{
    const ctrl = new AbortController(); const t=setTimeout(()=>ctrl.abort(),3500);
    const r = await fetch(HONEST_EP, {mode:'cors',cache:'no-store',signal:ctrl.signal}); clearTimeout(t);
    if(r.ok){ pill.textContent='LIVE honest ✓'; pill.className='pill live'; }
    else throw 0;
  }catch(e){ pill.textContent='DEMO (honest ep offline) · 749/14/163 from v11 LOCK'; pill.className='pill demo'; }
}

// ---- boot ----
async function boot(){
  renderer = await makeRenderer();
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(SZLMobileControls.rendererHints().pixelRatio);
  document.getElementById('root').appendChild(renderer.domElement);
  document.getElementById('renderPill').textContent = BACKEND.toUpperCase();
  addEventListener('resize', ()=>{ camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });
  await loadData();

  const clock = new THREE.Clock();
  function loop(){
    const dt = Math.min(clock.getDelta(), 0.05);
    if(controls.isLocked){
      const speed = (keys['ShiftLeft']||keys['ShiftRight']) ? 26 : 12;
      vel.set(0,0,0);
      if(keys['KeyW']||keys['ArrowUp']) vel.z -= 1;
      if(keys['KeyS']||keys['ArrowDown']) vel.z += 1;
      if(keys['KeyA']||keys['ArrowLeft']) vel.x -= 1;
      if(keys['KeyD']||keys['ArrowRight']) vel.x += 1;
      if(vel.lengthSq()>0) vel.normalize().multiplyScalar(speed*dt);
      controls.moveRight(vel.x); controls.moveForward(-vel.z);
      // clamp inside hall
      const o = controls.object || camera;
      o.position.x = Math.max(-HALL_W/2+2.5, Math.min(HALL_W/2-2.5, o.position.x));
      o.position.z = Math.max(-86, Math.min(63, o.position.z));
      o.position.y = 4.2;
      document.getElementById('pos').textContent = `x ${o.position.x.toFixed(0)}  z ${o.position.z.toFixed(0)}`;
    }
    if(MC.isMobile && MC.active){
      const mv = MC.getMove(); const look = MC.consumeLook(); const fov = MC.consumeFov();
      mYaw -= look.dx * 0.0024;
      mPitch = Math.max(-Math.PI/2+0.05, Math.min(Math.PI/2-0.05, mPitch - look.dy*0.0024));
      mEuler.set(mPitch, mYaw, 0, 'YXZ'); camera.quaternion.setFromEuler(mEuler);
      const speed = 12; vel.set(mv.x, 0, mv.y);
      if(vel.lengthSq()>0){ vel.normalize().multiplyScalar(speed*dt); controls.moveRight(vel.x); controls.moveForward(-vel.z); }
      const o = controls.object || camera;
      o.position.x = Math.max(-HALL_W/2+2.5, Math.min(HALL_W/2-2.5, o.position.x));
      o.position.z = Math.max(-86, Math.min(63, o.position.z)); o.position.y = 4.2;
      if(fov){ camera.fov = Math.max(40, Math.min(95, camera.fov + fov)); camera.updateProjectionMatrix(); }
      document.getElementById('pos').textContent = `x ${o.position.x.toFixed(0)}  z ${o.position.z.toFixed(0)}`;
    }
    const t = clock.getElapsedTime();
    altarLight.intensity = 3.0 + Math.sin(t*1.5)*0.4;
    WINDOWS.forEach((w,i)=> w.material.emissiveIntensity = 0.9 + Math.sin(t*0.8 + i)*0.25);
    if(!document.hidden) renderer.render(scene, camera);
    requestAnimationFrame(loop);
  }
  loop();
}
boot().catch(e=>{ document.getElementById('renderPill').textContent='ERR'; console.error(e); });
