// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/braincommand.js — BRAIN COMMAND (Wave O, Dev 5). The founder's
// "Brain powering the ecosystem" dashboard: one honest command view of the live
// ecosystem PULSE — what the Brain has HARVESTED (knowledge), what it has HARNESSED
// (energy), how many organs/surfaces it lights, the Λ advisory — plus a subscribe/
// budget view ("what is the Brain feeding this surface right now?") and the signed
// receipt of the snapshot.
//
// SCENE: a central BRAIN CORE glows by the harnessed-energy label (teal when real
// MEASURED joules are in the ledger, amber when MODELED, grey when UNAVAILABLE) and
// PULSES. A ring of ORGAN nodes = the surfaces the Brain lights (count from the live
// pulse). A KNOWLEDGE HALO scales with the harvested distinct-artifact count. A
// blue-violet RECEIPT SEAL ring brightens when the snapshot carries a REAL DSSE
// signature. HUD shows every number with its honest label and a plain-language mode.
//
// HONESTY (Doctrine v11, verbatim — never upgraded):
//   * Reads GET /api/a11oy/v1/brain/command (this Dev's backend), which PREFERS
//     Dev-1's central hub pulse (/brain/pulse) and falls back to an HONEST locally-
//     composed pulse (pulse_ok:false) when #brain-hub is not merged — never a
//     fabricated joule. When the backend is offline the HUD reads NO-LIVE-DATA.
//   * Honest labels only: LIVE / MEASURED / MODELED / UNAVAILABLE / CONJECTURE.
//   * Λ = Conjecture 1 — advisory, GREY, NEVER green/theorem/proven. Trust ≤ 0.97.
//   * locked-proven = EXACTLY 8; the Brain harvest adds nothing to it.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8 ·
//     amber 0xe8c074 · greys. PURPLE BANNED. 0 runtime CDN (three via ctx.THREE).
// Surface export shape mirrors sovereign.js exactly:
//   export default { id, title, endpoints, mount, unmount }

import { createShowcase } from "./_showcase.js";

const ID    = "braincommand";
const TITLE = "Brain Command — powering the ecosystem";

const EP_CMD   = "/api/a11oy/v1/brain/command";
const EP_SUBS  = "/api/a11oy/v1/brain/command/subscribe/"; // + surface_id
const EP_PULSE = "/api/a11oy/v1/brain/pulse";              // Dev-1 (read via backend when merged)

// data-viz hues — purple BANNED
const C_MEASURED = 0x3af4c8; // proof-teal (real MEASURED joules harnessed)
const C_MODELED  = 0xe8c074; // amber (MODELED energy — dry-run projection)
const C_DOWN     = 0x5a6570; // grey (UNAVAILABLE)
const C_ORGAN    = 0x5b8dee; // lattice-blue (lit organ/surface)
const C_KNOW     = 0x8fdcff; // light blue (knowledge halo)
const C_SEAL     = 0x8a6bff; // blue-violet (receipt seal — advisory, NOT purple/green)

const CORE_R = 1.0, ORGAN_RING_R = 3.4, KNOW_R = 1.7, SEAL_R = 2.35;
const MAX_ORGAN_MESHES = 48; // cap rendered organ dots (perf; count shown honestly regardless)

let _stage=null,_THREE=null,_ctx=null,_group=null,_overlay=null;
let _frameReg=false,_polls=[],_badge=null,_plain=false,_t0=0,_show=null;
let _core=null,_coreGlow=null,_know=null,_seal=null,_organs=[];

const S = {
  label:"UNAVAILABLE", state:"init",
  source:null, pulseOk:false,
  energyLabel:"UNAVAILABLE", joules:null, kwh:null, tokens:null, jobs:null,
  knowLabel:"UNAVAILABLE", distinct:null, nodes:null, links:null,
  surfaces:null, surfacesLabel:"UNAVAILABLE",
  lambda:"Conjecture 1",
  signMode:null, signed:null,
  subSurface:"brain", subState:null,
};

function _clamp01(x){ return x<0?0:(x>1?1:x); }

