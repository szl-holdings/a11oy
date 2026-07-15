// LLM Graph-Router constellation — SZL Holdings
//
// The visual layer never upgrades configuration or a successful render into a
// claim of live inference. A green endpoint state requires a validated response
// from /v1/router/stats; its value is labelled as the backend describes it: a
// deterministic catalog pulse, not production QPS. When the endpoint cannot be
// validated, the same transparent local affinity calculation is shown as MODELED.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TIERS, ORGANS, MODELS, TASKS, ORGAN_TASKMIX, edgeAffinity, rankForTask } from './models.js';
import { SZLMobileControls } from './szl-mobile-controls.js';

const STATS_EP = 'https://szlholdings-a11oy.hf.space/v1/router/stats';
const POLL_MS = 5000;
const LIC = { GREEN:0x38df82, AMBER:0xffd36a, RED:0xff6b63 };
const LIC_CSS = { GREEN:'#38df82', AMBER:'#ffd36a', RED:'#ff6b63' };
const TIER_COLORS = [0x8ee9ff,0x55f2d2,0x54dfa0,0x70a7ff,0xa38cff,0xe593ff,0xffbe72];
const SZL_MOBILE = SZLMobileControls.isMobileDevice();
const SZL_REDUCED = SZLMobileControls.prefersReducedMotion();

let renderer;
let controls;
let BACKEND = 'unavailable';
let sovereign = false;
let endpointResponseAt = 0;
let localModelAt = 0;
let lastState = 'pending';
let lastRoutes = [];

function esc(value){
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

async function makeRenderer(){
  if(navigator.gpu){
    try{
      const module = await import('three/webgpu');
      const gpuRenderer = new module.WebGPURenderer({ antialias:true, alpha:true });
      await gpuRenderer.init();
      BACKEND = 'webgpu';
      return gpuRenderer;
    }catch(error){
      console.warn('WebGPU unavailable; checking WebGL2', error);
    }
  }
  const probe = document.createElement('canvas');
  const context = probe.getContext('webgl2', { failIfMajorPerformanceCaveat:true });
  if(!context) throw new Error('WebGPU and WebGL2 are unavailable');
  const hints = SZLMobileControls.rendererHints();
  BACKEND = 'webgl2';
  return new THREE.WebGLRenderer({ antialias:hints.antialias, powerPreference:hints.powerPreference, alpha:true });
}

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x071421);
scene.fog = new THREE.FogExp2(0x071421, 0.0065);
const camera = new THREE.PerspectiveCamera(54, innerWidth / innerHeight, 0.1, 1000);
camera.position.set(0, 78, 112);
camera.lookAt(0,0,0);

scene.add(new THREE.HemisphereLight(0xb9efff, 0x09131f, 2.25));
scene.add(new THREE.AmbientLight(0x7aa8c3, 1.45));
const key = new THREE.PointLight(0x3af4c8, 5.2, 420); key.position.set(0,76,35); scene.add(key);
const rim = new THREE.PointLight(0x7d8cff, 3.4, 360); rim.position.set(-75,22,-42); scene.add(rim);

// A restrained star field gives the rings depth without implying telemetry.
const stars = new Float32Array(360 * 3);
for(let i=0;i<360;i++){
  const a = i * 2.399963;
  const r = 22 + ((i * 47) % 116);
  stars[i*3] = Math.cos(a) * r;
  stars[i*3+1] = -5 + ((i * 19) % 27) * 0.45;
  stars[i*3+2] = Math.sin(a) * r;
}
const starsGeometry = new THREE.BufferGeometry();
starsGeometry.setAttribute('position', new THREE.BufferAttribute(stars, 3));
scene.add(new THREE.Points(starsGeometry, new THREE.PointsMaterial({ color:0x65c9e8, size:0.28, transparent:true, opacity:0.48 })));
const polarGrid = new THREE.PolarGridHelper(91, 20, 9, 96, 0x315d76, 0x163a50);
polarGrid.material.transparent = true; polarGrid.material.opacity = 0.34; scene.add(polarGrid);

const TIER_R = { T0:9, T1:17, T2:25, T3:33, T4:41, T5:49, T6:57 };
const MODEL_R = 79;
const organMeshes = {};
const modelMeshes = [];
const tierNodes = {};
const tierRings = {};

