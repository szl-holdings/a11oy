// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/loopforge.js — LOOP FORGE (SZL, Wave 25, the 66th surface).
// A MODELED 3D rendering of the KERNEL-GATED AGENTIC LOOP fused with an honest,
// J-lens-analogue WORKSPACE READOUT of the loop's own pre-commit state.
// See DEV3_REPORT.md for the full write-up. ZERO PURPLE. Vendored three via ctx.THREE.

import { createShowcase } from "./_showcase.js";

const ID    = "loopforge";
const TITLE = "Loop Forge";

const EP_RUN       = "/api/a11oy/v1/loopforge/run";
const EP_ARCHIVE   = "/api/a11oy/v1/loopforge/archive";
const EP_WORKSPACE = "/api/a11oy/v1/loopforge/workspace";
const EP_HORIZON   = "/api/a11oy/v1/loopforge/horizon";
const EP_METRICS   = "/api/a11oy/v1/loopforge/metrics";

const C_HUB = 0x3af4c8, C_ACCEPT = 0xe8c074, C_PROPOSE = 0x5b8dee, C_REJECT = 0x5a6570,
      C_TOKEN = 0x8fb3bd, C_RING_OK = 0x3af4c8, C_RING_NO = 0x42505d,
      C_FLAG = 0xd98a3a, C_DANGER = 0xff6b6b, C_EDGE = 0x1b3a44, C_BLACK = 0x000000;

const FLAG_CLASSES = {
  error:{color:C_DANGER,label:"ERROR (unflagged bug)"}, injection:{color:C_DANGER,label:"injection (prompt injection)"},
  fake:{color:C_DANGER,label:"fake / secretly (fabrication)"}, manipulation:{color:C_FLAG,label:"manipulation / realistic"},
  fraud:{color:C_DANGER,label:"fraud / sabotage organism"}, drift:{color:C_FLAG,label:"drift (workspace drift)"},
};
function _flagClass(k){ if(k==null) return {color:C_FLAG,label:"flag"}; const s=String(k).toLowerCase();
  for(const key of Object.keys(FLAG_CLASSES)) if(s.indexOf(key)>=0) return FLAG_CLASSES[key]; return {color:C_FLAG,label:String(k)}; }

const HUB_R=0.6, RING_R=3.0, BRANCH_IN=0.9, ARCHIVE_R=4.3, TOKEN_R=2.0, FLAG_LANE_Y=2.7;

let _stage=null,_THREE=null,_ctx=null,_group=null,_overlay=null;
let _frameReg=false,_polls=[],_badge=null,_plain=false,_show=null;
let _hub=null,_ring=null,_ringGlow=null,_branchGroup=null,_tokenGroup=null,_flagGroup=null;
let _branchMeshes=[],_tokenMeshes=[],_flagMeshes=[],_t0=0;

const S={ label:null,state:"init",branches:[],accepted:null,rejected:null,pending:null,
  recursionDepth:null,depthCap:null,diffCap:null,tokens:[],flags:[],horizon:[],horizonNow:null,
  acceptRate:null,writerNeJudge:null,kernelOutsideLoop:null,conjGreen:null,provCoverage:null };

function _hash(str){ let h=2166136261>>>0; for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619)>>>0;} return h; }
function _clamp01(x){ return x<0?0:(x>1?1:x); }

