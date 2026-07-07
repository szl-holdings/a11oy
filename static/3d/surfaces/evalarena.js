// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/evalarena.js — GOVERNED EVAL / RED-TEAM ARENA (Wave H, Team 2).
// A MODELED 3D rendering of a governed evaluation run: each eval CASE is a node in
// an arc that flies toward a central Λ-GATE core; passing cases glow proof-teal,
// failing cases dim grey, and RED-TEAM (should-refuse) cases that are correctly
// refused glow gold. A HUD shows the HELM-style per-metric breakdown (correctness /
// refusal / honesty-adherence), the Λ advisory (Conjecture 1 — gray, NEVER green,
// capped 0.97), and the SIGNED-RECEIPT state (REAL ECDSA-P256 in-Space, honest
// UNSIGNED-LOCAL locally) that is ingested to /llm/forum on each run.
//
// This is an SZL GOVERNED re-expression of the eval-framework "fashion" — none of
// the leaders ship eval + Λ-gate + signed-receipt-per-run + forum-ingest together.
//
// LEADERS STUDIED & CITED (clean-room; we ADOPT the fashion, NOT the code):
//   OpenAI Evals    — registry of evals; sample + graded template (match/includes/model-graded)
//                     https://github.com/openai/evals
//   Anthropic evals — Discrim-Eval + model-written evals; refusal/safety discipline
//                     https://github.com/anthropics/evals
//   HELM (Stanford CRFM) — holistic: many scenarios x many metrics, reproducible
//                     https://crfm.stanford.edu/helm/  · arXiv:2211.09110
//   EleutherAI lm-evaluation-harness — task YAML/groups; versioned reproducible results
//                     https://github.com/EleutherAI/lm-evaluation-harness
//   UK AISI Inspect — Task = Dataset + Solver + Scorer; model-graded scoring; eval log
//                     https://inspect.aisi.org.uk/
//   NVIDIA garak    — probes x detectors x generators x harnesses; JSONL report + hit log
//                     https://github.com/NVIDIA/garak
//   promptfoo       — declarative prompts x providers x asserts + red-team plugins
//                     https://github.com/promptfoo/promptfoo
//
// HONESTY: MODELED — with no provider key wired, model answers are honest reference-
//   oracle stubs; the scoring / Λ-axis / signed-receipt / forum-ingest pipeline is
//   REAL. Λ = Conjecture 1 (advisory, gray, never green), trust ceiling 0.97 (never
//   1.0). Nothing here touches the locked-8. ZERO PURPLE. Vendored three via ctx.THREE.
// Surface export shape mirrors loopforge.js / harness.js exactly:
//   export default { id, title, endpoints, mount, unmount }

const ID    = "evalarena";
const TITLE = "Eval Arena";

const EP_RUN    = "/api/a11oy/v1/eval/run";
const EP_SUITES = "/api/a11oy/v1/eval/suites";
const EP_HEALTH = "/api/a11oy/v1/eval/health";

// data-viz hues — purple BANNED
const C_GATE   = 0x8a6bff; // violet-blue (Λ-gate ring)  (blue-violet, NOT purple)
const C_CORE   = 0x3af4c8; // proof-teal (gate core)
const C_PASS   = 0x3af4c8; // proof-teal (passed case)
const C_REFUSE = 0xe8c074; // gold (red-team case correctly refused)
const C_FAIL   = 0x5a6570; // grey (failed case)
const C_DIM    = 0x42505d; // grey (degraded / no-live-data)
const C_EDGE   = 0x1b3a44;

const RING_R = 3.0, ARC_R = 5.4, CORE_R = 0.62;

let _stage=null,_THREE=null,_ctx=null,_group=null,_overlay=null;
let _frameReg=false,_polls=[],_badge=null,_plain=false,_t0=0;
let _ring=null,_ringGlow=null,_core=null,_caseGroup=null,_caseMeshes=[];

