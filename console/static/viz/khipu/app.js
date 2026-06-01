// Khipu Constellation — SZL Holdings
// Three.js r171, WebGPURenderer baseline with WebGL2 fallback.
// Every Khipu receipt across flagships = a star, positioned by hash(receiptId).
// Arcs connect chained receipts (prev -> cur). Polls real /v1/ledger endpoints every 5s.
// Honest DEMO MODE when an endpoint is unreachable; auto-promotes to LIVE on success.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
// SZL canonical mobile layer (additive).
import { SZLMobileControls } from './szl-mobile-controls.js';
const SZL_MOBILE = SZLMobileControls.isMobileDevice();
const SZL_REDUCED = SZLMobileControls.prefersReducedMotion();

// ---- Kanchay flagship registry + REAL endpoints (HATUN_WILLAY_PER_FLAGSHIP) ----
const FLAGSHIPS = [
  { id:'a11oy',     color:0x34aaa4, base:'https://szlholdings-a11oy.hf.space/api/a11oy' },
  { id:'amaru',     color:0x1f9d57, base:'https://szlholdings-amaru.hf.space/api/amaru' },
  { id:'sentra',    color:0xc0392b, base:'https://szlholdings-sentra.hf.space/api/sentra' },
  { id:'rosie',     color:0xc78aff, base:'https://szlholdings-rosie.hf.space/api/rosie' },
  { id:'vessels',   color:0xc08f2f, base:'https://szlholdings-vessels.hf.space/api/vessels' },
  { id:'killinchu', color:0x5cc4bf, base:'https://szlholdings-killinchu.hf.space/api/killinchu' },
];
const LEDGER = '/v1/ledger';
const POLL_MS = 5000;

// ---- deterministic hash -> 3D position on a shell (stable across reloads) ----
function fnv1a(str){ let h=0x811c9dc5; for(let i=0;i<str.length;i++){ h^=str.charCodeAt(i); h=Math.imul(h,0x01000193); } return h>>>0; }
function hashVec(id){
  const a=fnv1a(id), b=fnv1a(id+'#y'), c=fnv1a(id+'#z');
  // map to spherical shell; radius bands so chains read as constellations
  const u=(a%100000)/100000, v=(b%100000)/100000, w=(c%100000)/100000;
  const theta=u*Math.PI*2, phi=Math.acos(2*v-1);
  const r=42 + w*26;
  return new THREE.Vector3(
    r*Math.sin(phi)*Math.cos(theta),
    r*Math.cos(phi),
    r*Math.sin(phi)*Math.sin(theta)
  );
}

// ---- renderer: WebGPU baseline, WebGL2 fallback ----
let renderer, RENDER_BACKEND='webgl2';
async function makeRenderer(){
  if (navigator.gpu){
    try{
      const mod = await import('three/webgpu');
      const r = new mod.WebGPURenderer({ antialias:true, alpha:false });
      await r.init();
      RENDER_BACKEND='webgpu';
      return r;
    }catch(e){ console.warn('WebGPU init failed, falling back to WebGL2', e); }
  }
  const H = SZLMobileControls.rendererHints();
  const r = new THREE.WebGLRenderer({ antialias:H.antialias, alpha:false, powerPreference:H.powerPreference });
  RENDER_BACKEND='webgl2';
  return r;
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0f1e);
scene.fog = new THREE.FogExp2(0x0a0f1e, 0.0042);

const camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, 0.1, 2000);
camera.position.set(0, 18, 122);

// lights
scene.add(new THREE.AmbientLight(0x33424f, 1.1));
const key = new THREE.PointLight(0x34aaa4, 2.2, 600); key.position.set(40,80,60); scene.add(key);
const rim = new THREE.PointLight(0xc08f2f, 1.0, 600); rim.position.set(-80,-40,-40); scene.add(rim);

// faint galactic core glow + reference grid sphere
const core = new THREE.Mesh(new THREE.SphereGeometry(6,32,32),
  new THREE.MeshBasicMaterial({ color:0x168f89, transparent:true, opacity:0.18 }));
scene.add(core);

// ---- star instanced mesh ----
const MAX_STARS = 20000;
const starGeo = new THREE.IcosahedronGeometry(0.62, 1);
// Base color is white so per-instance instanceColor (flagship hue) shows through;
// emissive kept dark + low so stars read as colored points, not washed-out white blobs.
const starMat = new THREE.MeshStandardMaterial({ emissive:0x111722, emissiveIntensity:0.35, color:0xffffff, metalness:0.05, roughness:0.55, vertexColors:false });
const stars = new THREE.InstancedMesh(starGeo, starMat, MAX_STARS);
stars.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_STARS*3), 3);
stars.count = 0;
scene.add(stars);

// arcs container
const arcGroup = new THREE.Group(); scene.add(arcGroup);

