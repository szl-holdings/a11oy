/* ============================================================================
 * a11oy_cathedral.js — a11oy front-door sovereign 3D hero (vendored Three.js).
 * Brain-sun (a11oy) + 3 internal capabilities orbiting + inspectable.
 * Honesty: locked proven = 5; experimental main 1304/22; Λ = Conjecture 1;
 * conformal (never 100%) not Hoeffding; SLSA L1 honest / L2 roadmap.
 * Live /healthz + /lambda (13-axis Trust Score). No fakery; honest fallback.
 * Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 * ========================================================================== */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const CAPABILITIES = [
  { id:'reasoning', title:'Reasoning & Provenance', color:0x5cc4bf, angle:0,
    plain:'Grounded reasoning, memory/recall and provenance over a signed knowledge base — an internal a11oy function.',
    functions:['grounded ask (cites its source, refuses to fabricate)','13-axis Trust Score (geometric-mean aggregate, floor 0.90)','knowledge ontology (axioms → theorems → formulas)','model router (5-tier, cost-aware)'],
    proof:['Trust-Score CI from CONFORMAL (W5-3 + W7-4) — distribution-free, anti-overconfidence floor (never 100%, NOT Hoeffding)','Model-Router stability C20 + PAC-Bayes/router envelope W7-5 (min ≤ avg ≤ max)','Ontology label-invariance: F-G2 / F-G4 / F-G6 / W7-1 (graph substrate)'] },
  { id:'policy', title:'Policy & Compliance', color:0xd7b96b, angle:2.094,
    plain:'Deny-by-default safety gates and full ALLOW/DENY verdicts with signed receipts — an internal a11oy function.',
    functions:['8 deny-by-default safety gates','full verdict (ALLOW / DENY) with signals + receipt hash','30-signature threat corpus (MITRE ATT&CK + CVSS)','readiness / compliance (NIST / STIG / ISO)'],
    proof:['Gate-soundness P2 — no action without BOTH policy AND kernel/doctrine check; a single DENY is absorbing','Agentic-loop P3 non-interference — poisoned input provably cannot flip a DENY into an ALLOW'] },
  { id:'operator', title:'Operator · Ask / Act / Approvals', color:0xe58e54, angle:4.189,
    plain:'The governed run loop: ask, act with approvals, and emit replayable signed receipts — an internal a11oy function.',
    functions:['governed run loop P1–P6 (sign → gate → chain → memory → replay)','human approvals gate for high-impact actions','replayable, hash-chained receipts (Khipu)','a11oy Code — governed agentic coder (P1–P6), open-weight models'],
    proof:['Agentic-loop P1–P6: 28 kernel-verified theorems — run is auditable, gate-sound, injection-resistant end-to-end','P5 replay-determinism gated only by declared hashFn_collision_resistant axiom (named, not a hardness proof)'] }
];

const A11OY = {
  id:'a11oy', title:'a11oy — Command Platform (the brain)',
  plain:'The orchestrating governance substrate: one brain coordinating reasoning, policy and operator capabilities. Live: /healthz.',
  functions:['command center + five superpowers + 25-demo Warhacker board (5×5 live)','a11oy Code (governed agentic coder, P1–P6, open-weight router)','one governance substrate (capabilities are internal, no service split)','13-axis Trust Score aggregate (yuyay_v3, geometric mean, floor 0.90)','/proven: 9 wave 9/10 formula cards (5 with live runtime checks)','signed Khipu receipts for every governed action'],
  proof:['Locked proven kernel = 5 {F1,F11,F12,F18,F19} @ c7c0ba17 (749/14/163) — machine-enforced count','Experimental main: 1304 decl / 22 axioms, waves 3–10 CI-green (~36–44 theorems), excluded from locked count','Λ-Aggregator uniqueness (F23) = Conjecture 1 — NOT a theorem (unconditional uniqueness machine-checked FALSE)'],
  url:'/console'
};

const ENDPOINTS = { health:'/healthz', lambda:'/api/a11oy/v1/lambda' };

const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.15;

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x070815, 0.0019);
const camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 4000);
camera.position.set(0, 70, 320);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.06;
controls.minDistance = 90; controls.maxDistance = 1000;
controls.autoRotate = true; controls.autoRotateSpeed = 0.45;