function mount(ctx){
  _ctx=ctx; _stage=ctx.stage; _THREE=ctx.THREE;
  _group=new _THREE.Group(); _stage.scene.add(_group);
  try{ _stage.camera.position.set(0,4.5,12); }catch(_){}
  try{ if(_stage.controls&&_stage.controls.target){ _stage.controls.target.set(0,0.3,0); _stage.controls.update(); } }catch(_){}
  try{ _stage.setBloom&&_stage.setBloom(true); }catch(_){}
  _t0=(typeof performance!=="undefined"?performance.now():Date.now());
  _badge=ctx.live.createBadge();
  _buildOverlay(ctx);
  _buildScaffold();

  // GET the command rollup — the CORE poll. Server-side it prefers Dev-1's hub pulse
  // and falls back honestly (pulse_ok:false). Degrades to NO-LIVE-DATA when offline.
  _polls.push(ctx.live.poll(EP_CMD, 10000, _onCmd, {
    badge:_badge,
    onState:(m)=>{ S.state=m.state; _paintOverlay(); },
  }));

  if(!_frameReg&&_stage.onFrame){ _stage.onFrame(_animate); _frameReg=true; }
  _paintOverlay();
  return { id:ID, started:true };
}

function _num(x){ return (typeof x==="number"&&isFinite(x))?x:null; }
function _up(s){ return String(s==null?"UNAVAILABLE":s).toUpperCase(); }

function _onCmd(j){
  if(!j){ S.state="error"; _paintOverlay(); return; }
  S.source=j.source||null;
  S.pulseOk=(j.pulse_ok===true);
  const e=j.energy||{};
  S.energyLabel=_up(e.label);
  S.joules=_num(e.joules_measured_billable);
  S.kwh=_num(e.kwh_total);
  S.tokens=_num(e.tokens_total);
  S.jobs=_num(e.jobs);
  const k=j.knowledge||{};
  S.knowLabel=_up(k.label);
  S.distinct=_num(k.distinct_artifacts);
  S.nodes=_num(k.node_count);
  S.links=_num(k.link_count);
  const s=j.surfaces_lit||{};
  S.surfaces=_num(s.count);
  S.surfacesLabel=_up(s.label);
  const lam=j.lambda||{};
  S.lambda=lam.value||"Conjecture 1";
  const r=j.receipt||{};
  S.signed=(r.signed===true);
  S.signMode=S.signed?"REAL DSSE":(r.signatures&&r.signatures.length===0?"UNSIGNED-LOCAL":null);
  S.label=S.energyLabel;

  _rebuildOrgans();
  _paintScene();
  _paintOverlay();
}

function _buildScaffold(){
  // Brain core sphere.
  const cg=new _THREE.SphereGeometry(CORE_R,40,40);
  const cm=new _THREE.MeshStandardMaterial({ color:C_DOWN,emissive:C_DOWN,emissiveIntensity:0.25,metalness:0.15,roughness:0.4 });
  _core=new _THREE.Mesh(cg,cm); _core.userData={role:"brain-core"}; _group.add(_core);
  const gg=new _THREE.SphereGeometry(CORE_R*1.4,24,24);
  const gm=new _THREE.MeshBasicMaterial({ color:C_DOWN,transparent:true,opacity:0.08,blending:_THREE.AdditiveBlending,depthWrite:false });
  _coreGlow=new _THREE.Mesh(gg,gm); _group.add(_coreGlow);

  // Knowledge halo (light-blue wireframe torus; scales with distinct-artifact count).
  const kg=new _THREE.TorusGeometry(KNOW_R,0.03,16,90);
  const km=new _THREE.MeshBasicMaterial({ color:C_KNOW,transparent:true,opacity:0.5,wireframe:true });
  _know=new _THREE.Mesh(kg,km); _know.rotation.x=Math.PI*0.5; _know.userData={role:"knowledge-halo"}; _group.add(_know);

  // Receipt seal ring (blue-violet, advisory — brightens when the snapshot is signed).
  const sg=new _THREE.TorusGeometry(SEAL_R,0.045,18,120);
  const sm=new _THREE.MeshStandardMaterial({ color:C_SEAL,emissive:C_SEAL,emissiveIntensity:0.4,metalness:0.2,roughness:0.35,transparent:true,opacity:0.85 });
  _seal=new _THREE.Mesh(sg,sm); _seal.rotation.x=Math.PI/2; _seal.userData={role:"receipt-seal"}; _group.add(_seal);
}

