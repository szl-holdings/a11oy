// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainbody.js — ANATOMY · BODY LIT BY THE BRAIN (Wave O, Dev 3).
//
// The founder's vision: "I want my Brain harnessing and giving energy to the whole
// ecosystem." This surface renders that literally — a central BRAIN CORE pulses and
// radiates light down "nerves" to a ring of organs, and EACH ORGAN'S BRIGHTNESS is
// driven by the real Brain pulse (Dev-1 GET /api/a11oy/v1/brain/pulse) and its energy
// allocation (Dev-2 GET /api/a11oy/v1/brain/energy), composed server-side by
// GET /api/a11oy/v1/frontier/brainbody (this Dev's thin backend, szl_brainbody.py).
//
// WHAT IS LIT BY THE BRAIN:
//   - BRAIN CORE — pulses at the pulse's activity; teal + bright when the pulse is
//     LIVE, dim grey when UNAVAILABLE. It is the light SOURCE.
//   - EACH ORGAN — a node on the body ring whose emissive brightness = its per-organ
//     value from the pulse (activity) blended with its energy allocation. A pulse of
//     light travels the nerve from the Brain to each LIT organ every beat.
//   - HONEST PER-ORGAN LABELS — every organ shows LIVE / MODELED / UNAVAILABLE
//     VERBATIM. An UNAVAILABLE organ is DARK + still; it is NEVER shown alive.
//
// HONESTY (Zero-Bandaid Law): the Brain hub/energy PRs may not be merged in this
//   runtime. The backend composes with a guarded fallback and returns honest
//   UNAVAILABLE when a source is absent — so this surface renders a DARK body rather
//   than a fabricated living one. Nothing here fabricates a pulse, a joule, or a lit
//   organ. Λ = Conjecture 1 (advisory, grey, never green); trust ceiling 0.97 (never
//   1.0). Nothing touches the locked-8. ZERO PURPLE. three via ctx.THREE (0 CDN).
//
// Surface export shape mirrors sovereign.js / evalarena.js exactly:
//   export default { id, title, endpoints, mount, unmount }

import { createShowcase } from "./_showcase.js";

const ID    = "brainbody";
const TITLE = "Anatomy · Body lit by the Brain";

const EP_PANEL  = "/api/a11oy/v1/frontier/brainbody"; // this Dev's composer
const EP_PULSE  = "/api/a11oy/v1/brain/pulse";         // Dev-1 (read server-side)
const EP_ENERGY = "/api/a11oy/v1/brain/energy";        // Dev-2 (read server-side)

// data-viz hues — purple BANNED
const C_LIVE    = 0x3af4c8; // proof-teal (LIVE — organ lit by the Brain)
const C_MODELED = 0x5b8dee; // lattice-blue (MODELED — dimmer, honest)
const C_DOWN    = 0x2b3542; // dark slate (UNAVAILABLE — dark, never alive)
const C_BRAIN   = 0x8fdcff; // light blue (Brain core — the light source)
const C_NERVE   = 0x1b3a44; // nerve edge (idle)

const BRAIN_R = 1.05, RING_R = 5.4;

let _stage=null,_THREE=null,_ctx=null,_group=null,_overlay=null;
let _frameReg=false,_polls=[],_badge=null,_plain=false,_t0=0,_show=null;
let _brain=null,_brainGlow=null,_nerves=[],_organs=[]; // _organs: [{mesh,glow,nerve,comet,data}]

const S = {
  label:"UNAVAILABLE", state:"init",
  pulseOk:false, pulseLabel:"UNAVAILABLE", pulseSource:null, pulseNote:null,
  energyOk:false, energyLabel:"UNAVAILABLE", energySource:null, energyNote:null,
  organs:[], // [{id,organ,role,label,brightness,activity,energy_alloc,lit_by_brain}]
  summary:{organs_total:0,organs_lit:0,live:0,modeled:0,unavailable:0},
  signMode:null, signed:false,
};