ORGANS.forEach((organ,index)=>{
  const angle = (index / ORGANS.length) * Math.PI * 2;
  const mesh = new THREE.Mesh(
    new THREE.IcosahedronGeometry(2.4,1),
    new THREE.MeshStandardMaterial({ color:0x174457, emissive:0x3af4c8, emissiveIntensity:1.15, roughness:0.3, metalness:0.32 })
  );
  mesh.position.set(Math.cos(angle)*5.2, 0.8, Math.sin(angle)*5.2);
  mesh.userData = { type:'organ', id:organ[0], desc:organ[1], tier:organ[2] };
  scene.add(mesh); organMeshes[organ[0]] = mesh;
});
const core = new THREE.Mesh(
  new THREE.SphereGeometry(1.9,24,24),
  new THREE.MeshBasicMaterial({ color:0x7bffe1 })
);
core.position.y = 0.8; scene.add(core);

TIERS.forEach((tier,index)=>{
  const radius = TIER_R[tier[0]];
  const color = TIER_COLORS[index];
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(radius,0.2,10,160),
    new THREE.MeshBasicMaterial({ color, transparent:true, opacity:0.64 })
  );
  ring.rotation.x = Math.PI/2; scene.add(ring); tierRings[tier[0]] = ring;
  const angle = -Math.PI/2 + (index-3) * 0.22;
  const node = new THREE.Mesh(
    new THREE.SphereGeometry(1.55,18,18),
    new THREE.MeshStandardMaterial({ color:0x14334a, emissive:color, emissiveIntensity:0.95, roughness:0.28, metalness:0.38 })
  );
  node.position.set(Math.cos(angle)*radius,0.5,Math.sin(angle)*radius);
  node.userData = { type:'tier', id:tier[0], label:tier[1], lat:tier[2], color };
  scene.add(node); tierNodes[tier[0]] = node;
});

MODELS.forEach((model,index)=>{
  const angle = (index / MODELS.length) * Math.PI * 2;
  const jitter = ((index * 53) % 7 - 3) * 1.15;
  const radius = MODEL_R + jitter;
  const mesh = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.75,1),
    new THREE.MeshStandardMaterial({
      color:0x162c40, emissive:LIC[model.license], emissiveIntensity:0.92,
      roughness:0.25, metalness:0.45, transparent:true
    })
  );
  mesh.position.set(Math.cos(angle)*radius,0,Math.sin(angle)*radius);
  mesh.userData = { type:'model', model, baseEmissive:0.92, active:false };
  scene.add(mesh); modelMeshes.push(mesh);
  const tierNode = tierNodes[model.tier];
  const geometry = new THREE.BufferGeometry().setFromPoints([tierNode.position,mesh.position]);
  const line = new THREE.Line(geometry,new THREE.LineBasicMaterial({ color:TIER_COLORS[Number(model.tier.slice(1))], transparent:true, opacity:0.3 }));
  scene.add(line);
});

const routeGroup = new THREE.Group(); scene.add(routeGroup);

function disposeRoutes(){
  for(const child of [...routeGroup.children]){
    routeGroup.remove(child);
    child.geometry?.dispose();
    child.material?.dispose();
  }
}

function lightRoute(route){
  const organ = organMeshes[route.organ] || core;
  const tier = tierNodes[route.tier];
  if(!tier) return;
  const exactModel = modelMeshes.find(item => item.userData.model.name === route.model);
  const color = new THREE.Color(LIC[route.license] || LIC.GREEN);
  const width = Math.max(0.16, Math.min(1.15, Number(route.throughput || 0) / 54));
  const segments = [[organ.position,tier.position]];
  // Never route a backend model to an unrelated visual node. Unknown endpoint
  // model ids terminate at their truthful tier and remain named in the route feed.
  if(exactModel) segments.push([tier.position,exactModel.position]);
  for(const [start,end] of segments){
    const middle = start.clone().add(end).multiplyScalar(0.5); middle.y += 5.5;
    const curve = new THREE.QuadraticBezierCurve3(start.clone(),middle,end.clone());
    const tube = new THREE.Mesh(
      new THREE.TubeGeometry(curve,24,width,7,false),
      new THREE.MeshBasicMaterial({ color, transparent:true, opacity:0.86 })
    );
    routeGroup.add(tube);
  }
  tier.material.emissiveIntensity = 1.7;
  if(exactModel){ exactModel.userData.active = true; exactModel.material.emissiveIntensity = 2.2; }
  if(organ !== core) organ.material.emissiveIntensity = 2.1;
}