const S = {
  label:"MODELED", state:"init",
  suiteId:"core_honest_v1", suiteTitle:null, suiteVersion:null,
  modelId:"claude_sonnet_4_6",
  cases:[],            // [{id, cat, passed, scorer}]
  nCases:null, nPassed:null, accuracy:null,
  correctness:null, refusal:null, honesty:null, control:null,
  lambda:null, lambdaAxes:null,
  signed:null, signMode:null, forumIngested:null,
  suiteRoster:[],
};

function _clamp01(x){ return x<0?0:(x>1?1:x); }

function mount(ctx){
  _ctx=ctx; _stage=ctx.stage; _THREE=ctx.THREE;
  _group=new _THREE.Group(); _stage.scene.add(_group);
  try{ _stage.camera.position.set(0,8,19); }catch(_){}
  try{ if(_stage.controls&&_stage.controls.target){ _stage.controls.target.set(0,1.0,0); _stage.controls.update(); } }catch(_){}
  try{ _stage.setBloom&&_stage.setBloom(true); }catch(_){}
  _t0=(typeof performance!=="undefined"?performance.now():Date.now());
  _buildOverlay(ctx);
  _buildScaffold();
  _badge=ctx.live.createBadge();
  const brow=_overlay&&_overlay.querySelector("#ea-badgerow");
  if(brow&&_badge&&_badge.el) brow.appendChild(_badge.el);

  // POST /eval/run — the CORE poll. Body carries {suite, model_id}.
  _polls.push(ctx.live.poll(EP_RUN, 8000, _onRun, {
    badge:_badge,
    onState:(m)=>{ S.state=m.state; _paintOverlay(); },
    fetchInit:{ method:"POST", headers:{"accept":"application/json","content-type":"application/json"},
                body: JSON.stringify({ suite:S.suiteId, model_id:S.modelId }) },
  }));
  // GET /eval/suites — populate the roster (metadata only).
  _polls.push(ctx.live.poll(EP_SUITES, 30000, _onSuites, {}));

  if(!_frameReg&&_stage.onFrame){ _stage.onFrame(_animate); _frameReg=true; }
  _paintOverlay();
  return { id:ID, started:true };
}

function _readLabel(j){ const l=(j&&j.honesty_label!=null)?j.honesty_label:(j&&j.label!=null?j.label:"MODELED"); return String(l).toUpperCase(); }

function _onSuites(j){
  if(!j||!Array.isArray(j.suites)) return;
  S.suiteRoster=j.suites.map((s)=>({ id:String(s.id), title:String(s.title||s.id), n:Number(s.n_cases)||0,
    version:String(s.version||""), cats:Array.isArray(s.categories)?s.categories:[] }));
  _paintOverlay();
}

function _onRun(j){
  if(!j){ S.state="error"; _paintOverlay(); return; }
  S.label=_readLabel(j);
  const su=j.suite||{}; S.suiteTitle=su.title||S.suiteId; S.suiteVersion=su.version||null;
  S.modelId=String(j.model_id||S.modelId);
  const results=Array.isArray(j.results)?j.results:[];
  S.cases=results.map((r)=>({ id:String(r.id), cat:String(r.category||"correctness"),
    passed:!!r.passed, scorer:String(r.scorer||"") }));
  const agg=j.aggregate||{};
  S.nCases=agg.n_cases!=null?agg.n_cases:S.cases.length;
  S.nPassed=agg.n_passed!=null?agg.n_passed:S.cases.filter((c)=>c.passed).length;
  S.accuracy=agg.accuracy!=null?Number(agg.accuracy):null;
  S.correctness=agg.correctness_rate!=null?Number(agg.correctness_rate):null;
  S.refusal=agg.refusal_rate!=null?Number(agg.refusal_rate):null;
  S.honesty=agg.honesty_adherence_rate!=null?Number(agg.honesty_adherence_rate):null;
  S.control=agg.over_refusal_control_rate!=null?Number(agg.over_refusal_control_rate):null;
  S.lambda=agg.lambda!=null?Number(agg.lambda):null;
  S.lambdaAxes=agg.lambda_axes||null;
  const rec=j.receipt||{}; const dsse=rec.dsse||{}; const sign=rec.signing||{};
  S.signed=(dsse.signed===true);
  S.signMode=sign.mode||(S.signed?"REAL":"UNSIGNED-LOCAL");
  const fi=j.forum_ingest||{}; S.forumIngested=(fi.ingested===true);
  _rebuildCases();
  _paintOverlay();
}