function _colFor(label){
  if(label==="LIVE") return C_LIVE;
  if(label==="MODELED") return C_MODELED;
  return C_DOWN;
}

function mount(ctx){
  _ctx=ctx; _stage=ctx.stage; _THREE=ctx.THREE;
  _group=new _THREE.Group(); _stage.scene.add(_group);
  try{ _stage.camera.position.set(0,3.5,14); }catch(_){}
  try{ if(_stage.controls&&_stage.controls.target){ _stage.controls.target.set(0,0.2,0); _stage.controls.update(); } }catch(_){}
  try{ _stage.setBloom&&_stage.setBloom(true); }catch(_){}
  _t0=(typeof performance!=="undefined"?performance.now():Date.now());
  _badge=ctx.live.createBadge();
  _buildOverlay(ctx);
  _buildBrain();

  // GET the composed panel — the CORE poll. It reads the Brain pulse (Dev-1) + energy
  // (Dev-2) server-side and returns per-organ lighting; degrades to honest UNAVAILABLE.
  _polls.push(ctx.live.poll(EP_PANEL, 8000, _onPanel, {
    badge:_badge,
    onState:(m)=>{ S.state=m.state; _paintOverlay(); },
  }));

  if(!_frameReg&&_stage.onFrame){ _stage.onFrame(_animate); _frameReg=true; }
  _paintOverlay();
  return { id:ID, started:true };
}

function _readLabel(j){ const l=(j&&j.label!=null)?j.label:"UNAVAILABLE"; return String(l).toUpperCase(); }

function _onPanel(j){
  if(!j){ S.state="error"; _paintOverlay(); return; }
  S.label=_readLabel(j);
  const pu=j.pulse||{}, en=j.energy||{};
  S.pulseOk=(pu.ok===true); S.pulseLabel=String(pu.label||"UNAVAILABLE").toUpperCase();
  S.pulseSource=pu.source||null; S.pulseNote=pu.note||pu.dependency||null;
  S.energyOk=(en.ok===true); S.energyLabel=String(en.label||"UNAVAILABLE").toUpperCase();
  S.energySource=en.source||null; S.energyNote=en.note||en.dependency||null;
  S.organs=Array.isArray(j.organs)?j.organs:[];
  S.summary=j.summary||S.summary;
  const sr=j.signed_receipt||{};
  S.signMode=sr.sign_mode||null; S.signed=(sr.signed===true);

  _rebuildOrgans();
  _paintScene();
  _paintOverlay();
}

// ---------------------------------------------------------------------------
// scene
// ---------------------------------------------------------------------------
function _buildBrain(){
  const cg=new _THREE.SphereGeometry(BRAIN_R,40,40);
  const cm=new _THREE.MeshStandardMaterial({ color:C_DOWN,emissive:C_DOWN,emissiveIntensity:0.2,metalness:0.12,roughness:0.45 });
  _brain=new _THREE.Mesh(cg,cm); _brain.position.set(0,0,0); _brain.userData={role:"brain-core"}; _group.add(_brain);
  const gg=new _THREE.SphereGeometry(BRAIN_R*1.5,24,24);
  const gm=new _THREE.MeshBasicMaterial({ color:C_BRAIN,transparent:true,opacity:0.06,blending:_THREE.AdditiveBlending,depthWrite:false });
  _brainGlow=new _THREE.Mesh(gg,gm); _group.add(_brainGlow);
}

function _disposeOrgans(){
  _organs.forEach((o)=>{
    [o.mesh,o.glow,o.nerve,o.comet].forEach((m)=>{ if(!m)return;
      try{ if(m.geometry&&m.geometry.dispose)m.geometry.dispose(); }catch(_){}
      try{ const ms=Array.isArray(m.material)?m.material:[m.material]; ms.forEach((x)=>{if(x&&x.dispose)x.dispose();}); }catch(_){}
      try{ _group.remove(m); }catch(_){}
    });
  });
  _organs=[]; _nerves=[];
}