function mount(ctx){
  _ctx=ctx;_stage=ctx.stage;_THREE=ctx.THREE;
  _group=new _THREE.Group();_stage.scene.add(_group);
  _t0=(typeof performance!=="undefined"?performance.now():Date.now());
  _badge=ctx.live.createBadge();
  _buildOverlay(ctx);_buildScaffold();
  _polls.push(ctx.live.poll(EP_RUN,6000,_onRun,{ badge:_badge, onState:(m)=>{S.state=m.state;_paintOverlay();},
    fetchInit:{ method:"POST", headers:{"accept":"application/json","content-type":"application/json"}, body:"{}" } }));
  _polls.push(ctx.live.poll(EP_ARCHIVE,7000,_onArchive,{ onState:(m)=>{S.state=m.state;_paintOverlay();} }));
  _polls.push(ctx.live.poll(EP_WORKSPACE,5000,_onWorkspace,{ onState:(m)=>{S.state=m.state;_paintOverlay();} }));
  _polls.push(ctx.live.poll(EP_HORIZON,8000,_onHorizon,{}));
  _polls.push(ctx.live.poll(EP_METRICS,8000,_onMetrics,{}));
  if(!_frameReg&&_stage.onFrame){ _stage.onFrame(_animate); _frameReg=true; }
  _paintOverlay();
}
function _readLabel(j){ const lbl=(j&&j.label!=null)?j.label:((j&&j.payload&&j.payload.label!=null)?j.payload.label:"MODELED"); return String(lbl).toUpperCase(); }

function _onRun(j){
  if(!j){S.state="error";_paintOverlay();return;}
  const p=j.payload||j; S.label=_readLabel(j);
  const raw=Array.isArray(p.branches)?p.branches:((p.trace&&Array.isArray(p.trace.candidates))?p.trace.candidates:(Array.isArray(p.candidates)?p.candidates:[]));
  S.branches=raw.map((b,i)=>({ id:String(b.id!=null?b.id:("br"+i)), verdict:_verdict(b),
    parent:b.parent!=null?String(b.parent):null, provenance:b.provenance!=null?String(b.provenance):null }));
  _tally();
  if(p.recursion_depth!=null) S.recursionDepth=p.recursion_depth;
  if(p.depth_cap!=null) S.depthCap=p.depth_cap;
  if(p.diff_cap!=null) S.diffCap=p.diff_cap;
  if(Array.isArray(p.workspace)||(p.workspace&&Array.isArray(p.workspace.tokens))) _ingestWorkspace(p.workspace);
  _rebuildBranches();_paintOverlay();
}
function _verdict(b){ const v=(b.verdict!=null?b.verdict:(b.kernel_verdict!=null?b.kernel_verdict:b.status));
  const s=String(v==null?"":v).toLowerCase();
  if(b.accepted===true||s.indexOf("accept")>=0||s==="ok"||s==="pass") return "accepted";
  if(b.accepted===false||s.indexOf("reject")>=0||s==="fail") return "rejected"; return "pending"; }
function _tally(){ let a=0,r=0,pd=0; S.branches.forEach((b)=>{ if(b.verdict==="accepted")a++; else if(b.verdict==="rejected")r++; else pd++; }); S.accepted=a;S.rejected=r;S.pending=pd; }