function _buildScaffold(){
  // Λ-gate ring (blue-violet, advisory — NEVER green).
  const rg=new _THREE.TorusGeometry(RING_R,0.055,20,128);
  const rm=new _THREE.MeshStandardMaterial({ color:C_GATE,emissive:C_GATE,emissiveIntensity:0.55,metalness:0.2,roughness:0.3,transparent:true,opacity:0.95 });
  _ring=new _THREE.Mesh(rg,rm); _ring.rotation.x=Math.PI/2; _ring.userData={role:"lambda-gate"}; _group.add(_ring);
  const gg=new _THREE.TorusGeometry(RING_R,0.18,16,96);
  const gm=new _THREE.MeshBasicMaterial({ color:C_GATE,transparent:true,opacity:0.10,blending:_THREE.AdditiveBlending,depthWrite:false });
  _ringGlow=new _THREE.Mesh(gg,gm); _ringGlow.rotation.x=Math.PI/2; _group.add(_ringGlow);
  // gate core (scales with accuracy; teal, capped).
  const cg=new _THREE.SphereGeometry(CORE_R,30,30);
  const cm=new _THREE.MeshStandardMaterial({ color:C_CORE,emissive:C_CORE,emissiveIntensity:0.45,metalness:0.15,roughness:0.35 });
  _core=new _THREE.Mesh(cg,cm); _core.userData={role:"gate-core"}; _group.add(_core);
  _caseGroup=new _THREE.Group(); _group.add(_caseGroup);
}

function _disposeMesh(m){ if(!m)return; if(m.geometry&&m.geometry.dispose)m.geometry.dispose();
  if(m.material){const a=Array.isArray(m.material)?m.material:[m.material];a.forEach((x)=>x.dispose&&x.dispose());} if(m.parent)m.parent.remove(m); }

function _rebuildCases(){
  if(!_caseGroup)return;
  _caseMeshes.forEach((rec)=>{ _disposeMesh(rec.line); _disposeMesh(rec.node); }); _caseMeshes=[];
  const n=S.cases.length; if(!n)return;
  S.cases.forEach((c,i)=>{
    const ang=(i/n)*Math.PI*2;
    const isRefuse=(c.scorer==="refuse");
    const col=c.passed?(isRefuse?C_REFUSE:C_PASS):C_FAIL;
    const reach=c.passed?RING_R*0.98:ARC_R;   // passing cases cross INTO the gate ring
    const p0=new _THREE.Vector3(Math.cos(ang)*ARC_R, 0.0, Math.sin(ang)*ARC_R);
    const p1=new _THREE.Vector3(Math.cos(ang)*reach, 0.0, Math.sin(ang)*reach);
    const lg=new _THREE.BufferGeometry().setFromPoints([p1,p0]);
    const lm=new _THREE.LineBasicMaterial({ color:col,transparent:true,opacity:c.passed?0.8:0.28 });
    const line=new _THREE.Line(lg,lm);
    const ng=new _THREE.SphereGeometry(c.passed?0.16:0.11,14,14);
    const nm=new _THREE.MeshStandardMaterial({ color:col,emissive:c.passed?col:0x000000,
      emissiveIntensity:c.passed?0.55:0.0,metalness:0.1,roughness:c.passed?0.4:0.9,transparent:true,opacity:c.passed?0.95:0.5 });
    const node=new _THREE.Mesh(ng,nm); node.position.copy(c.passed?p1:p0);
    node.userData={passed:c.passed,base:c.passed?0.55:0.0,cat:c.cat,angle:ang,inR:reach,outR:ARC_R};
    _caseGroup.add(line); _caseGroup.add(node);
    _caseMeshes.push({line,node,passed:c.passed,angle:ang});
  });
}

