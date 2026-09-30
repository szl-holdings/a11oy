# SPDX-License-Identifier: Apache-2.0
"""Finance-only source workbench for the existing flagship renderer.

All requests use the existing same-origin, read-only finance projection. Provider
strings are rendered as text. This adds no provider client, credential field,
order path, model inference, ledger, or publication side effect.
"""
from __future__ import annotations

WORKSPACE_VERSION = "finance-source-workbench/v1"
CSS = r'''
.finance-desk{margin-top:32px;display:grid;gap:16px;min-width:0}.finance-desk *{box-sizing:border-box;min-width:0}.finance-desk .fin-head{display:flex;gap:12px;flex-wrap:wrap;justify-content:space-between;align-items:center}.finance-desk h2{margin:0;font-size:clamp(22px,4vw,34px)}.finance-desk h3{font-size:18px;margin:0 0 12px}.finance-desk .fin-note{font-size:14px;line-height:1.65;color:var(--muted);overflow-wrap:anywhere}.finance-desk .fin-state{font:700 12px ui-monospace,monospace;letter-spacing:.08em;border:1px solid var(--line);padding:10px;overflow-wrap:anywhere}.finance-desk .fin-grid{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.4fr);gap:16px}.finance-desk .fin-fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:12px;margin:16px 0}.finance-desk label{display:block;font-size:14px;line-height:1.6}.finance-desk input,.finance-desk select{display:block;width:100%;max-width:100%;min-height:44px;background:#0b1119;color:var(--text,#edf3ff);border:1px solid #50637d;border-radius:6px;padding:10px;font-size:16px}.finance-desk button{min-width:44px;min-height:44px;white-space:normal}.finance-desk button:disabled{opacity:.65;cursor:not-allowed}.finance-desk .fin-actions{display:flex;flex-wrap:wrap;gap:10px}.finance-desk :focus-visible{outline:3px solid var(--accent,#a6c8ff);outline-offset:3px}.finance-desk .fin-scroll{overflow:auto;max-width:100%;border:1px solid var(--line)}.finance-desk table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:13px}.finance-desk th,.finance-desk td{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.finance-desk summary{min-height:44px;padding:12px;cursor:pointer}.finance-desk caption{padding:10px;text-align:left;line-height:1.5}.finance-desk svg{display:block;width:100%;height:auto;max-height:280px;border:1px solid var(--line);background:linear-gradient(130deg,rgba(86,136,255,.09),rgba(136,80,255,.04))}.finance-desk .fin-provenance{white-space:pre-wrap;overflow-wrap:anywhere;max-height:380px;overflow:auto;font-size:12px;line-height:1.6}.finance-desk .fin-instrument{min-height:170px;background:radial-gradient(ellipse at 30% 0,rgba(94,143,255,.13),transparent 70%)}.finance-desk [hidden]{display:none!important}@media(max-width:800px){.finance-desk .fin-grid{grid-template-columns:1fr}.finance-desk th,.finance-desk td{padding:6px}}@media(prefers-reduced-motion:reduce){.finance-desk *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}@media(forced-colors:active){.finance-desk input,.finance-desk select,.finance-desk button,.finance-desk svg{border:1px solid CanvasText}.finance-desk polyline{stroke:CanvasText!important}}
'''

