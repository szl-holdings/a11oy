// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/sovereign.js — SOVEREIGN LOCAL MODEL (Wave M, Dev 4).
// An honest 3D status panel for the founder's LOCAL sovereign model — the
// llama3-based, Doctrine-v11-wrapped model on the Tower (OMEN, RTX 4060 Ti) served by
// Ollama at SZL_LOCAL_LLM_URL. A central SOVEREIGN CORE glows proof-teal + pulses when
// the node answered live THIS request (LIVE-SOVEREIGN), and goes dim grey when it did
// NOT (UNAVAILABLE — Tower down / off-Tower / unset). Two orbiting nodes show Stage A
// (system-prompt derivative, NOW) vs Stage B (real LoRA fine-tune, LATER — Dev 3). A
// seal ring shows the SIGNED-RECEIPT of the check (REAL DSSE in-Space, honest
// UNSIGNED-LOCAL otherwise). The HUD shows reachability, the doctrine self-test answer
// ("State your doctrine in one line" → the model's REAL line when reachable, else an
// honest UNAVAILABLE), and the receipt state.
//
// HONESTY: the Tower is NOT reachable from CI/cloud, so off-Tower this MUST read
//   UNAVAILABLE — never a fabricated "reachable" or a fabricated doctrine line
//   (Zero-Bandaid Law). Λ = Conjecture 1 (advisory, grey, never green), trust ceiling
//   0.97 (never 1.0). Nothing here touches the locked-8. ZERO PURPLE. Vendored three
//   via ctx.THREE. Backend: GET /api/a11oy/v1/frontier/sovereign (this Dev's panel),
//   which reads Dev-1's GET /api/a11oy/v1/llm/sovereign/health when present.
// Surface export shape mirrors evalarena.js / zkinfer.js exactly:
//   export default { id, title, endpoints, mount, unmount }

import { createShowcase } from "./_showcase.js";

const ID    = "sovereign";
const TITLE = "Sovereign Local Model";

const EP_PANEL  = "/api/a11oy/v1/frontier/sovereign";
const EP_HEALTH = "/api/a11oy/v1/llm/sovereign/health"; // Dev-1 (read when merged)

// data-viz hues — purple BANNED
const C_LIVE   = 0x3af4c8; // proof-teal (core reachable / LIVE-SOVEREIGN)
const C_DOWN   = 0x5a6570; // grey (UNAVAILABLE)
const C_STAGEA = 0x8fdcff; // light blue (Stage A — system-prompt derivative NOW)
const C_STAGEB = 0xe8c074; // gold (Stage B — real LoRA, roadmap)
const C_SEAL   = 0x8a6bff; // blue-violet (receipt seal ring — advisory, NOT purple/green)
const C_EDGE   = 0x1b3a44;

const CORE_R = 0.9, ORBIT_R = 3.2, SEAL_R = 2.15;

let _stage=null,_THREE=null,_ctx=null,_group=null,_overlay=null;
let _frameReg=false,_polls=[],_badge=null,_plain=false,_t0=0,_show=null;
let _core=null,_coreGlow=null,_seal=null,_nodeA=null,_nodeB=null;

const S = {
  label:"UNAVAILABLE", state:"init",
  reachable:false, baseUrl:null, envPresent:null, apiStyle:null,
  modelTag:"llama3-szl-finetuned-q4", modelServed:null, modelsLive:[],
  via:null, dependency:null, reachNote:null,
  selftestLabel:"UNAVAILABLE", selftestAnswer:null, selftestPrompt:"State your doctrine in one line",
  activeStage:"UNKNOWN", stageNote:null,
  signMode:null, signed:null, signerFp:null,
};

function _clamp01(x){ return x<0?0:(x>1?1:x); }