scene.add(new THREE.AmbientLight(0x33304a, 0.9));
scene.add(new THREE.PointLight(0xffe6a8, 2.4, 1600, 1.4));
const rim = new THREE.DirectionalLight(0x5c8fd1, 0.5); rim.position.set(-200,120,-150); scene.add(rim);

(function backdrop(){
  const N=2600, pos=new Float32Array(N*3);
  for(let i=0;i<N;i++){ const r=1400+Math.random()*1600, t=Math.random()*Math.PI*2, p=Math.acos(2*Math.random()-1);
    pos[i*3]=r*Math.sin(p)*Math.cos(t); pos[i*3+1]=r*Math.cos(p); pos[i*3+2]=r*Math.sin(p)*Math.sin(t); }
  const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos,3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color:0x8a90c0, size:1.4, sizeAttenuation:true, transparent:true, opacity:0.55 })));
})();

const interactables=[];
function registerBody(mesh,data){ mesh.userData.inspect=data; interactables.push(mesh); }

const sunGroup=new THREE.Group(); scene.add(sunGroup);
const sunCore=new THREE.Mesh(new THREE.IcosahedronGeometry(36,4),
  new THREE.MeshStandardMaterial({ color:0xffce6e, emissive:0xd79a2e, emissiveIntensity:1.5, roughness:0.35, metalness:0.1 }));
sunGroup.add(sunCore); registerBody(sunCore, A11OY);
const sunGlow=new THREE.Mesh(new THREE.SphereGeometry(50,32,32),
  new THREE.MeshBasicMaterial({ color:0xffd98a, transparent:true, opacity:0.10, side:THREE.BackSide }));
sunGroup.add(sunGlow);
const brainLattice=new THREE.Mesh(new THREE.IcosahedronGeometry(42,2),
  new THREE.MeshBasicMaterial({ color:0xffe6a8, wireframe:true, transparent:true, opacity:0.22 }));
sunGroup.add(brainLattice);
sunGroup.add(makeLabel('a11oy', 0xffe6a8, 66));

const ORBIT_R=150; const capBodies=[];
CAPABILITIES.forEach((cap)=>{
  const grp=new THREE.Group();
  const mesh=new THREE.Mesh(new THREE.IcosahedronGeometry(15,2),
    new THREE.MeshStandardMaterial({ color:cap.color, emissive:cap.color, emissiveIntensity:0.55, roughness:0.5, metalness:0.2 }));
  grp.add(mesh);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(22,0.7,8,64), new THREE.MeshBasicMaterial({ color:cap.color, transparent:true, opacity:0.35 }));
  ring.rotation.x=Math.PI/2; grp.add(ring);
  grp.add(makeLabel(cap.title.split(/[ &·]/)[0], cap.color, 30));
  scene.add(grp); registerBody(mesh, cap);
  const tether=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(),new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color:cap.color, transparent:true, opacity:0.28 }));
  scene.add(tether);
  capBodies.push({ grp, mesh, cap, baseAngle:cap.angle, tether });
});

function makeLabel(text,color,size){
  const c=document.createElement('canvas'); c.width=256; c.height=64; const ctx=c.getContext('2d');
  ctx.font='700 34px ui-monospace, Menlo, Consolas, monospace';
  ctx.fillStyle='#'+new THREE.Color(color).getHexString();
  ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.shadowColor='rgba(0,0,0,0.8)'; ctx.shadowBlur=8;
  ctx.fillText(text,128,34);
  const tex=new THREE.CanvasTexture(c); tex.anisotropy=4;
  const spr=new THREE.Sprite(new THREE.SpriteMaterial({ map:tex, transparent:true, depthWrite:false }));
  spr.scale.set(size*2,size*0.5,1); spr.position.y=size*0.9; spr.userData.isLabel=true; return spr;
}

const ray=new THREE.Raycaster(); const ptr=new THREE.Vector2();
canvas.addEventListener('click',(e)=>{
  const r=canvas.getBoundingClientRect();
  ptr.x=((e.clientX-r.left)/r.width)*2-1; ptr.y=-((e.clientY-r.top)/r.height)*2+1;
  ray.setFromCamera(ptr,camera);
  const hits=ray.intersectObjects(interactables,false);
  if(hits.length) openInspector(hits[0].object.userData.inspect);
});