SCRIPT = r'''
(()=>{'use strict';
const $=id=>document.getElementById(id), area=$('fin-desk');
if(!area)return;
const defaults={
 'polymarket-markets':{limit:'12',offset:'0'},'polymarket-book':{token_id:''},
 'polymarket-history':{token_id:'',interval:'1d',fidelity:'60'},
 'kalshi-markets':{limit:'12',cursor:'',series_ticker:''},'kalshi-book':{ticker:'',depth:'20'},
 'coinbase-products':{},'coinbase-ticker':{product:'BTC-USD'},
 'coinbase-candles':{product:'BTC-USD',granularity:'3600',end:'',count:'60'},
 'sec-submissions':{cik:'320193',limit:'10'},'sec-companyfacts':{cik:'320193',limit:'10'},
 'treasury-rates':{limit:'12'},'treasury-debt':{limit:'12'},'bls-series':{series_id:'CUUR0000SA0'},
 'fred-series':{},'alpaca-quote':{},'alpaca-bars':{}};
const privateIds=new Set(['fred-series','alpaca-quote','alpaca-bars']);
const sha=/^[0-9a-f]{40}$/, digest=/^[0-9a-f]{64}$/, code=/^[A-Z][A-Z0-9_]{0,95}$/;
const states=new Set(['NOT_PROBED','SNAPSHOT','CACHED','STALE','UNAVAILABLE','EXPIRED']);
let revision=null, specs=new Map(), registryEpoch=0, queryEpoch=0, pending=null, receipt=null;
function text(tag,value){const e=document.createElement(tag);e.textContent=value;return e;}
function showState(value){$('fin-result-state').textContent=value;}
function clearResult(){receipt=null;$('fin-export').disabled=true;$('fin-result-table').replaceChildren();$('fin-chart').replaceChildren();$('fin-detail').textContent='No accepted observation.';$('fin-chart-note').textContent='No chart observation.';}
function invalidate(){queryEpoch++;if(pending)pending.abort();pending=null;clearResult();}
async function readJson(path,signal){
 const response=await fetch(path,{method:'GET',credentials:'omit',cache:'no-store',redirect:'error',signal,headers:{Accept:'application/json'}});
 if(!/^application\/(json|[a-z0-9.+-]+\+json)(;|$)/i.test(response.headers.get('content-type')||''))throw Error('INVALID_RESPONSE_TYPE');
 const rawLength=response.headers.get('content-length');
 if(rawLength!==null&&(!/^\d+$/.test(rawLength)||Number(rawLength)>4000000))throw Error('RESPONSE_TOO_LARGE');
 const reader=response.body.getReader(),chunks=[];let bytes=0;
 try{for(;;){const part=await reader.read();if(part.done)break;bytes+=part.value.length;if(bytes>4000000)throw Error('RESPONSE_TOO_LARGE');chunks.push(part.value);}}
 catch(error){await reader.cancel();throw error;}
 const raw=new Uint8Array(bytes);let at=0;for(const part of chunks){raw.set(part,at);at+=part.length;}
 return {status:response.status,body:JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw))};
}
function identity(body,schema){return body&&body.schema===schema&&body.source_revision===revision&&body.execution_enabled===false;}
function form(){
 invalidate();const source=$('fin-source').value,spec=specs.get(source);$('fin-fields').replaceChildren();
 $('fin-observe').disabled=!spec||privateIds.has(source)||spec.private!==false;
 if(!spec){showState('UNAVAILABLE');return;}
 $('fin-operation').textContent=spec.operation;
 if(privateIds.has(source)){showState('OWNER-ONLY SOURCE — unavailable in this public Space');return;}
 for(const name of spec.parameters){const label=text('label',name.replaceAll('_',' '));const input=document.createElement('input');input.name=name;input.id='fin-param-'+name;input.maxLength=2048;input.autocomplete='off';input.value=defaults[source][name]||'';label.htmlFor=input.id;label.append(input);$('fin-fields').append(label);}
 showState('READY TO REQUEST — not a connectivity claim');
}
async function registry(){
 const generation=++registryEpoch;invalidate();revision=null;specs.clear();$('fin-source').replaceChildren();$('fin-source').disabled=true;$('fin-observe').disabled=true;$('fin-provider-body').replaceChildren();$('fin-registry-state').textContent='CHECKING SOURCE IDENTITY';
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
 try{
  const witness=await readJson('/api/source',controller.signal);const value=witness.body;
  if(witness.status!==200||value.deployment_source!=='szl-holdings/a11oy'||!sha.test(value.source_revision)||value.source_revision==='0'.repeat(40))throw Error('INVALID_SOURCE_WITNESS');
  const result=await readJson('/api/finance/providers',controller.signal);
  if(generation!==registryEpoch)return;
  revision=value.source_revision;const body=result.body;
  if(result.status!==200||!identity(body,'szl.finance.providers/v1')||body.read_only!==true||body.canonical_repository!=='szl-holdings/a11oy'||!Array.isArray(body.sources)||body.sources.length!==Object.keys(defaults).length)throw Error('INVALID_PROVIDER_CONTRACT');
  const next=new Map();
  for(const row of body.sources){
   if(!row||!Object.hasOwn(defaults,row.id)||next.has(row.id)||typeof row.operation!=='string'||row.operation.length>500||typeof row.provider!=='string'||row.private!==privateIds.has(row.id)||!Array.isArray(row.parameters)||row.parameters.length>8||!states.has(row.observed_connection)||!['PRESENT','MISSING'].includes(row.configuration))throw Error('INVALID_PROVIDER_CONTRACT');
   if(!row.private&&(row.parameters.length!==Object.keys(defaults[row.id]).length||row.parameters.some(k=>!Object.hasOwn(defaults[row.id],k))||new Set(row.parameters).size!==row.parameters.length))throw Error('INVALID_PARAMETERS');
   next.set(row.id,row);
  }
  specs=next;
  for(const [id,row] of specs){const option=text('option',id+(row.private?' — owner-only':''));option.value=id;option.disabled=row.private;$('fin-source').append(option);const tr=document.createElement('tr');for(const value of [id,row.observed_connection,row.private?'OWNER-ONLY':row.configuration==='MISSING'?'CONFIGURATION MISSING':'PUBLIC READ'])tr.append(text('td',value));$('fin-provider-body').append(tr);}
  $('fin-source').disabled=false;$('fin-source').value='coinbase-ticker';$('fin-registry-state').textContent='16 ADAPTERS / 13 PUBLIC / 3 OWNER-ONLY — last-request state only';$('fin-revision').textContent=revision;form();
 }catch(error){if(generation!==registryEpoch)return;revision=null;specs.clear();$('fin-source').disabled=true;$('fin-observe').disabled=true;$('fin-registry-state').textContent='UNAVAILABLE — provider registry not accepted';$('fin-revision').textContent='UNAVAILABLE';showState('UNAVAILABLE');clearResult();}
 finally{clearTimeout(timer);}
}
function scalar(value){return value===null||value===undefined?'Unavailable':typeof value==='object'?JSON.stringify(value):String(value);}
function table(data){
 const rows=Array.isArray(data.items)?data.items:[data];const table=document.createElement('table');table.append(text('caption','Displaying '+Math.min(rows.length,30)+' of '+rows.length+' returned records. Bounded response, not an all-market census. Null is unavailable; zero is retained.'));
 if(!rows.length){$('fin-result-table').append(text('p','EMPTY — the source returned no records.'));return;}
 const keys=[...new Set(rows.flatMap(row=>Object.keys(row)))].slice(0,6),head=document.createElement('thead'),hr=document.createElement('tr');for(const key of keys){const th=text('th',key.replaceAll('_',' '));th.scope='col';hr.append(th);}head.append(hr);table.append(head);
 const tbody=document.createElement('tbody');for(const row of rows.slice(0,30)){const tr=document.createElement('tr');for(const key of keys)tr.append(text('td',scalar(row[key]).slice(0,300)));tbody.append(tr);}table.append(tbody);$('fin-result-table').append(table);
}
function chart(source,data){
 const note=$('fin-chart-note');if(source!=='coinbase-candles'){note.textContent='Structured source records below. No chart inferred for this data type.';return;}
 if(data.window_complete!==true||!Array.isArray(data.missing_intervals)||data.missing_intervals.length||!Array.isArray(data.items)||data.items.length<2||!Number.isSafeInteger(data.granularity_seconds)||data.granularity_seconds<=0){note.textContent='Chart withheld — complete contiguous candles were not established. No gap filling.';return;}
 const points=data.items.map(row=>[row.time,typeof row.close==='string'&&/^(\d+)(\.\d+)?$/.test(row.close)?Number(row.close):NaN]);
 if(points.length>300||points.some(([t,v],i)=>!Number.isSafeInteger(t)||!Number.isFinite(v)||v<=0||(i>0&&t-points[i-1][0]!==data.granularity_seconds))){note.textContent='Chart withheld — invalid chart inputs.';return;}
 const lo=Math.min(...points.map(p=>p[1])),hi=Math.max(...points.map(p=>p[1])),span=hi-lo||1,elapsed=points.at(-1)[0]-points[0][0];
 const NS='http://www.w3.org/2000/svg',svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox','0 0 800 260');svg.setAttribute('role','img');svg.setAttribute('aria-label','Historical candle close prices. Approximate drawing only; exact source values are in the records and export.');
 const title=document.createElementNS(NS,'title');title.textContent='Historical close, quote-currency units; no execution or performance claim';svg.append(title);
 const poly=document.createElementNS(NS,'polyline');poly.setAttribute('points',points.map(([t,v])=>[20+(t-points[0][0])/elapsed*760,220-(v-lo)/span*190].join(',')).join(' '));poly.setAttribute('fill','none');poly.setAttribute('stroke','currentColor');poly.setAttribute('stroke-width','2');svg.append(poly);$('fin-chart').append(svg);
 note.textContent=data.product+' / '+points.length+' completed candles / '+data.granularity_seconds+' seconds per candle. Visual range '+lo+'–'+hi+' quote units. Approximate rendering only; source decimals are unchanged in the export.';
}
async function observe(event){
 event.preventDefault();invalidate();const generation=queryEpoch,source=$('fin-source').value,spec=specs.get(source);
 if(!revision||!spec||spec.private!==false||privateIds.has(source)){showState('DENIED — source is not public');return;}
 const params=new URLSearchParams();for(const [key,value] of new FormData($('fin-form'))){if(key==='source')continue;if(!spec.parameters.includes(key)||typeof value!=='string'||value.length>2048){showState('INVALID PARAMETERS');return;}if(value.trim())params.set(key,value.trim());}
 const controller=new AbortController();pending=controller;const timer=setTimeout(()=>controller.abort(),15000);showState('REQUESTING — previous result cleared');$('fin-observe').disabled=true;
 try{
  const result=await readJson('/api/finance/observations/'+source+(params.size?'?'+params:''),controller.signal);if(generation!==queryEpoch)return;const body=result.body;
  if(!identity(body,'szl.finance.observation/v1')||body.source!==source)throw Error('INVALID_OBSERVATION');
  if(result.status!==200||body.ok!==true||!['SNAPSHOT','CACHED'].includes(body.state)){showState('UNAVAILABLE / '+(code.test(body.error||'')?body.error:'NO_CURRENT_OBSERVATION'));return;}
  if(!body.data||typeof body.data!=='object'||Array.isArray(body.data)||body.truth_label!=='REPORTED'||!body.provenance||body.provenance.signed!==false||!digest.test(body.provenance.observation_id||'')||body.provenance.retrieved_at!==body.retrieved_at||body.provenance.runtime_reported_source_revision!==revision)throw Error('INVALID_OBSERVATION');
  if(Array.isArray(body.data.items)&&body.data.items.some(row=>!row||typeof row!=='object'||Array.isArray(row)))throw Error('INVALID_RECORDS');
  table(body.data);chart(source,body.data);receipt=body;$('fin-export').disabled=false;$('fin-detail').textContent=JSON.stringify(body,null,2).slice(0,250000);showState(body.state+' / REPORTED / retrieved '+body.retrieved_at+' — not current-price assurance');
 }catch(error){if(generation===queryEpoch){clearResult();showState('UNAVAILABLE — request failed or response was rejected');}}
 finally{clearTimeout(timer);if(generation===queryEpoch){pending=null;$('fin-observe').disabled=!specs.has(source)||privateIds.has(source);}}
}
$('fin-form').addEventListener('input',event=>{if(event.target.id==='fin-source')return;invalidate();const spec=specs.get($('fin-source').value);$('fin-observe').disabled=!spec||spec.private!==false;showState('PARAMETERS CHANGED — request a new observation');});
$('fin-form').addEventListener('submit',observe);$('fin-source').addEventListener('change',form);$('fin-refresh').addEventListener('click',registry);
$('fin-export').addEventListener('click',()=>{if(!receipt)return;const blob=new Blob([JSON.stringify(receipt,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='puriq-'+receipt.source+'-observation.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
window.addEventListener('pagehide',invalidate);registry();
})();
'''