function _onArchive(j){
  if(!j)return; const p=j.payload||j; S.label=_readLabel(j);
  const raw=Array.isArray(p.branches)?p.branches:(Array.isArray(p.archive)?p.archive:(Array.isArray(p.nodes)?p.nodes:[]));
  if(raw.length){
    S.branches=raw.map((b,i)=>({ id:String(b.id!=null?b.id:("ar"+i)), verdict:_verdict(b),
      parent:b.parent!=null?String(b.parent):null, provenance:b.provenance!=null?String(b.provenance):null }));
    _tally();
    const cov=S.branches.filter((b)=>b.provenance&&b.provenance.length>0).length;
    if(S.branches.length) S.provCoverage=cov/S.branches.length;
    if(p.max_depth!=null) S.recursionDepth=p.max_depth;
    _rebuildBranches();
  }
  _paintOverlay();
}
function _ingestWorkspace(src){
  const obj=Array.isArray(src)?{tokens:src}:(src||{});
  const toks=Array.isArray(obj.tokens)?obj.tokens:(Array.isArray(obj.candidates)?obj.candidates:[]);
  S.tokens=toks.map((t,i)=>(typeof t==="object"&&t!==null)
    ?{token:String(t.token!=null?t.token:(t.text!=null?t.text:("t"+i))), salience:_clamp01(Number(t.salience!=null?t.salience:(t.weight!=null?t.weight:0.5))||0.5)}
    :{token:String(t),salience:0.5});
  const flagsRaw=Array.isArray(obj.flags)?obj.flags:(Array.isArray(obj.safety_flags)?obj.safety_flags:(Array.isArray(obj.safety)?obj.safety:[]));
  S.flags=flagsRaw.map((f)=>(typeof f==="object"&&f!==null)
    ?{cls:String(f.class!=null?f.class:(f.type!=null?f.type:(f.flag!=null?f.flag:"flag"))), token:String(f.token!=null?f.token:(f.text!=null?f.text:"")), note:String(f.note!=null?f.note:(f.reason!=null?f.reason:""))}
    :{cls:String(f),token:"",note:""});
}
function _onWorkspace(j){ if(!j)return; const p=j.payload||j; S.label=_readLabel(j); _ingestWorkspace(p); _rebuildTokens(); _rebuildFlags(); _paintOverlay(); }
function _onHorizon(j){
  if(!j)return; const p=j.payload||j; S.label=_readLabel(j);
  const raw=Array.isArray(p.series)?p.series:(Array.isArray(p.horizon)?p.horizon:(Array.isArray(p)?p:[]));
  S.horizon=raw.map((row)=>(typeof row==="object"&&row!==null)?Number(row.value!=null?row.value:(row.horizon!=null?row.horizon:(row.y!=null?row.y:0)))||0:Number(row)||0);
  if(p.now!=null) S.horizonNow=Number(p.now)||0; else if(S.horizon.length) S.horizonNow=S.horizon[S.horizon.length-1];
  _paintOverlay();
}
function _onMetrics(j){
  if(!j)return; const p=j.payload||j; S.label=_readLabel(j); const inv=p.invariants||p;
  S.acceptRate=_num(p.acceptance_rate!=null?p.acceptance_rate:p.accept_rate);
  S.writerNeJudge=_bool(inv.writer_ne_judge!=null?inv.writer_ne_judge:inv.writer_neq_judge);
  S.kernelOutsideLoop=_bool(inv.kernel_outside_loop!=null?inv.kernel_outside_loop:inv.verifier_outside_loop);
  S.conjGreen=(inv.conjecture_rendered_green!=null)?Number(inv.conjecture_rendered_green):S.conjGreen;
  if(p.provenance_coverage!=null) S.provCoverage=Number(p.provenance_coverage);
  if(p.mean_recursion_depth!=null) S.recursionDepth=p.mean_recursion_depth;
  if(p.depth_cap!=null) S.depthCap=p.depth_cap;
  _paintOverlay();
}
function _num(x){ return x==null?null:(Number(x)||0); }
function _bool(x){ if(x==null)return null; if(typeof x==="boolean")return x; const s=String(x).toLowerCase(); return s==="true"||s==="1"||s==="yes"; }

function _buildScaffold(){
  const hg=new _THREE.SphereGeometry(HUB_R,30,30);
  const hm=new _THREE.MeshStandardMaterial({ color:C_HUB,emissive:C_HUB,emissiveIntensity:0.45,metalness:0.15,roughness:0.35 });
  _hub=new _THREE.Mesh(hg,hm); _hub.userData={role:"hub"}; _group.add(_hub);
  const rg=new _THREE.TorusGeometry(RING_R,0.055,20,128);
  const rm=new _THREE.MeshStandardMaterial({ color:C_RING_OK,emissive:C_RING_OK,emissiveIntensity:0.7,metalness:0.2,roughness:0.3,transparent:true,opacity:0.95 });
  _ring=new _THREE.Mesh(rg,rm); _ring.rotation.x=Math.PI/2; _ring.userData={role:"kernel-gate"}; _group.add(_ring);
  const gg=new _THREE.TorusGeometry(RING_R,0.18,16,96);
  const gm=new _THREE.MeshBasicMaterial({ color:C_RING_OK,transparent:true,opacity:0.12,blending:_THREE.AdditiveBlending,depthWrite:false });
  _ringGlow=new _THREE.Mesh(gg,gm); _ringGlow.rotation.x=Math.PI/2; _group.add(_ringGlow);
  _branchGroup=new _THREE.Group(); _group.add(_branchGroup);
  _tokenGroup=new _THREE.Group(); _group.add(_tokenGroup);
  _flagGroup=new _THREE.Group(); _group.add(_flagGroup);
}
function _disposeMesh(m){ if(!m)return; if(m.geometry&&m.geometry.dispose)m.geometry.dispose();
  if(m.material){const a=Array.isArray(m.material)?m.material:[m.material];a.forEach((x)=>x.dispose&&x.dispose());} if(m.parent)m.parent.remove(m); }