const insp=document.getElementById('inspector');
document.getElementById('insp-close').addEventListener('click',()=>insp.classList.remove('show'));
function openInspector(d){
  if(!d) return;
  document.getElementById('insp-title').textContent=d.title;
  document.getElementById('insp-plain').textContent=d.plain;
  let html='<div class="ih">Functions</div><ul>'+d.functions.map(f=>`<li>${esc(f)}</li>`).join('')+'</ul>';
  if(d.proof) html+='<div class="ih">Proof support (honest)</div><ul>'+d.proof.map(p=>`<li class="proof">${esc(p)}</li>`).join('')+'</ul>';
  if(d.url) html+=`<div class="ih">Open</div><ul><li><a href="${d.url}" style="color:#5cc4bf">Enter the working app ↗</a></li></ul>`;
  document.getElementById('insp-body').innerHTML=html; insp.classList.add('show');
}
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

let liveState={ a11oy:'…' }, feedSource='connecting…', liveLambda=null;
async function getJSON(url,ms){
  const ctrl=new AbortController(); const t=setTimeout(()=>ctrl.abort(), ms||7000);
  try{ const r=await fetch(url,{ signal:ctrl.signal, headers:{accept:'application/json'} }); if(!r.ok) throw 0; return await r.json(); }
  finally{ clearTimeout(t); }
}
async function poll(){
  try{ const h=await getJSON(ENDPOINTS.health,7000); liveState.a11oy=(h&&(h.status==='ok'||h.ok))?'LIVE':'DEGRADED'; }
  catch(_){ liveState.a11oy='OFFLINE'; }
  try{ const lam=await getJSON(ENDPOINTS.lambda,7000); if(lam&&typeof lam.lambda==='number'){ liveLambda=lam.lambda; feedSource='LIVE a11oy Λ='+lam.lambda.toFixed(3)+' (13-axis Trust Score)'; } }
  catch(_){ if(liveLambda===null) feedSource='Λ feed reconnecting…'; }
  paintHUD();
}
function paintHUD(){
  const cls=liveState.a11oy==='LIVE'?'live':(liveState.a11oy==='OFFLINE'?'off':'seed');
  let rows=`<div class="row"><span class="dot ${cls}"></span><span>a11oy · brain</span><span class="meta">${liveState.a11oy}</span></div>`;
  if(liveLambda!==null){ const v=liveLambda>=0.9?'green':(liveLambda>=0.5?'amber':'red'); const col=v==='green'?'#4fd18b':(v==='amber'?'#d7b96b':'#c0392b');
    rows+=`<div class="row"><span class="dot" style="background:${col};box-shadow:0 0 9px ${col}"></span><span>Trust Score Λ</span><span class="meta">${liveLambda.toFixed(3)}</span></div>`; }
  document.getElementById('status-rows').innerHTML=rows;
  document.getElementById('feed-src').textContent=feedSource;
}

let tms=0;
function animate(){
  requestAnimationFrame(animate); tms+=0.004;
  sunCore.rotation.y+=0.0015; brainLattice.rotation.y-=0.0011; brainLattice.rotation.x+=0.0006;
  sunGlow.material.opacity=0.08+0.04*Math.sin(tms*2);
  capBodies.forEach((cb,i)=>{ const a=cb.baseAngle+tms*0.6; const x=Math.cos(a)*ORBIT_R, z=Math.sin(a)*ORBIT_R, y=Math.sin(a*1.3+i)*22;
    cb.grp.position.set(x,y,z); cb.mesh.rotation.y+=0.01;
    cb.tether.geometry.setFromPoints([new THREE.Vector3(0,0,0), new THREE.Vector3(x,y,z)]); cb.tether.geometry.attributes.position.needsUpdate=true; });
  controls.update(); renderer.render(scene,camera);
}
window.addEventListener('resize',()=>{ camera.aspect=window.innerWidth/window.innerHeight; camera.updateProjectionMatrix(); renderer.setSize(window.innerWidth,window.innerHeight); });
paintHUD(); animate();
(function(){ var b=document.getElementById('boot'); b.classList.add('hide');
  b.addEventListener('transitionend', function(){ b.style.display='none'; });
  setTimeout(function(){ b.style.display='none'; }, 1200); })();
poll(); setInterval(poll, 8000);
controls.addEventListener('start',()=>{ controls.autoRotate=false; });