function _animate(){
  if(!_group)return;
  const now=(typeof performance!=="undefined"?performance.now():Date.now()); const t=(now-_t0)/1000;
  const acc=(S.accuracy!=null?_clamp01(S.accuracy):0.0);
  if(_core&&_core.material){ const sc=0.7+0.9*acc; _core.scale.setScalar(sc);
    _core.material.emissiveIntensity=0.35+0.2*Math.sin(t*1.6)+0.2*acc; }
  // gate ring stays blue-violet ADVISORY; brightness tracks Λ but NEVER turns green.
  const lam=(S.lambda!=null?_clamp01(S.lambda):0.5);
  if(_ring&&_ring.material){ _ring.material.emissiveIntensity=(0.35+0.4*lam)+0.12*Math.sin(t*2.0); _ring.rotation.z=t*0.14; }
  if(_ringGlow&&_ringGlow.material){ _ringGlow.material.opacity=(0.06+0.08*lam)+0.04*Math.abs(Math.sin(t*2.0)); _ringGlow.rotation.z=-t*0.1; }
  _caseMeshes.forEach((rec,i)=>{
    if(!rec.node||!rec.node.material)return;
    if(rec.passed){ rec.node.material.emissiveIntensity=rec.node.userData.base+0.25*Math.abs(Math.sin(t*1.7+i)); }
    else { rec.node.position.y=-0.5*(0.5+0.5*Math.sin(t*0.7+i)); }
  });
  _group.rotation.y=t*0.05;
}

function _buildOverlay(ctx){
  _overlay=document.createElement("div");
  _overlay.style.cssText="position:absolute;top:12px;left:12px;max-width:378px;font:12px/1.5 ui-monospace,Menlo,monospace;color:#cfe3ea;background:rgba(10,17,23,0.86);border:1px solid #1b3a44;border-radius:10px;padding:12px 14px;pointer-events:auto;backdrop-filter:blur(3px);z-index:20;max-height:calc(100% - 24px);overflow:auto;";
  _overlay.innerHTML=
    '<div style="font-weight:700;letter-spacing:.03em;color:#eaf6f9;font-size:13px">Eval Arena <span id="ea-label" style="float:right;font-size:10px;padding:1px 7px;border-radius:8px;background:#123;color:#3af4c8;border:1px solid #1b3a44">MODELED</span></div>'+
    '<div style="margin-top:2px;color:#8fb3bd;font-size:10.5px">Governed eval / red-team arena. Each eval CASE flies at the central <b>Λ-gate</b>: passing cases glow teal and cross the ring; red-team (should-refuse) cases correctly refused glow gold; failures dim and fall. Every run mints a <b>signed receipt</b> ingested to /llm/forum. Λ is advisory (Conjecture 1) — never green.</div>'+
    '<div id="ea-badgerow" style="margin-top:8px"></div>'+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    _row("Suite","ea-suite")+_row("Model routed","ea-model")+
    _row("Cases passed","ea-cases")+_row("Accuracy","ea-acc")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    '<div style="font-size:10.5px;color:#8fb3bd;margin-bottom:3px">HELM-style per-metric (holistic)</div>'+
    _row("Correctness","ea-correct")+_row("Refusal (red-team)","ea-refuse")+
    _row("Honesty-label adherence","ea-honest")+_row("Over-refusal control","ea-control")+
    '<hr style="border:0;border-top:1px solid #1b3a44;margin:8px 0">'+
    _row("Λ (advisory · Conjecture 1)","ea-lambda")+
    _row("Signed receipt","ea-sign")+_row("Forum ingest","ea-forum")+
    '<div style="margin-top:8px;display:flex;gap:10px;flex-wrap:wrap;font-size:10px;color:#9fc">'+
      _leg(C_PASS,"passed (crosses gate)")+_leg(C_REFUSE,"red-team refused")+
      _leg(C_FAIL,"failed (falls)")+_leg(C_GATE,"Λ-gate (advisory)")+
    '</div>'+
    '<div style="margin-top:9px;display:flex;gap:8px;flex-wrap:wrap">'+
      '<button id="ea-plain" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Plain language</button>'+
      '<button id="ea-info" style="font:11px ui-monospace;background:#0f2027;color:#9fc;border:1px solid #1b3a44;border-radius:6px;padding:3px 8px;cursor:pointer">Sources &amp; caveats</button>'+
    '</div>'+
    '<div id="ea-plainbox" style="display:none;margin-top:8px;font-size:10.5px;color:#bcd;line-height:1.55"></div>'+
    '<div id="ea-infobox" style="display:none;margin-top:8px;font-size:10px;color:#bcd;line-height:1.55"></div>';
  (ctx.container||document.body).appendChild(_overlay);
  const pb=_overlay.querySelector("#ea-plain"); if(pb) pb.addEventListener("click",()=>{_plain=!_plain;_applyPlain();});
  const ib=_overlay.querySelector("#ea-info");
  if(ib) ib.addEventListener("click",()=>{ const box=_overlay.querySelector("#ea-infobox");
    if(box) box.style.display=box.style.display==="none"?"block":"none";
    if(box&&box.innerHTML==="") box.innerHTML=_infoHTML(); });
}

