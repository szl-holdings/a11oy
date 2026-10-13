# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Signed public prices and a separately labeled synthetic estimator replay."""
HTML = r'''
<section id="fin-signed" class="finance-desk" aria-labelledby="fin-signed-title">
 <div class="fin-head"><h2 id="fin-signed-title">Signed price observatory</h2><a href="/signed-prices#fin-signed">Open observatory</a></div>
 <p class="fin-note">Inspect public BTC, ETH and SOL prints. Provider signatures authenticate assertions; they do not establish market accuracy or independent sources. Keys come from the provider over HTTPS.</p>
 <div class="fin-grid"><div class="card">
  <form id="fin-signed-form"><label for="fin-signed-symbol">Public sample</label><select id="fin-signed-symbol"><option>BTC</option><option>ETH</option><option>SOL</option></select><div class="fin-actions"><button type="submit">Verify latest print</button><button type="button" id="fin-signed-export" disabled>Download evidence</button></div></form>
  <p class="fin-state" id="fin-signed-state" role="status" aria-live="polite">NOT CHECKED</p>
  <h3 id="fin-signed-price">No accepted price</h3><p class="fin-note" id="fin-signed-proof">Full-record signature, freshness and source policy are required.</p>
  <p class="fin-note">Review only. Local evidence digests are unsigned. No orders or capital movement.</p>
 </div><div class="card">
  <h3>Reference-price research</h3><p class="fin-note">MODELED / SYNTHETIC. Compare equal-venue and declared-group medians under outliers and duplicated sources. Group independence is an assumption; this is not an accuracy or performance benchmark.</p>
  <button type="button" id="fin-signed-model">Run synthetic comparison</button><p id="fin-signed-model-state" class="fin-state" role="status">NOT RUN</p><div class="fin-scroll"><table><caption>Synthetic USD reference values</caption><thead><tr><th>Scenario</th><th>Venue median</th><th>Group median</th></tr></thead><tbody id="fin-signed-model-rows"></tbody></table></div>
 </div></div>
 <details><summary>Verification evidence and source revision</summary><pre id="fin-signed-evidence" class="fin-provenance">No observation.</pre></details>
 <p class="fin-note"><a href="https://github.com/szl-holdings/puriq-live/blob/2ea8ea4bb9de2ca432f40c0c55ea5a5ed02786bf/docs/SIGNED_PRICE_RESEARCH_2026-10-07.md" target="_blank" rel="noopener noreferrer">Research, source code and prior art</a></p>
</section>
<script>
(()=>{'use strict';
const $=id=>document.getElementById(id);if(!$('fin-signed'))return;
let serial=0,pending=null,accepted=null,expiry=null;
function clear(){accepted=null;clearTimeout(expiry);$('fin-signed-export').disabled=true;$('fin-signed-price').textContent='No accepted price';$('fin-signed-proof').textContent='Full-record signature, freshness and source policy are required.';$('fin-signed-evidence').textContent='No observation.';}
function invalidate(){serial++;if(pending)pending.abort();clear();$('fin-signed-state').textContent='NOT CHECKED';}
async function json(path,signal){const response=await fetch(path,{credentials:'omit',cache:'no-store',redirect:'error',signal,headers:{Accept:'application/json'}});if(!/^application\/json(?:;|$)/i.test(response.headers.get('content-type')||''))throw Error('INVALID_RESPONSE');const reader=response.body.getReader(),parts=[];let size=0;try{for(;;){const p=await reader.read();if(p.done)break;size+=p.value.length;if(size>200000)throw Error('RESPONSE_TOO_LARGE');parts.push(p.value);}}catch(e){await reader.cancel();throw e;}const raw=new Uint8Array(size);let i=0;for(const p of parts){raw.set(p,i);i+=p.length;}const body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));if(response.status!==200)throw Error('SOURCE_UNAVAILABLE');if(body.schema!=='szl.finance.signed-price/v1'||! /^[0-9a-f]{40}$/.test(body.source_revision)||body.execution_enabled!==false||body.advisory_only!==true||body.receipt?.signing!=='UNSIGNED_HONEST')throw Error('INVALID_CONTRACT');return body;}
$('fin-signed-form').addEventListener('submit',async e=>{e.preventDefault();invalidate();const epoch=serial,symbol=$('fin-signed-symbol').value;const controller=new AbortController();pending=controller;const timer=setTimeout(()=>controller.abort(),15000),started=performance.now();$('fin-signed-state').textContent='VERIFYING';try{
 const body=await json('/api/finance/signed-prices/'+encodeURIComponent(symbol),pending.signal);if(epoch!==serial)return;const result=body.result,proof=result?.verification;
 if(result?.symbol!==symbol||result.can_authorize!==false||result.trading_enabled!==false)throw Error('INVALID_CONTRACT');$('fin-signed-evidence').textContent=JSON.stringify(body,null,2);
 if(result.status!=='REVIEW'){if(result.status!=='ABSTAIN'||result.price_text!==null)throw Error('INVALID_CONTRACT');$('fin-signed-state').textContent='ABSTAIN';$('fin-signed-proof').textContent=(result.decision_reasons||[]).join(', ');return;}
 const age=proof?.freshness?.age_seconds,eventTime=Date.parse(result.provider_print?.at),price=result.price_text;
 if(body.state!=='REVIEW'||proof.core_valid!==true||proof.record_valid!==true||proof.fresh!==true||proof.verification_scope!=='full-record'||proof.freshness?.max_age_seconds!==30||!Number.isFinite(age)||!Number.isFinite(eventTime)||!/^\d+(?:\.\d+)?$/.test(price)||result.decision_reasons?.length!==0)throw Error('INVALID_CONTRACT');
 const remaining=(30-Math.max(0,age,(Date.now()-eventTime)/1000))*1000-(performance.now()-started);
 if(remaining<=0){$('fin-signed-state').textContent='EXPIRED';return;}
 accepted=body;$('fin-signed-export').disabled=false;$('fin-signed-state').textContent='REVIEW / PROVIDER SIGNATURES VERIFIED';$('fin-signed-price').textContent=symbol+' $'+price;$('fin-signed-proof').textContent='Core and full-record signatures verified. Freshness expires locally. Key fingerprint: '+proof.key_fingerprint;
 expiry=setTimeout(()=>{if(epoch===serial){clear();$('fin-signed-state').textContent='EXPIRED — VERIFY AGAIN';}},remaining);
 }catch(error){if(epoch===serial){clear();$('fin-signed-state').textContent=error.name==='AbortError'?'UNAVAILABLE / DEADLINE':'UNAVAILABLE';}}finally{clearTimeout(timer);if(epoch===serial)pending=null;}});
$('fin-signed-symbol').addEventListener('change',invalidate);
$('fin-signed-export').addEventListener('click',()=>{if(!accepted)return;const url=URL.createObjectURL(new Blob([JSON.stringify(accepted,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='puriq-signed-price-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('fin-signed-model').addEventListener('click',async()=>{const button=$('fin-signed-model'),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);button.disabled=true;$('fin-signed-model-rows').replaceChildren();$('fin-signed-model-state').textContent='COMPUTING';try{const body=await json('/api/finance/signed-prices/model',controller.signal);if(body.state!=='MODELED'||body.result?.data_kind!=='SYNTHETIC')throw Error('INVALID_CONTRACT');for(const [name,item] of Object.entries(body.result.cases)){const row=document.createElement('tr');for(const value of [name.replaceAll('_',' '),item.venue_median_usd,item.reference_price_usd]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}$('fin-signed-model-rows').append(row);}$('fin-signed-model-state').textContent='MODELED / SYNTHETIC';}catch(error){$('fin-signed-model-state').textContent='UNAVAILABLE';}finally{clearTimeout(timer);button.disabled=false;}});
window.addEventListener('pagehide',invalidate);document.addEventListener('visibilitychange',()=>{if(document.hidden)invalidate();});
})();
</script>
'''