function _rebuildOrgans(){
  // Ring of organ dots = surfaces the Brain lights. Cap the rendered count for perf;
  // the HUD always shows the true count. Never fabricate organs when UNAVAILABLE.
  _organs.forEach((o)=>{ try{ _group.remove(o); if(o.geometry)o.geometry.dispose(); if(o.material)o.material.dispose(); }catch(_){} });
  _organs=[];
  const n=(S.surfaces!=null)?Math.max(0,Math.min(MAX_ORGAN_MESHES,S.surfaces)):0;
  for(let i=0;i<n;i++){
    const g=new _THREE.SphereGeometry(0.12,12,12);
    const m=new _THREE.MeshStandardMaterial({ color:C_ORGAN,emissive:C_ORGAN,emissiveIntensity:0.4,metalness:0.1,roughness:0.5,transparent:true,opacity:0.9 });
    const o=new _THREE.Mesh(g,m); o.userData={role:"organ",i:i,n:n}; _group.add(o); _organs.push(o);
  }
}

function _energyColor(){
  if(S.energyLabel==="MEASURED"||S.energyLabel==="LIVE") return C_MEASURED;
  if(S.energyLabel==="MODELED") return C_MODELED;
  return C_DOWN;
}

function _paintScene(){
  const col=_energyColor();
  const lit=(S.energyLabel==="MEASURED"||S.energyLabel==="LIVE"||S.energyLabel==="MODELED");
  if(_core&&_core.material){ _core.material.color.setHex(col); _core.material.emissive.setHex(col);
    _core.material.emissiveIntensity=lit?0.55:0.2; }
  if(_coreGlow&&_coreGlow.material){ _coreGlow.material.color.setHex(col); _coreGlow.material.opacity=lit?0.16:0.06; }
  // Knowledge halo scales with distinct-artifact count (log-damped so it stays framed).
  if(_know){ const d=S.distinct||0; const sc=1.0+0.5*_clamp01(Math.log10(1+d)/4); _know.scale.setScalar(sc);
    if(_know.material) _know.material.opacity=(S.knowLabel==="UNAVAILABLE")?0.18:0.55; }
  // Seal ring: brighter when a REAL DSSE signature is present.
  const signed=(S.signed===true);
  if(_seal&&_seal.material){ _seal.material.emissiveIntensity=signed?0.75:0.35; _seal.material.opacity=signed?0.95:0.55; }
  // Organ dots inherit lit-blue; dim if the surface count is UNAVAILABLE.
  const oOpacity=(S.surfacesLabel==="UNAVAILABLE")?0.3:0.9;
  _organs.forEach((o)=>{ if(o.material) o.material.opacity=oOpacity; });
}

function _animate(){
  if(!_group)return;
  const now=(typeof performance!=="undefined"?performance.now():Date.now()); const t=(now-_t0)/1000;
  const lit=(S.energyLabel==="MEASURED"||S.energyLabel==="LIVE"||S.energyLabel==="MODELED");
  // Core pulses (the ecosystem heartbeat) — faster/brighter when energy is real.
  const rate=(S.energyLabel==="MEASURED")?2.0:(S.energyLabel==="MODELED"?1.3:0.8);
  if(_core&&_core.material){ _core.material.emissiveIntensity=(lit?0.45:0.16)+(lit?0.22:0.05)*Math.abs(Math.sin(t*rate)); }
  if(_coreGlow){ const s=1.0+(lit?0.07:0.02)*Math.sin(t*rate); _coreGlow.scale.setScalar(s); }
  if(_know) _know.rotation.z=t*0.12;
  if(_seal) _seal.rotation.z=-t*0.14;
  // Organs orbit the core; each pulses on a phase so it reads as a nervous system.
  const n=_organs.length;
  for(let i=0;i<n;i++){
    const o=_organs[i]; if(!o) continue;
    const a=(i/Math.max(1,n))*Math.PI*2 + t*0.12;
    const y=0.5*Math.sin(a*2.0+t*0.6);
    o.position.set(Math.cos(a)*ORGAN_RING_R, y, Math.sin(a)*ORGAN_RING_R);
    if(o.material) o.material.emissiveIntensity=0.3+0.25*Math.abs(Math.sin(t*rate + i*0.5));
  }
  _group.rotation.y=t*0.03;
}