function graphStats(){
  const routes = [];
  let modeledLoad = 0;
  const topK = 2;
  for(const organ of ORGANS){
    const mix = ORGAN_TASKMIX[organ[0]] || { general:1 };
    for(const [taskId,share] of Object.entries(mix)){
      const task = TASKS.find(item => item.id === taskId);
      if(!task) continue;
      const ranked = rankForTask(task,MODELS,sovereign).slice(0,topK);
      ranked.forEach((result,index)=>{
        const load = +(share * result.aff.score * (index===0 ? 1 : 0.5) * 120).toFixed(1);
        if(load <= 0) return;
        routes.push({
          organ:organ[0], tier:result.m.tier, model:result.m.name,
          throughput:load, license:result.m.license, task:task.label,
          affinity:+result.aff.score.toFixed(3)
        });
        modeledLoad += load;
      });
    }
  }
  return {
    mode:'modeled', source:'local transparent affinity', routes,
    servedThisWindow:Math.round(modeledLoad),
    honesty:'MODELED decision signal from declared model-card features; not inference traffic or measured QPS.'
  };
}

function normalizeStats(payload){
  if(!payload || typeof payload !== 'object' || payload.mode !== 'live' || !Array.isArray(payload.routes)){
    throw new Error('router stats envelope is not a live route array');
  }
  const routes = payload.routes.map(route=>({
    organ:String(route?.organ ?? ''), tier:String(route?.tier ?? ''), model:String(route?.model ?? ''),
    throughput:Number(route?.throughput), license:String(route?.license ?? '')
  })).filter(route =>
    route.organ && /^T[0-6]$/.test(route.tier) && route.model &&
    Number.isFinite(route.throughput) && route.throughput >= 0 &&
    Object.hasOwn(LIC,route.license)
  );
  if(!routes.length || routes.length !== payload.routes.length) throw new Error('router stats routes failed schema validation');
  if(!Number.isFinite(Number(payload.servedThisWindow))) throw new Error('router stats signal is not numeric');
  const routeTotal = routes.reduce((sum,route)=>sum+route.throughput,0);
  if(Math.abs(routeTotal-Number(payload.servedThisWindow)) > 0.001) throw new Error('router stats signal does not equal route total');
  return {
    mode:'endpoint', source:String(payload.source || 'unlabelled endpoint source'), routes,
    servedThisWindow:Number(payload.servedThisWindow), honesty:String(payload.honesty || '')
  };
}

function renderRouteFeed(stats,state){
  const feed = document.getElementById('routeFeed');
  feed.replaceChildren();
  const visible = [...stats.routes].sort((a,b)=>b.throughput-a.throughput).slice(0,9);
  for(const route of visible){
    const item = document.createElement('li');
    item.style.setProperty('--route-color',LIC_CSS[route.license] || LIC_CSS.GREEN);
    const title = document.createElement('strong');
    title.textContent = `${route.tier} · ${route.organ} → ${route.model}`;
    const detail = document.createElement('span');
    detail.textContent = state === 'responding'
      ? `${Math.round(route.throughput)} catalog pulse · ${route.license}`
      : `${Math.round(route.throughput)} modeled load · ${route.license}${route.task ? ` · ${route.task}` : ''}`;
    item.append(title,detail); feed.append(item);
  }
}

function setOperationalState(stats,state,detail){
  lastState = state;
  lastRoutes = stats.routes;
  const pill = document.getElementById('livePill');
  const source = document.getElementById('sourceState');
  const routeMode = document.getElementById('routeMode');
  const signalLabel = document.getElementById('signalLabel');
  document.getElementById('signalValue').textContent = String(Math.round(stats.servedThisWindow));
  if(state === 'responding'){
    pill.textContent = 'ENDPOINT · RESPONDING'; pill.className = 'pill responding';
    signalLabel.textContent = 'catalog pulse · not QPS';
    source.textContent = `Validated response · ${stats.source}`;
    routeMode.textContent = stats.honesty || 'Endpoint-derived catalog signal; not production traffic.';
  }else if(state === 'degraded'){
    pill.textContent = 'DEGRADED · MODELED FALLBACK'; pill.className = 'pill degraded';
    signalLabel.textContent = 'modeled affinity load';
    source.textContent = `Endpoint source degraded (${detail}); local model shown.`;
    routeMode.textContent = stats.honesty;
  }else{
    pill.textContent = 'UNAVAILABLE · MODELED FALLBACK'; pill.className = 'pill modeled';
    signalLabel.textContent = 'modeled affinity load';
    source.textContent = `Endpoint unavailable (${detail}); local model shown.`;
    routeMode.textContent = stats.honesty;
  }
  renderRouteFeed(stats,state);
  updateRouteVisuals(stats.routes);
  updateFreshness();
}

