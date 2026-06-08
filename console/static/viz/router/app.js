// LLM-Router Live (GRAPH ROUTER) — SZL Holdings
// 3D bipartite routing graph: organs (query sources) at center, 7 router tiers
// (T0..T6) as concentric rings, 30+ open LLMs (model nodes) on the outer ring.
// Routing is GRAPH-BASED: each organ emits a task mix, every task is scored
// against all model nodes by a transparent edge-affinity weight
// (quality x ctx-fit x cost x license-pref), and the top-affinity edges are lit.
// Clean-room implementation inspired by GraphRouter (MIT), Router-R1 (Apache-2.0)
// and LLMRouter (MIT) — concept only, no code copied (see THIRD_PARTY_NOTICES).
// Prefers live /v1/router/stats when present; otherwise shows the SAME graph
// decision locally (labelled "GRAPH ROUTER", never fabricated served-QPS).
// "Sovereign mode" greys all non-GREEN models (router contract: governanceTier=sovereign -> GREEN-only).
// Three.js r171, WebGPURenderer baseline + WebGL2 fallback, Kanchay tokens.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TIERS, ORGANS, MODELS, TASKS, ORGAN_TASKMIX, edgeAffinity, rankForTask } from './models.js';
// SZL canonical mobile layer (additive).
import { SZLMobileControls } from './szl-mobile-controls.js';
const SZL_MOBILE = SZLMobileControls.isMobileDevice();
const SZL_REDUCED = SZLMobileControls.prefersReducedMotion();

const STATS_EP = 'https://szlholdings-a11oy.hf.space/v1/router/stats';
const ROUTER_EP = 'https://szlholdings-a11oy.hf.space/v1/router';
const POLL_MS = 1000;
const LIC = { GREEN:0x1f9d57, AMBER:0xcda64a, RED:0xc0392b };

// ---------- renderer ----------
let renderer, BACKEND='webgl2';
async function makeRenderer(){
  if(navigator.gpu){ try{ const m=await import('three/webgpu'); const r=new m.WebGPURenderer({antialias:true}); await r.init(); BACKEND='webgpu'; return r; }catch(e){ console.warn('WebGPU fallback',e);} }
  const H = SZLMobileControls.rendererHints();
  return new THREE.WebGLRenderer({antialias:H.antialias, powerPreference:H.powerPreference});
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0f1e);
scene.fog = new THREE.FogExp2(0x0a0f1e, 0.012);
const camera = new THREE.PerspectiveCamera(58, innerWidth/innerHeight, 0.1, 1000);
camera.position.set(0, 60, 96);
camera.lookAt(0,0,0);
scene.add(new THREE.AmbientLight(0x33424f, 1.1));
const key = new THREE.PointLight(0x34aaa4, 2, 600); key.position.set(0,90,40); scene.add(key);

// ---------- layout (radial, on XZ plane, slight Y by ring) ----------
const TIER_R = { T0:8, T1:16, T2:24, T3:32, T4:40, T5:48, T6:56 };
const MODEL_R = 78;

// organs at center cluster
const organMeshes = {};
ORGANS.forEach((o,i)=>{
  const a = (i/ORGANS.length)*Math.PI*2;
  const m = new THREE.Mesh(new THREE.IcosahedronGeometry(2.2,1),
    new THREE.MeshStandardMaterial({ color:0x223043, emissive:0x34aaa4, emissiveIntensity:0.6, roughness:0.4 }));
  m.position.set(Math.cos(a)*4, 0, Math.sin(a)*4);
  m.userData={ type:'organ', id:o[0], desc:o[1], tier:o[2] };
  scene.add(m); organMeshes[o[0]]=m;
});
// center core
scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.6,24,24), new THREE.MeshBasicMaterial({color:0x168f89})));

// tier rings + tier label nodes
const tierNodes = {};
TIERS.forEach((t,i)=>{
  const r = TIER_R[t[0]];
  const ring = new THREE.Mesh(new THREE.TorusGeometry(r,0.12,8,128),
    new THREE.MeshBasicMaterial({ color:0x2a3340 }));
  ring.rotation.x = Math.PI/2; scene.add(ring);
  // a representative tier marker
  const node = new THREE.Mesh(new THREE.SphereGeometry(1.3,16,16),
    new THREE.MeshStandardMaterial({ color:0x223043, emissive:0x5cc4bf, emissiveIntensity:0.35 }));
  node.position.set(0,0,-r);
  node.userData={ type:'tier', id:t[0], label:t[1], lat:t[2] };
  scene.add(node); tierNodes[t[0]]=node;
});

