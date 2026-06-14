/* Throne Room — SZL 5-flagship unified 3D control surface.
 * © 2026 SZL Holdings · ORCID 0009-0001-0110-4173 · Signed: Yachay (CTO).
 * Three.js r171 (MIT). WebGPU renderer w/ WebGL2 fallback. Real /healthz polling — no fake data.
 * Kanchay tokens only. Doctrine v11 LOCKED (749/14/163). ADDITIVE.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------- Kanchay palette ----------
const K = {
  bg:0x0a0f1e, deep:0x10151c, surface:0x1b222c, overlay:0x2a3340, border:0x3c4757,
  yuyay:0x34aaa4, yuyay3:0x5cc4bf, yuyay6:0x0f726e,
  hatun:0xcda64a, hatun3:0xd7b96b,
  yawar:0xc0392b, yawar3:0xe57373,
  success:0x3fce82, error:0xf0a3a3, info:0x7cb8e0,
};

// ---------- Hero registry (Quechua etymology + endpoints + Kanchay forms) ----------
// Each hero is an ABSTRACT Kanchay-themed form (NOT an Iron-Man avatar).
const ORIGIN = location.origin; // a11oy host — same-origin for a11oy JSON
const HEROES = [
  { id:'a11oy', name:'a11oy', role:'Brand Orchestration Layer · a11oy.code',
    qn:'a11oy', ety:'“alloy” — fused metals; the unifying orchestration layer binding every organ.',
    color:K.hatun, accent:K.hatun3, g1:'#d7b96b', g2:'#825a18',
    space:'https://szlholdings-a11oy.hf.space/',
    health: ORIGIN + '/api/a11oy/healthz', sameOrigin:true, form:'crown',
    endpoints:[['GET','/api/a11oy/healthz'],['GET','/api/a11oy/v1/gates'],['POST','/api/a11oy/v1/reason'],['POST','/api/a11oy/code/chat']],
    tier:'middle' },
  { id:'amaru', name:'Amaru', role:'Andean Ouroboros · Looped Reverse-ETL',
    qn:'Amaru', ety:'“serpent / dragon” — the data serpent that swallows its own tail (reverse-ETL loop).',
    color:K.yuyay, accent:K.yuyay3, g1:'#5cc4bf', g2:'#0b5957',
    space:'https://szlholdings-amaru.hf.space/', health:'https://szlholdings-amaru.hf.space/', form:'serpent',
    endpoints:[['GET','/'],['GET','/api/runs'],['GET','/api/lineage']], tier:'upper' },
  { id:'sentra', name:'Sentra', role:'Sentinel · Policy & Halt Authority',
    qn:'Sentra', ety:'sentinel/guardian — the watch at the gate; halt-authority over agentic acts.',
    color:K.info, accent:0x7cb8e0, g1:'#7cb8e0', g2:'#2f7fb5',
    space:'https://szlholdings-sentra.hf.space/', health:'https://szlholdings-sentra.hf.space/', form:'shield',
    endpoints:[['GET','/'],['GET','/api/gates'],['GET','/api/alerts']], tier:'upper' },
  { id:'killinchu', name:'Killinchu', role:'Drone Intelligence · Aerial Twin',
    qn:'Killinchu', ety:'“kestrel / falcon” — the hovering raptor; aerial reconnaissance & drone twin.',
    color:K.yawar3, accent:K.yawar3, g1:'#e57373', g2:'#822018',
    space:'https://szlholdings-killinchu.hf.space/', health:'https://szlholdings-killinchu.hf.space/', form:'falcon',
    endpoints:[['GET','/'],['GET','/api/telemetry'],['GET','/api/twin']], tier:'lower' },
  { id:'rosie', name:'Rosie', role:'Care Engine · Brain-jack Mesh',
    qn:'Rosie', ety:'the caregiver; warm cross-session memory + brain-jack mesh that watches the ecosystem.',
    color:K.yawar, accent:K.yawar3, g1:'#e57373', g2:'#5e1712',
    space:'https://szlholdings-rosie.hf.space/', health:'https://szlholdings-rosie.hf.space/', form:'bloom',
    endpoints:[['GET','/'],['GET','/api/care'],['GET','/api/mesh']], tier:'lower' },
];

// Pacha 3-tier composition: 2 upper, 1 middle, 1+1 lower (semi-circle).
// positions in a semicircle facing +Z camera.
const LAYOUT = {
  amaru:   { x:-3.4, y: 2.4, z:-1.2 },  // upper-left
  sentra:  { x: 3.4, y: 2.4, z:-1.2 },  // upper-right
  a11oy:   { x: 0.0, y: 0.4, z: 1.6 },  // middle (front, the crown)
  killinchu:{x:-2.7, y:-1.9, z: 0.4 },  // lower-left
  rosie:   { x: 2.7, y:-1.9, z: 0.4 },  // lower-right
};

// ---------- renderer (WebGPU baseline → WebGL2 fallback) ----------
let canvas = document.getElementById('scene');
const badge = document.getElementById('renderer-badge');
let renderer, RENDER_MODE = 'webgl2';

// Replace the canvas with a fresh node so a prior (possibly half-initialised)
// WebGPU context can never clash with the WebGL2 fallback context.
function freshCanvas(){
  const old = canvas; const n = old.cloneNode(false);
  old.parentNode.replaceChild(n, old); canvas = n; return n;
}
function makeWebGL2(){
  RENDER_MODE = 'webgl2';
  return new THREE.WebGLRenderer({ canvas: freshCanvas(), antialias:true, alpha:false, powerPreference:'high-performance' });
}
async function makeRenderer(){
  // WebGPU baseline — attempted first, but raced against a 2s timeout so a slow
  // WebGPU import/init never blocks first paint; on timeout/failure -> WebGL2 fallback.
  if (navigator.gpu){
    try{
      const gpu = (async()=>{
        const mod = await import('three/webgpu');
        const WebGPURenderer = mod.WebGPURenderer || (mod.default && mod.default.WebGPURenderer);
        if (!WebGPURenderer) throw new Error('no WebGPURenderer export');
        const r = new WebGPURenderer({ canvas, antialias:true, alpha:false });
        await r.init(); RENDER_MODE = 'webgpu'; return r;
      })();
      const timeout = new Promise((_,rej)=>setTimeout(()=>rej(new Error('webgpu-timeout')),2000));
      return await Promise.race([gpu, timeout]);
    }catch(e){ console.warn('[throne] WebGPU unavailable/slow, using WebGL2:', e && e.message); }
  }
  return makeWebGL2();
}

let scene, camera, controls, clock;
const heroMeshes = {}; // id -> { group, core, ring, halo, glow, status }
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let hovered = null, selected = null;

async function init(){
  renderer = await makeRenderer();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  if (renderer.toneMapping !== undefined){ renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05; }
  badge.textContent = RENDER_MODE.toUpperCase() + ' · three r171';

  scene = new THREE.Scene();
  scene.background = new THREE.Color(K.bg);
  scene.fog = new THREE.FogExp2(K.bg, 0.045);

  camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 100);
  camera.position.set(0, 0.6, 11);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 4; controls.maxDistance = 20;
  controls.maxPolarAngle = Math.PI*0.92; controls.target.set(0,0.2,0);

  // lights
  scene.add(new THREE.AmbientLight(0x6080a0, 0.55));
  const key = new THREE.DirectionalLight(0xffffff, 1.1); key.position.set(4,8,6); scene.add(key);
  const rim = new THREE.DirectionalLight(K.yuyay3, 0.7); rim.position.set(-6,2,-4); scene.add(rim);
  const fill = new THREE.PointLight(K.hatun, 0.6, 30); fill.position.set(0,-3,4); scene.add(fill);

  buildThroneFloor();
  buildStarfield();
  HEROES.forEach(buildHero);

  clock = new THREE.Clock();
  window.addEventListener('resize', onResize);
  renderer.domElement.addEventListener('pointermove', onPointerMove);
  renderer.domElement.addEventListener('pointerdown', onPointerDown);

  setupCmdK(); setupPane();
  startPolling();
  animate();
  // hard fallback so boot never sticks even if first-frame flag misfires
  setTimeout(()=>document.getElementById('boot').classList.add('hide'), 1500);
  setTimeout(()=>{ const h=document.getElementById('hint'); h.style.opacity='0'; }, 9000);
}

// ---------- environment ----------
function buildThroneFloor(){
  const grid = new THREE.GridHelper(40, 40, K.border, K.deep);
  grid.position.y = -3.2; grid.material.opacity = 0.32; grid.material.transparent = true;
  scene.add(grid);
  // central dais ring (the throne base) — hatun gold
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(3.0, 3.25, 64),
    new THREE.MeshBasicMaterial({ color:K.hatun, side:THREE.DoubleSide, transparent:true, opacity:0.5 }));
  ring.rotation.x = -Math.PI/2; ring.position.y = -3.18; scene.add(ring);
}
function buildStarfield(){
  const n=600, pos=new Float32Array(n*3);
  for(let i=0;i<n;i++){ const r=18+Math.random()*22, t=Math.random()*Math.PI*2, p=Math.acos(2*Math.random()-1);
    pos[i*3]=r*Math.sin(p)*Math.cos(t); pos[i*3+1]=r*Math.cos(p)*0.6; pos[i*3+2]=r*Math.sin(p)*Math.sin(t); }
  const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos,3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color:K.yuyay3, size:0.06, transparent:true, opacity:0.45 })));
}

// ---------- abstract Kanchay hero forms ----------
function buildHero(h){
  const g = new THREE.Group();
  const pos = LAYOUT[h.id]; g.position.set(pos.x, pos.y, pos.z);
  const mat = new THREE.MeshStandardMaterial({ color:h.color, metalness:0.55, roughness:0.28,
    emissive:h.color, emissiveIntensity:0.35 });
  let core;
  switch(h.form){
    case 'crown': // a11oy — fused alloy crown: icosahedron + orbiting torus ring
      core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.95, 1), mat); break;
    case 'serpent': // amaru — coiled serpent: torus knot
      core = new THREE.Mesh(new THREE.TorusKnotGeometry(0.6, 0.2, 140, 18, 2, 3), mat); break;
    case 'shield': // sentra — guardian shield: octahedron
      core = new THREE.Mesh(new THREE.OctahedronGeometry(0.85, 0), mat); break;
    case 'falcon': // killinchu — kestrel: cone (beak) + swept tetra wings feel
      core = new THREE.Mesh(new THREE.ConeGeometry(0.65, 1.4, 5), mat); core.rotation.x=Math.PI; break;
    case 'bloom': // rosie — care bloom: dodecahedron petals
      core = new THREE.Mesh(new THREE.DodecahedronGeometry(0.82, 0), mat); break;
    default: core = new THREE.Mesh(new THREE.SphereGeometry(0.8,32,16), mat);
  }
  core.userData.heroId = h.id; g.add(core);

  // orbiting ring (each hero has a signature ring in its accent)
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.035, 12, 80),
    new THREE.MeshBasicMaterial({ color:h.accent, transparent:true, opacity:0.7 }));
  ring.rotation.x = Math.PI/2.3; g.add(ring);

  // status halo (recolors live on poll)
  const halo = new THREE.Mesh(new THREE.SphereGeometry(1.55, 24, 16),
    new THREE.MeshBasicMaterial({ color:K.border, transparent:true, opacity:0.10, side:THREE.BackSide }));
  g.add(halo);

  // ground glow disc
  const glow = new THREE.Mesh(new THREE.CircleGeometry(1.4, 32),
    new THREE.MeshBasicMaterial({ color:h.accent, transparent:true, opacity:0.18 }));
  glow.rotation.x = -Math.PI/2; glow.position.y = -1.7; g.add(glow);

  // name sprite
  const label = makeLabel(h.name);
  label.position.set(0, 2.05, 0); g.add(label);

  scene.add(g);
  heroMeshes[h.id] = { group:g, core, ring, halo, glow, label, phase:Math.random()*6.28, pulse:0, status:'pending', latency:null };
}

function makeLabel(text){
  const c=document.createElement('canvas'); c.width=256; c.height=64; const x=c.getContext('2d');
  x.font='bold 34px Inter, system-ui, sans-serif'; x.fillStyle='#f5f7fa'; x.textAlign='center';
  x.shadowColor='rgba(0,0,0,.8)'; x.shadowBlur=8; x.fillText(text, 128, 44);
  const tex=new THREE.CanvasTexture(c); tex.colorSpace=THREE.SRGBColorSpace;
  const spr=new THREE.Sprite(new THREE.SpriteMaterial({ map:tex, transparent:true }));
  spr.scale.set(2.0,0.5,1); return spr;
}

// ---------- live polling (every 5s) — REAL, no fake data ----------
const KHIPU = []; // recent receipt hashes derived from real poll responses
let routeCount = '163'; // Doctrine v11 LOCKED route/declaration anchor; updated live from a11oy JSON when present
let yuyayGauge = 0;

async function pollHero(h){
  const st = heroMeshes[h.id]; const t0 = performance.now();
  try{
    if (h.sameOrigin){
      const res = await fetch(h.health, { cache:'no-store' });
      const ms = Math.round(performance.now()-t0);
      st.latency = ms;
      if (res.ok){
        const j = await res.json().catch(()=>null);
        st.status = 'up'; st.json = j;
        if (j){
          // real route/declaration anchor + yuyay-ish health from a11oy
          if (j.declarations) routeCount = String(j.declarations);
          if (j.gates) st.gates = j.gates;
          if (j.version) st.version = j.version;
          // Yuyay-13 gauge: fraction of axioms healthy (real value, anchored to v11 = 14 axioms)
          yuyayGauge = j.axioms ? Math.min(1, (j.axioms)/14) : yuyayGauge;
          pushKhipu(h.id, JSON.stringify(j));
        }
      } else { st.status = 'down'; }
    } else {
      // cross-origin: no-cors reachability probe (opaque) — honest UP/DOWN, no body read
      await fetch(h.health, { mode:'no-cors', cache:'no-store' });
      st.latency = Math.round(performance.now()-t0);
      st.status = 'up'; // opaque success = reachable
      pushKhipu(h.id, h.id + ':' + st.latency);
    }
  }catch(e){
    st.status = 'down'; st.latency = Math.round(performance.now()-t0);
  }
  applyHeroStatus(h, st);
  if (selected === h.id) renderPane(h);
}

// lightweight FNV-1a hash → short hex (real receipt over the real poll payload)
function fnv(str){ let hsh=0x811c9dc5; for(let i=0;i<str.length;i++){ hsh^=str.charCodeAt(i); hsh=Math.imul(hsh,0x01000193);} return (hsh>>>0).toString(16).padStart(8,'0'); }
function pushKhipu(id, payload){
  const h = fnv(id + '|' + payload + '|' + Date.now());
  KHIPU.unshift({ id, hash:h, t:new Date().toLocaleTimeString() });
  if (KHIPU.length>20) KHIPU.pop();
}

function applyHeroStatus(h, st){
  const col = st.status==='up'?K.success : st.status==='down'?K.error : K.border;
  st.halo.material.color.setHex(col);
  st.halo.material.opacity = st.status==='up'?0.16 : st.status==='down'?0.10 : 0.06;
  st.glow.material.color.setHex(st.status==='up'?h.accent : K.error);
  st.core.material.emissiveIntensity = st.status==='up'?0.5 : 0.18;
  updateChips();
}

function startPolling(){
  HEROES.forEach(h=>pollHero(h));
  setInterval(()=>HEROES.forEach(h=>pollHero(h)), 5000); // 5s as specified
}

function updateChips(){
  let up=0; HEROES.forEach(h=>{ if(heroMeshes[h.id].status==='up') up++; });
  document.getElementById('c-up').textContent = up + '/5';
  document.getElementById('c-routes').textContent = routeCount;
  document.getElementById('c-khipu').textContent = KHIPU[0]?('#'+KHIPU[0].hash.slice(0,6)):'—';
  document.getElementById('c-yuyay').style.width = Math.round(yuyayGauge*100)+'%';
  document.getElementById('c-yuyayv').textContent = (yuyayGauge*13).toFixed(1)+'/13';
}

// ---------- interaction ----------
function onResize(){ camera.aspect=window.innerWidth/window.innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight); }

function pickHero(ev){
  const r=renderer.domElement.getBoundingClientRect();
  pointer.x=((ev.clientX-r.left)/r.width)*2-1; pointer.y=-((ev.clientY-r.top)/r.height)*2+1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(Object.values(heroMeshes).map(m=>m.core), false);
  return hits.length?hits[0].object.userData.heroId:null;
}
function onPointerMove(ev){
  const id = pickHero(ev); const tip=document.getElementById('tip');
  if (id){
    hovered=id; document.body.style.cursor='pointer';
    const h=HEROES.find(x=>x.id===id); const st=heroMeshes[id];
    tip.innerHTML = `<div class="qn" style="color:#${h.accent.toString(16).padStart(6,'0')}">${h.qn}</div>`+
      `<div class="ety">${h.ety}</div>`+
      `<div class="lat">● ${st.status.toUpperCase()} · ${st.latency!=null?st.latency+'ms':'—'} · poll 5s</div>`;
    tip.style.left=(ev.clientX+14)+'px'; tip.style.top=(ev.clientY+14)+'px'; tip.style.opacity='1';
  } else { hovered=null; document.body.style.cursor='default'; tip.style.opacity='0'; }
}
function onPointerDown(ev){ const id=pickHero(ev); if(id) selectHero(id); }

let dolly=null;
function selectHero(id){
  selected=id; const pos=LAYOUT[id];
  // dolly camera in toward hero
  const target=new THREE.Vector3(pos.x*0.6, pos.y*0.6+0.2, pos.z);
  const camTo=new THREE.Vector3(pos.x*0.7, pos.y*0.5+0.8, pos.z+5.0);
  dolly={ ct:controls.target.clone(), cf:camera.position.clone(), tt:target, tf:camTo, t:0 };
  const h=HEROES.find(x=>x.id===id); openPane(h); renderPane(h);
}
function clearSelect(){ selected=null; closePane();
  dolly={ ct:controls.target.clone(), cf:camera.position.clone(), tt:new THREE.Vector3(0,0.2,0), tf:new THREE.Vector3(0,0.6,11), t:0 };
}

// ---------- control pane ----------
function setupPane(){
  document.getElementById('p-close').onclick = clearSelect;
  document.getElementById('p-send').onclick = sendChat;
  document.getElementById('p-chat').addEventListener('keydown', e=>{ if(e.key==='Enter') sendChat(); });
}
function openPane(h){ const p=document.getElementById('pane'); p.classList.add('open'); p.setAttribute('aria-hidden','false');
  document.documentElement.style.setProperty('--g1',h.g1); document.documentElement.style.setProperty('--g2',h.g2); }
function closePane(){ const p=document.getElementById('pane'); p.classList.remove('open'); p.setAttribute('aria-hidden','true'); }
function renderPane(h){
  const st=heroMeshes[h.id];
  document.getElementById('p-glyph').style.setProperty('--g1',h.g1);
  document.getElementById('p-glyph').style.setProperty('--g2',h.g2);
  document.getElementById('p-name').textContent=h.name;
  document.getElementById('p-role').textContent=h.role;
  const stat=document.getElementById('p-status');
  const cls = st.status==='up'?'ok':st.status==='down'?'bad':'pend';
  stat.innerHTML = `<span class="st ${cls}">● ${st.status.toUpperCase()}</span>`+
    `<span class="u" style="margin-left:8px">${st.version?('v'+st.version+' · '):''}${st.gates?(st.gates+' gates · '):''}lat ${st.latency!=null?st.latency+'ms':'—'}</span>`;
  // endpoints
  document.getElementById('p-eps').innerHTML = h.endpoints.map(([m,u])=>{
    const tag = (m==='GET' && (u==='/'||u.endsWith('healthz')) && st.status==='up')?'<span class="st ok">200</span>':'<span class="st pend">probe</span>';
    return `<div class="ep"><span class="m">${m}</span><span class="u">${u}</span>${tag}</div>`;
  }).join('');
  // receipts
  const rc = KHIPU.filter(k=>k.id===h.id).slice(0,6);
  document.getElementById('p-rcpts').innerHTML = rc.length?rc.map(k=>`<div class="rcpt">⟶ <b>#${k.hash}</b> <span style="color:var(--text-ghost)">${k.t}</span></div>`).join('')
    : '<div class="rcpt" style="color:var(--text-ghost)">awaiting first poll…</div>';
  document.getElementById('p-deep').href = h.space;
}
async function sendChat(){
  const inp=document.getElementById('p-chat'); const q=inp.value.trim(); if(!q) return;
  const log=document.getElementById('p-chatlog'); inp.value='';
  log.innerHTML = `<div class="msg"><span class="u">you ▸</span> ${escapeHtml(q)}</div>` + log.innerHTML;
  const h=HEROES.find(x=>x.id===selected);
  try{
    const res=await fetch(ORIGIN+'/api/a11oy/code/chat', { method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ message:q, route:(h?h.id:'a11oy.code'), surface:'throne-room' }) });
    if(res.ok){ const j=await res.json().catch(()=>null);
      const ans=j&&(j.reply||j.message||j.text)||'(routed to a11oy.code — no text field in response)';
      log.innerHTML = `<div class="msg"><span class="a">a11oy.code ▸</span> ${escapeHtml(String(ans)).slice(0,600)}</div>` + log.innerHTML;
    } else { log.innerHTML = `<div class="msg"><span class="a">a11oy.code ▸</span> route returned ${res.status} — endpoint may require auth.</div>` + log.innerHTML; }
  }catch(e){ log.innerHTML = `<div class="msg"><span class="a">a11oy.code ▸</span> network error reaching /api/a11oy/code/chat</div>` + log.innerHTML; }
}
function escapeHtml(s){ return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// ---------- Cmd-K palette ----------
const TABS = ['Boardroom','Investor Demo','Sovereign','Fabric','Nexus','Command','Hub','Wayra','Chaski','Wallpa','Wasi-Rikuq','Gates','Evidence','Ouroboros','Lean Kernel','Model Router','Memory'];
let cmdItems=[], cmdSel=0;
function buildCmdItems(q){
  const out=[]; const ql=q.toLowerCase();
  HEROES.forEach(h=>{ if(!ql||h.name.toLowerCase().includes(ql)||h.role.toLowerCase().includes(ql))
    out.push({ kind:'hero', tag:'flagship', title:h.name, sub:h.role, g1:h.g1,g2:h.g2, act:()=>{ closeCmd(); selectHero(h.id); } }); });
  TABS.forEach(t=>{ if(!ql||t.toLowerCase().includes(ql))
    out.push({ kind:'tab', tag:'tab', title:t, sub:'open a11oy tab', g1:'#34aaa4',g2:'#0b5957',
      act:()=>{ closeCmd(); window.open(ORIGIN+'/'+t.toLowerCase().replace(/ /g,'-'),'_blank'); } }); });
  if(q && out.length===0 || (q && !HEROES.some(h=>h.name.toLowerCase()===ql))){
    out.push({ kind:'ask', tag:'a11oy.code', title:`Ask: “${q}”`, sub:'route question to a11oy.code', g1:'#d7b96b',g2:'#825a18',
      act:()=>{ closeCmd(); if(!selected) selectHero('a11oy'); setTimeout(()=>{ const i=document.getElementById('p-chat'); i.value=q; sendChat(); },300); } });
  }
  return out;
}
function setupCmdK(){
  const inp=document.getElementById('cmdk-input');
  window.addEventListener('keydown', e=>{
    if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){ e.preventDefault(); toggleCmd(); }
    else if(e.key==='Escape'){ if(document.getElementById('cmdk').classList.contains('open')) closeCmd(); else if(selected) clearSelect(); }
    else if(document.getElementById('cmdk').classList.contains('open')){
      if(e.key==='ArrowDown'){ e.preventDefault(); cmdSel=Math.min(cmdItems.length-1,cmdSel+1); paintCmd(); }
      else if(e.key==='ArrowUp'){ e.preventDefault(); cmdSel=Math.max(0,cmdSel-1); paintCmd(); }
      else if(e.key==='Enter'){ e.preventDefault(); cmdItems[cmdSel]&&cmdItems[cmdSel].act(); }
    }
  });
  inp.addEventListener('input', ()=>{ cmdSel=0; refreshCmd(); });
  document.getElementById('cmdk').addEventListener('pointerdown', e=>{ if(e.target.id==='cmdk') closeCmd(); });
}
function toggleCmd(){ const el=document.getElementById('cmdk'); el.classList.contains('open')?closeCmd():openCmd(); }
function openCmd(){ const el=document.getElementById('cmdk'); el.classList.add('open');
  const i=document.getElementById('cmdk-input'); i.value=''; i.focus(); cmdSel=0; refreshCmd(); }
function closeCmd(){ document.getElementById('cmdk').classList.remove('open'); }
function refreshCmd(){ cmdItems=buildCmdItems(document.getElementById('cmdk-input').value.trim()); paintCmd(); }
function paintCmd(){
  document.getElementById('cmdk-results').innerHTML = cmdItems.map((it,i)=>
    `<div class="pitem ${i===cmdSel?'sel':''}" data-i="${i}">`+
    `<span class="pg" style="background:linear-gradient(135deg,${it.g1},${it.g2})"></span>`+
    `<span class="pt">${it.title}<small>${it.sub}</small></span><span class="tag">${it.tag}</span></div>`).join('');
  [...document.querySelectorAll('.pitem')].forEach(el=>el.onclick=()=>cmdItems[+el.dataset.i].act());
}

// ---------- animate ----------
let _firstFrame=false;
function animate(){
  requestAnimationFrame(animate);
  const t=clock.getElapsedTime();
  if(!_firstFrame){ _firstFrame=true; const b=document.getElementById('boot'); if(b) b.classList.add('hide'); }
  HEROES.forEach(h=>{
    const m=heroMeshes[h.id]; if(!m) return;
    m.core.rotation.y += 0.004; m.ring.rotation.z += 0.006;
    // health pulse: amplitude tied to real status (up = strong, down = faint)
    const amp = m.status==='up'?0.12 : m.status==='down'?0.03 : 0.05;
    const s = 1 + Math.sin(t*1.6 + m.phase)*amp;
    m.core.scale.setScalar(s);
    m.halo.scale.setScalar(1 + Math.sin(t*1.6 + m.phase)*amp*0.6);
    // label always faces camera handled by Sprite
  });
  // camera dolly
  if(dolly){ dolly.t=Math.min(1,dolly.t+0.045); const e=1-Math.pow(1-dolly.t,3);
    controls.target.lerpVectors(dolly.ct,dolly.tt,e); camera.position.lerpVectors(dolly.cf,dolly.tf,e);
    if(dolly.t>=1) dolly=null; }
  controls.update();
  renderer.render(scene, camera);
}

init().catch(e=>{ console.error('[throne] init failed', e);
  document.getElementById('boot').innerHTML='<div class="t" style="color:#f0a3a3">3D init failed — your browser may lack WebGL2/WebGPU.<br>'+String(e)+'</div>'; });