function updateRouteVisuals(routes){
  disposeRoutes();
  modelMeshes.forEach(mesh=>{ mesh.userData.active=false; mesh.material.emissiveIntensity=mesh.userData.baseEmissive; });
  routes.forEach(route=>{ if(!sovereign || route.license === 'GREEN') lightRoute(route); });
  syncLabelStates();
}

async function poll(){
  document.getElementById('lastPoll').textContent = `polling ${new Date().toLocaleTimeString()}`;
  try{
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),1800);
    const response = await fetch(STATS_EP,{ mode:'cors',cache:'no-store',signal:controller.signal });
    clearTimeout(timeout);
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    const stats = normalizeStats(await response.json());
    if(stats.source !== 'szl_brain.TIERS'){
      localModelAt = Date.now();
      setOperationalState(graphStats(),'degraded',stats.source);
      return;
    }
    endpointResponseAt = Date.now();
    setOperationalState(stats,'responding','validated schema');
  }catch(error){
    localModelAt = Date.now();
    const reason = error?.name === 'AbortError' ? 'timeout' : String(error?.message || error);
    setOperationalState(graphStats(),'unavailable',reason);
  }finally{
    document.getElementById('lastPoll').textContent = `last attempt ${new Date().toLocaleTimeString()}`;
  }
}

function updateFreshness(){
  const node = document.getElementById('freshnessState');
  const now = Date.now();
  if(lastState === 'responding' && endpointResponseAt){
    const seconds = Math.max(0,Math.floor((now-endpointResponseAt)/1000));
    node.textContent = `Validated response received ${seconds}s ago (response age, not model age).`;
  }else if(localModelAt){
    const seconds = Math.max(0,Math.floor((now-localModelAt)/1000));
    node.textContent = `Local modeled decision calculated ${seconds}s ago.`;
  }else{
    node.textContent = 'No validated response received.';
  }
}

const labelLayer = document.getElementById('labelLayer');
const modelLabelByName = new Map();
const projectedLabels = [];

function openTierCard(tier){
  const color = `#${TIER_COLORS[Number(tier[0].slice(1))].toString(16).padStart(6,'0')}`;
  const models = MODELS.filter(model=>model.tier===tier[0]);
  cardBody.innerHTML = `<h2>${esc(tier[0])} · ${esc(tier[1])}</h2>`+
    `<span class="lic" style="background:${color};color:#05101c">${esc(tier[2])}</span>`+
    `<table><tr><td>registry nodes</td><td>${models.length}</td></tr>`+
    models.map(model=>`<tr><td>${esc(model.license)}</td><td>${esc(model.name)}</td></tr>`).join('')+
    `</table>`;
  card.hidden = false;
}

