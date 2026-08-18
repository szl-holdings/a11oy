# SPDX-License-Identifier: Apache-2.0
"""Zero-CDN ORO operational dashboard."""
from __future__ import annotations

import html


def render_dashboard(api_prefix: str = "/api/a11oy/v1/oro") -> str:
    prefix = html.escape(api_prefix, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>ORO — Obligation-Ranked Orbits</title>
<meta name="description" content="Source-bound ORO rank, barrier, evidence, signer, and refusal readback.">
<style>
:root{{--bg:#071018;--panel:#0e1b26;--line:#203648;--text:#e7f1f5;--muted:#91a8b7;--ok:#75e6b1;--warn:#ffd27a;--bad:#ff8e8e;--accent:#56c9d8;--mono:ui-monospace,SFMono-Regular,Consolas,monospace}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#102432 0,#071018 45%);color:var(--text);font:15px/1.5 system-ui,sans-serif;min-height:100vh}}a{{color:var(--accent)}}
.wrap{{width:min(1180px,100%);margin:auto;padding:24px}}header{{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin:8px 0 24px}}h1{{font-size:clamp(1.8rem,5vw,3.6rem);line-height:1;margin:0}}h2{{font-size:1rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:0 0 14px}}p{{margin:.45rem 0}}.mono{{font-family:var(--mono);overflow-wrap:anywhere}}.sub{{max-width:760px;color:var(--muted)}}
.badge{{display:inline-flex;align-items:center;min-height:32px;padding:5px 10px;border:1px solid var(--line);border-radius:999px;font:12px var(--mono);background:#0a151e}}.badge.ready{{color:var(--ok);border-color:#2f6d56}}.badge.bad{{color:var(--bad);border-color:#713d43}}
.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}}.card{{grid-column:span 4;background:linear-gradient(155deg,rgba(16,34,46,.96),rgba(8,20,29,.98));border:1px solid var(--line);border-radius:15px;padding:18px;min-width:0;box-shadow:0 16px 50px rgba(0,0,0,.16)}}.wide{{grid-column:span 8}}.full{{grid-column:1/-1}}.metric{{font:700 clamp(1.4rem,4vw,2.5rem) var(--mono);margin:4px 0}}.label{{color:var(--muted);font:11px var(--mono);text-transform:uppercase;letter-spacing:.09em}}.stack{{display:grid;gap:9px}}.row{{padding:10px 0;border-top:1px solid var(--line)}}.row:first-child{{border-top:0}}.kv{{display:grid;grid-template-columns:minmax(120px,.45fr) 1fr;gap:12px}}.state-ready{{color:var(--ok)}}.state-bad{{color:var(--bad)}}.state-warn{{color:var(--warn)}}button{{min-height:44px;border:1px solid #2a5967;border-radius:9px;background:#102c37;color:var(--text);padding:8px 14px;font-weight:700;cursor:pointer}}button:hover{{border-color:var(--accent)}}pre{{white-space:pre-wrap;word-break:break-word;background:#07131c;border:1px solid var(--line);border-radius:10px;padding:12px;max-height:360px;overflow:auto;color:#c9dce5}}.empty{{color:var(--muted);font-style:italic}}
@media(max-width:850px){{.card,.wide{{grid-column:1/-1}}header{{display:block}}header .badge{{margin-top:14px}}}}@media(max-width:520px){{.wrap{{padding:16px}}.card{{padding:15px}}.kv{{grid-template-columns:1fr;gap:3px}}}}
</style>
</head>
<body>
<main class="wrap">
<header><div><div class="label">A11oy control plane</div><h1>ORO</h1><p class="sub">Obligation-Ranked Orbits. Every continuing barrier must reduce rank; every halt preserves evidence; no role can release or self-certify its own candidate.</p></div><span id="readyBadge" class="badge">OBSERVING</span></header>
<section class="grid" aria-label="ORO operational status">
<article class="card"><h2>Readiness</h2><div id="readyState" class="metric">—</div><div id="readyDetail" class="mono sub">No observation yet.</div></article>
<article class="card"><h2>Plans</h2><div id="planCount" class="metric">—</div><div class="label">persisted</div></article>
<article class="card"><h2>Orbits</h2><div id="orbitCount" class="metric">—</div><div class="label">persisted</div></article>
<article class="card wide"><h2>Runtime contract</h2><div id="contract" class="stack"><div class="empty">No observation yet.</div></div></article>
<article class="card"><h2>Evidence counts</h2><div id="counts" class="stack"><div class="empty">No observation yet.</div></div></article>
<article class="card full"><h2>Latest plans</h2><div id="plans" class="stack"><div class="empty">No persisted plans.</div></div></article>
<article class="card full"><h2>Latest orbits</h2><div id="orbits" class="stack"><div class="empty">No persisted orbits.</div></div></article>
<article class="card full"><h2>Negative evidence</h2><div id="negatives" class="stack"><div class="empty">No persisted negative results.</div></div></article>
<article class="card full"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><h2 style="margin:0">Raw source-bound readback</h2><button id="refresh" type="button">Refresh</button></div><pre id="raw">No observation yet.</pre></article>
</section>
</main>
<script>
'use strict';
const API={prefix!r};
const $=id=>document.getElementById(id);
const safeText=(node,value)=>{{node.textContent=String(value??'—')}};
function row(label,value,klass=''){{const r=document.createElement('div');r.className='row kv';const l=document.createElement('div');l.className='label';l.textContent=label;const v=document.createElement('div');v.className='mono '+klass;v.textContent=String(value??'—');r.append(l,v);return r}}
function renderList(node,items,fields){{node.replaceChildren();if(!Array.isArray(items)||!items.length){{const e=document.createElement('div');e.className='empty';e.textContent='No persisted records.';node.append(e);return}}for(const item of items){{const r=document.createElement('div');r.className='row';for(const [label,key] of fields)r.append(row(label,item?.[key]));node.append(r)}}}}
async function get(path){{const res=await fetch(API+path,{{headers:{{Accept:'application/json'}},cache:'no-store'}});let body;try{{body=await res.json()}}catch{{body={{error:'non-JSON response',status:res.status}}}}if(!res.ok)throw Object.assign(new Error(body?.error?.message||body?.error||`HTTP ${{res.status}}`),{{body,status:res.status}});return body}}
async function refresh(){{safeText($('readyBadge'),'OBSERVING');$('readyBadge').className='badge';const raw={{observedAt:new Date().toISOString()}};try{{const [ready,contract,plans,orbits,negatives,counts]=await Promise.all([get('/readyz'),get('/contract'),get('/plans?limit=20'),get('/orbits?limit=20'),get('/negative-results?limit=20'),get('/counts')]);Object.assign(raw,{{ready,contract,plans,orbits,negatives,counts}});const ok=ready.ready===true;safeText($('readyBadge'),ok?'READY':'UNAVAILABLE');$('readyBadge').className='badge '+(ok?'ready':'bad');safeText($('readyState'),ready.state);$('readyState').className='metric '+(ok?'state-ready':'state-bad');safeText($('readyDetail'),`storage=${{ready.storage?.state??'—'}} · signer=${{ready.signer?.state??'—'}}`);safeText($('planCount'),counts.plans??0);safeText($('orbitCount'),counts.orbit_runs??0);const c=$('contract');c.replaceChildren(row('rank',contract.rank_schema),row('termination',contract.normal_termination),row('codex digest',contract.codex_digest),row('machine checked',contract.machine_checked_termination),row('release effector',contract.release_effector));const cn=$('counts');cn.replaceChildren();for(const key of Object.keys(counts).sort())cn.append(row(key,counts[key]));renderList($('plans'),plans.items,[['plan','plan_id'],['kind','orbit_kind'],['status','status'],['digest','plan_digest']]);renderList($('orbits'),orbits.items,[['orbit','orbit_id'],['plan','plan_id'],['generation','generation'],['status','status']]);renderList($('negatives'),negatives.items,[['id','negative_id'],['reason','reason'],['created','created_at']]);}}catch(error){{raw.failure={{message:error.message,status:error.status??null,body:error.body??null}};safeText($('readyBadge'),'UNAVAILABLE');$('readyBadge').className='badge bad';safeText($('readyState'),'UNAVAILABLE');$('readyState').className='metric state-bad';safeText($('readyDetail'),error.message);}}safeText($('raw'),JSON.stringify(raw,null,2))}}
$('refresh').addEventListener('click',refresh);refresh();setInterval(refresh,30000);
</script>
</body>
</html>"""