// model nodes on outer ring, grouped by tier sector
const modelMeshes = [];
const tierGroups = {}; TIERS.forEach(t=>tierGroups[t[0]]=[]);
MODELS.forEach(m=>tierGroups[m.tier].push(m));
let placed=0;
const totalModels = MODELS.length;
const dummyCol = new THREE.Color();
MODELS.forEach((m, gi)=>{
  const a = (placed/totalModels)*Math.PI*2;
  const jitter = ((placed*53)%7-3)*1.2;
  const r = MODEL_R + jitter;
  const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1.5,1),
    new THREE.MeshStandardMaterial({ color:0x1a2230, emissive:LIC[m.license], emissiveIntensity:0.5, roughness:0.45, metalness:0.2 }));
  mesh.position.set(Math.cos(a)*r, 0, Math.sin(a)*r);
  mesh.userData={ type:'model', model:m, baseEmissive:0.5, active:0 };
  scene.add(mesh); modelMeshes.push(mesh);
  // static thin edge tier->model (structure)
  const tn = tierNodes[m.tier];
  const g = new THREE.BufferGeometry().setFromPoints([tn.position, mesh.position]);
  const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color:0x2a3340, transparent:true, opacity:0.28 }));
  scene.add(line);
  placed++;
});
document.getElementById('modelCount').textContent = totalModels;

// dynamic "served route" lit edges live in this group (rebuilt each poll)
const routeGroup = new THREE.Group(); scene.add(routeGroup);

// ---------- live route path: organ -> tier -> model ----------
function lightRoute(organId, tier, modelName, throughput){
  const om = organMeshes[organId]; const tn = tierNodes[tier];
  const mm = modelMeshes.find(x=>x.userData.model.name===modelName) || modelMeshes.find(x=>x.userData.model.tier===tier);
  if(!om||!tn||!mm) return;
  const w = Math.max(0.18, Math.min(2.2, throughput/40)); // edge width = throughput
  const lic = mm.userData.model.license;
  const c = new THREE.Color(LIC[lic]);
  // organ->tier and tier->model as glowing tube curves
  [[om.position,tn.position],[tn.position,mm.position]].forEach(([p0,p1])=>{
    const mid = p0.clone().add(p1).multiplyScalar(0.5); mid.y += 6;
    const curve = new THREE.QuadraticBezierCurve3(p0.clone(), mid, p1.clone());
    const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 20, w, 6, false),
      new THREE.MeshBasicMaterial({ color:c, transparent:true, opacity:0.85 }));
    tube.userData.fade = 1.0; routeGroup.add(tube);
  });
  // glow the active model + organ
  mm.userData.active = 1.0;
  om.material.emissiveIntensity = 1.6;
  tn.material.emissiveIntensity = 1.2;
}

// ---------- GRAPH-ROUTER local route generator (labelled GRAPH) ----------
// No live /v1/router/stats? We DON'T fabricate measured traffic. Instead we run
// the SAME graph-router decision that the platform uses: every organ emits a
// task mix (query nodes), each task is scored against all model nodes by
// edgeAffinity(), and the top-affinity edges are the routes shown. Throughput is
// derived from affinity x task weight (a transparent decision signal, NOT a
// claim of real served QPS) so the picture is honest + reproducible.
function graphStats(){
  const routes=[]; let served=0;
  const TOPK = 2;                               // top-K models per (organ,task)
  ORGANS.forEach(o=>{
    const mix = ORGAN_TASKMIX[o[0]] || { general:1 };
    Object.entries(mix).forEach(([taskId, share])=>{
      const task = TASKS.find(t=>t.id===taskId); if(!task) return;
      const ranked = rankForTask(task, MODELS, sovereign).slice(0, TOPK);
      ranked.forEach((r, k)=>{
        // edge load = organ task share x model affinity x rank-decay, scaled.
        const load = +(share * r.aff.score * (k===0?1:0.5) * 120).toFixed(1);
        if(load <= 0) return;
        routes.push({ organ:o[0], tier:r.m.tier, model:r.m.name,
                      throughput:load, license:r.m.license,
                      task:task.label, affinity:+r.aff.score.toFixed(3) });
        served += load;
      });
    });
  });
  return { mode:'graph', routes, servedThisWindow:Math.round(served), tiers:TIERS.map(t=>t[0]) };
}