function createPersistentLabels(){
  TIERS.forEach(tier=>{
    const button = document.createElement('button');
    const color = `#${TIER_COLORS[Number(tier[0].slice(1))].toString(16).padStart(6,'0')}`;
    button.type='button'; button.className='node-label'; button.dataset.kind='tier';
    button.style.setProperty('--node-color',color);
    button.innerHTML = `<span class="node-tier">${esc(tier[0])}</span>${esc(tier[1])}`;
    button.setAttribute('aria-label',`${tier[0]} ${tier[1]}, latency target ${tier[2]}`);
    button.addEventListener('click',()=>openTierCard(tier));
    labelLayer.append(button); projectedLabels.push({ element:button, object:tierNodes[tier[0]] });

    const chip = document.createElement('button');
    chip.type='button'; chip.className='tier-chip'; chip.style.setProperty('--tier-color',color);
    chip.innerHTML = `<b>${esc(tier[0])}</b><span>${esc(tier[1])} · ${esc(tier[2])}</span>`;
    chip.setAttribute('aria-label',`${tier[0]} ${tier[1]}, latency target ${tier[2]}`);
    chip.addEventListener('click',()=>openTierCard(tier));
    document.getElementById('tierRail').append(chip);
  });

  modelMeshes.forEach(mesh=>{
    const model = mesh.userData.model;
    const button = document.createElement('button');
    button.type='button'; button.className='node-label'; button.dataset.kind='model';
    button.style.setProperty('--node-color',LIC_CSS[model.license]);
    const tier = document.createElement('span'); tier.className='node-tier'; tier.textContent=model.tier;
    button.append(tier,document.createTextNode(model.name));
    button.setAttribute('aria-label',`${model.name}; ${model.tier}; ${model.license}; context ${model.ctx}`);
    button.addEventListener('mouseenter',()=>showTipForModel(model,button));
    button.addEventListener('mouseleave',()=>{ tip.hidden=true; });
    button.addEventListener('focus',()=>showTipForModel(model,button));
    button.addEventListener('blur',()=>{ tip.hidden=true; });
    button.addEventListener('click',()=>openModelCard(model));
    labelLayer.append(button); projectedLabels.push({ element:button, object:mesh });
    modelLabelByName.set(model.name,button);
  });
}

function updateProjectedLabels(){
  if(!renderer) return;
  scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
  const world = new THREE.Vector3();
  for(const item of projectedLabels){
    item.object.getWorldPosition(world); world.project(camera);
    const visible = world.z > -1 && world.z < 1 && Math.abs(world.x) < 1.08 && Math.abs(world.y) < 1.08;
    item.element.hidden = !visible;
    if(!visible) continue;
    const x = (world.x * .5 + .5) * innerWidth;
    const y = (-world.y * .5 + .5) * innerHeight;
    item.element.style.transform = `translate(-50%,-50%) translate(${x}px,${y}px)`;
  }
}

function syncLabelStates(){
  const active = new Set(lastRoutes.map(route=>route.model));
  modelMeshes.forEach(mesh=>{
    const model = mesh.userData.model;
    const muted = sovereign && model.license !== 'GREEN';
    mesh.material.opacity = muted ? 0.08 : 1;
    const label = modelLabelByName.get(model.name);
    if(label){ label.dataset.active = String(active.has(model.name)); label.dataset.muted = String(muted); }
  });
}

document.getElementById('modelCount').textContent = String(MODELS.length);
document.getElementById('tierCount').textContent = String(TIERS.length);
document.getElementById('sov').addEventListener('change',event=>{
  sovereign = event.target.checked;
  const stats = lastState === 'responding' ? { routes:lastRoutes } : graphStats();
  if(lastState !== 'responding'){
    localModelAt = Date.now();
    setOperationalState(stats,lastState === 'degraded' ? 'degraded' : 'unavailable','sovereign filter updated');
  }else{
    updateRouteVisuals(stats.routes);
  }
  syncLabelStates();
});

const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
const tip = document.getElementById('tip');
const card = document.getElementById('card');
const cardBody = document.getElementById('cardBody');
document.getElementById('closeCard').addEventListener('click',()=>{ card.hidden=true; });

function showTipForModel(model,anchorOrEvent){
  let x; let y;
  if(anchorOrEvent instanceof Element){
    const rect = anchorOrEvent.getBoundingClientRect(); x=rect.right+10; y=rect.top;
  }else{ x=anchorOrEvent.clientX+12; y=anchorOrEvent.clientY+12; }
  let best;
  TASKS.forEach(task=>{ const score=edgeAffinity(task,model).score; if(!best || score>best.score) best={task,score}; });
  tip.innerHTML = `<b>${esc(model.name)}</b> · ${esc(model.tier)}<br>${esc(model.license)} · ${esc(model.ctx)}`+
    (best ? `<br>best modeled fit: ${esc(best.task.label)} ${Math.round(best.score*100)}%` : '');
  tip.hidden=false;
  const maxX = innerWidth - Math.min(320,tip.offsetWidth) - 10;
  const maxY = innerHeight - tip.offsetHeight - 10;
  tip.style.left=`${Math.max(8,Math.min(x,maxX))}px`; tip.style.top=`${Math.max(8,Math.min(y,maxY))}px`;
}

