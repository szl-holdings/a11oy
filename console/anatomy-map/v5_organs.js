/* =====================================================================
   v5_organs.js — v5 (EVOLVES v4) additive overlays for the Living Anatomy.

   Self-contained, vendored-free, 0-CDN. Reads only the SZL a11oy origin
   (in the page CSP connect-src allow-list), READ-ONLY, credentials omitted.
   Adds, all honestly labeled (LIVE / MEASURED / MODELED / SAMPLE / ROADMAP):

     1. WILLAY  — conscience / immune-gate: 5 inspectable signed-refusal
        classifiers (trust ceiling 0.97). Tamper-EVIDENT, not tamper-proof.
     2. SOVEREIGN MESH — circulatory upgrade: live per-node up/DOWN from
        /govern/health. A node that is offline reads DOWN — never a
        fabricated green light. VRAM-fusion is ROADMAP.
     3. Buyer-verifiable receipt in-scene — "Verify offline" reuses Tier-1
        WebCrypto ECDSA-P256 against /cosign.pub, plus a live ledger
        bloodstream counter (total_receipts + sha3_256 chain head).
     4. 8 locked-proven → organ map (verbatim Lean statement + #print axioms,
        "kernel-verified sorry-free @ c7c0ba17"). Λ = heart-gate, advisory,
        Conjecture 1. Khipu BFT = Conjecture 2.
     5. AI-Assurance (WDP/CDAO) overlay — organ → assurance artifact with
        honest LIVE / PARTIAL / ROADMAP status chips.
     6. yarqa CFD + thermal-PINN physics layer — composed "physics-governed"
        overlay, labeled MODELED (not measured), bounded error.
     7. GPU-Sovereign Stack (SUBSTRATE) — the VERTICAL compute anatomy:
        owned GPU fabric → runtime → sovereign mesh → open-weight model →
        native governance → buyer-verifiable receipts. Live layers read
        /govern/health and degrade to DOWN, never a fabricated green light.

   Doctrine v11 LOCKED is unchanged: locked-proven stays EXACTLY 8; Λ is
   never a theorem; nothing here is folded into the locked-8.
   ===================================================================== */