HTML = r'''
<section id="fin-desk" class="finance-desk" data-szl-finance-workspace="1" aria-labelledby="fin-title">
 <div class="panel fin-head"><div><div class="mono">PURIQ / SOURCE WORKBENCH</div><h2 id="fin-title">Inspect the evidence before the thesis.</h2></div><button id="fin-refresh" type="button">Refresh source status</button></div>
 <div class="panel"><p id="fin-registry-state" class="fin-state" role="status">NOT PROBED</p><p class="fin-note">Configuration is not connectivity. Status describes the last request for an adapter, not every market or instrument. Source revision: <span id="fin-revision">UNAVAILABLE</span>.</p><details><summary>Inspect the 16-source access register</summary><div class="fin-scroll" tabindex="0" role="region" aria-label="Provider status table"><table><caption>Canonical market-data adapters. Owner-only sources are not exposed by this public Space.</caption><thead><tr><th scope="col">Source</th><th scope="col">Last-request state</th><th scope="col">Access</th></tr></thead><tbody id="fin-provider-body"></tbody></table></div></details></div>
 <div class="fin-grid"><section class="panel"><h3>One bounded observation</h3><form id="fin-form"><label for="fin-source">Source</label><select id="fin-source" name="source" disabled></select><p id="fin-operation" class="fin-note">Waiting for the canonical source contract.</p><div id="fin-fields" class="fin-fields"></div><div class="fin-actions"><button id="fin-observe" type="submit" disabled>Read public source</button><button id="fin-export" type="button" disabled>Export observation</button></div></form><p class="fin-note">Public observations only. No account, wallet, order, credential entry, model inference, or trading authorization. Polymarket and Kalshi contract equivalence is not established. Filings retain period and filing-date context.</p></section>
 <section class="panel fin-instrument"><h3>Source instrument</h3><p id="fin-result-state" class="fin-state" role="status">UNAVAILABLE</p><div id="fin-chart"></div><p id="fin-chart-note" class="fin-note">No chart observation.</p></section></div>
 <section class="panel"><h3>Returned records</h3><div id="fin-result-table" class="fin-scroll" tabindex="0" role="region" aria-label="Returned source records"></div><details><summary>Source envelope and provenance</summary><p class="fin-note">Digests establish internal consistency, not signatures, investment performance, or source authenticity. Display is limited to 250,000 characters; export preserves the accepted public response.</p><pre id="fin-detail" class="fin-provenance">No accepted observation.</pre></details></section>
</section>
<script>''' + SCRIPT + '</script>'