function _clearGroup(store){ store.forEach((rec)=>{ Object.values(rec).forEach((v)=>{ if(v&&v.isObject3D)_disposeMesh(v); }); }); }

function _rebuildBranches(){
  if(!_branchGroup)return; _clearGroup(_branchMeshes); _branchMeshes=[];
  const n=S.branches.length; if(!n)return;
  S.branches.forEach((b,i)=>{
    const ang=((_hash(b.id)%3600)/3600)*Math.PI*2+(i/Math.max(1,n))*0.35;
    const accepted=b.verdict==="accepted", rejected=b.verdict==="rejected";
    const reach=accepted?ARCHIVE_R:(rejected?RING_R*0.7:RING_R*0.92);
    const col=accepted?C_ACCEPT:(rejected?C_REJECT:C_PROPOSE);
    const p0=new _THREE.Vector3(Math.cos(ang)*BRANCH_IN,0,Math.sin(ang)*BRANCH_IN);
    const p1=new _THREE.Vector3(Math.cos(ang)*reach,0,Math.sin(ang)*reach);
    const lg=new _THREE.BufferGeometry().setFromPoints([p0,p1]);
    const lm=new _THREE.LineBasicMaterial({ color:col,transparent:true,opacity:rejected?0.28:(accepted?0.85:0.55) });
    const line=new _THREE.Line(lg,lm);
    const tg=new _THREE.SphereGeometry(accepted?0.16:0.11,14,14);
    const tm=new _THREE.MeshStandardMaterial({ color:col,emissive:rejected?C_BLACK:col,
      emissiveIntensity:accepted?0.6:(rejected?0.0:0.3),metalness:0.1,roughness:rejected?0.95:0.45,transparent:true,opacity:rejected?0.45:0.95 });
    const tip=new _THREE.Mesh(tg,tm); tip.position.copy(p1);
    tip.userData={verdict:b.verdict,baseEmissive:accepted?0.6:(rejected?0.0:0.3)};
    _branchGroup.add(line);_branchGroup.add(tip);
    _branchMeshes.push({line,tip,verdict:b.verdict,angle:ang,reach});
  });
}
function _rebuildTokens(){
  if(!_tokenGroup)return; _clearGroup(_tokenMeshes); _tokenMeshes=[];
  const n=S.tokens.length; if(!n)return;
  S.tokens.forEach((t,i)=>{
    const ang=(i/n)*Math.PI*2; const y=(((_hash(t.token+"y")%200)/200)-0.5)*1.4;
    const r=0.07+0.10*_clamp01(t.salience);
    const g=new _THREE.SphereGeometry(r,10,10);
    const m=new _THREE.MeshStandardMaterial({ color:C_TOKEN,emissive:C_TOKEN,emissiveIntensity:0.15+0.4*_clamp01(t.salience),metalness:0.0,roughness:0.7,transparent:true,opacity:0.6 });
    const mesh=new _THREE.Mesh(g,m); _tokenGroup.add(mesh);
    _tokenMeshes.push({mesh,angle:ang,y,salience:_clamp01(t.salience)});
  });
}
function _rebuildFlags(){
  if(!_flagGroup)return; _clearGroup(_flagMeshes); _flagMeshes=[];
  const n=S.flags.length; if(!n)return;
  S.flags.forEach((f,i)=>{
    const cls=_flagClass(f.cls);
    const x=((i/Math.max(1,n-1))-0.5)*(RING_R*1.6);
    const pos=new _THREE.Vector3(x,FLAG_LANE_Y,RING_R*0.65);
    const g=new _THREE.TetrahedronGeometry(0.24);
    const m=new _THREE.MeshStandardMaterial({ color:cls.color,emissive:cls.color,emissiveIntensity:0.85,metalness:0.1,roughness:0.4 });
    const mesh=new _THREE.Mesh(g,m); mesh.position.copy(pos);
    const hg=new _THREE.RingGeometry(0.34,0.44,24);
    const hm=new _THREE.MeshBasicMaterial({ color:cls.color,transparent:true,opacity:0.5,side:_THREE.DoubleSide,blending:_THREE.AdditiveBlending,depthWrite:false });
    const halo=new _THREE.Mesh(hg,hm); halo.position.copy(pos);
    _flagGroup.add(mesh);_flagGroup.add(halo);
    _flagMeshes.push({mesh,halo});
  });
}
function _animate(){
  if(!_group)return;
  const now=(typeof performance!=="undefined"?performance.now():Date.now()); const t=(now-_t0)/1000;
  if(_hub&&_hub.material) _hub.material.emissiveIntensity=0.45+0.1*Math.sin(t*1.4);
  const gating=S.accepted!=null&&S.accepted>0;
  if(_ring&&_ring.material){ _ring.material.color.setHex(gating?C_RING_OK:C_RING_NO); _ring.material.emissive.setHex(gating?C_RING_OK:C_RING_NO);
    _ring.material.emissiveIntensity=(gating?0.7:0.25)+0.15*Math.sin(t*2.0); _ring.rotation.z=t*0.15; }
  if(_ringGlow&&_ringGlow.material){ _ringGlow.material.color.setHex(gating?C_RING_OK:C_RING_NO);
    _ringGlow.material.opacity=(gating?0.14:0.05)+0.05*Math.abs(Math.sin(t*2.0)); _ringGlow.rotation.z=-t*0.1; }
  _branchMeshes.forEach((br,i)=>{
    if(!br.tip||!br.tip.material)return;
    if(br.verdict==="accepted"){ br.tip.material.emissiveIntensity=br.tip.userData.baseEmissive+0.25*Math.abs(Math.sin(t*1.6+i)); }
    else if(br.verdict==="rejected"){ br.tip.position.y=-0.6*(0.5+0.5*Math.sin(t*0.6+i)); br.tip.material.emissiveIntensity=0.0; }
    else { br.tip.material.emissiveIntensity=br.tip.userData.baseEmissive+0.15*Math.sin(t*2.2+i); }
  });
  _tokenMeshes.forEach((tk,i)=>{ if(!tk.mesh)return; const a=tk.angle+t*0.25;
    tk.mesh.position.set(Math.cos(a)*TOKEN_R,tk.y+0.12*Math.sin(t*0.9+i),Math.sin(a)*TOKEN_R); });
  _flagMeshes.forEach((fl,i)=>{ if(fl.mesh)fl.mesh.rotation.y=t*1.2+i;
    if(fl.halo&&fl.halo.material){ fl.halo.material.opacity=0.35+0.35*Math.abs(Math.sin(t*3.0+i)); fl.halo.scale.setScalar(1+0.12*Math.abs(Math.sin(t*3.0+i))); } });
  _group.rotation.y=t*0.06;
}
function _buildOverlay(ctx){
  _show=createShowcase(ctx,{
    id:ID, title:TITLE, accent:"#3af4c8", badge:_badge,
    chips:[{label:"MODELED", name:"label"}],
  });
  _overlay=document.createElement("div");
  _overlay.style.cssText="font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;";
  _overlay.innerHTML=
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">Kernel-gated agentic loop. Proposer branches bloom from the HEART/BLOOD hub; the kernel gate ring accepts (gold, archived) or rejects (grey, falls away). The orbiting cloud is the workspace readout of the "silent" candidate tokens; the raised lane surfaces safety flags <b>before commit</b>.</div>'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">Kernel-gate invariants</div>'+
    '<div id="lf-inv" style="font-size:11px;color:#eaf6f9"></div>'+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    _row("Proof horizon (kernel-accepted)","lf-horizon")+_row("Acceptance rate","lf-accept")+
    _row("Branches acc / rej / pend","lf-branches")+_row("Recursion depth","lf-depth")+
    _row("Provenance coverage","lf-prov")+_row("Workspace tokens","lf-tokens")+
    _row("Safety flags (pre-commit)","lf-flags")+
    '<div id="lf-flaglist" style="margin-top:4px;font-size:10.5px;color:#eaf6f9"></div>'+
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">'+
      _leg(C_HUB,"HEART/BLOOD hub")+_leg(C_PROPOSE,"proposer branch")+_leg(C_ACCEPT,"kernel-accepted")+
      _leg(C_REJECT,"rejected (falls away)")+_leg(C_TOKEN,"workspace token")+_leg(C_FLAG,"safety flag")+
    '</div>'+
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button id="lf-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>'+
      '<button id="lf-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Sources &amp; caveats</button>'+
    '</div>'+
    '<div id="lf-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>'+
    '<div id="lf-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  _show.body.appendChild(_overlay);
  const pb=_overlay.querySelector("#lf-plain"); if(pb) pb.addEventListener("click",()=>{_plain=!_plain;_applyPlain();});
  const ib=_overlay.querySelector("#lf-info");
  if(ib) ib.addEventListener("click",()=>{ const box=_overlay.querySelector("#lf-infobox");
    if(box) box.style.display=box.style.display==="none"?"block":"none";
    if(box&&box.innerHTML==="") box.innerHTML=_infoHTML(); });
}
function _row(k,id){ return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px"><span style="color:#8fb3bd">'+k+'</span><span id="'+id+'" style="color:#eaf6f9;font-variant-numeric:tabular-nums">—</span></div>'; }
function _leg(hex,txt){ const c="#"+hex.toString(16).padStart(6,"0"); return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';margin-right:4px;vertical-align:middle"></span>'+txt+'</span>'; }
function _set(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }
function _check(name,val,wantTrue){ let mark,color;
  if(val==null){mark="…";color="#7d8a96";}
  else if(wantTrue?val===true:val===false){mark="✓";color="#3af4c8";}
  else {mark="✗";color="#ff6b6b";}
  return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px"><span style="color:#cfe3ea">'+name+'</span><span style="color:'+color+';font-weight:700">'+mark+'</span></div>'; }
function _checkZero(name,val){ let mark,color;
  if(val==null){mark="0 (grey by construction)";color="#3af4c8";}
  else if(Number(val)===0){mark="0 ✓";color="#3af4c8";}
  else {mark=String(val)+" ✗";color="#ff6b6b";}
  return '<div style="display:flex;justify-content:space-between;gap:10px;margin-top:2px"><span style="color:#cfe3ea">'+name+'</span><span style="color:'+color+';font-variant-numeric:tabular-nums">'+mark+'</span></div>'; }
function _paintOverlay(){
  if(!_overlay)return;
  const missing=(S.state==="missing"||S.state==="error"); const deg=missing||(S.state==="degraded");
  const nd="NO-LIVE-DATA"; const d=deg?"—":null;
  if(_show) _show.setChip("label",S.label||"MODELED");
  const inv=_overlay.querySelector("#lf-inv");
  if(inv) inv.innerHTML=_check("writer ≠ judge",S.writerNeJudge,true)+_check("kernel outside loop",S.kernelOutsideLoop,true)+_checkZero("conjecture rendered green",S.conjGreen);
  if(missing&&!S.branches.length){
    _set("lf-horizon",nd);_set("lf-accept",nd);_set("lf-branches",nd);_set("lf-depth",nd);
    _set("lf-prov",nd);_set("lf-tokens",nd);_set("lf-flags",nd+" — lane clears until the organ answers.");
    const fl=_overlay.querySelector("#lf-flaglist"); if(fl) fl.innerHTML="";
    _dimForDegrade(); if(_plain)_applyPlain(); return;
  }
  _set("lf-horizon",d||(S.horizonNow!=null?String(S.horizonNow)+" (kernel-accepted)":"—"));
  _set("lf-accept",d||(S.acceptRate!=null?(S.acceptRate<=1?(S.acceptRate*100).toFixed(1)+"%":String(S.acceptRate)):"—"));
  _set("lf-branches",d||((S.accepted!=null?S.accepted:"—")+" / "+(S.rejected!=null?S.rejected:"—")+" / "+(S.pending!=null?S.pending:"—")));
  _set("lf-depth",d||(S.recursionDepth!=null?(String(S.recursionDepth)+(S.depthCap!=null?" (cap "+S.depthCap+")":"")):"—"));
  _set("lf-prov",d||(S.provCoverage!=null?(S.provCoverage*100).toFixed(1)+"%":"—"));
  _set("lf-tokens",d||(S.tokens.length?String(S.tokens.length)+" silent candidates":"—"));
  _set("lf-flags",(S.flags.length?String(S.flags.length)+" surfaced pre-commit":(deg?"—":"0 this cycle")));
  const flist=_overlay.querySelector("#lf-flaglist");
  if(flist){ flist.innerHTML=S.flags.slice(0,8).map((f)=>{ const cls=_flagClass(f.cls); const c="#"+cls.color.toString(16).padStart(6,"0");
    const note=(f.token||f.note)?(" — "+(f.token?"'"+f.token+"'":"")+(f.note?" "+f.note:"")):"";
    return '<div style="display:flex;gap:6px;align-items:flex-start;margin-top:2px"><span style="color:'+c+';font-weight:700">▲</span><span style="color:#eaf6f9">'+cls.label+'<span style="color:#8fb3bd">'+note+'</span></span></div>'; }).join(""); }
  if(_plain)_applyPlain();
}
function _dimForDegrade(){ _branchMeshes.forEach((br)=>{ if(br.tip&&br.tip.material) br.tip.material.emissiveIntensity=0.0; });
  _tokenMeshes.forEach((tk)=>{ if(tk.mesh&&tk.mesh.material) tk.mesh.material.emissiveIntensity=0.0; }); }
function _applyPlain(){
  const box=_overlay&&_overlay.querySelector("#lf-plainbox"); if(!box)return;
  box.style.display=_plain?"block":"none";
  if(_plain) box.innerHTML="This shows our agentic loop as a forge. The teal ball in the middle is the <b>broadcasting hub</b> (the HEART/BLOOD spine). The loop <b>proposes</b> many small edits — those are the blue branches growing outward. A separate authority we call the <b>kernel gate</b> (the glowing ring) decides which proposals are actually correct: accepted ones turn <b>gold and cross into the archive</b>; rejected ones <b>dim and fall away</b>. Crucially, the thing that <i>writes</i> proposals is never the thing that <i>judges</i> them (writer ≠ judge), and the judge sits <b>outside</b> the loop so it cannot be talked into a yes. The drifting cloud is a <b>readout of the candidate tokens on the loop's mind</b> before it commits — our honest analogue of Anthropic's J-lens. The raised warning lane surfaces <b>safety flags (bugs, injection, fabrication) BEFORE anything commits</b>. Label is <b>"+(S.label||"MODELED")+"</b>: a faithful drawing of a modeled loop on a real topology, not a trained model, not a real Jacobian, not \u201Calive.\u201D If the organ is offline it says \u201CNO-LIVE-DATA\u201D and the loop goes quiet.";
}
function _infoHTML(){
  return "<b>What is MODELED vs real.</b> The loop's node set traces to the real Flower/Brain graph. The kernel gate here is a <b>MODELED acceptance oracle</b> that mirrors the discipline of the real lutar-lean kernel (c7c0ba17) and cites it — it is <b>not</b> the Lean kernel (no toolchain in-Space); the real proof authority is re-verified in CI/dev. The workspace readout is a <b>MODELED readout of the loop's own proposal buffer</b>, inspired by Anthropic's J-lens — it reads the loop's candidates, <b>not</b> neural activations or a real Jacobian. No consciousness or sentience is claimed (mirroring Anthropic's own caveat: J-lens is \u201Can imperfect method\u201D that \u201Capproximately captures\u201D single-token concepts). \u039B stays <b>Conjecture 1</b>, rendered grey, never green.<br><br><b>We borrow structure; we do not claim it.</b><br>&bull; Anthropic \u2014 A global workspace in language models (J-space / J-lens): <a href=\"https://www.anthropic.com/research/global-workspace\" style=\"color:#3af4c8\">anthropic.com/research/global-workspace</a><br>&bull; Darwin G\u00f6del Machine \u2014 arXiv:2505.22954 &nbsp;&bull;&nbsp; SICA \u2014 arXiv:2504.15228<br>&bull; Voyager \u2014 arXiv:2305.16291 &nbsp;&bull;&nbsp; Reflexion \u2014 arXiv:2303.11366 &nbsp;&bull;&nbsp; ReAct \u2014 arXiv:2210.03629<br>&bull; SWE-agent \u2014 arXiv:2405.15793 &nbsp;&bull;&nbsp; OpenHands \u2014 arXiv:2407.16741<br>&bull; Loop-engineering \u2014 arXiv:2607.00038 &nbsp;&bull;&nbsp; SpecBench \u2014 arXiv:2605.21384 &nbsp;&bull;&nbsp; RHB \u2014 arXiv:2605.02964<br>&bull; Reward-hacking / CoT-obfuscation \u2014 arXiv:2503.11926 (writer\u2260judge motivation)<br>&bull; Kernel authority \u2014 lutar-lean kernel c7c0ba17 (cited; re-verified in CI/dev, not in-Space).";
}
function unmount(){
  _polls.forEach((p)=>{ try{p.stop();}catch(_){} }); _polls=[];
  try{ if(_show) _show.destroy(); }catch(_){} _show=null;
  try{ if(_group&&_stage){ _group.traverse((o)=>{ if(o.geometry&&o.geometry.dispose)o.geometry.dispose();
    if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach((m)=>{if(m.dispose)m.dispose();});} }); _stage.scene.remove(_group); } }catch(_){}
  _group=_overlay=null; _hub=_ring=_ringGlow=null; _branchGroup=_tokenGroup=_flagGroup=null;
  _branchMeshes=[];_tokenMeshes=[];_flagMeshes=[]; _badge=null;_plain=false;_frameReg=false;
  _stage=_THREE=_ctx=null;
  S.label=null;S.state="init"; S.branches=[];S.accepted=S.rejected=S.pending=null;
  S.recursionDepth=S.depthCap=S.diffCap=null; S.tokens=[];S.flags=[];
  S.horizon=[];S.horizonNow=null; S.acceptRate=null;S.writerNeJudge=null;S.kernelOutsideLoop=null;
  S.conjGreen=null;S.provCoverage=null;
}
export default { id: ID, title: TITLE, endpoints: [EP_RUN, EP_ARCHIVE, EP_WORKSPACE, EP_HORIZON, EP_METRICS], mount, unmount };