function _buildOverlay(ctx){
  _show=createShowcase(ctx,{
    id:ID, title:TITLE, accent:"#3af4c8", badge:_badge,
    chips:[{label:"UNAVAILABLE", name:"label"}],
  });
  _overlay=document.createElement("div");
  _overlay.style.cssText="font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;";
  _overlay.innerHTML=
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">The founder\'s <b>Brain powering the ecosystem</b> — one honest command view of the live <b>pulse</b>: what the Brain has <b>harvested</b> (knowledge), <b>harnessed</b> (energy), and how many organs it <b>lights</b>. Reads Dev-1\'s central hub when merged; otherwise an <b>honest local fallback</b> (never a fabricated joule).</div>'+
    _row("Pulse source","bc-source")+_row("Pulse OK","bc-pulseok")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Energy harnessed</div>'+
    _row("Label","bc-elabel")+_row("Joules (measured)","bc-joules")+_row("kWh","bc-kwh")+_row("Jobs · tokens","bc-jobs")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Knowledge harvested</div>'+
    _row("Label","bc-klabel")+_row("Distinct artifacts","bc-distinct")+_row("Graph nodes · links","bc-nodes")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    _row("Organs / surfaces lit","bc-surfaces")+_row("Λ advisory","bc-lambda")+_row("Signed receipt","bc-sign")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Subscribe — what is the Brain feeding a surface?</div>'+
    '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">'+
      '<input id="bc-surfin" value="brain" spellcheck="false" style="font:11px ui-monospace;background:#0b1a20;color:#eaf6f9;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;width:130px">'+
      '<button id="bc-subgo" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Ask the Brain</button>'+
    '</div>'+
    '<div id="bc-subbox" style="display:none;margin-top:7px;padding:6px 8px;background:#0b1a20;border:1px solid #1b3a44;border-radius:6px;color:#eaf6f9;font-size:10.5px;line-height:1.5">—</div>'+
    '<div style="margin-top:9px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">'+
      _leg(C_MEASURED,"MEASURED")+_leg(C_MODELED,"MODELED")+_leg(C_DOWN,"UNAVAILABLE")+
      _leg(C_ORGAN,"organ lit")+_leg(C_KNOW,"knowledge")+_leg(C_SEAL,"receipt seal")+
    '</div>'+
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button id="bc-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>'+
      '<button id="bc-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Sources &amp; caveats</button>'+
    '</div>'+
    '<div id="bc-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>'+
    '<div id="bc-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  _show.body.appendChild(_overlay);

  const pb=_overlay.querySelector("#bc-plain"); if(pb) pb.addEventListener("click",()=>{_plain=!_plain;_applyPlain();});
  const ib=_overlay.querySelector("#bc-info");
  if(ib) ib.addEventListener("click",()=>{ const box=_overlay.querySelector("#bc-infobox");
    if(box) box.style.display=box.style.display==="none"?"block":"none";
    if(box&&box.innerHTML==="") box.innerHTML=_infoHTML(); });
  const go=_overlay.querySelector("#bc-subgo");
  if(go) go.addEventListener("click",_askSubscribe);
  const inp=_overlay.querySelector("#bc-surfin");
  if(inp) inp.addEventListener("keydown",(ev)=>{ if(ev.key==="Enter") _askSubscribe(); });
}

function _askSubscribe(){
  const inp=_overlay&&_overlay.querySelector("#bc-surfin");
  const box=_overlay&&_overlay.querySelector("#bc-subbox");
  if(!box) return;
  const sid=((inp&&inp.value)||"brain").trim().replace(/[^a-zA-Z0-9_.-]/g,"").slice(0,64)||"brain";
  S.subSurface=sid;
  box.style.display="block"; box.textContent="Asking the Brain about “"+sid+"” …";
  const url=EP_SUBS+encodeURIComponent(sid);
  const fetchFn=(_ctx&&_ctx.live&&_ctx.live.fetchJSON)?_ctx.live.fetchJSON:((u)=>fetch(u).then((r)=>r.json()));
  Promise.resolve(fetchFn(url)).then((j)=>{
    if(!j){ box.textContent="UNAVAILABLE — backend offline (honest, nothing fabricated)."; return; }
    const a=j.allocation||{}; const en=a.energy||{}; const kn=a.knowledge||{};
    const known=(a.known_surface===true)?"known surface":"not a registered surface id (still answered honestly)";
    const js=(typeof en.joules_share_modeled==="number")?(en.joules_share_modeled+" J ("+_up(en.label)+")"):("— ("+_up(en.label)+")");
    box.innerHTML="<b>"+sid+"</b> — "+known+"<br>"+
      "Energy budget: "+js+"<br>"+
      "Knowledge: corpus <b>brain</b> ("+_up(kn.label)+"), "+((kn.distinct_artifacts_available!=null)?kn.distinct_artifacts_available+" distinct artifacts available":"UNAVAILABLE")+"<br>"+
      "Source: "+(j.source||"—")+" · receipt: "+((j.receipt&&j.receipt.signed)?"REAL DSSE ✓":"UNSIGNED-LOCAL")+"<br>"+
      '<span style="color:#8fb3bd">'+((a.energy&&a.energy.note)?a.energy.note:"")+'</span>';
  }).catch((e)=>{ box.textContent="UNAVAILABLE — "+(e&&e.message?e.message:"fetch failed")+" (honest)."; });
}