const dummy = new THREE.Object3D();
const col = new THREE.Color();

// state
let receipts = [];           // {id, flagship, color, yuyay, ts, prev, pos}
let byId = new Map();
let liveFlags = new Set();
const enabled = new Set(FLAGSHIPS.map(f=>f.id));
let yuyayFloor = 0;
let timeWindowIdx = 6;        // 0..6 -> hours; 6 = all
const WINDOWS = [1,3,6,12,24,72,Infinity];

// ---- DEMO data generator (deterministic, labelled honestly) ----
function demoLedger(fid, n){
  const out=[]; let prev=null;
  for(let i=0;i<n;i++){
    const id = `${fid}-demo-${i.toString().padStart(4,'0')}`;
    // chain in runs of ~8
    const linked = (i%8!==0) ? prev : null;
    const yuyay = 0.62 + ((fnv1a(id)%38)/100); // 0.62..1.00
    const ts = Date.now() - (n-i)*42000;
    out.push({ receiptId:id, prev:linked, yuyayScore:+yuyay.toFixed(3), ts, chainVerified:true });
    prev = id;
  }
  return out;
}

// ---- fetch one flagship ledger; returns {ok, entries} ----
async function fetchLedger(f){
  const ctrl = new AbortController();
  const t = setTimeout(()=>ctrl.abort(), 3500);
  try{
    const res = await fetch(f.base+LEDGER, { mode:'cors', cache:'no-store', signal:ctrl.signal });
    clearTimeout(t);
    if(!res.ok) throw new Error('http '+res.status);
    const data = await res.json();
    const arr = Array.isArray(data) ? data : (data.receipts || data.entries || data.items || []);
    return { ok:true, entries: arr.map(normalize(f)) };
  }catch(e){
    clearTimeout(t);
    return { ok:false, entries: demoLedger(f.id, Math.round(320*SZLMobileControls.particleScale())).map(normalize(f)) };
  }
}
function normalize(f){
  return (r)=>{
    const id = r.receiptId || r.id || r.receipt_id || (''+Math.random());
    const prev = r.prev || r.prevId || r.parent || (r.khipuReceipt && r.khipuReceipt.prev) || null;
    let y = r.yuyayScore ?? r.yuyay ?? (r.yuyay13) ?? (r.khipuReceipt && r.khipuReceipt.yuyay) ?? 0.9;
    if (typeof y !== 'number') y = 0.9;
    const ts = r.ts || r.timestamp || r.time || Date.now();
    return { id:`${f.id}:${id}`, rawId:id, flagship:f.id, color:f.color, yuyay:Math.max(0,Math.min(1,y)),
             ts: typeof ts==='number'?ts:Date.parse(ts)||Date.now(), prev: prev?`${f.id}:${prev}`:null };
  };
}

// ---- rebuild geometry from current receipts + filters ----
function passesFilter(r){
  if(!enabled.has(r.flagship)) return false;
  if(r.yuyay < yuyayFloor) return false;
  const w = WINDOWS[timeWindowIdx];
  if(w!==Infinity && (Date.now()-r.ts) > w*3600*1000) return false;
  return true;
}
function rebuild(){
  // stars
  let n=0;
  const visible = new Set();
  for(const r of receipts){
    if(!passesFilter(r)) continue;
    if(!r.pos) r.pos = hashVec(r.id);
    dummy.position.copy(r.pos);
    const s = 0.55 + r.yuyay*0.95;
    dummy.scale.setScalar(s);
    dummy.updateMatrix();
    stars.setMatrixAt(n, dummy.matrix);
    col.setHex(r.color);
    const lift = 0.35 + r.yuyay*0.65;            // brightness by Yuyay
    col.multiplyScalar(lift);
    stars.setColorAt(n, col);
    r._idx = n; visible.add(r.id);
    n++;
    if(n>=MAX_STARS) break;
  }
  stars.count = n;
  stars.instanceMatrix.needsUpdate = true;
  if(stars.instanceColor) stars.instanceColor.needsUpdate = true;

  // arcs (prev -> cur) for visible, chained receipts
  arcGroup.clear();
  const positions=[]; const colors=[];
  let arcs=0;
  for(const r of receipts){
    if(!r.prev || !visible.has(r.id)) continue;
    const p = byId.get(r.prev);
    if(!p || !visible.has(p.id)) continue;
    const a=r.pos, b=p.pos;
    const mid = a.clone().add(b).multiplyScalar(0.5).multiplyScalar(1.18); // bow outward
    const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
    const pts = curve.getPoints(14);
    for(let i=0;i<pts.length-1;i++){
      positions.push(pts[i].x,pts[i].y,pts[i].z, pts[i+1].x,pts[i+1].y,pts[i+1].z);
      col.setHex(r.color).multiplyScalar(0.5);
      colors.push(col.r,col.g,col.b, col.r,col.g,col.b);
    }
    arcs++;
    if(arcs>4000) break;
  }
  if(positions.length){
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(positions,3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors,3));
    const m = new THREE.LineBasicMaterial({ vertexColors:true, transparent:true, opacity:0.5 });
    arcGroup.add(new THREE.LineSegments(g,m));
  }

  document.getElementById('starCount').textContent = n;
  document.getElementById('arcCount').textContent = arcs;
  document.getElementById('liveCount').textContent = liveFlags.size;
}