function normalizeStats(j){
  // accept several shapes
  let routes = j.routes || j.active || j.paths || [];
  if(!Array.isArray(routes) && j.byOrgan) routes = Object.entries(j.byOrgan).map(([organ,v])=>({organ, tier:v.tier, model:v.model, throughput:v.throughput||v.qps||10, license:v.license}));
  return routes.map(r=>({ organ:r.organ||r.caller||'a11oy', tier:r.tier||'T2', model:r.model||r.modelId||'', throughput:+(r.throughput||r.qps||r.count||10), license:r.license||r.licenseClass||'GREEN' }));
}

// ---------- poll ----------
let sovereign=false;
async function poll(){
  let stats, live=false;
  try{
    const ctrl=new AbortController(); const t=setTimeout(()=>ctrl.abort(),800);
    const res = await fetch(STATS_EP, {mode:'cors',cache:'no-store',signal:ctrl.signal}); clearTimeout(t);
    if(!res.ok) throw new Error('http '+res.status);
    const j = await res.json();
    stats = { routes: normalizeStats(j), servedThisWindow: j.servedThisWindow||j.served||0 };
    live=true;
  }catch(e){
    stats = graphStats();   // honest graph-router decision, not fabricated traffic
  }
  const pill=document.getElementById('livePill');
  if(live){ pill.textContent='LIVE · /v1/router/stats'; pill.className='pill live'; }
  else { pill.textContent='GRAPH ROUTER · local affinity'; pill.className='pill demo'; }
  document.getElementById('lastPoll').textContent='last poll '+new Date().toLocaleTimeString();
  document.getElementById('qps').textContent = stats.servedThisWindow|0;

  // fade & clear old routes, draw new
  routeGroup.clear();
  // reset model active decay handled in loop
  let served=0;
  stats.routes.forEach(r=>{
    if(sovereign && r.license!=='GREEN') return; // sovereign hides non-GREEN routes
    lightRoute(r.organ, r.tier, r.model, r.throughput); served+=r.throughput;
  });
}

// ---------- sovereign toggle ----------
document.getElementById('sov').addEventListener('change', e=>{
  sovereign = e.target.checked;
  modelMeshes.forEach(mm=>{
    const green = mm.userData.model.license==='GREEN';
    mm.material.opacity = (sovereign && !green) ? 0.12 : 1.0;
    mm.material.transparent = true;
    mm.material.emissiveIntensity = (sovereign && !green) ? 0.05 : mm.userData.baseEmissive;
  });
});

// ---------- picking ----------
const ray=new THREE.Raycaster(); const ndc=new THREE.Vector2();
const tip=document.getElementById('tip');
const card=document.getElementById('card'); const cardBody=document.getElementById('cardBody');
document.getElementById('closeCard').onclick=()=>card.hidden=true;