(function(root){
  'use strict';
  if(!root.SZL_ANATOMY) return;
  var D = root.SZL_ANATOMY;
  var EP = D.V5_ENDPOINTS || {};

  /* ---------------- small DOM + fetch helpers ---------------- */
  function el(tag, attrs, html){ var e=document.createElement(tag); if(attrs){for(var k in attrs){ if(k==='class')e.className=attrs[k]; else e.setAttribute(k,attrs[k]); }} if(html!=null)e.innerHTML=html; return e; }
  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
  function getJSON(url){ return fetch(url,{mode:'cors',credentials:'omit',cache:'no-store'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); }); }
  function getText(url){ return fetch(url,{mode:'cors',credentials:'omit',cache:'no-store'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.text(); }); }

  /* ---------------- styles (theme-consistent, inline-CSP-allowed) ---------------- */
  var css = [
    '#v5panel{position:fixed;z-index:41;top:0;left:0;height:100%;width:min(440px,94vw);background:linear-gradient(180deg,rgba(10,14,26,.99),rgba(6,9,16,.98));border-right:1px solid var(--border,rgba(255,255,255,.1));box-shadow:8px 0 40px rgba(0,0,0,.5);transform:translateX(-102%);transition:transform .32s cubic-bezier(.2,.7,.2,1);display:flex;flex-direction:column;pointer-events:auto}',
    '#v5panel.open{transform:translateX(0)}',
    '#v5panel .v5ph{padding:20px 22px 14px;border-bottom:1px solid var(--border,rgba(255,255,255,.1));position:sticky;top:0;background:rgba(8,11,20,.96)}',
    '#v5panel .v5ph .eyebrow{font-family:var(--font-m,monospace);font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--text-dim,#8aa)}',
    '#v5panel .v5ph h2{font-size:21px;font-weight:700;margin:6px 0 0;line-height:1.1}',
    '#v5panel .v5pb{padding:16px 22px 90px;overflow:auto}',
    '#v5panel .v5close{position:absolute;top:14px;right:14px;background:none;border:1px solid var(--border,rgba(255,255,255,.18));color:var(--text,#dfe);border-radius:8px;width:30px;height:30px;cursor:pointer;font-size:16px;line-height:1}',
    '.v5-chip{font-family:var(--font-m,monospace);font-size:9.5px;letter-spacing:.06em;border:1px solid currentColor;border-radius:6px;padding:1px 6px;white-space:nowrap}',
    '.v5-chip.live{color:#5ad1ff}.v5-chip.down{color:#ff7eb6}.v5-chip.partial{color:#ffd166}.v5-chip.roadmap{color:#9ea7c0}.v5-chip.modeled{color:#c9a0ff}.v5-chip.locked{color:#ffd166}',
    '.v5-card{border:1px solid var(--border,rgba(255,255,255,.12));border-radius:12px;padding:13px 14px;margin:11px 0;background:rgba(255,255,255,.02)}',
    '.v5-card .v5-h{display:flex;align-items:center;gap:8px;justify-content:space-between;font-weight:700;font-size:13.5px}',
    '.v5-card .v5-sub{font-size:11.5px;color:var(--text-muted,#aab);margin-top:3px;font-family:var(--font-m,monospace)}',
    '.v5-card p{font-size:12.5px;line-height:1.55;color:var(--text,#dfe);opacity:.92;margin:8px 0 0}',
    '.v5-lean{font-family:var(--font-m,monospace);font-size:11px;background:rgba(0,0,0,.34);border-left:2px solid var(--skel,#ffd166);border-radius:6px;padding:8px 10px;margin-top:8px;white-space:pre-wrap;word-break:break-word;color:#e7ecff}',
    '.v5-note{border:1px solid var(--warn,#ff7eb6);background:rgba(255,126,182,.08);border-radius:10px;padding:11px 13px;margin:12px 0;font-size:12px;line-height:1.5}',
    '.v5-note .nh{font-family:var(--font-m,monospace);font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--warn,#ff7eb6);margin-bottom:6px}',
    '.v5-btn{pointer-events:auto;font-family:var(--font-m,monospace);font-size:11px;letter-spacing:.03em;color:var(--text,#dfe);background:rgba(255,255,255,.04);border:1px solid var(--border,rgba(255,255,255,.18));border-radius:9px;padding:8px 12px;cursor:pointer}',
    '.v5-btn:hover{border-color:#39d8c8;color:#39d8c8}',
    '#v5-blood{position:fixed;z-index:21;top:12px;left:50%;transform:translateX(-50%);pointer-events:auto;cursor:pointer;font-family:var(--font-m,monospace);font-size:10.5px;letter-spacing:.04em;color:#ff8fb0;background:rgba(8,11,20,.82);border:1px solid rgba(255,59,92,.4);border-radius:999px;padding:5px 13px;backdrop-filter:blur(6px);display:flex;gap:9px;align-items:center}',
    '#v5-blood .bdot{width:7px;height:7px;border-radius:50%;background:#ff3b5c;box-shadow:0 0 8px #ff3b5c;animation:v5beat 1.2s ease-in-out infinite}',
    '@keyframes v5beat{0%,100%{transform:scale(.8);opacity:.7}50%{transform:scale(1.3);opacity:1}}',
    '.v5-verify{border:1px solid #39d8c8;background:rgba(57,216,200,.07);border-radius:12px;padding:13px 14px;margin:16px 0}',
    '.v5-verify .vh{font-family:var(--font-m,monospace);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#39d8c8;margin-bottom:8px}',
    '.v5-verify .vres{font-family:var(--font-m,monospace);font-size:11.5px;margin-top:9px;line-height:1.5;word-break:break-all}',
    '.v5-verify .pass{color:#5ad1ff;font-weight:700}.v5-verify .fail{color:#ff7eb6;font-weight:700}',
    '@media (max-width:720px){#v5panel{width:100vw}#v5-blood{font-size:9.5px;top:8px}}'
  ].join('\n');
  document.head.appendChild(el('style',null,css));

  /* ---------------- shared left panel ---------------- */
  var panel = el('div',{id:'v5panel','aria-hidden':'true',role:'dialog','aria-label':'v5 overlay'});
  var head  = el('div',{class:'v5ph'});
  var eyebrow = el('div',{class:'eyebrow'},'SZL Agent Body · v5 (evolves v4)');
  var titleEl = el('h2',null,'');
  var closeBtn = el('button',{class:'v5close','aria-label':'close'},'×');
  head.appendChild(eyebrow); head.appendChild(titleEl); head.appendChild(closeBtn);
  var body = el('div',{class:'v5pb'});
  panel.appendChild(head); panel.appendChild(body);
  document.body.appendChild(panel);
  var openView=null;
  function closePanel(){ panel.classList.remove('open'); panel.setAttribute('aria-hidden','true'); openView=null; syncButtons(); }
  closeBtn.addEventListener('click',closePanel);
  document.addEventListener('keydown',function(e){ if(e.key==='Escape' && panel.classList.contains('open')) closePanel(); });
  function openPanel(view,title,render){
    if(openView===view){ closePanel(); return; }
    openView=view; titleEl.textContent=title; body.innerHTML='<div class="v5-sub">loading live data…</div>';
    panel.classList.add('open'); panel.setAttribute('aria-hidden','false'); panel.scrollTop=0;
    syncButtons();
    try{ render(body); }catch(err){ body.innerHTML='<div class="v5-note"><div class="nh">error</div>'+esc(String(err))+'</div>'; }
  }
  function emptyState(msg){ return '<div class="v5-note"><div class="nh">honest empty-state</div>'+esc(msg)+'</div>'; }

  /* ===================================================================
     1. WILLAY — conscience / immune-gate (live classifiers)
     =================================================================== */
  function renderWillay(b){
    getJSON(EP.willay).then(function(d){
      var cs=(d&&d.classifiers)||[];
      var tc=(d&&d.trust_ceiling);
      var h='';
      h+='<div class="v5-card"><div class="v5-h">Inspectable signed refusals <span class="v5-chip live">LIVE</span></div>';
      h+='<div class="v5-sub">trust ceiling '+esc(tc!=null?tc:'—')+' · '+esc(cs.length)+' classifiers</div>';
      h+='<p>'+esc((d&&d.honest_note)||'')+'</p></div>';
      h+='<div class="v5-note"><div class="nh">honest label</div>Refusals are <b>tamper-EVIDENT</b> (alteration is detectable via the signed receipt), <b>not tamper-proof</b>. These are auditable rules — the inverse of a removed / hidden classifier. No Anthropic classifier code or weights are used.</div>';
      cs.forEach(function(c){
        h+='<div class="v5-card"><div class="v5-h">'+esc(c.title||c.category)+' <span class="v5-chip live">'+esc((c.category||'').toUpperCase())+'</span></div>';
        h+='<div class="v5-sub">fires on: '+esc(c.fires_on||'')+'</div>';
        h+='<p>'+esc(c.rationale||'')+'</p>';
        h+='<div class="v5-sub" style="margin-top:7px">lineage: '+esc(c.lineage||'')+'</div></div>';
      });
      b.innerHTML=h;
    }).catch(function(e){ b.innerHTML=emptyState('WILLAY classifiers endpoint unreachable ('+e.message+'). No classifiers fabricated. Try again when '+EP.willay+' answers.'); });
  }

  /* ===================================================================
     2. SOVEREIGN MESH — circulatory upgrade (live per-node up/DOWN)
     =================================================================== */
  function renderMesh(b){
    getJSON(EP.mesh).then(function(d){
      var nodes=(d&&d.mesh)||[];
      var h='';
      h+='<div class="v5-card"><div class="v5-h">Governed inference mesh <span class="v5-chip live">LIVE</span></div>';
      h+='<div class="v5-sub">engines live '+esc((d&&d.engines_live))+' / '+esc((d&&d.engines_total))+' · governance '+esc((d&&d.governance))+'</div>';
      h+='<p>The circulatory system as a sovereign mesh. Each node’s status is read live — a node that is offline reads <b>DOWN</b>, never a fabricated green light. Per-node F11 Ayni reciprocity (LOCKED) keeps the mesh balanced.</p></div>';
      nodes.forEach(function(n){
        var live=!!n.live;
        h+='<div class="v5-card"><div class="v5-h">'+esc(n.name||n.model||'node')+' <span class="v5-chip '+(live?'live':'down')+'">'+(live?'LIVE':'DOWN')+'</span></div>';
        h+='<div class="v5-sub">model '+esc(n.model||'—')+' · tier '+esc(n.tier||'—')+' · effort '+esc(n.effort||'—')+'</div>';
        h+='<div class="v5-sub" style="margin-top:5px">F11 Ayni reciprocity contribution: '+(live?'active (LOCKED)':'paused — node down')+'</div></div>';
      });
      // GLM honest status
      var glm=d&&d.glm;
      if(glm){
        var glmLive=!!glm.on_metal_live;
        h+='<div class="v5-card"><div class="v5-h">GLM engine <span class="v5-chip '+(glmLive?'live':'down')+'">'+(glmLive?'LIVE':'DOWN')+'</span></div>';
        h+='<div class="v5-sub">'+esc(glm.model_tag||'')+'</div><p>'+esc(glm.note||'')+(glm.remote_provider_enabled?'':' Remote provider not enabled.')+'</p></div>';
      }
      h+='<div class="v5-note"><div class="nh">roadmap · honest energy</div>VRAM-fusion across nodes is <b>ROADMAP</b> — today the mesh is a scheduler / router ("Smart Routing"), not a fused address space. Energy joules are <b>UNAVAILABLE</b> unless a live NVML meter answers; '+esc((d&&d.meter_fresh_live)?'a meter is fresh':'no fresh meter')+' — never fabricated.</div>';
      b.innerHTML=h;
    }).catch(function(e){ b.innerHTML=emptyState('Mesh /govern/health unreachable ('+e.message+'). No node is shown as up. Try again when '+EP.mesh+' answers.'); });
  }

  /* ===================================================================
     3a. Ledger bloodstream counter (live) + 3b. buyer-verifiable receipt
     =================================================================== */
  var bloodHUD = el('div',{id:'v5-blood',title:'Receipt bloodstream — live unified ledger. Click to inspect + verify offline.','role':'button','tabindex':'0'},
    '<span class="bdot"></span><span id="v5-blood-txt">ledger …</span>');
  document.body.appendChild(bloodHUD);
  function refreshBlood(){
    getJSON(EP.ledger).then(function(d){
      var n=(d&&d.total_receipts);
      var alg=(d&&d.chain_alg)||'?';
      var head='';
      try{ var org=d.organs; for(var k in org){ if(org[k]&&org[k].chain_head){ head=org[k].chain_head; break; } } }catch(_){}
      document.getElementById('v5-blood-txt').innerHTML='bloodstream · '+esc(n)+' receipts · '+esc(alg)+(head?' · head '+esc(head.slice(0,8)):'')+' · LIVE';
    }).catch(function(){ document.getElementById('v5-blood-txt').textContent='bloodstream · ledger unreachable · honest empty-state'; });
  }
  bloodHUD.addEventListener('click',function(){ openPanel('ledger','Receipt bloodstream — unified ledger',renderLedger); });
  bloodHUD.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); bloodHUD.click(); } });

  function renderLedger(b){
    getJSON(EP.ledger).then(function(d){
      var head='', idx='';
      try{ var org=d.organs; for(var k in org){ if(org[k]){ head=org[k].chain_head||''; idx=org[k].chain_index; break; } } }catch(_){}
      var h='';
      h+='<div class="v5-card"><div class="v5-h">Unified ledger <span class="v5-chip live">LIVE</span></div>';
      h+='<div class="v5-sub">total receipts '+esc(d.total_receipts)+' · chain '+esc(d.chain_alg)+' · schema '+esc(d.schema)+'</div>';
      h+='<div class="v5-lean">chain head: '+esc(head||'—')+'\nchain index: '+esc(idx)+'</div>';
      h+='<p>The bloodstream of the body: every governed decision appends one signed receipt to a '+esc(d.chain_alg)+' hash-chain. Append-only, tamper-evident.</p></div>';
      h+=verifyCardHTML();
      b.innerHTML=h;
      wireVerify(b.querySelector('.v5-verify'));
    }).catch(function(e){ b.innerHTML=emptyState('Ledger /api/lake/v1/health unreachable ('+e.message+'). Counter not fabricated.'); });
  }

  function verifyCardHTML(){
    return '<div class="v5-verify"><div class="vh">Buyer-verifiable receipt — verify offline</div>'+
      '<div class="v5-sub">Tier-1 WebCrypto ECDSA-P256-SHA256 over the DSSE PAE, against cosign.pub. Runs entirely in your browser — no key sent, no trust in us required.</div>'+
      '<button class="v5-btn" style="margin-top:10px">✓ Verify a live receipt offline</button>'+
      '<div class="vres" aria-live="polite"></div></div>';
  }

  /* --- WebCrypto DSSE ECDSA-P256 verify (ported, tested in Node) --- */
  function b64ToBytes(b64){ var bin=atob(b64.replace(/-/g,'+').replace(/_/g,'/')); var u=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i); return u; }
  function cat(){ var arrs=[].slice.call(arguments),n=0,i; for(i=0;i<arrs.length;i++)n+=arrs[i].length; var o=new Uint8Array(n),p=0; for(i=0;i<arrs.length;i++){o.set(arrs[i],p);p+=arrs[i].length;} return o; }
  function derToRaw(der){
    var i=0; if(der[i++]!==0x30) throw new Error('bad DER (no SEQUENCE)'); var sl=der[i++]; if(sl&0x80){var n=sl&0x7f; while(n--)i++;}
    function rdInt(){ if(der[i++]!==0x02) throw new Error('bad DER (no INTEGER)'); var len=der[i++]; var v=der.slice(i,i+len); i+=len; while(v.length>1&&v[0]===0)v=v.slice(1); return v; }
    var r=rdInt(), s=rdInt(); var out=new Uint8Array(64); out.set(r,32-r.length); out.set(s,64-s.length); return out;
  }
  function importCosign(pem){
    var b64=pem.replace(/-----[^-]+-----/g,'').replace(/\s+/g,'');
    return crypto.subtle.importKey('spki', b64ToBytes(b64), {name:'ECDSA',namedCurve:'P-256'}, false, ['verify']);
  }
  function verifyDSSE(env, key){
    var enc=new TextEncoder();
    var payload=b64ToBytes(env.payload);
    var type=env.payloadType||'';
    var pae=cat(enc.encode('DSSEv1 '), enc.encode(String(enc.encode(type).length)+' '), enc.encode(type), enc.encode(' '+String(payload.length)+' '), payload);
    var rawSig=derToRaw(b64ToBytes(env.signatures[0].sig));
    return crypto.subtle.verify({name:'ECDSA',hash:'SHA-256'}, key, rawSig, pae).then(function(ok){ return {ok:ok,pae:pae,type:type}; });
  }
  function wireVerify(card){
    if(!card) return; var btn=card.querySelector('.v5-btn'), out=card.querySelector('.vres');
    btn.addEventListener('click',function(){
      out.innerHTML='verifying…'; btn.disabled=true;
      Promise.all([ getJSON(EP.receipts), getText(EP.cosign) ]).then(function(res){
        var rec=res[0]&&res[0].results&&res[0].results[0];
        var env=rec&&rec.receipt&&rec.receipt.dsse;
        if(!env||!env.payload||!env.signatures){ out.innerHTML=emptyState('No signed DSSE receipt available to verify yet.'); btn.disabled=false; return; }
        return importCosign(res[1]).then(function(key){ return verifyDSSE(env,key); }).then(function(v){
          var headHash=rec.chain_hash||'';
          out.innerHTML='<div class="'+(v.ok?'pass':'fail')+'">'+(v.ok?'✓ SIGNATURE VALID':'✗ SIGNATURE INVALID')+'</div>'+
            'alg: ECDSA-P256-SHA256 over DSSE PAE<br>'+
            'payloadType: '+esc(env.payloadType)+'<br>'+
            'keyid: '+esc((env.signatures[0]||{}).keyid||'—')+'<br>'+
            'chain head: '+esc(headHash.slice(0,32))+'…<br>'+
            'chain index: '+esc(rec.chain_index)+
            '<div class="v5-sub" style="margin-top:8px">Verified locally with the browser WebCrypto API against cosign.pub — '+(v.ok?'this receipt is unaltered from the signer.':'do NOT trust this receipt.')+'</div>';
          btn.disabled=false;
        });
      }).catch(function(e){ out.innerHTML=emptyState('Verify unavailable ('+e.message+'). Endpoints read-only; nothing fabricated.'); btn.disabled=false; });
    });
  }

  /* in-scene: inject "Verify offline" into the open organ panel for
     receipt-emitting organs (heart gate, bus, conscience, mesh, write, crown) */
  var RECEIPT_ORGANS={yuyay:1,yawar:1,willay:1,sovereign_mesh:1,ruway:1,hatun:1,sentra:1};
  root.addEventListener('szl:organ-open',function(ev){
    var o=ev.detail; if(!o||!RECEIPT_ORGANS[o.key]) return;
    var pb=document.getElementById('p-body'); if(!pb) return;
    if(pb.querySelector('.v5-verify')) return;
    var wrap=el('div'); wrap.innerHTML=verifyCardHTML(); var card=wrap.firstChild;
    pb.appendChild(card); wireVerify(card);
  });

  /* ===================================================================
     4. 8 locked-proven → organ map (verbatim Lean + axioms)
     =================================================================== */
  function leanStatement(fid){
    var f=D.FORMULAS&&D.FORMULAS[fid]; if(!f) return fid;
    return fid+'  '+(f.name||'')+'\n'+(f.latex||'')+'\n#print axioms: '+(f.axioms||'');
  }
  function renderProofs(b){
    var M=D.LEAN_MAP||{}; var h='';
    h+='<div class="v5-card"><div class="v5-h">8 locked-proven → organs <span class="v5-chip locked">LOCKED</span></div>';
    h+='<div class="v5-sub">'+esc(M.verified_note||'')+' · exactly 8 {F1,F4,F7,F11,F12,F18,F19,F22}</div>';
    h+='<p>Presentational map only — it does NOT change the locked set. Each statement below is kernel-verified sorry-free at '+esc(M.kernel_sha||'c7c0ba17')+'.</p></div>';
    (M.organs||[]).forEach(function(row){
      h+='<div class="v5-card"><div class="v5-h"><span style="color:'+esc(row.color)+'">'+esc(row.organ)+'</span> <span class="v5-chip locked">'+esc(row.formulas.join(' + '))+'</span></div>';
      h+='<p>'+esc(row.why)+'</p>';
      row.formulas.forEach(function(fid){ h+='<div class="v5-lean">'+esc(leanStatement(fid))+'</div>'; });
      h+='</div>';
    });
    h+='<div class="v5-note"><div class="nh">Λ honesty · Conjecture 1</div>'+esc(M.lambda||'')+'</div>';
    h+='<div class="v5-note"><div class="nh">Khipu BFT · Conjecture 2</div>'+esc(M.khipu||'')+'</div>';
    b.innerHTML=h;
  }

  /* ===================================================================
     5. AI-Assurance (WDP/CDAO) overlay
     =================================================================== */
  function statusClass(s){ return s==='LIVE'?'live':(s==='PARTIAL'?'partial':'roadmap'); }
  function renderAssurance(b){
    var A=D.ASSURANCE_MAP||{}; var h='';
    h+='<div class="v5-card"><div class="v5-h">AI-Assurance map (WDP / CDAO)</div>';
    h+='<p>'+esc(A.note||'')+' <a href="'+esc(A.surface||'#')+'" target="_blank" rel="noopener" style="color:#39d8c8">live /assurance surface ↗</a></p></div>';
    (A.rows||[]).forEach(function(r){
      h+='<div class="v5-card"><div class="v5-h">'+esc(r.organ)+' <span class="v5-chip '+statusClass(r.status)+'">'+esc(r.status)+'</span></div>';
      h+='<div class="v5-sub">artifact: '+esc(r.artifact)+'</div><p>'+esc(r.detail)+'</p></div>';
    });
    h+='<div class="v5-note"><div class="nh">honest chips</div>LIVE = artifact exists and is reachable · PARTIAL = exists but incomplete / sampled · ROADMAP = planned, not yet real. No status is inflated.</div>';
    b.innerHTML=h;
  }

  /* ===================================================================
     6. yarqa CFD + thermal-PINN physics overlay (MODELED)
     =================================================================== */
  function renderPhysics(b){
    var P=D.PHYSICS_OVERLAY||{}; var h='';
    h+='<div class="v5-card"><div class="v5-h">'+esc(P.headline||'physics-governed layer')+' <span class="v5-chip modeled">'+esc(P.label||'MODELED')+'</span></div>';
    h+='<p>'+esc(P.honest||'')+'</p></div>';
    (P.components||[]).forEach(function(c){
      h+='<div class="v5-card"><div class="v5-h">'+esc(c.name)+' <span class="v5-chip modeled">'+esc(c.kind)+'</span></div><p>'+esc(c.detail)+'</p></div>';
    });
    h+='<div class="v5-note"><div class="nh">bounded error</div>'+esc(P.bounded_error||'')+'</div>';
    h+='<div class="v5-note"><div class="nh">never</div>'+esc(P.never||'')+'</div>';
    h+='<div class="v5-sub" style="margin-top:8px">Composes with the existing yarqa flow-compartments overlay in the v4 dissection dock (off by default). data.js stays the single source of truth; locked-proven count unchanged at 8.</div>';
    b.innerHTML=h;
  }

  /* ===================================================================
     7. GPU-SOVEREIGN STACK (SUBSTRATE) — vertical compute anatomy.
        Static layer model from D.STACK_LAYER; live layers (runtime, mesh)
        light up from EP.mesh /govern/health and degrade to DOWN when
        unreachable — never a fabricated green light. The frontier layer is
        buyer-verifiable in-scene via the shared WebCrypto verify card.
     =================================================================== */
  function renderStack(b){
    var S=D.STACK_LAYER||{};
    if(!S.layers){ b.innerHTML=emptyState('Stack-layer data not loaded.'); return; }
    function paint(mesh, ledger){
      var engLive=mesh&&mesh.engines_live, engTot=mesh&&mesh.engines_total;
      var nodes=(mesh&&mesh.mesh&&mesh.mesh.length)||0;
      var nodesLive=(mesh&&mesh.mesh&&mesh.mesh.filter)?mesh.mesh.filter(function(n){return n.live;}).length:0;
      var meshUp=!!(mesh && ((engLive>0) || nodesLive>0));
      var rcpt=ledger&&ledger.total_receipts, rcptAlg=(ledger&&ledger.chain_alg)||'sha3_256', rcptHead='';
      if(ledger&&ledger.organs){ for(var k in ledger.organs){ var ch=ledger.organs[k]&&ledger.organs[k].chain_head; if(ch){ rcptHead=ch; break; } } }
      var h='';
      h+='<div class="v5-card"><div class="v5-h">'+esc(S.headline||'GPU-Sovereign Stack')+' <span class="v5-chip live">SUBSTRATE</span></div>';
      h+='<p>'+esc(S.thesis||'')+'</p></div>';
      (S.layers||[]).forEach(function(L){
        var chip=L.chip||'roadmap', posture=String(L.posture||''), extra='';
        if(L.live_key){
          if(mesh==null){ chip='down'; posture='UNREACHABLE'; }
          else if(L.live_key==='mesh'){ chip=meshUp?'live':'down'; posture=meshUp?('LIVE · '+esc(nodesLive)+'/'+esc(nodes)+' nodes'):('DOWN · 0/'+esc(nodes)+' nodes'); }
          else if(L.live_key==='engine'){ chip=(engLive>0)?'live':'down'; posture=(engLive>0)?('LIVE · '+esc(engLive)+'/'+esc(engTot)+' engines'):'DOWN'; }
        }
        if(L.receipt_key==='ledger'){
          if(ledger && rcpt!=null){ chip='live'; posture='LIVE · '+esc(rcpt)+' receipts'; extra='ledger · '+esc(rcpt)+' receipts · '+esc(rcptAlg)+(rcptHead?' · head '+esc(rcptHead.slice(0,12))+'…':'')+' — verify any one below, offline'; }
          else { extra='ledger unreachable — receipt count not shown; nothing fabricated'; }
        }
        h+='<div class="v5-card"><div class="v5-h"><span><span style="opacity:.55;font-family:var(--font-m,monospace);font-size:11px">'+esc(L.tier)+'</span> '+esc(L.name)+'</span> <span class="v5-chip '+chip+'">'+posture+'</span></div>';
        h+='<div class="v5-sub">leaders: '+esc(L.leaders||'')+'</div>';
        h+='<p>'+esc(L.szl||'')+'</p>';
        if(extra) h+='<div class="v5-sub" style="margin-top:6px;color:var(--ok,#39d98a)">'+extra+'</div>';
        if(L.honest) h+='<div class="v5-sub" style="margin-top:7px;color:var(--warn,#ff7eb6)">honest · '+esc(L.honest)+'</div>';
        h+='</div>';
      });
      h+='<div class="v5-note"><div class="nh">push the frontier</div>'+esc(S.frontier||'')+'</div>';
      h+='<div class="v5-note"><div class="nh">never</div>'+esc(S.never||'')+'</div>';
      h+=verifyCardHTML();
      b.innerHTML=h;
      wireVerify(b.querySelector('.v5-verify'));
    }
    Promise.all([ getJSON(EP.mesh).catch(function(){return null;}), getJSON(EP.ledger).catch(function(){return null;}) ])
      .then(function(r){ paint(r[0], r[1]); });
  }

  /* ---------------- buttons (wired to ids placed in index.html) ---------------- */
  var BTNS=[
    {id:'btn-v5-willay',    view:'willay',    title:'WILLAY — conscience / immune-gate', render:renderWillay},
    {id:'btn-v5-mesh',      view:'mesh',      title:'Sovereign Mesh — circulatory upgrade', render:renderMesh},
    {id:'btn-v5-proofs',    view:'proofs',    title:'8 locked-proven → organs', render:renderProofs},
    {id:'btn-v5-assurance', view:'assurance', title:'AI-Assurance (WDP / CDAO)', render:renderAssurance},
    {id:'btn-v5-physics',   view:'physics',   title:'yarqa CFD + thermal PINN (MODELED)', render:renderPhysics},
    {id:'btn-v5-stack',     view:'stack',     title:'SUBSTRATE — GPU-Sovereign Stack', render:renderStack}
  ];
  function syncButtons(){ BTNS.forEach(function(cfg){ var btn=document.getElementById(cfg.id); if(btn){ var on=openView===cfg.view; btn.classList.toggle('active',on); btn.setAttribute('aria-expanded',on?'true':'false'); } }); }
  function wireButtons(){ BTNS.forEach(function(cfg){ var btn=document.getElementById(cfg.id); if(btn) btn.addEventListener('click',function(){ openPanel(cfg.view,cfg.title,cfg.render); }); }); }

  /* ---------------- init ---------------- */
  function init(){ wireButtons(); refreshBlood(); setInterval(refreshBlood, 30000); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();

})(window);