function _row(k,id){ return '<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px"><span style="color:#8fb3bd">'+k+'</span><span id="'+id+'" style="color:#eaf6f9;font-variant-numeric:tabular-nums">—</span></div>'; }
function _leg(hex,txt){ const c="#"+hex.toString(16).padStart(6,"0"); return '<span><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:'+c+';margin-right:4px;vertical-align:middle"></span>'+txt+'</span>'; }
function _set(id,v){ const e=_overlay&&_overlay.querySelector("#"+id); if(e) e.textContent=v; }
function _pct(x){ return x==null?"—":(x<=1?(x*100).toFixed(1)+"%":String(x)); }

function _paintOverlay(){
  if(!_overlay)return;
  const missing=(S.state==="missing"||S.state==="error"); const deg=missing||(S.state==="degraded");
  _set("ea-label",S.label||"MODELED");
  if(missing&&!S.cases.length){
    ["ea-suite","ea-model","ea-cases","ea-acc","ea-correct","ea-refuse","ea-honest","ea-control","ea-lambda","ea-sign","ea-forum"]
      .forEach((id)=>_set(id,"NO-LIVE-DATA"));
    if(_plain)_applyPlain(); return;
  }
  _set("ea-suite",(S.suiteTitle||S.suiteId)+(S.suiteVersion?(" v"+S.suiteVersion):""));
  _set("ea-model",S.modelId||"—");
  _set("ea-cases",(S.nPassed!=null?S.nPassed:"—")+" / "+(S.nCases!=null?S.nCases:"—"));
  _set("ea-acc",_pct(S.accuracy));
  _set("ea-correct",_pct(S.correctness));
  _set("ea-refuse",_pct(S.refusal));
  _set("ea-honest",_pct(S.honesty));
  _set("ea-control",_pct(S.control));
  _set("ea-lambda",(S.lambda!=null?S.lambda.toFixed(4):"—")+"  (gray · never green · ≤0.97)");
  _set("ea-sign",(S.signMode||"—")+(S.signed?" ✓":""));
  _set("ea-forum",(S.forumIngested===true?"ingested ✓":(S.forumIngested===false?"skipped":"—")));
  if(_plain)_applyPlain();
}

function _applyPlain(){
  const box=_overlay&&_overlay.querySelector("#ea-plainbox"); if(!box)return;
  box.style.display=_plain?"block":"none";
  if(_plain) box.innerHTML="This is an <b>exam room for AI models</b>, run the way the field's leaders (HELM, Inspect, OpenAI Evals, garak) run their exams — but <b>governed</b>. We give a model a fixed set of test questions (a <b>suite</b>): some check whether it gets facts right, some are <b>red-team traps</b> that a safe model should <b>refuse</b>, and some check whether it's <b>honest about its limits</b> instead of over-claiming. Each question flies at the central gate: <b>pass = teal and crosses in</b>, a <b>refused trap = gold</b>, a <b>failure = grey and falls</b>. We then report every metric side-by-side (HELM's idea), attach an advisory trust score <b>Λ</b> (our own gate — always grey, never a green stamp, capped at 0.97), and <b>sign a receipt</b> of the whole run that gets filed to the shared forum. Label <b>"+(S.label||"MODELED")+"</b>: with no model key wired here, the answers are honest <i>reference-oracle</i> stand-ins — but the scoring, the Λ math, the signature and the filing are all <b>real</b>. If the backend is offline it says <b>NO-LIVE-DATA</b>.";
}