function openModelCard(model){
  const color = LIC_CSS[model.license];
  cardBody.innerHTML = `<h2>${esc(model.name)}</h2>`+
    `<span class="lic" style="background:${color};color:#05101c">${esc(model.license)}</span>`+
    `<table><tr><td>tier</td><td>${esc(model.tier)} — ${esc(TIERS.find(tier=>tier[0]===model.tier)?.[1] || '')}</td></tr>`+
    `<tr><td>context</td><td>${esc(model.ctx)}</td></tr><tr><td>benchmark</td><td>${esc(model.bench)}</td></tr>`+
    `<tr><td>provider</td><td>${esc(model.prov)}</td></tr><tr><td>license class</td><td>${esc(model.license)}</td></tr></table>`+
    `<div class="aff"><b>modeled graph affinity</b> <small>(heuristic; not an online benchmark)</small><table>`+
    TASKS.map(task=>{ const pct=Math.round(edgeAffinity(task,model).score*100); return `<tr><td>${esc(task.label)}</td><td>${pct}%</td></tr>`; }).join('')+
    `</table></div>`+
    (model.hf ? `<a href="https://huggingface.co/${esc(model.hf)}" target="_blank" rel="noopener">huggingface.co/${esc(model.hf)}</a>` : '');
  card.hidden=false;
}

function setPointer(event){
  ndc.x=(event.clientX/innerWidth)*2-1; ndc.y=-(event.clientY/innerHeight)*2+1;
  ray.setFromCamera(ndc,camera);
}

function pick(event){
  setPointer(event);
  const hit=ray.intersectObjects(modelMeshes,false)[0];
  if(hit) showTipForModel(hit.object.userData.model,event); else tip.hidden=true;
}

function clickPick(event){
  setPointer(event);
  const hit=ray.intersectObjects(modelMeshes,false)[0];
  if(hit) openModelCard(hit.object.userData.model);
}

function showRenderFallback(message){
  document.body.classList.remove('scene-ready');
  document.body.classList.add('scene-unavailable');
  document.getElementById('renderPill').textContent='3D UNAVAILABLE';
  document.getElementById('renderPill').className='pill unavailable';
  document.getElementById('fallbackReason').textContent=`${message}. The accessible tier registry and route-status panels remain available; no blank canvas is shown.`;
}

async function boot(){
  createPersistentLabels();
  try{
    renderer=await makeRenderer();
    renderer.setSize(innerWidth,innerHeight);
    renderer.setPixelRatio(SZLMobileControls.rendererHints().pixelRatio);
    document.getElementById('root').appendChild(renderer.domElement);
    document.body.classList.add('scene-ready');
    document.getElementById('renderPill').textContent=BACKEND.toUpperCase();
    controls=new OrbitControls(camera,renderer.domElement);
    controls.enableDamping=!SZL_REDUCED; controls.dampingFactor=0.055;
    controls.minDistance=48; controls.maxDistance=210; controls.maxPolarAngle=Math.PI*0.49;
    controls.enablePan=true;
    if(SZL_MOBILE){ controls.rotateSpeed=.55; controls.zoomSpeed=.75; }
    renderer.domElement.addEventListener('pointermove',pick);
    renderer.domElement.addEventListener('click',clickPick);
    addEventListener('resize',()=>{
      camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight);
    });
  }catch(error){
    console.error(error);
    showRenderFallback(error?.message || 'Renderer initialization failed');
  }

  await poll();
  setInterval(poll,POLL_MS);
  setInterval(updateFreshness,1000);

  if(!renderer) return;
  const clock=new THREE.Clock();
  function loop(){
    const elapsed=clock.getElapsedTime();
    if(!SZL_REDUCED) scene.rotation.y=elapsed*0.025;
    Object.values(organMeshes).forEach(mesh=>{ mesh.material.emissiveIntensity+=(1.15-mesh.material.emissiveIntensity)*.025; });
    Object.values(tierNodes).forEach(mesh=>{ mesh.material.emissiveIntensity+=(.95-mesh.material.emissiveIntensity)*.025; });
    controls.update(); updateProjectedLabels();
    if(!document.hidden) renderer.render(scene,camera);
    requestAnimationFrame(loop);
  }
  loop();
}

boot().catch(error=>{
  console.error(error);
  showRenderFallback(error?.message || 'Router boot failed');
});