function _rebuildOrgans(){
  if(!_group||!_THREE)return;
  _disposeOrgans();
  const n=S.organs.length||1;
  S.organs.forEach((d,i)=>{
    const ang=(i/n)*Math.PI*2;
    const px=Math.cos(ang)*RING_R, pz=Math.sin(ang)*RING_R, py=0.6*Math.sin(ang*1.3);
    const col=_colFor(d.label);

    // organ node
    const og=new _THREE.SphereGeometry(0.5,22,22);
    const om=new _THREE.MeshStandardMaterial({ color:col,emissive:col,emissiveIntensity:0.25,metalness:0.1,roughness:0.5,transparent:true,opacity:0.92 });
    const mesh=new _THREE.Mesh(og,om); mesh.position.set(px,py,pz); mesh.userData={role:"organ",id:d.id}; _group.add(mesh);

    // organ glow
    const gg=new _THREE.SphereGeometry(0.7,16,16);
    const gm=new _THREE.MeshBasicMaterial({ color:col,transparent:true,opacity:0.05,blending:_THREE.AdditiveBlending,depthWrite:false });
    const glow=new _THREE.Mesh(gg,gm); glow.position.set(px,py,pz); _group.add(glow);

    // nerve from Brain core to organ
    const pts=[new _THREE.Vector3(0,0,0), new _THREE.Vector3(px,py,pz)];
    const ng=new _THREE.BufferGeometry().setFromPoints(pts);
    const nm=new _THREE.LineBasicMaterial({ color:C_NERVE,transparent:true,opacity:0.5 });
    const nerve=new _THREE.Line(ng,nm); _group.add(nerve);

    // pulse comet that travels the nerve when the organ is lit by the Brain
    const cg=new _THREE.SphereGeometry(0.11,10,10);
    const cm=new _THREE.MeshBasicMaterial({ color:col,transparent:true,opacity:0.0,blending:_THREE.AdditiveBlending,depthWrite:false });
    const comet=new _THREE.Mesh(cg,cm); _group.add(comet);

    // billboard label — organ name + VERBATIM honesty label
    let sprite=null;
    try{ sprite=_ctx.label.billboard(_THREE, d.label, { text:(d.organ||d.id)+" · "+d.label, scale:1.15, position:[px,py+1.0,pz] }); if(sprite)_group.add(sprite); }catch(_){}

    _organs.push({ mesh, glow, nerve, comet, sprite, data:d, ang, base:new _THREE.Vector3(px,py,pz) });
  });
}

function _paintScene(){
  const live=(S.pulseLabel==="LIVE");
  const bcol=live?C_BRAIN:C_DOWN;
  if(_brain&&_brain.material){ _brain.material.color.setHex(bcol); _brain.material.emissive.setHex(bcol); _brain.material.emissiveIntensity=live?0.6:0.18; }
  if(_brainGlow&&_brainGlow.material){ _brainGlow.material.color.setHex(bcol); _brainGlow.material.opacity=live?0.14:0.04; }
  _organs.forEach((o)=>{
    const d=o.data, col=_colFor(d.label), b=(typeof d.brightness==="number")?d.brightness:0.06;
    if(o.mesh&&o.mesh.material){ o.mesh.material.color.setHex(col); o.mesh.material.emissive.setHex(col); o.mesh.material.emissiveIntensity=b; o.mesh.material.opacity=(d.label==="UNAVAILABLE")?0.35:0.92; }
    if(o.glow&&o.glow.material){ o.glow.material.color.setHex(col); o.glow.material.opacity=(d.label==="UNAVAILABLE")?0.02:(0.04+0.10*b); }
    if(o.nerve&&o.nerve.material){ o.nerve.material.color.setHex(d.lit_by_brain?col:C_NERVE); o.nerve.material.opacity=d.lit_by_brain?(0.35+0.4*b):0.18; }
  });
}

