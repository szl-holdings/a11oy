"""a11oy_ayllu.py — register the ayllu (ingested-and-reborn tribe) on the a11oy app.

Follows a11oy's module convention: expose `register(app, ns="a11oy") -> str`, mounted
by serve.py inside a try/except guard so a11oy boots unaffected if anything here fails.

The model backend is a11oy's OWN orchestrator (see ayllu/backend.py): ask/council now
produce REAL answers when an inference credential is present on the Space, and an
honest, clearly-labeled stub otherwise — never a fabricated answer. Cost is bounded:
prompt length is capped, council fan-out is capped, and ask/council carry a process-
wide rate limit (429 + Retry-After).

Receipts use `szl_dsse` when present, else an honest UNSIGNED DSSE envelope (never a
fabricated signature). The DSSE payload chains the backend model + energy-receipt hash.

Routes:
  GET  /api/{ns}/v1/ayllu/roster   — roster + honest live/stub backend status
  POST /api/{ns}/v1/ayllu/ask      — one persona, bounded + honest + receipted
  POST /api/{ns}/v1/ayllu/council  — bounded multi-persona deliberation (capped fan-out)
  GET  /api/{ns}/v1/ayllu/lounge   — recent collaboration feed
  GET  /ayllu                      — honest human-readable chat + council page
"""
from __future__ import annotations

import base64
import hashlib
import json
import threading
import time
import uuid
from typing import Any, Dict, Optional

# FastAPI resolves endpoint annotations with get_type_hints against THIS module's
# globals. The handlers in register() annotate `request: "Request"` — a string
# forward-ref, because of `from __future__ import annotations` above — so `Request`
# (and the response classes) MUST be importable at MODULE level, or FastAPI cannot
# recognize the special Request parameter and mis-treats it as a REQUIRED query
# param (every GET route then 422s with loc=["query","request"]). They are also
# imported locally inside register() for the call sites; this module-level (guarded)
# import is solely what makes the string annotations resolvable at route-build time.
try:
    from fastapi import Request  # noqa: F401
    from fastapi.responses import HTMLResponse, JSONResponse  # noqa: F401
except Exception:  # pragma: no cover - fastapi absent only where register() is never called
    Request = HTMLResponse = JSONResponse = None  # type: ignore

# POC (szl-substrate extraction): prefer the shared package as the single source
# of truth; fall back to the local vendored copy so nothing breaks if the package
# is not installed in this runtime. See szl-holdings/szl-substrate MIGRATION.md.
try:
    from szl_substrate import szl_dsse as _dsse  # type: ignore  # single source of truth
    _dsse_source = "szl-substrate"
except Exception:  # pragma: no cover
    try:
        import szl_dsse as _dsse  # type: ignore  # fall back to local vendored copy
        _dsse_source = "local-vendored"
    except Exception:
        _dsse = None  # honest UNSIGNED fallback
        _dsse_source = "unavailable"

from ayllu import __version__ as _AYLLU_VERSION
from ayllu import backend as _backend
from ayllu.lounge import Lounge
from ayllu.loop import run_turn
from ayllu.personas import ROSTER, get_persona

__version__ = _AYLLU_VERSION

# ---- cost + abuse bounds (public Space; real token cost once live) -----------
MAX_PROMPT_CHARS = 6000
COUNCIL_MAX = 5                                     # hard cap on participants / call
COUNCIL_DEBATE_MAX = 3  # debate doubles model calls; tighter cap bounds cost
COUNCIL_DEFAULT = ["Amaru", "Kamachiq", "Qhatuq"]  # architect · orchestrator · markets

# One process-wide lounge (in-memory, honest source labels).
_LOUNGE = Lounge()


class _RateBucket:
    """Tiny process-wide sliding-window limiter. Honest: bounds THIS process only."""

    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = int(limit)
        self.window = float(window_s)
        self._hits: list[float] = []
        self._lock = threading.Lock()

    def check(self) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            self._hits = [t for t in self._hits if now - t < self.window]
            if len(self._hits) >= self.limit:
                retry = self.window - (now - self._hits[0])
                return False, max(1, int(retry) + 1)
            self._hits.append(now)
            return True, 0