function mount(ctx){
  _ctx=ctx; _stage=ctx.stage; _THREE=ctx.THREE;
  _group=new _THREE.Group(); _stage.scene.add(_group);
  try{ _stage.camera.position.set(0,4.5,12); }catch(_){}
  try{ if(_stage.controls&&_stage.controls.target){ _stage.controls.target.set(0,0.4,0); _stage.controls.update(); } }catch(_){}
  try{ _stage.setBloom&&_stage.setBloom(true); }catch(_){}
  _t0=(typeof performance!=="undefined"?performance.now():Date.now());
  _badge=ctx.live.createBadge();
  _buildOverlay(ctx);
  _buildScaffold();

  // GET the panel — the CORE poll. It self-probes reachability + runs the doctrine
  // self-test + signs a receipt server-side. Degrades to honest UNAVAILABLE when down.
  _polls.push(ctx.live.poll(EP_PANEL, 10000, _onPanel, {
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
  const sov=j.sovereign||{};
  S.reachable=(sov.reachable===true);
  S.baseUrl=sov.base_url||null;
  S.envPresent=(sov.env_present===true);
  S.apiStyle=sov.api_style||null;
  S.modelServed=sov.model||null;
  S.modelsLive=Array.isArray(sov.models_live)?sov.models_live:[];
  S.via=sov.via||null;
  S.dependency=sov.dependency||null;
  S.reachNote=sov.note||null;
  S.modelTag=j.model_tag||S.modelTag;

  const st=j.doctrine_selftest||{};
  S.selftestLabel=String(st.label||"UNAVAILABLE").toUpperCase();
  S.selftestAnswer=(typeof st.answer==="string"&&st.answer.trim())?st.answer.trim():null;
  S.selftestPrompt=st.prompt||S.selftestPrompt;

  const stg=j.stage||{};
  S.activeStage=String(stg.active_stage||"UNKNOWN");
  S.stageNote=stg.active_note||null;

  const sr=j.signed_receipt||{};
  S.signMode=sr.sign_mode||null;
  S.signed=(sr.signed===true);
  S.signerFp=sr.signer_fingerprint||null;

  _paintScene();
  _paintOverlay();
}

function _buildScaffold(){
  // Sovereign core sphere (teal when live, grey when UNAVAILABLE).
  const cg=new _THREE.SphereGeometry(CORE_R,36,36);
  const cm=new _THREE.MeshStandardMaterial({ color:C_DOWN,emissive:C_DOWN,emissiveIntensity:0.25,metalness:0.15,roughness:0.4 });
  _core=new _THREE.Mesh(cg,cm); _core.userData={role:"sovereign-core"}; _group.add(_core);
  const gg=new _THREE.SphereGeometry(CORE_R*1.35,24,24);
  const gm=new _THREE.MeshBasicMaterial({ color:C_DOWN,transparent:true,opacity:0.08,blending:_THREE.AdditiveBlending,depthWrite:false });
  _coreGlow=new _THREE.Mesh(gg,gm); _group.add(_coreGlow);

  // Receipt seal ring (blue-violet, advisory — brightens when the receipt is signed).
  const sg=new _THREE.TorusGeometry(SEAL_R,0.045,18,120);
  const sm=new _THREE.MeshStandardMaterial({ color:C_SEAL,emissive:C_SEAL,emissiveIntensity:0.4,metalness:0.2,roughness:0.35,transparent:true,opacity:0.9 });
  _seal=new _THREE.Mesh(sg,sm); _seal.rotation.x=Math.PI/2; _seal.userData={role:"receipt-seal"}; _group.add(_seal);

  // Stage A + Stage B orbit nodes.
  _nodeA=_mkNode(C_STAGEA); _nodeA.userData={role:"stage-a"}; _group.add(_nodeA);
  _nodeB=_mkNode(C_STAGEB); _nodeB.userData={role:"stage-b"}; _group.add(_nodeB);
}

function _mkNode(col){
  const g=new _THREE.SphereGeometry(0.24,18,18);
  const m=new _THREE.MeshStandardMaterial({ color:col,emissive:col,emissiveIntensity:0.3,metalness:0.1,roughness:0.5,transparent:true,opacity:0.9 });
  return new _THREE.Mesh(g,m);
}

function _paintScene(){
  const live=S.reachable;
  const col=live?C_LIVE:C_DOWN;
  if(_core&&_core.material){ _core.material.color.setHex(col); _core.material.emissive.setHex(col);
    _core.material.emissiveIntensity=live?0.55:0.2; }
  if(_coreGlow&&_coreGlow.material){ _coreGlow.material.color.setHex(col); _coreGlow.material.opacity=live?0.16:0.06; }
  // Stage A active when it's the derivative running now; Stage B is roadmap (dim unless its tag is live).
  const aActive=(S.activeStage==="STAGE_A");
  const bActive=(S.activeStage==="STAGE_B_TAG_PRESENT");
  if(_nodeA&&_nodeA.material){ _nodeA.material.emissiveIntensity=aActive?0.7:0.22; _nodeA.material.opacity=aActive?1.0:0.55; }
  if(_nodeB&&_nodeB.material){ _nodeB.material.emissiveIntensity=bActive?0.7:0.22; _nodeB.material.opacity=bActive?1.0:0.4; }
  // Seal ring: brighter + fuller when a REAL DSSE signature is present.
  const signed=(S.signed===true);
  if(_seal&&_seal.material){ _seal.material.emissiveIntensity=signed?0.75:0.35; _seal.material.opacity=signed?0.95:0.6; }
}

function _animate(){
  if(!_group)return;
  const now=(typeof performance!=="undefined"?performance.now():Date.now()); const t=(now-_t0)/1000;
  const live=S.reachable;
  if(_core&&_core.material){ _core.material.emissiveIntensity=(live?0.45:0.18)+(live?0.2:0.05)*Math.abs(Math.sin(t*1.6)); }
  if(_coreGlow){ const s=1.0+(live?0.06:0.02)*Math.sin(t*1.6); _coreGlow.scale.setScalar(s); }
  // Stage nodes orbit the core.
  if(_nodeA){ _nodeA.position.set(Math.cos(t*0.5)*ORBIT_R, 0.3*Math.sin(t*0.9), Math.sin(t*0.5)*ORBIT_R); }
  if(_nodeB){ const a=t*0.5+Math.PI; _nodeB.position.set(Math.cos(a)*ORBIT_R, 0.3*Math.sin(t*0.9+Math.PI), Math.sin(a)*ORBIT_R); }
  if(_seal){ _seal.rotation.z=t*0.16; }
  _group.rotation.y=t*0.04;
}

function _buildOverlay(ctx){
  _show=createShowcase(ctx,{
    id:ID, title:TITLE, accent:"#3af4c8", badge:_badge,
    chips:[{label:"UNAVAILABLE", name:"label"}],
  });
  _overlay=document.createElement("div");
  _overlay.style.cssText="font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;";
  _overlay.innerHTML=
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">Operator status of the founder\'s <b>LOCAL sovereign model</b> (Ollama on the Tower, Doctrine-v11 system prompt over base llama3.1:8b). The Tower is <b>not reachable from CI/cloud</b>, so off-Tower this reads <b>UNAVAILABLE</b> — never a fabricated live status or doctrine line.</div>'+
    _row("Reachable","sv-reach")+_row("Model tag","sv-tag")+
    _row("Served (live)","sv-served")+_row("Endpoint base","sv-base")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Doctrine self-test — “State your doctrine in one line”</div>'+
    _row("Result","sv-stlabel")+
    '<div id="sv-answer" style="margin-top:3px;padding:6px 8px;background:#0b1a20;border:1px solid #1b3a44;border-radius:6px;color:#eaf6f9;font-size:11px;min-height:16px">—</div>'+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    _row("Active stage","sv-stage")+_row("Signed receipt","sv-sign")+
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">'+
      _leg(C_LIVE,"LIVE-SOVEREIGN")+_leg(C_DOWN,"UNAVAILABLE")+
      _leg(C_STAGEA,"Stage A (now)")+_leg(C_STAGEB,"Stage B (roadmap)")+_leg(C_SEAL,"receipt seal")+
    '</div>'+
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button id="sv-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>'+
      '<button id="sv-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Sources &amp; caveats</button>'+
    '</div>'+
    '<div id="sv-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>'+
    '<div id="sv-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  _show.body.appendChild(_overlay);
  const pb=_overlay.querySelector("#sv-plain"); if(pb) pb.addEventListener("click",()=>{_plain=!_plain;_applyPlain();});
  const ib=_overlay.querySelector("#sv-info");
  if(ib) ib.addEventListener("click",()=>{ const box=_overlay.querySelector("#sv-infobox");
    if(box) box.style.display=box.style.display==="none"?"block":"none";
    if(box&&box.innerHTML==="") box.innerHTML=_infoHTML(); });
}

function _row(k,id){ return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px"><span style="color:#8fb3bd">'+k+'</span><span id="'+id+'" style="color:#eaf6f9;font-variant-numeric:tabular-nums;text-align:right">—</span></div>'; }
function _leg(hex,txt){ const c="#"+hex.toString(16).padStart(6,"0"); return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';margin-right:4px;vertical-align:middle"></span>'+txt+'</span>'; }
function _set(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }

function _stageLabel(s){
  if(s==="STAGE_A") return "A · system-prompt derivative (now)";
  if(s==="STAGE_B_TAG_PRESENT") return "B-tag present (finetuned tag served)";
  return "UNKNOWN (node unreachable)";
}

function _paintOverlay(){
  if(!_overlay)return;
  const missing=(S.state==="missing"||S.state==="error");
  if(_show) _show.setChip("label",S.label||"UNAVAILABLE");
  if(missing){
    ["sv-reach","sv-tag","sv-served","sv-base","sv-stlabel","sv-stage","sv-sign"].forEach((id)=>_set(id,"NO-LIVE-DATA"));
    _set2("sv-answer","backend offline — NO-LIVE-DATA (honest, never fabricated).");
    if(_plain)_applyPlain(); return;
  }
  _set("sv-reach",S.reachable?"YES · LIVE-SOVEREIGN":"NO · UNAVAILABLE");
  _set("sv-tag",S.modelTag||"—");
  _set("sv-served",(S.reachable&&S.modelServed)?S.modelServed:"— (node unreachable)");
  _set("sv-base",S.baseUrl?String(S.baseUrl):(S.envPresent===false?"SZL_LOCAL_LLM_URL unset":"—"));
  _set("sv-stlabel",S.selftestLabel||"UNAVAILABLE");
  _set2("sv-answer", S.selftestAnswer
    ? S.selftestAnswer
    : "UNAVAILABLE — the Tower did not answer this request; no doctrine line fabricated.");
  _set("sv-stage",_stageLabel(S.activeStage));
  _set("sv-sign",(S.signMode||"—")+(S.signed?" ✓ (REAL DSSE)":(S.signMode==="UNSIGNED-LOCAL"?" (unsigned, honest)":"")));
  if(_plain)_applyPlain();
}

function _set2(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }

function _applyPlain(){
  const box=_overlay&&_overlay.querySelector("#sv-plainbox"); if(!box)return;
  box.style.display=_plain?"block":"none";
  if(_plain) box.innerHTML="This tab is the <b>dashboard for the founder\'s own AI model</b> — the one running on the home Tower (an OMEN PC with an RTX 4060&nbsp;Ti) instead of on someone else\'s cloud. It answers three plain questions honestly. <b>Is it awake?</b> The glowing core is <b>teal when the model is reachable right now</b> and <b>grey when it isn\'t</b>. Because the Tower can\'t be reached from the cloud where this site runs, it will usually read <b>UNAVAILABLE here — and we say so rather than pretend</b>. <b>Does it know who it is?</b> We ask it to \u201cstate its doctrine in one line\u201d and show its <b>real answer when it\u2019s reachable</b>; otherwise we show <b>UNAVAILABLE</b> and invent nothing. <b>Which version is it?</b> <b>Stage&nbsp;A</b> is the quick version (the base model wrapped in a doctrine instruction, running now); <b>Stage&nbsp;B</b> is the real trained version (a LoRA fine-tune, coming later) that will slot in under the same name. Finally we <b>sign a receipt of the check</b> so the result is tamper-evident even when the answer is \u201cunavailable.\u201d Trust is advisory (\u039b, capped at 0.97, never a green stamp), and nothing here touches the locked-8.";
}

function _infoHTML(){
  return "<b>What is real vs UNAVAILABLE.</b> This panel calls <code>GET /api/a11oy/v1/frontier/sovereign</code>, which probes the local node <b>server-side</b> (via Dev-1\u2019s <code>szl_llm_registry.sovereign_probe</code>, the same code that backs <code>GET /api/a11oy/v1/llm/sovereign/health</code>; if Dev-1\u2019s PR isn\u2019t merged it probes <code>SZL_LOCAL_LLM_URL</code> directly and records the dependency). <b>Reachable = true only if the node returned a real 2xx JSON THIS request</b> \u2014 never fabricated. The <b>doctrine self-test</b> runs a real generation only when reachable; otherwise it is an honest <b>UNAVAILABLE</b> with the intended prompt + backend id recorded (no invented line \u2014 Zero-Bandaid Law). The <b>signed receipt</b> is a <b>REAL ECDSA-P256 DSSE</b> envelope in-Space (SZL cosign key) and an honest <b>UNSIGNED-LOCAL</b> envelope otherwise \u2014 never a fabricated signature.<br><br><b>Stage A vs Stage B.</b> Stage A = a Doctrine-v11 <b>system-prompt derivative</b> over base <b>llama3.1:8b</b> (behavior from the prompt, no weight change). Stage B = a real <b>4-bit QLoRA fine-tune</b> exported to GGUF + an Ollama <b>ADAPTER</b>, replacing Stage A under the <b>same tag <code>llama3-szl-finetuned-q4</code></b> (Dev&nbsp;3 \u2014 <code>feat/stage-b-lora</code>).<br><br>&bull; Ollama (local OpenAI-compatible serving) \u2014 <a href=\"https://ollama.com\" style=\"color:#3af4c8\">ollama.com</a><br>&bull; Sovereign backend registry (<code>szl-sovereign-local</code>) \u2014 Dev&nbsp;1, <code>feat/sovereign-backend</code><br>&bull; Stage-B LoRA pipeline \u2014 Dev&nbsp;3, <code>feat/stage-b-lora</code><br>&bull; \u039b trust gate = Conjecture&nbsp;1 (lutar-lean; advisory, never green). Nothing here touches the locked-8; trust capped at 0.97, never 100%.";
}

function unmount(){
  _polls.forEach((p)=>{ try{p.stop();}catch(_){} }); _polls=[];
  try{ if(_show) _show.destroy(); }catch(_){} _show=null;
  try{ if(_group&&_stage){ _group.traverse((o)=>{ if(o.geometry&&o.geometry.dispose)o.geometry.dispose();
    if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach((m)=>{if(m.dispose)m.dispose();});} }); _stage.scene.remove(_group); } }catch(_){}
  _group=_overlay=null; _core=_coreGlow=_seal=_nodeA=_nodeB=null;
  _badge=null; _plain=false; _frameReg=false; _stage=_THREE=_ctx=null;
  S.label="UNAVAILABLE"; S.state="init"; S.reachable=false; S.selftestAnswer=null;
  S.selftestLabel="UNAVAILABLE"; S.activeStage="UNKNOWN"; S.signMode=null; S.signed=null;
  S.modelServed=null; S.modelsLive=[]; S.baseUrl=null;
}

export default { id: ID, title: TITLE, endpoints: [EP_PANEL, EP_HEALTH], mount, unmount };