// ---- poll loop ----
async function poll(){
  const results = await Promise.all(FLAGSHIPS.map(fetchLedger));
  liveFlags = new Set();
  const merged = [];
  results.forEach((res,i)=>{ if(res.ok) liveFlags.add(FLAGSHIPS[i].id); merged.push(...res.entries); });
  receipts = merged;
  byId = new Map(receipts.map(r=>[r.id,r]));
  // live pill: LIVE if at least one real endpoint answered
  const pill = document.getElementById('livePill');
  if(liveFlags.size>0){ pill.textContent = `LIVE · ${liveFlags.size}/6`; pill.className='pill live'; }
  else { pill.textContent = 'DEMO MODE'; pill.className='pill demo'; }
  document.getElementById('lastPoll').textContent = 'last poll '+new Date().toLocaleTimeString();
  rebuild();
}

// ---- picking / tooltip ----
const ray = new THREE.Raycaster(); const ndc = new THREE.Vector2();
const tip = document.getElementById('tip');
function onMove(ev){
  ndc.x = (ev.clientX/innerWidth)*2-1; ndc.y = -(ev.clientY/innerHeight)*2+1;
  ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObject(stars);
  if(hit.length){
    const idx = hit[0].instanceId;
    const r = receipts.find(x=>x._idx===idx && passesFilter(x));
    if(r){
      tip.hidden=false;
      tip.style.left=(ev.clientX+14)+'px'; tip.style.top=(ev.clientY+14)+'px';
      const ago = Math.round((Date.now()-r.ts)/1000);
      tip.innerHTML = `<b>${r.flagship}</b> receipt<br><span class="k">id</span> ${r.rawId}<br>`+
        `<span class="k">yuyay</span> ${r.yuyay.toFixed(3)}<br>`+
        `<span class="k">chained</span> ${r.prev?'yes':'root'}<br>`+
        `<span class="k">age</span> ${ago}s`;
      return;
    }
  }
  tip.hidden=true;
}

// ---- boot ----
let controls;
async function boot(){
  renderer = await makeRenderer();
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(SZLMobileControls.rendererHints().pixelRatio);
  document.getElementById('root').appendChild(renderer.domElement);
  document.getElementById('renderPill').textContent = RENDER_BACKEND.toUpperCase();
  document.getElementById('renderPill').style.borderColor = RENDER_BACKEND==='webgpu'?'#34aaa4':'#3c4757';

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor=0.06;
  controls.minDistance=20; controls.maxDistance=400;
  if(SZL_MOBILE){ controls.rotateSpeed=0.6; controls.zoomSpeed=0.8; controls.enablePan=true; }

  // filter UI
  const ft = document.getElementById('flagToggles');
  FLAGSHIPS.forEach(f=>{
    const b=document.createElement('button');
    b.textContent=f.id; b.setAttribute('aria-pressed','true');
    b.style.color = '#'+f.color.toString(16).padStart(6,'0');
    b.onclick=()=>{ if(enabled.has(f.id)){enabled.delete(f.id);b.setAttribute('aria-pressed','false');}
                    else{enabled.add(f.id);b.setAttribute('aria-pressed','true');} rebuild(); };
    ft.appendChild(b);
  });
  const yu=document.getElementById('yuyay');
  yu.oninput=()=>{ yuyayFloor=+yu.value; document.getElementById('yuyayVal').textContent=yuyayFloor.toFixed(2); rebuild(); };
  const win=document.getElementById('win');
  const labels=['1h','3h','6h','12h','24h','72h','all'];
  win.oninput=()=>{ timeWindowIdx=+win.value; document.getElementById('winVal').textContent=labels[timeWindowIdx]; rebuild(); };

  renderer.domElement.addEventListener('pointermove', onMove);
  addEventListener('resize', ()=>{ camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });

  await poll();
  setInterval(poll, POLL_MS);

  const clock = new THREE.Clock();
  function loop(){
    const t = clock.getElapsedTime();
    if(!SZL_REDUCED) scene.rotation.y = t*0.018;
    core.scale.setScalar(1+(SZL_REDUCED?0:Math.sin(t*1.2)*0.06));
    controls.update();
    if(!document.hidden) renderer.render(scene, camera);
    requestAnimationFrame(loop);
  }
  loop();
}
boot().catch(err=>{
  document.getElementById('renderPill').textContent='ERR';
  console.error(err);
});
