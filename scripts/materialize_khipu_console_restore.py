#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot restoration of the source-backed Try Khipu console panel.

The panel was merged in a11oy#1390 and remains a permanent investor-smoke
contract. This materializer restores only that missing HTML/JavaScript block,
then deletes itself through its controller after focused verification.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "pages" / "console.html"
BEGIN = "/* try-khipu-panel"
END = "/* end try-khipu-panel */"

PANEL = r'''
<script>
/* try-khipu-panel :: investor-hittable live Khipu GGUF on Command Center only.
   Same-origin POST /api/a11oy/v1/khipu/chat (CORS bypass). Does NOT add a
   nav SPEC tab (tabs.json gate). Pin + READY/FAILED + UNSIGNED
   record_sha256. No throughput marketing number. GPU Inference Endpoint ROADMAP. Forge lab
   SNAPSHOT. killinchu detector SIMULATED. Λ = Conjecture 1. */
(function(){
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function chip(txt, cls){ return '<span class="badge '+(cls||'b-gold')+'">'+esc(txt)+'</span>'; }
  function pinLine(pin){
    if(!pin) return '<div class="mono dim">pin unavailable</div>';
    return '<div class="mono" style="font-size:11px;line-height:1.7">'
      +'<div><b>lab</b> '+esc(pin.lab_base||'')+'</div>'
      +'<div><b>model</b> '+esc(pin.model_repo||'')+'@'+esc(pin.model_rev||'')+'</div>'
      +'<div><b>file</b> '+esc(pin.gguf_file||'')+'</div>'
      +'<div><b>sha256</b> '+esc(pin.gguf_sha256||'')+'</div>'
      +'<div>max_tokens='+esc(pin.max_tokens)+' · temperature='+esc(pin.temperature)+' · stream=false · dummy Bearer not-a-secret</div>'
      +'</div>';
  }
  function panelHTML(){
    return '<div class="card" id="try-khipu-panel" style="border-left:3px solid #5fb3a3">'
      +'<div class="card-h"><span class="card-t">Try Khipu</span>'
      +'<span class="card-ep" id="tk-lab-st">probing lab…</span></div>'
      +'<div class="mono dim" style="font-size:11px;line-height:1.6;margin:0 0 .7rem">Live CPU-lab GGUF from this origin. Sovereign path is the pinned SZL-Khipu-1.5B Q4_K_M — not Llama/Mistral/Qwen Hugging Face voters. GPU Inference Endpoint is <b>ROADMAP</b>. Forge lab is <b>SNAPSHOT</b>. killinchu detector stays <b>SIMULATED</b>. Λ = <b>Conjecture 1</b> (not a theorem). Receipts are <b>UNSIGNED</b> unless the lab says otherwise — never fabricated. No throughput marketing number.</div>'
      +'<div id="tk-pin" class="mono dim">loading pin…</div>'
      +'<div id="tk-probe" class="mono dim" style="font-size:10.5px;margin:.55rem 0 .7rem"></div>'
      +'<textarea id="tk-prompt" aria-label="Khipu prompt" style="width:100%;box-sizing:border-box;min-height:72px;font-family:var(--mono);font-size:12px;padding:.6rem .7rem;border:1px solid var(--gold-line);border-radius:8px;background:var(--panel);color:var(--cream)">Reply in one short sentence: what is a Khipu receipt?</textarea>'
      +'<div class="btns" style="margin-top:.55rem"><button type="button" class="btn teal" id="tk-go">Try Khipu</button>'
      +'<span class="mono dim" id="tk-run-st" aria-live="polite" style="margin-left:.6rem"></span></div>'
      +'<pre class="out" id="tk-out" aria-live="polite" style="margin-top:.7rem">— submit a prompt to hit the CPU lab —</pre>'
      +'<div id="tk-receipt" class="mono dim" style="font-size:11px;line-height:1.7;margin-top:.55rem"></div>'
      +'</div>';
  }
  function renderProbe(host, probe){
    if(!host || !probe) return;
    host.innerHTML = 'Past MEASURED probe '+esc(probe.when||'')
      +' · HTTP '+esc(probe.http_status)
      +' · wall '+esc(probe.wall_s)+'s'
      +' · usage '+esc((probe.usage&&probe.usage.prompt_tokens)||'?')+'/'
      +esc((probe.usage&&probe.usage.completion_tokens)||'?')+'/'
      +esc((probe.usage&&probe.usage.total_tokens)||'?')
      +' · elapsed_ms '+esc(probe.elapsed_ms)
      +' · signature '+esc(probe.signature)
      +' · record_sha256 '+esc(probe.record_sha256)
      +'. History, not a live rate.';
  }
  function paintReceipt(host, body){
    if(!host) return;
    if(!body){ host.innerHTML=''; return; }
    var st = body.lab_status==='READY' ? 'b-live' : 'b-gold';
    host.innerHTML = chip(body.lab_status||'FAILED', st)
      +' '+chip((body.signature||'UNKNOWN'), 'b-gold')
      +'<div style="margin-top:.4rem"><b>record_sha256</b> '+esc(body.record_sha256||'UNKNOWN')+'</div>'
      +'<div>elapsed_ms '+esc(body.elapsed_ms)+' <b>'+esc(body.elapsed_ms_label||'MEASURED')+'</b>'
      +' · usage '+esc(JSON.stringify(body.usage||{}))+' <b>'+esc(body.usage_label||'REPORTED')+'</b></div>'
      +(body.error?'<div>error '+esc(body.error)+'</div>':'');
  }
  async function loadStatus(root){
    var st=root.querySelector('#tk-lab-st');
    var pinEl=root.querySelector('#tk-pin');
    var probeEl=root.querySelector('#tk-probe');
    try{
      var res=await fetch('/api/a11oy/v1/khipu/status',{method:'GET',headers:{'Accept':'application/json'},cache:'no-store'});
      var j=await res.json();
      var ready=j.lab_status==='READY';
      if(st) st.innerHTML=chip(j.lab_status||'FAILED', ready?'b-live':'b-gold');
      if(pinEl) pinEl.innerHTML=pinLine(j.pin);
      renderProbe(probeEl, j.measured_probe_2026_08_28);
    }catch(e){
      if(st) st.innerHTML=chip('FAILED','b-gold');
      if(pinEl) pinEl.innerHTML='<div class="mono dim">status probe failed — shown honestly, not faked. '+esc(e.message||e)+'</div>';
    }
  }
  function bind(root){
    var btn=root.querySelector('#tk-go');
    if(!btn || btn.dataset.bound) return;
    btn.dataset.bound='1';
    btn.addEventListener('click', async function(){
      var prompt=(root.querySelector('#tk-prompt')||{}).value||'';
      var out=root.querySelector('#tk-out');
      var rec=root.querySelector('#tk-receipt');
      var run=root.querySelector('#tk-run-st');
      prompt=String(prompt).trim();
      if(!prompt){ if(out) out.textContent='prompt required'; return; }
      btn.disabled=true;
      if(run) run.textContent='calling CPU lab…';
      if(out) out.textContent='…';
      try{
        var res=await fetch('/api/a11oy/v1/khipu/chat',{
          method:'POST',
          headers:{'content-type':'application/json','Accept':'application/json'},
          body:JSON.stringify({prompt:prompt,max_tokens:32,temperature:0,stream:false})
        });
        var j=await res.json();
        if(out) out.textContent=j.text || (j.error || ('lab_status '+ (j.lab_status||'FAILED')));
        paintReceipt(rec, j);
        if(run) run.textContent='';
      }catch(e){
        if(out) out.textContent='proxy did not resolve: '+(e.message||e)+' — shown honestly.';
        paintReceipt(rec, {lab_status:'FAILED',signature:'UNKNOWN',record_sha256:'UNKNOWN',elapsed_ms:null,elapsed_ms_label:'UNKNOWN',usage:{},usage_label:'UNKNOWN',error:String(e.message||e)});
        if(run) run.textContent='';
      }finally{
        btn.disabled=false;
      }
    });
  }
  function inject(c){
    if(!c || c.querySelector('#try-khipu-panel')) return;
    var wrap=document.createElement('div');
    wrap.innerHTML=panelHTML();
    var node=wrap.firstElementChild;
    var honest=c.querySelector('.honesty');
    if(honest) c.insertBefore(node, honest);
    else c.appendChild(node);
    bind(node);
    loadStatus(node);
  }
  function wrapCommand(){
    var V=window.VIEWS;
    if(!V || !V.command || typeof V.command.render!=='function'){
      return setTimeout(wrapCommand, 80);
    }
    if(V.command.__tryKhipuWrapped) return;
    V.command.__tryKhipuWrapped=true;
    var orig=V.command.render;
    V.command.render=async function(c){
      var p=orig.call(this,c);
      inject(c);
      return await p;
    };
    var body=document.getElementById('vbody');
    if(body && !body.querySelector('#try-khipu-panel')) inject(body);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', wrapCommand);
  else wrapCommand();
})();
/* end try-khipu-panel */
</script>
'''

html = CONSOLE.read_text(encoding="utf-8")
if BEGIN in html or END in html or 'id="try-khipu-panel"' in html:
    raise SystemExit("Try Khipu panel already exists; refusing duplicate injection")
closing = html.rfind("</body>")
if closing < 0:
    raise SystemExit("closing body tag not found")
html = html[:closing] + PANEL + "\n" + html[closing:]
CONSOLE.write_text(html, encoding="utf-8", newline="\n")
print("restored Try Khipu console panel")
