/* ============================================================================
 * a11oy_cathedral.js — "The Sovereign Lattice" front-door hero (vendored Three.js).
 * A luminous gold lattice-core (a11oy) with three governed faculties orbiting it,
 * in deep sovereign space. Cinematic: layered additive bloom, multi-depth starfield,
 * faint nebula, pointer parallax, scroll-driven camera. Live /healthz + Λ.
 * Honesty: locked proven = 5; Λ = Conjecture 1. No fakery; honest fallback.
 * Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 * ========================================================================== */
import * as THREE from 'three';

const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias:true, alpha:false, powerPreference:'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.9));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.18;

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x05060f, 0.0016);
const camera = new THREE.PerspectiveCamera(46, innerWidth/innerHeight, 0.1, 6000);

// composition: core sits on the right; hero text breathes on the left
const HOME = new THREE.Vector3(46, 16, 250);
const LOOK = new THREE.Vector3(64, 6, 0);
camera.position.copy(HOME);

scene.add(new THREE.AmbientLight(0x2a2942, 0.85));
const keyLight = new THREE.PointLight(0xffe2a0, 2.7, 2200, 1.5); keyLight.position.set(70, 30, 40); scene.add(keyLight);
const rim = new THREE.DirectionalLight(0x6d8fd6, 0.55); rim.position.set(-220, 120, -120); scene.add(rim);
const fill = new THREE.DirectionalLight(0x7fd6d1, 0.18); fill.position.set(120, -80, 120); scene.add(fill);

/* ---- faint nebula: large additive gradient sprites ---- */
function radialSprite(c1, c2, sz, op){
  const cv=document.createElement('canvas'); cv.width=cv.height=256; const g=cv.getContext('2d');
  const grd=g.createRadialGradient(128,128,0,128,128,128);
  grd.addColorStop(0,c1); grd.addColorStop(0.45,c2); grd.addColorStop(1,'rgba(0,0,0,0)');
  g.fillStyle=grd; g.fillRect(0,0,256,256);
  const tex=new THREE.CanvasTexture(cv);
  const s=new THREE.Sprite(new THREE.SpriteMaterial({ map:tex, transparent:true, opacity:op, blending:THREE.AdditiveBlending, depthWrite:false }));
  s.scale.set(sz,sz,1); return s;
}
const neb1=radialSprite('rgba(215,185,107,0.5)','rgba(120,90,30,0.18)',1500,0.5); neb1.position.set(160,40,-500); scene.add(neb1);
const neb2=radialSprite('rgba(60,80,150,0.5)','rgba(30,40,90,0.16)',1900,0.45); neb2.position.set(-380,-120,-820); scene.add(neb2);
const neb3=radialSprite('rgba(127,214,209,0.32)','rgba(20,90,90,0.1)',1000,0.4); neb3.position.set(-180,180,-360); scene.add(neb3);

/* ---- multi-depth starfield ---- */
function starLayer(n, rMin, rMax, size, col, op){
  const pos=new Float32Array(n*3);
  for(let i=0;i<n;i++){ const r=rMin+Math.random()*(rMax-rMin), t=Math.random()*Math.PI*2, p=Math.acos(2*Math.random()-1);
    pos[i*3]=r*Math.sin(p)*Math.cos(t); pos[i*3+1]=r*Math.cos(p); pos[i*3+2]=r*Math.sin(p)*Math.sin(t); }
  const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos,3));
  const pts=new THREE.Points(g, new THREE.PointsMaterial({ color:col, size, sizeAttenuation:true, transparent:true, opacity:op, depthWrite:false }));
  scene.add(pts); return pts;
}
const stars1=starLayer(1700, 700, 1500, 1.1, 0x9aa0d0, 0.55);
const stars2=starLayer(1100, 1400, 2800, 2.2, 0xcdbb8e, 0.5);
const stars3=starLayer(500, 380, 900, 1.5, 0x7fd6d1, 0.32);

/* ---- the sovereign lattice-core (a11oy) ---- */
const core=new THREE.Group(); core.position.copy(LOOK); scene.add(core);

const coreMesh=new THREE.Mesh(new THREE.IcosahedronGeometry(34,5),
  new THREE.MeshStandardMaterial({ color:0xffcf73, emissive:0xe0a536, emissiveIntensity:1.55, roughness:0.34, metalness:0.12, flatShading:true }));
core.add(coreMesh);

const latticeA=new THREE.Mesh(new THREE.IcosahedronGeometry(44,2),
  new THREE.MeshBasicMaterial({ color:0xffe6a8, wireframe:true, transparent:true, opacity:0.26 }));
core.add(latticeA);
const latticeB=new THREE.Mesh(new THREE.IcosahedronGeometry(56,1),
  new THREE.MeshBasicMaterial({ color:0xd7b96b, wireframe:true, transparent:true, opacity:0.12 }));