function _animate(){
  if(!_group)return;
  const now=(typeof performance!=="undefined"?performance.now():Date.now()); const t=(now-_t0)/1000;
  const live=(S.pulseLabel==="LIVE");
  // Brain core breathes with the pulse.
  if(_brain&&_brain.material){ _brain.material.emissiveIntensity=(live?0.5:0.16)+(live?0.25:0.05)*Math.abs(Math.sin(t*1.8)); }
  if(_brainGlow){ const s=1.0+(live?0.10:0.03)*Math.sin(t*1.8); _brainGlow.scale.setScalar(s); }
  // Organs pulse in proportion to their brightness; comet of light travels the nerve.
  _organs.forEach((o,i)=>{
    const d=o.data, b=(typeof d.brightness==="number")?d.brightness:0.06;
    const lit=d.lit_by_brain;
    if(o.mesh&&o.mesh.material&&lit){ o.mesh.material.emissiveIntensity=b*(0.75+0.25*Math.sin(t*2.2+i)); }
    if(o.comet&&o.comet.material){
      if(lit){
        const phase=((t*0.6+i*0.13)%1); // 0..1 along the nerve
        o.comet.position.copy(o.base).multiplyScalar(phase);
        o.comet.material.opacity=0.7*(1-Math.abs(0.5-phase)*1.4);
      } else { o.comet.material.opacity=0.0; }
    }
    // gentle bob
    if(o.mesh){ o.mesh.position.y=o.base.y+0.12*Math.sin(t*0.9+i); if(o.glow)o.glow.position.y=o.mesh.position.y; }
  });
  _group.rotation.y=t*0.05;
}

// ---------------------------------------------------------------------------
// overlay / HUD — mobile-friendly (flex-wrap, small fonts, matches sovereign.js)
// ---------------------------------------------------------------------------
function _buildOverlay(ctx){
  _show=createShowcase(ctx,{
    id:ID, title:TITLE, accent:"#3af4c8", badge:_badge,
    chips:[{label:"UNAVAILABLE", name:"label"},{label:"Λ=Conjecture 1", name:"lambda"}],
  });
  _overlay=document.createElement("div");
  _overlay.style.cssText="font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;";
  _overlay.innerHTML=
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">The founder\'s <b>Brain harnessing and giving energy to the whole ecosystem</b>: a central Brain core pulses and radiates light down nerves to each organ. <b>Each organ\'s brightness is driven by the real Brain pulse</b> (Dev-1 <code>/brain/pulse</code>) <b>and its energy allocation</b> (Dev-2 <code>/brain/energy</code>). If the Brain endpoints aren\'t merged yet, organs read <b>UNAVAILABLE + go dark</b> — never a fabricated living body.</div>'+
    _row("Brain pulse","bb-pulse")+_row("Brain energy","bb-energy")+
    _row("Organs lit","bb-lit")+_row("Signed receipt","bb-sign")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Per-organ — brightness = pulse activity × energy allocation (honest label each)</div>'+
    '<div id="bb-organs" style="display:flex;flex-direction:column;gap:3px"></div>'+
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">'+
      _leg(C_LIVE,"LIVE")+_leg(C_MODELED,"MODELED")+_leg(C_DOWN,"UNAVAILABLE")+_leg(C_BRAIN,"Brain (source)")+
    '</div>'+
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button id="bb-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>'+
      '<button id="bb-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Sources &amp; caveats</button>'+
    '</div>'+
    '<div id="bb-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>'+
    '<div id="bb-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  _show.body.appendChild(_overlay);
  const pb=_overlay.querySelector("#bb-plain"); if(pb) pb.addEventListener("click",()=>{_plain=!_plain;_applyPlain();});
  const ib=_overlay.querySelector("#bb-info");
  if(ib) ib.addEventListener("click",()=>{ const box=_overlay.querySelector("#bb-infobox");
    if(box) box.style.display=box.style.display==="none"?"block":"none";
    if(box&&box.innerHTML==="") box.innerHTML=_infoHTML(); });
}