function _row(k,id){ return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px"><span style="color:#8fb3bd">'+k+'</span><span id="'+id+'" style="color:#eaf6f9;font-variant-numeric:tabular-nums;text-align:right">—</span></div>'; }
function _leg(hex,txt){ const c="#"+hex.toString(16).padStart(6,"0"); return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';margin-right:4px;vertical-align:middle"></span>'+txt+'</span>'; }
function _set(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }
function _fmt(x){ return (x==null)?"—":(typeof x==="number"?x.toLocaleString():String(x)); }

function _paintOverlay(){
  if(!_overlay)return;
  const missing=(S.state==="missing"||S.state==="error");
  if(_show) _show.setChip("label",S.label||"UNAVAILABLE");
  if(missing){
    ["bc-source","bc-pulseok","bc-elabel","bc-joules","bc-kwh","bc-jobs","bc-klabel","bc-distinct","bc-nodes","bc-surfaces","bc-lambda","bc-sign"].forEach((id)=>_set(id,"NO-LIVE-DATA"));
    if(_plain)_applyPlain(); return;
  }
  _set("bc-source",(S.source||"—")+(S.source==="local-fallback"?" (hub not merged)":""));
  _set("bc-pulseok",S.pulseOk?"YES · hub live":"NO · local fallback (honest)");
  _set("bc-elabel",S.energyLabel);
  _set("bc-joules",(S.joules!=null)?_fmt(S.joules)+" J":(S.energyLabel==="UNAVAILABLE"?"UNAVAILABLE (no telemetry)":"—"));
  _set("bc-kwh",(S.kwh!=null)?_fmt(S.kwh):"—");
  _set("bc-jobs",_fmt(S.jobs)+" · "+_fmt(S.tokens)+" tok");
  _set("bc-klabel",S.knowLabel);
  _set("bc-distinct",(S.distinct!=null)?_fmt(S.distinct):"UNAVAILABLE");
  _set("bc-nodes",_fmt(S.nodes)+" · "+_fmt(S.links));
  _set("bc-surfaces",(S.surfaces!=null)?_fmt(S.surfaces)+" ("+S.surfacesLabel+")":"UNAVAILABLE");
  _set("bc-lambda","Λ = "+(S.lambda||"Conjecture 1")+" (advisory, never green)");
  _set("bc-sign",(S.signMode||"—")+(S.signed?" ✓":(S.signMode==="UNSIGNED-LOCAL"?" (unsigned, honest)":"")));
  if(_plain)_applyPlain();
}

function _applyPlain(){
  const box=_overlay&&_overlay.querySelector("#bc-plainbox"); if(!box)return;
  box.style.display=_plain?"block":"none";
  if(_plain) box.innerHTML="This tab is the founder\'s <b>mission-control view of the Brain</b> — the idea that one central Brain both <b>learns for the whole company and powers it</b>. It answers three plain questions honestly. <b>How much has it learned?</b> The light-blue halo grows with the number of <b>distinct things harvested</b> (papers, repos, formulas), and we show the honest count — not an inflated total. <b>How much energy is it running on?</b> The core glows <b>teal when we have real measured energy</b> from the ledger, <b>amber when the number is only a projection</b>, and <b>grey when we have no reading</b> — in which case we say <b>UNAVAILABLE</b> instead of inventing joules. <b>How much does it light up?</b> The orbiting dots are the <b>surfaces the Brain powers</b>, and the number is shown exactly. You can also type any surface name and hit <b>“Ask the Brain”</b> to see the honest energy/knowledge <b>budget</b> it feeds that surface. Every snapshot gets a <b>signed receipt</b> so it\'s tamper-evident. Trust is advisory (Λ = Conjecture&nbsp;1, capped at 0.97, never a green stamp), and nothing here touches the locked-8. When our central hub isn\'t wired in yet, the view says so (<b>“local fallback”</b>) rather than pretending.";
}

function _infoHTML(){
  return "<b>What is real vs UNAVAILABLE.</b> This panel calls <code>GET /api/a11oy/v1/brain/command</code> (this Dev\\u2019s backend). Server-side it PREFERS Dev-1\\u2019s central hub pulse <code>GET /api/a11oy/v1/brain/pulse</code> (read in-process); if <code>szl_brain_hub</code> isn\\u2019t merged it composes an <b>honest local fallback</b> from the shipped organs \\u2014 <code>a11oy_brain_graph</code> (knowledge), <code>szl_energy_ledger</code> (energy), <code>szl3d_holographic.SURFACES</code> (organs lit) \\u2014 and sets <b><code>pulse_ok:false</code></b> so you know the hub isn\\u2019t the source of truth yet.<br><br><b>Energy labels.</b> <b>MEASURED</b> = real NVML-attested billable joules in the ledger chain; <b>MODELED</b> = a dry-run projection (jobs exist but no measured joules); <b>UNAVAILABLE</b> = no telemetry \\u2014 <b>joules are never fabricated</b>.<br><br><b>Knowledge.</b> <code>distinct_artifacts</code> is the honest headline (excludes arXiv co-author person nodes); the raw <code>node_count</code> is never presented as all distinct work.<br><br><b>Subscribe / budget.</b> \\u201cAsk the Brain\\u201d calls <code>GET /api/a11oy/v1/brain/command/subscribe/{surface_id}</code>. It delegates to the hub\\u2019s allocation when merged; otherwise it returns a <b>MODELED equal-share</b> of the harnessed-energy pool over the lit surfaces \\u2014 a transparent function, <b>not a live per-organ meter</b>.<br><br><b>Receipt.</b> Each snapshot is a <b>REAL ECDSA-P256 DSSE</b> envelope in-Space (SZL cosign key) and an honest <b>UNSIGNED-LOCAL</b> envelope otherwise \\u2014 never a fabricated signature.<br><br>&bull; Central hub pulse \\u2014 Dev&nbsp;1, <code>feat/brain-hub</code> &nbsp;&bull; Energy harness \\u2014 Dev&nbsp;2, <code>feat/brain-energy</code> &nbsp;&bull; Living body \\u2014 Dev&nbsp;3, <code>feat/brain-body</code> &nbsp;&bull; Brain-fed flywheel \\u2014 Dev&nbsp;4, <code>feat/brain-feeds-flywheel</code>.<br>&bull; \\u039b trust gate = Conjecture&nbsp;1 (lutar-lean; advisory, never green). Nothing here touches the locked-8; trust capped at 0.97, never 100%.";
}

function unmount(){
  _polls.forEach((p)=>{ try{p.stop();}catch(_){} }); _polls=[];
  try{ if(_show) _show.destroy(); }catch(_){} _show=null;
  try{ if(_group&&_stage){ _group.traverse((o)=>{ if(o.geometry&&o.geometry.dispose)o.geometry.dispose();
    if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach((m)=>{if(m.dispose)m.dispose();});} }); _stage.scene.remove(_group); } }catch(_){}
  _group=_overlay=null; _core=_coreGlow=_know=_seal=null; _organs=[];
  _badge=null; _plain=false; _frameReg=false; _stage=_THREE=_ctx=null;
  S.label="UNAVAILABLE"; S.state="init"; S.source=null; S.pulseOk=false;
  S.energyLabel="UNAVAILABLE"; S.joules=null; S.kwh=null; S.tokens=null; S.jobs=null;
  S.knowLabel="UNAVAILABLE"; S.distinct=null; S.nodes=null; S.links=null;
  S.surfaces=null; S.surfacesLabel="UNAVAILABLE"; S.signMode=null; S.signed=null;
}

export default { id: ID, title: TITLE, endpoints: [EP_CMD, EP_SUBS, EP_PULSE], mount, unmount };