core.add(latticeB);

// layered additive bloom halos
for(const [r,o] of [[64,0.16],[92,0.09],[140,0.05]]){
  const h=new THREE.Mesh(new THREE.SphereGeometry(r,32,32),
    new THREE.MeshBasicMaterial({ color:0xffd98a, transparent:true, opacity:o, side:THREE.BackSide, blending:THREE.AdditiveBlending, depthWrite:false }));
  core.add(h);
}
const flare=radialSprite('rgba(255,222,150,0.95)','rgba(224,165,54,0.35)',360,0.9); core.add(flare);

// inner sparks orbiting inside the core
const sparkN=80, sparkPos=new Float32Array(sparkN*3), sparkSeed=[];
for(let i=0;i<sparkN;i++){ sparkSeed.push({a:Math.random()*Math.PI*2,b:Math.random()*Math.PI,r:20+Math.random()*22,s:0.4+Math.random()}); }
const sparkGeo=new THREE.BufferGeometry(); sparkGeo.setAttribute('position',new THREE.BufferAttribute(sparkPos,3));
core.add(new THREE.Points(sparkGeo, new THREE.PointsMaterial({ color:0xfff0c8, size:1.7, transparent:true, opacity:0.85, blending:THREE.AdditiveBlending, depthWrite:false })));

/* ---- three orbiting faculties ---- */
const FAC=[
  {color:0x7fd6d1, angle:0.2,  rx:120, rz:120, tilt:0.12},
  {color:0xd7b96b, angle:2.25, rx:138, rz:128, tilt:-0.22},
  {color:0xe58e54, angle:4.2,  rx:128, rz:140, tilt:0.30},
];
const facBodies=[];
FAC.forEach((f)=>{
  const g=new THREE.Group();
  const m=new THREE.Mesh(new THREE.IcosahedronGeometry(11,2),
    new THREE.MeshStandardMaterial({ color:f.color, emissive:f.color, emissiveIntensity:0.7, roughness:0.45, metalness:0.25 }));
  g.add(m);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(17,0.5,8,72),
    new THREE.MeshBasicMaterial({ color:f.color, transparent:true, opacity:0.4 })); ring.rotation.x=Math.PI/2; g.add(ring);
  g.add(radialSprite(`rgba(${(f.color>>16)&255},${(f.color>>8)&255},${f.color&255},0.8)`,'rgba(0,0,0,0)',70,0.7));
  scene.add(g);
  // curved tether (core -> faculty) as a tube we rebuild each frame
  const tetherMat=new THREE.MeshBasicMaterial({ color:f.color, transparent:true, opacity:0.16, blending:THREE.AdditiveBlending, depthWrite:false });
  let tetherMesh=null;
  facBodies.push({ f, g, m, tetherMat, get tether(){return tetherMesh;}, set tether(v){tetherMesh=v;} });
});

/* ---- live mesh: /healthz + Λ ---- */
const lamDot=document.getElementById('lam-dot'), lamText=document.getElementById('lam-text');
async function getJSON(url,ms){ const c=new AbortController(); const t=setTimeout(()=>c.abort(),ms||7000);
  try{ const r=await fetch(url,{signal:c.signal,headers:{accept:'application/json'}}); if(!r.ok) throw 0; return await r.json(); } finally{ clearTimeout(t); } }
let lambda=null, alive=false;
async function poll(){
  try{ const h=await getJSON('/healthz',7000); alive=!!(h&&(h.status==='ok'||h.ok)); }catch(_){ alive=false; }
  try{ const l=await getJSON('/api/a11oy/v1/lambda',7000); if(l&&typeof l.lambda==='number') lambda=l.lambda; }catch(_){}
  paint();
}
function paint(){
  if(!lamDot) return;
  if(alive){ lamDot.classList.add('live'); }else{ lamDot.classList.remove('live'); }
  if(lambda!==null) lamText.innerHTML = `<b>Λ ${lambda.toFixed(3)}</b> · live trust score · 13-axis`;
  else lamText.textContent = alive ? 'mesh live · Λ reconnecting…' : 'live mesh offline · honest fallback';
}
paint(); poll(); setInterval(poll, 8000);

/* ---- pointer parallax + scroll ---- */
let px=0, py=0, tpx=0, tpy=0;
if(!REDUCED) addEventListener('pointermove',(e)=>{ tpx=(e.clientX/innerWidth-0.5); tpy=(e.clientY/innerHeight-0.5); }, {passive:true});
let scrollP=0;
function onScroll(){ const max=document.body.scrollHeight-innerHeight; scrollP = max>0 ? Math.min(1, scrollY/max) : 0; }
addEventListener('scroll', onScroll, {passive:true}); onScroll();