function _row(k,id){ return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px"><span style="color:#8fb3bd">'+k+'</span><span id="'+id+'" style="color:#eaf6f9;font-variant-numeric:tabular-nums;text-align:right">—</span></div>'; }
function _leg(hex,txt){ const c="#"+hex.toString(16).padStart(6,"0"); return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';margin-right:4px;vertical-align:middle"></span>'+txt+'</span>'; }
function _set(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }

function _paintOverlay(){
  if(!_overlay)return;
  const missing=(S.state==="missing"||S.state==="error");
  if(_show){ _show.setChip("label",S.label||"UNAVAILABLE"); _show.setChip("lambda","Λ=Conjecture 1"); }
  if(missing){
    ["bb-pulse","bb-energy","bb-lit","bb-sign"].forEach((id)=>_set(id,"NO-LIVE-DATA"));
    const box=_overlay.querySelector("#bb-organs");
    if(box) box.innerHTML='<div style="color:#8fb3bd;font-size:10.5px">backend offline — NO-LIVE-DATA (honest, never fabricated).</div>';
    if(_plain)_applyPlain(); return;
  }
  _set("bb-pulse",(S.pulseOk?"":"UNAVAILABLE · ")+S.pulseLabel+(S.pulseSource?(" · "+_short(S.pulseSource)):""));
  _set("bb-energy",(S.energyOk?"":"UNAVAILABLE · ")+S.energyLabel+(S.energySource?(" · "+_short(S.energySource)):""));
  _set("bb-lit",(S.summary.organs_lit||0)+" / "+(S.summary.organs_total||0)+
    "  (LIVE "+(S.summary.live||0)+" · MODELED "+(S.summary.modeled||0)+" · UNAVAILABLE "+(S.summary.unavailable||0)+")");
  _set("bb-sign",(S.signMode||"—")+(S.signed?" ✓ (REAL DSSE)":(S.signMode==="UNSIGNED-LOCAL"?" (unsigned, honest)":"")));
  const box=_overlay.querySelector("#bb-organs");
  if(box){
    if(!S.organs.length){ box.innerHTML='<div style="color:#8fb3bd;font-size:10.5px">no organs — Brain pulse/energy UNAVAILABLE (honest, no fabrication).</div>'; }
    else {
      box.innerHTML=S.organs.map((o)=>{
        const c="#"+_colFor(o.label).toString(16).padStart(6,"0");
        const pct=Math.round((o.brightness||0)*100);
        return '<div style="display:flex;align-items:center;gap:8px;font-size:10.5px">'+
          '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';flex:0 0 auto"></span>'+
          '<span style="flex:1 1 auto;color:#dfeaf0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+_esc(o.organ||o.id)+'</span>'+
          '<span style="flex:0 0 auto;color:'+c+';font-weight:600">'+_esc(o.label)+'</span>'+
          '<span style="flex:0 0 auto;color:#8fb3bd;font-variant-numeric:tabular-nums;width:34px;text-align:right">'+pct+'%</span>'+
        '</div>';
      }).join("");
    }
  }
  if(_plain)_applyPlain();
}

function _short(s){ s=String(s||""); return s.length>26?(s.slice(0,24)+"…"):s; }
function _esc(s){ return String(s==null?"":s).replace(/[&<>]/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }

function _applyPlain(){
  const box=_overlay&&_overlay.querySelector("#bb-plainbox"); if(!box)return;
  box.style.display=_plain?"block":"none";
  if(_plain) box.innerHTML="This tab shows the founder\u2019s idea made visible: <b>one Brain in the middle that powers the whole body</b>. The glowing ball in the center is the <b>Brain</b> \u2014 it is the light source. Around it sit the <b>organs</b> (heart, lungs, memory, muscles, and so on), each standing for a part of the ecosystem. A <b>thread of light runs from the Brain out to each organ</b>, and <b>how bright each organ glows is decided by the real Brain \u2014 how active its pulse is and how much energy the Brain is sending it right now</b>. If the Brain\u2019s live feeds aren\u2019t switched on in this build yet, the organs simply <b>stay dark and say \u201cUNAVAILABLE\u201d</b> \u2014 we would rather show an honest dark body than pretend it\u2019s alive. Green never means \u201cproven\u201d here: trust is advisory (\u039b, capped at 0.97), and nothing on this screen touches the eight locked results.";
}

function _infoHTML(){
  return "<b>What is real vs UNAVAILABLE.</b> This surface calls <code>GET "+EP_PANEL+"</code>, a thin composer (<code>szl_brainbody.py</code>) that reads the <b>Brain pulse</b> (<code>"+EP_PULSE+"</code>, Dev-1 <code>feat/brain-hub</code>) and the <b>Brain energy allocation</b> (<code>"+EP_ENERGY+"</code>, Dev-2 <code>feat/brain-energy</code>) <b>server-side</b> \u2014 preferring the in-process module so it agrees with the routed endpoint by construction, else a same-origin HTTP read. <b>Each organ\u2019s brightness is a deterministic function of its per-organ pulse activity blended with its energy allocation.</b> An organ is <b>LIVE</b> only when a real per-organ pulse value backed it THIS request; <b>MODELED</b> when only a modeled/derived signal (energy share or a global pulse) is present; <b>UNAVAILABLE</b> (dark, still) when no signal is present. No label is ever upgraded and no organ is shown alive without a real value (Zero-Bandaid Law).<br><br><b>Guarded fallback.</b> The Brain hub/energy PRs may not be merged in this runtime; when they are absent the composer returns honest <b>UNAVAILABLE</b> per source and the body renders <b>dark</b> \u2014 never a fabricated living body. A <b>signed receipt</b> of the read is a <b>REAL ECDSA-P256 DSSE</b> envelope in-Space and an honest <b>UNSIGNED-LOCAL</b> envelope otherwise \u2014 never a fabricated signature.<br><br>&bull; Brain pulse hub \u2014 Dev-1, <code>feat/brain-hub</code> (<code>"+EP_PULSE+"</code>)<br>&bull; Brain energy \u2014 Dev-2, <code>feat/brain-energy</code> (<code>"+EP_ENERGY+"</code>)<br>&bull; \u039b = <b>Conjecture 1</b> (lutar-lean; advisory, never green). Nothing here touches the locked-8; trust capped at 0.97, never 100%.";
}

function unmount(){
  _polls.forEach((p)=>{ try{p.stop();}catch(_){} }); _polls=[];
  try{ if(_show) _show.destroy(); }catch(_){} _show=null;
  _disposeOrgans();
  try{ if(_group&&_stage){ _group.traverse((o)=>{ if(o.geometry&&o.geometry.dispose)o.geometry.dispose();
    if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach((m)=>{if(m.dispose)m.dispose();});} }); _stage.scene.remove(_group); } }catch(_){}
  _group=_overlay=null; _brain=_brainGlow=null; _organs=[]; _nerves=[];
  _badge=null; _plain=false; _frameReg=false; _stage=_THREE=_ctx=null;
  S.label="UNAVAILABLE"; S.state="init"; S.pulseOk=false; S.pulseLabel="UNAVAILABLE";
  S.energyOk=false; S.energyLabel="UNAVAILABLE"; S.organs=[];
  S.summary={organs_total:0,organs_lit:0,live:0,modeled:0,unavailable:0};
  S.signMode=null; S.signed=false;
}

export default { id: ID, title: TITLE, endpoints: [EP_PANEL, EP_PULSE, EP_ENERGY], mount, unmount };