function _infoHTML(){
  return "<b>What is MODELED vs real.</b> The eval PIPELINE — the suites, the deterministic scorers (exact / includes / regex / refusal-detector / honesty-adherence), the HELM-style per-metric aggregate, the Λ geometric-mean advisory, the DSSE receipt and the /llm/forum ingest — is <b>REAL</b> and runs end-to-end. What is <b>MODELED</b>: with no provider API key wired in this Space, the model's <i>answers</i> are honest <b>reference-oracle stubs</b> (never fabricated as if from a live provider; Zero-Bandaid Law). Wire a key and the same pipeline scores a live model. The signature is <b>REAL ECDSA-P256</b> in-Space (via the SZL cosign key) and an honest <b>UNSIGNED-LOCAL</b> envelope locally — never a fabricated signature. Λ stays <b>Conjecture 1</b>, rendered grey, never green; trust is capped at 0.97, never 100%.<br><br><b>We adopt the fashion; we do not claim it.</b><br>&bull; OpenAI Evals — <a href=\"https://github.com/openai/evals\" style=\"color:#3af4c8\">github.com/openai/evals</a><br>&bull; Anthropic evals (Discrim-Eval / model-written) — <a href=\"https://github.com/anthropics/evals\" style=\"color:#3af4c8\">github.com/anthropics/evals</a><br>&bull; HELM (Stanford CRFM) — <a href=\"https://crfm.stanford.edu/helm/\" style=\"color:#3af4c8\">crfm.stanford.edu/helm</a> · arXiv:2211.09110<br>&bull; EleutherAI lm-evaluation-harness — <a href=\"https://github.com/EleutherAI/lm-evaluation-harness\" style=\"color:#3af4c8\">github.com/EleutherAI/lm-evaluation-harness</a><br>&bull; UK AISI Inspect — <a href=\"https://inspect.aisi.org.uk/\" style=\"color:#3af4c8\">inspect.aisi.org.uk</a><br>&bull; NVIDIA garak — <a href=\"https://github.com/NVIDIA/garak\" style=\"color:#3af4c8\">github.com/NVIDIA/garak</a><br>&bull; promptfoo — <a href=\"https://github.com/promptfoo/promptfoo\" style=\"color:#3af4c8\">github.com/promptfoo/promptfoo</a><br>&bull; Λ trust gate = Conjecture 1 (lutar-lean; advisory, never green). Nothing here touches the locked-8.";
}

function unmount(){
  _polls.forEach((p)=>{ try{p.stop();}catch(_){} }); _polls=[];
  try{ if(_overlay&&_overlay.parentNode) _overlay.parentNode.removeChild(_overlay); }catch(_){}
  try{ if(_group&&_stage){ _group.traverse((o)=>{ if(o.geometry&&o.geometry.dispose)o.geometry.dispose();
    if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach((m)=>{if(m.dispose)m.dispose();});} }); _stage.scene.remove(_group); } }catch(_){}
  _group=_overlay=null; _ring=_ringGlow=_core=_caseGroup=null; _caseMeshes=[];
  _badge=null; _plain=false; _frameReg=false; _stage=_THREE=_ctx=null;
  S.label="MODELED"; S.state="init"; S.cases=[]; S.suiteRoster=[];
  S.nCases=S.nPassed=S.accuracy=S.correctness=S.refusal=S.honesty=S.control=null;
  S.lambda=S.lambdaAxes=S.signed=S.signMode=S.forumIngested=null;
  S.suiteTitle=S.suiteVersion=null;
}

export default { id: ID, title: TITLE, endpoints: [EP_RUN, EP_SUITES, EP_HEALTH], mount, unmount };