function pick(ev){
  ndc.x=(ev.clientX/innerWidth)*2-1; ndc.y=-(ev.clientY/innerHeight)*2+1;
  ray.setFromCamera(ndc,camera);
  const hit=ray.intersectObjects(modelMeshes,false);
  if(hit.length){
    const m=hit[0].object.userData.model;
    // surface the model's single best task-node affinity in the tooltip
    let best=null; TASKS.forEach(t=>{ const s=edgeAffinity(t,m).score; if(!best||s>best.s) best={t,s}; });
    tip.hidden=false; tip.style.left=(ev.clientX+12)+'px'; tip.style.top=(ev.clientY+12)+'px';
    tip.innerHTML=`<b>${m.name}</b> · ${m.tier}<br>${m.license} · ${m.ctx}`+
      (best?`<br>best fit: ${best.t.label} ${Math.round(best.s*100)}%`:'');
  } else tip.hidden=true;
}
function clickPick(ev){
  ndc.x=(ev.clientX/innerWidth)*2-1; ndc.y=-(ev.clientY/innerHeight)*2+1;
  ray.setFromCamera(ndc,camera);
  const hit=ray.intersectObjects(modelMeshes,false);
  if(!hit.length) return;
  const m=hit[0].object.userData.model;
  const c='#'+LIC[m.license].toString(16).padStart(6,'0');
  cardBody.innerHTML=`<h2>${m.name}</h2>`+
    `<span class="lic" style="background:${c};color:#0a0f1e">${m.license}</span>`+
    `<table>`+
    `<tr><td>tier</td><td>${m.tier} — ${TIERS.find(t=>t[0]===m.tier)[1]}</td></tr>`+
    `<tr><td>context</td><td>${m.ctx}</td></tr>`+
    `<tr><td>benchmark</td><td>${m.bench}</td></tr>`+
    `<tr><td>provider</td><td>${m.prov}</td></tr>`+
    `<tr><td>license class</td><td>${m.license} ${m.license==='GREEN'?'(Apache/MIT)':m.license==='AMBER'?'(community/Llama/TII)':'(research-only, API)'}</td></tr>`+
    `</table>`+
    // graph-router edge affinities: this model's fit across every task node
    `<div class="aff"><b>graph-router affinity</b> <small>(heuristic, from public model-card features — not measured online)</small><table>`+
    TASKS.map(t=>{ const a=edgeAffinity(t,m).score; const pct=Math.round(a*100);
      return `<tr><td>${t.label}</td><td><span style="display:inline-block;height:7px;width:${Math.max(3,pct)}%;background:${c};border-radius:3px"></span> ${pct}%</td></tr>`;
    }).join('')+
    `</table></div>`+
    (m.hf?`<a href="https://huggingface.co/${m.hf}" target="_blank" rel="noopener">huggingface.co/${m.hf}</a>`:'');
  card.hidden=false;
}

// ---------- boot ----------
let controls;
async function boot(){
  renderer=await makeRenderer();
  renderer.setSize(innerWidth,innerHeight); renderer.setPixelRatio(SZLMobileControls.rendererHints().pixelRatio);
  document.getElementById('root').appendChild(renderer.domElement);
  document.getElementById('renderPill').textContent=BACKEND.toUpperCase();
  controls=new OrbitControls(camera, renderer.domElement); controls.enableDamping=true; controls.dampingFactor=0.06;
  controls.minDistance=30; controls.maxDistance=220; controls.maxPolarAngle=Math.PI*0.49;
  if(SZL_MOBILE){ controls.rotateSpeed=0.6; controls.zoomSpeed=0.8; controls.enablePan=true; }
  renderer.domElement.addEventListener('pointermove',pick);
  renderer.domElement.addEventListener('click',clickPick);
  addEventListener('resize',()=>{ camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });

  await poll(); setInterval(poll, POLL_MS);

  const clock=new THREE.Clock();
  function loop(){
    const dt=clock.getDelta(); const t=clock.getElapsedTime();
    if(!SZL_REDUCED) scene.rotation.y = t*0.04;
    // decay route tubes
    routeGroup.children.forEach(tube=>{ tube.userData.fade-=dt*1.6; tube.material.opacity=Math.max(0,tube.userData.fade*0.85); });
    // decay model/organ glow
    modelMeshes.forEach(mm=>{ if(mm.userData.active>0){ mm.userData.active-=dt*1.2; mm.material.emissiveIntensity = mm.userData.baseEmissive + Math.max(0,mm.userData.active)*1.6; } });
    Object.values(organMeshes).forEach(om=>{ om.material.emissiveIntensity += (0.6-om.material.emissiveIntensity)*dt*2; });
    Object.values(tierNodes).forEach(tn=>{ tn.material.emissiveIntensity += (0.35-tn.material.emissiveIntensity)*dt*2; });
    controls.update(); if(!document.hidden) renderer.render(scene,camera); requestAnimationFrame(loop);
  }
  loop();
}
boot().catch(e=>{ document.getElementById('renderPill').textContent='ERR'; console.error(e); });