/* ---- intro dolly ---- */
let intro=REDUCED?1:0;

const _v=new THREE.Vector3();
const _look=new THREE.Vector3();
let t=0;
function animate(){
  requestAnimationFrame(animate);
  t+=0.0045;
  if(intro<1){ intro=Math.min(1, intro+0.012); }
  const e=intro<1 ? 1-Math.pow(1-intro,3) : 1; // easeOutCubic

  // core motion
  coreMesh.rotation.y+=0.0016; coreMesh.rotation.x+=0.0005;
  latticeA.rotation.y-=0.0012; latticeA.rotation.x+=0.0007;
  latticeB.rotation.y+=0.0009; latticeB.rotation.z-=0.0006;
  const pulse=1+0.012*Math.sin(t*2.0); core.scale.setScalar(pulse);
  flare.material.opacity=0.78+0.12*Math.sin(t*1.7);

  // inner sparks
  for(let i=0;i<sparkN;i++){ const s=sparkSeed[i]; const a=s.a+t*s.s; const b=s.b+t*0.3*s.s; const r=s.r;
    sparkPos[i*3]=r*Math.sin(b)*Math.cos(a); sparkPos[i*3+1]=r*Math.cos(b); sparkPos[i*3+2]=r*Math.sin(b)*Math.sin(a); }
  sparkGeo.attributes.position.needsUpdate=true;

  // faculties orbit + curved tethers
  facBodies.forEach((fb,i)=>{
    const f=fb.f; const a=f.angle + t*0.22*(i%2?-1:1);
    const x=LOOK.x+Math.cos(a)*f.rx;
    const z=LOOK.z+Math.sin(a)*f.rz;
    const y=LOOK.y+Math.sin(a*1.4+i)*26 + f.tilt*40*Math.cos(a*0.7);
    fb.g.position.set(x,y,z); fb.m.rotation.y+=0.012;
    const mid=new THREE.Vector3((LOOK.x+x)/2,(LOOK.y+y)/2+24,(LOOK.z+z)/2);
    const curve=new THREE.QuadraticBezierCurve3(new THREE.Vector3(LOOK.x,LOOK.y,LOOK.z), mid, new THREE.Vector3(x,y,z));
    if(fb.tether){ fb.tether.geometry.dispose(); core.parent.remove(fb.tether); }
    fb.tether=new THREE.Mesh(new THREE.TubeGeometry(curve,20,0.45,6,false), fb.tetherMat); scene.add(fb.tether);
  });

  // starfield drift
  stars1.rotation.y+=0.00012; stars2.rotation.y-=0.00007; stars3.rotation.y+=0.0002;

  // camera: parallax + gentle idle + scroll framing.
  // We aim LEFT of the core so it sits in the right third (text breathes on the
  // left). As you scroll we push the core toward the right edge (no zoom-in that
  // would swamp the headlines) and pull back slightly so it reads as an accent.
  px+=(tpx-px)*0.04; py+=(tpy-py)*0.04;
  const frameX = 60 + 84*scrollP;        // aim offset: larger -> core further right
  const frameY = 4 + 14*scrollP;
  const camHome=HOME.clone();
  camHome.y += 24*scrollP;               // gentle lift
  camHome.z += 30*scrollP;               // pull back (core smaller) instead of zoom-in
  camHome.x += 14*scrollP;
  const idleX=Math.sin(t*0.5)*5, idleY=Math.cos(t*0.4)*4;
  _v.set(camHome.x + px*32 + idleX, camHome.y - py*22 + idleY, camHome.z);
  camera.position.lerp(_v, e<1?0.06*e+0.02:0.06);
  const look=_look.set(LOOK.x - frameX + px*12, LOOK.y + frameY - py*6, LOOK.z);
  camera.lookAt(look);
  renderer.toneMappingExposure = 1.2 - 0.16*scrollP;

  renderer.render(scene,camera);
}
animate();

addEventListener('resize',()=>{ camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });

/* ---- nav stuck + scroll reveals + boot ---- */
const nav=document.getElementById('nav');
function navState(){ if(scrollY>24) nav.classList.add('stuck'); else nav.classList.remove('stuck'); }
addEventListener('scroll', navState, {passive:true}); navState();

const io=new IntersectionObserver((es)=>{ es.forEach(en=>{ if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); } }); }, {threshold:0.16});
document.querySelectorAll('.reveal').forEach((el,i)=>{ el.style.transitionDelay=(Math.min(i,6)*70)+'ms'; io.observe(el); });

const boot=document.getElementById('boot');
function hideBoot(){ boot.classList.add('hide'); setTimeout(()=>boot.style.display='none', 850); }
setTimeout(hideBoot, REDUCED?200:700);