_ASK_BUCKET = _RateBucket(30, 60.0)      # 30 asks / minute (process-wide)
_COUNCIL_BUCKET = _RateBucket(8, 60.0)   # 8 councils / minute (process-wide)


def _receipt_sha(receipt: Optional[dict]) -> Optional[str]:
    if not receipt:
        return None
    try:
        body = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(body).hexdigest()
    except Exception:
        return None


def _make_receipt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap payload in a DSSE envelope (honest UNSIGNED if no cosign key)."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    honesty = "UNSIGNED — szl_dsse not present; no signature fabricated."
    if _dsse is not None:
        try:
            return _dsse.sign(payload)
        except Exception as exc:
            honesty = (f"UNSIGNED — szl_dsse.sign raised ({str(exc)[:80]}); "
                       "no signature fabricated.")
    return {
        "payloadType": "application/vnd.szl.receipt+json",
        "payload": base64.b64encode(body).decode("ascii"),
        "signatures": [],
        "signed": False,
        "honesty": honesty,
    }


# --- The /ayllu page: a working chat + council UI. 0-CDN (pure inline markup, no
#     external assets). `__NS__`/`__VERSION__` are substituted at render time so the
#     JS+CSS braces stay literal (no f-string brace-doubling). --------------------
_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ayllu — a11oy agent council</title>
<style>
:root{--void:#080c14;--panel:#0d1520;--line:#16202c;--teal:#3af4c8;--fg:#dfe7ee;--dim:#7f93a6;--gold:#d4a444}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
background:radial-gradient(60% 40% at 70% -10%,rgba(58,244,200,.07),transparent 60%),
radial-gradient(50% 35% at 10% 110%,rgba(212,164,68,.05),transparent 60%)}
main{max-width:980px;margin:0 auto;padding:36px 22px;position:relative;z-index:1}
h1{color:var(--teal);margin:0 0 4px;font-size:26px;display:flex;align-items:center;gap:10px}
h2{font-size:16px;margin:0 0 10px;color:var(--fg)}
.sub{color:var(--dim);margin:0 0 22px}
.badge{font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 8px;border-radius:20px;
border:1px solid var(--line);color:var(--dim)}
.badge.live{color:#0a1;background:#0a2a17;border-color:#1c5}
.badge.stub{color:#da3;background:#2a2109;border-color:#a83}
.badge.warn{color:#e66;background:#2a1010;border-color:#a44}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 16px;margin:0 0 16px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}
select,textarea,input{width:100%;background:#0a121c;color:var(--fg);border:1px solid var(--line);
border-radius:7px;padding:8px 10px;font:inherit}
.row select{flex:2}.row input{flex:1}
select[multiple]{height:auto}
textarea{resize:vertical;margin-bottom:8px}
button{background:var(--teal);color:#04140f;border:0;border-radius:7px;padding:8px 16px;
font-weight:700;cursor:pointer}
button.mini{background:transparent;color:var(--teal);border:1px solid var(--line);padding:3px 9px;
font-weight:600;font-size:12px}
.hint{color:var(--dim);font-size:12px;margin:0 0 8px}
.out{margin-top:10px}
.turn{border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-top:8px;background:#0a121c}
.turnh{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.chip{width:26px;height:26px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;
font-size:11px;font-weight:800;color:var(--fg);border:1px solid var(--line);flex:none}
.meta{color:var(--dim);font-size:12px;margin-left:auto}
.arch{color:var(--dim);font-size:12px}
.ans{margin-top:7px;white-space:pre-wrap}
.rcpt{color:var(--dim);font-size:12px;margin-top:8px}
.note{color:#da3;font-size:12px;margin-bottom:8px}
.err{color:#e66}
.stub{color:#da3;font-weight:700;font-size:11px}
.roundhdr{margin:14px 0 2px;color:var(--gold);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.loopchip{font-size:10px;border:1px solid var(--line);border-radius:12px;padding:1px 7px;color:var(--dim)}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);font-size:14px}
th{color:var(--teal);font-weight:600}
.lg{border-top:1px solid var(--line);padding:7px 0}
.src{color:var(--dim);font-size:11px}
.law{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--teal);
padding:12px 14px;border-radius:6px;color:var(--dim);margin-top:6px;font-size:13px}
code{color:var(--teal)}
html{scroll-behavior:smooth}
.topbar{position:sticky;top:0;z-index:20;background:rgba(8,12,20,.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.tb-wrap{max-width:980px;margin:0 auto;padding:10px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.tb-brand{color:var(--teal);font-weight:800;text-decoration:none;font-size:18px;display:flex;align-items:center;gap:8px}
.tb-nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.tb-nav a{color:var(--dim);text-decoration:none;font-size:13px}
.tb-nav a:hover{color:var(--fg)}
.tb-nav a.tb-home{color:var(--gold);font-weight:600}
section[id]{scroll-margin-top:72px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
.panel{background:#0a121c;border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:0}
.panel h3{margin:0 0 6px;font-size:13px;color:var(--teal);display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.kpi{font-size:19px;font-weight:800;color:var(--fg)}
.small{font-size:12px;color:var(--dim)}
.links{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.links a{color:var(--teal);text-decoration:none;font-size:12px;border:1px solid var(--line);border-radius:16px;padding:4px 11px}
.links a:hover{border-color:var(--teal)}
.tgl{display:flex;gap:7px;align-items:center;color:var(--dim);font-size:13px;margin:0 0 8px}
.tgl input{width:auto}
.prov{color:var(--dim);font-size:11px;margin-top:14px;line-height:1.6}
</style></head><body>
<header class="topbar"><div class="tb-wrap">
<a class="tb-brand" href="/ayllu">Ayllu <span id="badge" class="badge">…</span></a>
<nav class="tb-nav"><a href="#sec-ask">Ask</a><a href="#sec-council">Council</a><a href="#sec-roster">Roster</a><a href="#sec-lounge">Lounge</a><a href="#sec-organism">Organism</a><a href="#sec-mesh">Mesh</a><a class="tb-home" href="/console" title="Back to the a11oy command centre">&#8592; a11oy command centre</a></nav>
</div></header>
<main>
<h1>Ayllu</h1>
<p class="sub">The AlloyScape tribe, ingested and reborn as a11oy's own agent community —
<span id="count">?</span> personas, one guarded loop. v__VERSION__ ·
<span title="Curated, cited text appended to every persona's system prompt — no weights changed anywhere.">knowledge instilled, never "trained"</span></p>

<section class="card" id="sec-ask">
  <h2>Ask a persona</h2>
  <div class="row">
    <select id="persona"></select>
    <input id="difficulty" type="number" min="0" max="1" step="0.1"
           placeholder="difficulty 0–1 (optional)">
  </div>
  <textarea id="askprompt" rows="3" placeholder="Ask a persona…"></textarea>
  <button id="askbtn">Ask</button>
  <div id="askout" class="out"></div>
</section>

<section class="card" id="sec-council">
  <h2>Convene a council</h2>
  <p class="hint">Defaults to 3 core personas; select up to 5 (⌘/Ctrl-click). Fan-out is
  capped to protect cost. Debate mode runs exactly two bounded rounds
  (after arXiv:2305.14325) and is capped to 3 personas.</p>
  <select id="councilsel" multiple size="6"></select>
  <label class="tgl"><input type="checkbox" id="debate">
  Debate mode — positions, then explicit dissent &amp; converge (2× cost)</label>
  <textarea id="councilprompt" rows="3" placeholder="A question for the council…"></textarea>
  <button id="councilbtn">Convene</button>
  <div id="councilout" class="out"></div>
</section>

<section class="card" id="sec-roster">
  <h2>Roster</h2>
  <table id="roster"><thead><tr><th>Persona</th><th>Quechua</th><th>Archetype</th>
  <th>a11oy domain</th><th>Autonomy</th><th>Knowledge</th></tr></thead><tbody></tbody></table>
  <div class="src" style="margin-top:6px">"Instilled ✓" = the shared, cited Wave-13 leaders
  corpus is appended to that persona's system prompt at runtime. No model weights are
  changed anywhere — this is knowledge instillation, not training.</div>
</section>

<section class="card" id="sec-lounge">
  <h2>Lounge <button id="refreshlounge" class="mini">refresh</button></h2>
  <div id="lounge" class="out"></div>
</section>

<section class="card" id="sec-organism">
  <h2>The organism — anatomy · brain · formulas</h2>
  <div class="src" style="margin:.2rem 0 .6rem">The council is one organ of one governed
  organism. These panels read the same governed endpoints as the command centre — an
  unavailable endpoint says so rather than faking a value.</div>
  <div class="grid">
    <div class="panel"><h3>Formulas <span class="small" id="f-badge">…</span></h3><div id="f-out" class="small">loading…</div></div>
    <div class="panel"><h3>Doctrine lock <span class="small" id="d-badge">…</span></h3><div id="d-out" class="small">loading…</div></div>
    <div class="panel"><h3>Sovereign energy <span class="small" id="e-badge">…</span></h3><div id="e-out" class="small">loading…</div></div>
  </div>
  <div class="links">
    <a href="/living-anatomy">Living anatomy</a>
    <a href="/formulas">PURIQ formulas</a>
    <a href="/wires">The constitution</a>
    <a href="/api/__NS__/v1/brain/graph" title="Full brain graph JSON (~4 MB)">Brain graph (raw JSON)</a>
    <a href="/console">Command centre</a>
  </div>
</section>

<section class="card" id="sec-mesh">
  <h2>Mesh &amp; observability <span class="stub" id="mesh-badge">&#8230;</span></h2>
  <div class="src" style="margin:.2rem 0 .6rem">Live platform context the council runs
  inside, read from the same governed endpoints the command centre uses. Shown honestly:
  an unavailable endpoint says so rather than faking a value.</div>
  <div id="mesh-out" class="out"></div>
  <div id="obs-out" class="out" style="margin-top:.5rem"></div>
</section>

<div class="law"><b>Bounded-autonomy law.</b> Every persona runs under a11oy's
fail-closed Λ-gate; state-changing actions require two-person attestation. The tribe's
"always execute" mandate is deliberately <b>not</b> adopted. Answers come from a11oy's
own model backend + router; when no inference credential is set on this Space,
<code>ask</code>/<code>council</code> return a clearly-labeled stub — never a fabricated
answer. Debate mode is bounded to exactly two rounds. These turns do direct completion
only (no tool dispatch yet).</div>

<p class="prov"><b>Provenance.</b> Council patterns studied from the field's leaders and
rebuilt in a11oy's own idiom — MetaGPT (SOP role handoffs), CrewAI (role/goal remits),
LangGraph (bounded graph loops), CAMEL (agent societies), OpenAI Agents SDK / Google ADK
(visible handoffs &amp; guardrails) — all permissive-licensed; debate-then-converge after
arXiv:2305.14325. No code was copied from pattern-only sources. Personas carry this as
instilled knowledge (cited text in the system prompt); nothing here was "trained".</p>
</main>
<script>
const NS="__NS__";
const api = p => `/api/${NS}/v1/ayllu/`+p;
const gapi = p => `/api/${NS}/v1/`+p;
async function j(url,opts){const r=await fetch(url,opts);
  let d={};try{d=await r.json();}catch(e){}return {ok:r.ok,status:r.status,data:d};}
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function hue(n){let h=0;for(const c of String(n))h=(h*31+c.charCodeAt(0))%360;return h;}
function chip(n){const h=hue(n);
  return `<span class="chip" style="background:hsl(${h} 55% 20%);border-color:hsl(${h} 55% 38%)">`
       + esc(String(n).slice(0,2).toUpperCase())+`</span>`;}
function renderTurn(t){
  const ans = t.answer!=null ? esc(t.answer) : '<i>'+esc(t.honesty)+'</i>';
  const model = t.model?('model: '+esc(t.model)):'no model';
  const tier = (t.tier&&t.tier.route)?(' · tier(advisory): '+esc(t.tier.route)):'';
  const stub = t.stub?' · <span class="stub">STUB</span>':'';
  const loop = (t.loop&&t.loop.mode)?`<span class="loopchip" title="${esc(t.loop.note||'')}">loop: ${esc(t.loop.mode)}</span>`:'';
  return `<div class="turn"><div class="turnh">${chip(t.persona)}<b>${esc(t.persona)}</b>`
       + `<span class="arch">${esc(t.archetype||'')}</span>${loop}`
       + `<span class="meta">${model}${tier}${stub}</span></div>`
       + `<div class="ans">${ans}</div></div>`;
}
async function loadRoster(){
  const {ok,data}=await j(api('roster'));
  if(!ok)return;
  document.getElementById('count').textContent=data.count;
  const b=data.backend||{}, badge=document.getElementById('badge'), mode=b.mode||'?';
  badge.textContent=mode.toUpperCase();
  badge.className='badge '+(mode==='live'?'live':mode==='stub'?'stub':'warn');
  badge.title=b.note||'';
  const sel=document.getElementById('persona'), csel=document.getElementById('councilsel');
  const rows=[];
  (data.personas||[]).forEach(p=>{
    const o=document.createElement('option');o.value=p.name;
    o.textContent=p.name+' — '+p.domain;sel.appendChild(o);
    csel.appendChild(o.cloneNode(true));
    const kn=p.knowledge_instilled?'instilled ✓':'—';
    rows.push(`<tr><td>${chip(p.name)} <b>${esc(p.name)}</b></td><td>${esc(p.quechua)}</td>`
      +`<td>${esc(p.archetype)}</td><td>${esc(p.domain)}</td>`
      +`<td>${esc(p.autonomy_level)}</td><td class="src">${kn}</td></tr>`);
  });
  document.querySelector('#roster tbody').innerHTML=rows.join('');
}
document.getElementById('askbtn').onclick=async()=>{
  const persona=document.getElementById('persona').value;
  const prompt=document.getElementById('askprompt').value.trim();
  const d=document.getElementById('difficulty').value;
  const out=document.getElementById('askout');
  if(!prompt){out.innerHTML='<span class="err">enter a prompt</span>';return;}
  out.textContent='…thinking';
  const body={persona,prompt}; if(d!=='')body.difficulty=parseFloat(d);
  const {ok,status,data}=await j(api('ask'),{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  if(!ok){out.innerHTML='<span class="err">'+esc(data.error||('HTTP '+status))+'</span>'
    +(data.retry_after_s?(' (retry in '+data.retry_after_s+'s)'):'');return;}
  const r=data.receipt||{}, sig=r.signed?'signed':'UNSIGNED';
  out.innerHTML=renderTurn(data.turn)
    +`<div class="rcpt">receipt: ${sig} · ask ${esc(String(data.ask_id)).slice(0,8)}</div>`;
};
document.getElementById('councilbtn').onclick=async()=>{
  const prompt=document.getElementById('councilprompt').value.trim();
  const out=document.getElementById('councilout');
  if(!prompt){out.innerHTML='<span class="err">enter a prompt</span>';return;}
  const picks=[...document.getElementById('councilsel').selectedOptions].map(o=>o.value);
  const debate=document.getElementById('debate').checked;
  out.textContent=debate?'…convening (debate: 2 bounded rounds)':'…convening';
  const body={prompt}; if(picks.length)body.personas=picks; if(debate)body.debate=true;
  const {ok,status,data}=await j(api('council'),{method:'POST',
    headers:{'content-type':'application/json'},body:JSON.stringify(body)});
  if(!ok){out.innerHTML='<span class="err">'+esc(data.error||('HTTP '+status))+'</span>'
    +(data.retry_after_s?(' (retry in '+data.retry_after_s+'s)'):'');return;}
  const res=data.result||{}, rounds=res.rounds||[];
  const cap=res.cap_note?('<div class="note">'+esc(res.cap_note)+'</div>'):'';
  const r1=rounds.filter(t=>(t.round||1)===1), r2=rounds.filter(t=>t.round===2);
  let html=cap;
  if(r2.length){
    html+='<div class="roundhdr">Round 1 — opening positions</div>'+r1.map(renderTurn).join('');
    html+='<div class="roundhdr">Round 2 — debate &amp; converge (final)</div>'+r2.map(renderTurn).join('');
  }else{
    html+=r1.map(renderTurn).join('');
    if(res.mode==='single-round'&&document.getElementById('debate').checked){
      html+='<div class="src">debate skipped honestly: fewer than two personas produced answers.</div>';
    }
  }
  out.innerHTML=html;
};
async function loadLounge(){
  const {ok,data}=await j(api('lounge')), out=document.getElementById('lounge');
  if(!ok){out.textContent='—';return;}
  const items=(data.recent||[]).slice().reverse();
  out.innerHTML=items.length? items.map(m=>`<div class="lg"><b>${esc(m.persona)}</b> `
    +`<span class="src">${esc(m.source)}</span><div>${esc(m.text)}</div></div>`).join('')
    :'<i>empty</i>';
}
document.getElementById('refreshlounge').onclick=loadLounge;
function unavailable(el,status){el.innerHTML='<span class="src">endpoint unavailable ('
  +esc(String(status))+') — shown honestly, not faked.</span>';}
async function loadFormulas(){
  const b=document.getElementById('f-badge'), out=document.getElementById('f-out');
  const {ok,status,data}=await j(gapi('formulas'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  b.textContent='live';
  const fs=(data.formulas||[]).slice(0,4);
  out.innerHTML='<div class="kpi">'+esc(String(data.count??'—'))+'</div>'
    +'<div class="small">registered formulas</div>'
    +fs.map(f=>`<div class="lg"><code>${esc(f.name)}</code><br><span class="src">${esc(f.proof_status||'')}</span></div>`).join('')
    +'<div class="src" style="margin-top:6px">Λ-aggregator uniqueness remains Conjecture 1 — never claimed proven.</div>';
}
async function loadDoctrine(){
  const b=document.getElementById('d-badge'), out=document.getElementById('d-out');
  const {ok,status,data}=await j(gapi('honest'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  const d=data.doctrine_lock||{};
  b.textContent=esc(d.state||'?');
  out.innerHTML='<div class="kpi">'+esc(String(d.declarations??'—'))+'</div>'
    +'<div class="small">Lean declarations · '+esc(String(d.axioms??'—'))+' axioms · '
    +esc(String(d.sorries??'—'))+' sorries (honest count)</div>'
    +'<div class="lg small">'+esc(d.lambda_note||'')+'</div>';
}
async function loadEnergy(){
  const b=document.getElementById('e-badge'), out=document.getElementById('e-out');
  const {ok,status,data}=await j(gapi('energy/live'));
  if(!ok){b.textContent='offline';unavailable(out,status);return;}
  b.textContent=esc(data.label||'?');
  const nodes=data.nodes||[];
  const live=nodes.filter(n=>n.live).length;
  out.innerHTML='<div class="kpi">'+(data.total_watts!=null?esc(String(data.total_watts))+' W':'—')+'</div>'
    +'<div class="small">'+live+'/'+nodes.length+' sovereign nodes live'
    +(data.total_watts==null?' — no wattage fabricated':'')+'</div>'
    +nodes.slice(0,3).map(n=>`<div class="lg small">${n.live?'●':'○'} ${esc(n.name)}</div>`).join('');
}
async function loadMesh(){
  const badge=document.getElementById('mesh-badge'), out=document.getElementById('mesh-out');
  const {ok,status,data}=await j(gapi('mesh/state'));
  if(!ok){badge.textContent='offline';unavailable(out,status);return;}
  badge.textContent='live';
  const wires=data.wires||{};
  const rows=Object.entries(wires).map(([k,w])=>
    `<tr><td><b>${esc(k)}</b></td><td>${esc(w.edge||'')}</td><td class="src">${esc(w.status||'')}</td></tr>`);
  out.innerHTML=rows.length?('<table><thead><tr><th>Wire</th><th>Edge</th><th>Status</th></tr></thead><tbody>'
    +rows.join('')+'</tbody></table>'
    +'<div class="src" style="margin-top:5px">doctrine '+esc(data.doctrine||'?')
    +' · khipu nodes: '+esc(String(data.khipu_nodes??'—'))+'</div>')
    :'<div class="lg"><b>mesh</b> <span class="src">no wires reported</span></div>';
}
async function loadObs(){
  const out=document.getElementById('obs-out');
  const {ok,status,data}=await j(gapi('observability/summary'));
  if(!ok){unavailable(out,status);return;}
  out.innerHTML='<div class="lg"><b>observability</b><pre class="src" style="white-space:pre-wrap;margin:.3rem 0 0">'
    +esc(JSON.stringify(data.melt||data,null,2).slice(0,600))+'</pre></div>';
}
loadRoster();loadLounge();loadMesh();loadObs();loadFormulas();loadDoctrine();loadEnergy();
</script>
</body></html>"""


def _page_html(ns: str) -> str:
    return _PAGE.replace("__NS__", ns).replace("__VERSION__", str(__version__))


def register(app, ns: str = "a11oy") -> str:
    """Mount the ayllu routes on `app`. Returns a status string."""
    from fastapi import Request
    from fastapi.responses import HTMLResponse, JSONResponse

    async def _roster(request: "Request") -> "JSONResponse":
        return JSONResponse({
            "count": len(ROSTER),
            "namespace": ns,
            "personas": [p.metadata() for p in ROSTER],
            "backend": _backend.backend_status(),
            "law": "a11oy bounded-autonomy (fail-closed Λ-gate); the tribe's unbounded "
                   "'always execute' mandate is NOT adopted",
            "provenance": "ingested from the AlloyScape tribe design; see ayllu/INGEST.md",
            "version": __version__,
        })

    async def _ask(request: "Request") -> "JSONResponse":
        ok, retry = _ASK_BUCKET.check()
        if not ok:
            return JSONResponse(
                {"error": "rate limited (process-wide ask budget)", "retry_after_s": retry},
                status_code=429, headers={"Retry-After": str(retry)})
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "request body must be a JSON object"},
                                status_code=422)
        name = body.get("persona")
        prompt = body.get("prompt")
        if not name or not prompt:
            return JSONResponse({"error": "'persona' and 'prompt' are required"},
                                status_code=422)
        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            return JSONResponse(
                {"error": f"'prompt' must be a string ≤ {MAX_PROMPT_CHARS} chars",
                 "max_chars": MAX_PROMPT_CHARS}, status_code=422)
        p = get_persona(name)
        if p is None:
            return JSONResponse(
                {"error": f"unknown persona '{name}'",
                 "known": [x.name for x in ROSTER]}, status_code=404)
        raw_diff = body.get("difficulty")
        try:
            difficulty = None if raw_diff is None else float(raw_diff)
        except (TypeError, ValueError):
            return JSONResponse(
                {"error": "'difficulty' must be a number between 0 and 1"},
                status_code=422)
        turn = await run_turn(p, prompt, model_complete=_backend.model_complete,
                              difficulty=difficulty)
        ask_id = str(uuid.uuid4())
        receipt = _make_receipt({
            "ask_id": ask_id,
            "persona": p.name,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "tier_advisory": turn.get("tier", {}).get("route"),
            "model": turn.get("model"),
            "stub": turn.get("stub"),
            "energy_receipt_sha256": _receipt_sha(turn.get("energy_receipt")),
            "honesty": turn.get("honesty"),
        })
        _LOUNGE.post(
            p.name, turn.get("answer") or turn.get("honesty"),
            source=("brain" if turn.get("answer") is not None else "persona-fallback"))
        return JSONResponse({"ask_id": ask_id, "turn": turn, "receipt": receipt})

    async def _council(request: "Request") -> "JSONResponse":
        ok, retry = _COUNCIL_BUCKET.check()
        if not ok:
            return JSONResponse(
                {"error": "rate limited (process-wide council budget)",
                 "retry_after_s": retry},
                status_code=429, headers={"Retry-After": str(retry)})
        try:
            body = await request.json()
        except Exception as e:
            return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"error": "request body must be a JSON object"},
                                status_code=422)
        prompt = body.get("prompt")
        if not prompt:
            return JSONResponse({"error": "'prompt' is required"}, status_code=422)
        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            return JSONResponse(
                {"error": f"'prompt' must be a string ≤ {MAX_PROMPT_CHARS} chars",
                 "max_chars": MAX_PROMPT_CHARS}, status_code=422)
        debate = bool(body.get("debate", False))
        max_n = COUNCIL_DEBATE_MAX if debate else COUNCIL_MAX
        requested = body.get("personas")
        cap_note = None
        if requested:
            if not isinstance(requested, list):
                return JSONResponse({"error": "'personas' must be a list"},
                                    status_code=422)
            names = [str(n) for n in requested][:max_n]
            if len(requested) > max_n:
                cap_note = (f"requested {len(requested)} personas; capped to "
                            f"{max_n} to bound cost"
                            + (" (debate mode runs two rounds)" if debate else ""))
        else:
            names = list(COUNCIL_DEFAULT)[:max_n]
            cap_note = (f"no personas specified; convened the {len(names)} core "
                        "personas (Amaru, Kamachiq, Qhatuq)")
        personas = [get_persona(n) for n in names]
        personas = [p for p in personas if p is not None]
        if not personas:
            return JSONResponse(
                {"error": "no known personas in request",
                 "known": [x.name for x in ROSTER]}, status_code=422)
        result = await _LOUNGE.deliberate(prompt, personas,
                                          model_complete=_backend.model_complete,
                                          debate=debate)
        if cap_note:
            result["cap_note"] = cap_note
        council_id = str(uuid.uuid4())
        receipt = _make_receipt({
            "council_id": council_id,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "participants": result["participants"],
            "mode": result.get("mode"),
            "models": [r.get("model") for r in result.get("rounds", [])],
        })
        return JSONResponse({"council_id": council_id, "result": result,
                             "receipt": receipt})

    async def _lounge_feed(request: "Request") -> "JSONResponse":
        return JSONResponse({"count": len(_LOUNGE.feed),
                             "recent": _LOUNGE.recent(50)})

    async def _page(request: "Request") -> "HTMLResponse":
        return HTMLResponse(_page_html(ns))

    app.add_api_route(f"/api/{ns}/v1/ayllu/roster", _roster, methods=["GET"],
                      tags=["ayllu"],
                      summary="a11oy-native agent roster + live/stub backend status")
    app.add_api_route(f"/api/{ns}/v1/ayllu/ask", _ask, methods=["POST"],
                      tags=["ayllu"],
                      summary="Ask one persona — bounded, honest, receipted")
    app.add_api_route(f"/api/{ns}/v1/ayllu/council", _council, methods=["POST"],
                      tags=["ayllu"],
                      summary="Bounded multi-persona deliberation (capped fan-out; optional 2-round debate mode after arXiv:2305.14325)")
    app.add_api_route(f"/api/{ns}/v1/ayllu/lounge", _lounge_feed, methods=["GET"],
                      tags=["ayllu"], summary="Recent collaboration lounge feed")
    app.add_api_route("/ayllu", _page, methods=["GET"], include_in_schema=False)

    return (
        f"ok — ayllu registered: {len(ROSTER)} personas; live model backend "
        f"({_backend.backend_status().get('mode')}); bounded-autonomy Λ-gate; "
        f"/ayllu + /api/{ns}/v1/ayllu/roster|ask|council|lounge; "
        f"debate-mode council; version={__version__}"
    )