ANALYTICS_HTML = r'''
<section class="finance-desk" id="fin-analytics" aria-labelledby="fin-analytics-title">
 <section class="panel"><div class="mono">PURIQ / ADVISORY ANALYTICS V2</div><h2 id="fin-analytics-title">From source evidence to measured inputs.</h2>
 <p class="fin-note">Daily-close indicators are modeled analysis, not investment advice or an execution quote. Paper use only. Live history comes from the canonical Coinbase adapter; the fixture is synthetic. Missing daily intervals block calculation.</p>
 <form id="fin-analysis-form"><div class="fin-fields"><label>Instrument<input id="fin-analysis-symbol" value="BTC-USD" maxlength="24" pattern="[A-Z0-9][A-Z0-9.\-]{0,23}" required></label><label>Input lane<select id="fin-analysis-origin"><option value="coinbase">Coinbase completed daily candles</option><option value="fixture">Synthetic fixture — offline demonstration</option></select></label><label>Analysis<select id="fin-analysis-kind"><option value="signals">Indicator suite</option><option value="quote">Historical risk statistics</option></select></label></div><button type="submit" id="fin-analysis-run">Compute advisory analysis</button></form>
 <p id="fin-analysis-state" class="fin-state" role="status">NOT COMPUTED</p><pre id="fin-analysis-summary" class="fin-provenance">No inputs accepted.</pre>
 <div class="fin-actions"><button type="button" id="fin-analysis-export" disabled>Export result and receipt</button><button type="button" id="fin-analysis-verify" disabled>Verify receipt integrity</button></div><p class="fin-note">Receipts are unsigned and caller-held. Integrity does not prove authenticity, profitability, or trading authority. No shared portfolio state or ledger is written.</p>
 <details><summary>Bounded portfolio statistics</summary><p class="fin-note">Enter 3–300 positive closes per asset, at most 16 assets. These are unverified caller inputs. The output contains per-asset statistics and simple means, not a weighted portfolio or backtest.</p><label for="fin-portfolio">Holdings as JSON</label><textarea id="fin-portfolio" rows="5" style="width:100%;max-width:100%;background:#0b1119;color:#edf3ff" maxlength="150000">{"BTC-USD":[100,102,101,104]}</textarea><label>Annual periods<select id="fin-annual"><option value="365">365 — daily crypto</option><option value="252">252 — trading days</option></select></label><button type="button" id="fin-portfolio-run">Compute caller-supplied series</button></details>
 <details><summary>Full source binding and computation evidence</summary><pre id="fin-analysis-evidence" class="fin-provenance">No evidence yet.</pre></details></section>
</section>
<script>
(()=>{'use strict';const $=id=>document.getElementById(id);let accepted=null,epoch=0,controller=null;
function clear(){accepted=null;$('fin-analysis-export').disabled=true;$('fin-analysis-verify').disabled=true;$('fin-analysis-summary').textContent='No inputs accepted.';$('fin-analysis-evidence').textContent='No evidence yet.';}
function invalidate(){epoch++;if(controller)controller.abort();clear();$('fin-analysis-state').textContent='INPUTS CHANGED — compute again';}
async function call(path,body){const serial=++epoch;if(controller)controller.abort();controller=new AbortController();const timer=setTimeout(()=>controller.abort(),20000);clear();$('fin-analysis-state').textContent='COMPUTING';
try{const r=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'omit',cache:'no-store',redirect:'error',signal:controller.signal,headers:{Accept:'application/json','Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
if(!(r.headers.get('content-type')||'').startsWith('application/json'))throw Error('INVALID_RESPONSE');const reader=r.body.getReader(),chunks=[];let size=0;for(;;){const part=await reader.read();if(part.done)break;size+=part.value.length;if(size>4000000){await reader.cancel();throw Error('RESPONSE_TOO_LARGE');}chunks.push(part.value);}const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}const data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));if(serial!==epoch)return;
if(!r.ok||data.ok!==true)throw Error(typeof data.error==='string'&&/^[A-Z_]+$/.test(data.error)?data.error:'UNAVAILABLE');
if(data.schema!=='szl.finance.analytics/v2'||data.execution_enabled!==false||data.advisory_only!==true||data.paper_only!==true||data.not_financial_advice!==true||data.receipt?.signing!=='UNSIGNED_HONEST')throw Error('INVALID_CONTRACT');accepted=data;
const origin=data.inputs?.asset?.origin||data.inputs?.origin||'integrity check';$('fin-analysis-state').textContent='COMPUTED / '+origin.toUpperCase()+' / ADVISORY ONLY';$('fin-analysis-summary').textContent=JSON.stringify(data.result,null,2);$('fin-analysis-evidence').textContent=JSON.stringify(data,null,2);$('fin-analysis-export').disabled=false;$('fin-analysis-verify').disabled=false;
}catch(e){if(serial===epoch){clear();$('fin-analysis-state').textContent='BLOCKED / '+(e.name==='AbortError'?'DEADLINE':e.message);}}finally{clearTimeout(timer);}}
$('fin-analysis-form').addEventListener('submit',e=>{e.preventDefault();call('/api/finance/v2/'+$('fin-analysis-kind').value+'/'+encodeURIComponent($('fin-analysis-symbol').value)+'?origin='+$('fin-analysis-origin').value);});
for(const id of ['fin-analysis-form','fin-portfolio','fin-annual'])$(id).addEventListener('input',invalidate);
$('fin-portfolio-run').addEventListener('click',()=>{try{call('/api/finance/v2/portfolio',{holdings:JSON.parse($('fin-portfolio').value),periods_per_year:Number($('fin-annual').value)});}catch(e){invalidate();$('fin-analysis-state').textContent='INVALID JSON';}});
$('fin-analysis-verify').addEventListener('click',()=>{if(accepted)call('/api/finance/v2/receipts/verify',accepted);});
$('fin-analysis-export').addEventListener('click',()=>{if(!accepted)return;const url=URL.createObjectURL(new Blob([JSON.stringify(accepted,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='puriq-computation.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});window.addEventListener('pagehide',invalidate);
})();
</script>
'''
HTML += ANALYTICS_HTML


def apply_workspace(renderer) -> None:
    """Change only the declared finance presentation, preserving all siblings."""
    if (not isinstance(getattr(renderer, "DOMAIN_HTML", None), dict)
            or not isinstance(getattr(renderer, "DOMAIN_CSS", None), dict)
            or "finance" not in renderer.DOMAIN_HTML or "finance" not in renderer.DOMAIN_CSS):
        raise TypeError("unsupported flagship presentation contract")
    renderer.DOMAIN_HTML = {**renderer.DOMAIN_HTML, "finance": HTML}
    renderer.DOMAIN_CSS = {**renderer.DOMAIN_CSS, "finance": renderer.DOMAIN_CSS["finance"] + CSS}
