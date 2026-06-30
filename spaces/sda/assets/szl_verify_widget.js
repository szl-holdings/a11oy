/* ============================================================================
 * SZL "ask the fabric" — verify-a-claim widget  (vendored, self-contained)
 * ----------------------------------------------------------------------------
 * 0 runtime CDN · system fonts only · AbortController · honest fallback.
 * Calls the REAL a11oy verify endpoint and renders its REAL honest verdict.
 *   POST {base}/api/a11oy/v1/verify   body = a receipt / DSSE envelope / in-toto stmt
 *   GET  {base}/api/a11oy/v1/verify?url=<public receipt url>
 *
 * Doctrine v11: this widget NEVER fabricates a verdict. It shows exactly what
 * the server returns (verdict: VERIFIED | STRUCTURAL-ONLY | FAILED | UNRECOGNISED).
 * "STRUCTURAL-ONLY" is shown as advisory, NOT green. Network/timeout/429 degrade
 * to an honest "unreachable / rate-limited" state — never to a false green.
 *
 * Attribution (clean-room rebuild of permissive ideas — see dev7 report):
 *   - Tool-call / receipt trace UI pattern inspired by smolagents (Apache-2.0,
 *     huggingface/smolagents) and assistant-ui (MIT). Rebuilt SZL-native; no code copied.
 *   - AbortController fetch contract reuses anatomy V8 (SZL own prior art).
 * ==========================================================================*/
(function (global) {
  'use strict';

  var DEFAULT_BASE = 'https://a11oy.net'; // same fabric the estate already talks to
  var TIMEOUT_MS   = 12000;
  var SAMPLE = {
    _type: 'https://in-toto.io/Statement/v1',
    subject: [{ name: 'szl-lake/homflyreceipt_gate',
      digest: { sha256: '0a2d153d81c00688b576e5a012ae6117465639807456d1bb72eb590cac3b1e9d' } }],
    predicateType: 'https://szlholdings.com/attestations/innovation/v1',
    predicate: { note: 'paste your own receipt JSON here, or a public receipt URL' }
  };

  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  /* honest fetch contract: AbortController + try/catch. NEVER throws. ----- */
  function pull(url, opts, timeoutMs){
    var ctl = (typeof AbortController!=='undefined') ? new AbortController() : null;
    var to  = ctl ? setTimeout(function(){ try{ctl.abort();}catch(e){} }, timeoutMs||TIMEOUT_MS) : null;
    opts = opts || {};
    opts.signal = ctl ? ctl.signal : undefined;
    opts.cache  = 'no-store';
    opts.mode   = 'cors';
    return fetch(url, opts).then(function(r){
      if(to) clearTimeout(to);
      var status = r.status;
      return r.json().then(function(data){ return {ok:r.ok, status:status, data:data}; },
                          function(){ return {ok:false, status:status, data:null}; });
    }).catch(function(e){
      if(to) clearTimeout(to);
      var aborted = e && (e.name==='AbortError');
      return {ok:false, status:0, data:null, err:String(e&&e.message||e), aborted:aborted};
    });
  }

  /* map an HONEST verdict string -> {label, cls, advisory} ---------------- */
  function verdictView(v){
    var s = String(v||'').toUpperCase();
    if(s==='VERIFIED')        return {label:'VERIFIED',        cls:'ok',   advisory:false};
    if(s==='STRUCTURAL-ONLY') return {label:'STRUCTURAL-ONLY', cls:'warn', advisory:true};
    if(s==='FAILED')          return {label:'FAILED',          cls:'fail', advisory:false};
    if(s==='UNRECOGNISED')    return {label:'UNRECOGNISED',    cls:'muted',advisory:false};
    return {label: s||'—', cls:'muted', advisory:false};
  }

  function renderChecks(checks){
    if(!Array.isArray(checks) || !checks.length) return '';
    var rows = checks.map(function(c){
      var st = String(c.status||'').toLowerCase();
      var cls = st==='pass' ? 'ok' : (st==='fail' ? 'fail' : 'muted');
      return '<li class="szlv-chk"><span class="szlv-pill '+cls+'">'+esc(c.status||'?')+'</span>'+
             '<code>'+esc(c.name||'check')+'</code>'+
             (c.detail ? '<span class="szlv-det">'+esc(c.detail)+'</span>' : '')+'</li>';
    }).join('');
    return '<ul class="szlv-checks">'+rows+'</ul>';
  }

  function renderResult(res){
    // res is the {ok,status,data,err,aborted} envelope from pull()
    if(res.status===429){
      return '<div class="szlv-state fail">rate-limited · the fabric caps at 60/min per IP. '+
             'This is honest backpressure, not a failure of your receipt. Try again shortly.</div>';
    }
    if(!res.ok || !res.data){
      var why = res.aborted ? 'timed out' : (res.status ? ('HTTP '+res.status) : 'unreachable');
      return '<div class="szlv-state muted">offline · fabric '+esc(why)+
             '. No verdict shown — the widget never invents a green. '+
             'Re-run the checks yourself per docs/developers/VERIFY.md.</div>';
    }
    var d = res.data;
    var vv = verdictView(d.verdict);
    var head = '<div class="szlv-verdict '+vv.cls+'">'+
      '<span class="szlv-dot"></span><b>'+esc(vv.label)+'</b>'+
      (vv.advisory ? '<span class="szlv-adv">advisory · not a cryptographic green</span>' : '')+
      '</div>';
    var detail = d.detail ? '<p class="szlv-detail">'+esc(d.detail)+'</p>' : '';
    var kinds  = (Array.isArray(d.kinds)&&d.kinds.length)
      ? '<p class="szlv-kinds">recognised as: '+d.kinds.map(esc).join(', ')+'</p>' : '';
    var checks = renderChecks(d.checks);
    var foot = '<p class="szlv-foot">engine '+esc(d.engine_version||'?')+
      ' · doctrine '+esc((d.doctrine&&d.doctrine.version)||'v11')+
      ' · Λ='+esc((d.doctrine&&d.doctrine.lambda)||'Conjecture 1')+
      (d.verified_at ? ' · '+esc(d.verified_at) : '')+
      '<br><span class="szlv-trust">No trust in the server is required — re-verify with cosign / rekor-cli / lake build.</span></p>';
    return head+detail+kinds+checks+foot;
  }

  var CSS = [
    '.szlv{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;',
    'color:#cdccca;background:#1c1b19;border:1px solid #393836;border-radius:10px;padding:16px;max-width:640px}',
    '.szlv h3{font-size:15px;margin:0 0 4px;font-weight:600;letter-spacing:.2px}',
    '.szlv .szlv-sub{font-size:12px;color:#797876;margin:0 0 12px}',
    '.szlv textarea{width:100%;min-height:120px;box-sizing:border-box;background:#171614;color:#cdccca;',
    'border:1px solid #393836;border-radius:8px;padding:10px;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;resize:vertical}',
    '.szlv-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}',
    '.szlv input[type=text]{flex:1;min-width:200px;background:#171614;color:#cdccca;border:1px solid #393836;border-radius:8px;padding:8px 10px;font-size:12px}',
    '.szlv button{background:#01696f;color:#fff;border:0;border-radius:8px;padding:9px 16px;font-size:13px;font-weight:600;cursor:pointer}',
    '.szlv button:hover{background:#0c4e54}.szlv button:disabled{opacity:.5;cursor:wait}',
    '.szlv button.ghost{background:transparent;color:#4f98a3;border:1px solid #393836}',
    '.szlv-out{margin-top:12px;font-size:13px;min-height:24px}',
    '.szlv-load{color:#797876;font-size:12px}',
    '.szlv-verdict{display:flex;align-items:center;gap:8px;font-size:15px;padding:8px 10px;border-radius:8px;border:1px solid #393836}',
    '.szlv-verdict .szlv-dot{width:9px;height:9px;border-radius:50%}',
    '.szlv-verdict.ok .szlv-dot{background:#6daa45}.szlv-verdict.ok{border-color:#3a5a26}',
    '.szlv-verdict.warn .szlv-dot{background:#e8af34}.szlv-verdict.warn{border-color:#6b5418}',
    '.szlv-verdict.fail .szlv-dot{background:#d163a7}.szlv-verdict.fail{border-color:#7a2c5a}',
    '.szlv-verdict.muted .szlv-dot{background:#797876}',
    '.szlv-adv{font-size:11px;color:#e8af34;font-weight:400;margin-left:auto}',
    '.szlv-detail{font-size:12px;color:#a9a8a5;margin:8px 0}',
    '.szlv-kinds{font-size:11px;color:#797876;margin:4px 0}',
    '.szlv-checks{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-direction:column;gap:4px}',
    '.szlv-chk{display:flex;align-items:center;gap:8px;font-size:12px;flex-wrap:wrap}',
    '.szlv-pill{font-size:10px;text-transform:uppercase;letter-spacing:.4px;padding:2px 6px;border-radius:4px;font-weight:700}',
    '.szlv-pill.ok{background:rgba(109,170,69,.18);color:#6daa45}',
    '.szlv-pill.fail{background:rgba(209,99,167,.18);color:#d163a7}',
    '.szlv-pill.muted{background:#2a2927;color:#797876}',
    '.szlv-chk code{color:#cdccca}.szlv-det{color:#797876;font-size:11px}',
    '.szlv-foot{font-size:10px;color:#5a5957;margin:10px 0 0;line-height:1.5}',
    '.szlv-trust{color:#797876}',
    '.szlv-state{font-size:12px;padding:8px 10px;border-radius:8px}',
    '.szlv-state.fail{background:rgba(209,99,167,.10);color:#d163a7}',
    '.szlv-state.muted{background:#211f1d;color:#a9a8a5}',
    /* DEV B mobile refinement: 12px type floor + 44px touch targets (additive, no logic change) */
    '@media (max-width:768px){',
    '.szlv-adv,.szlv-kinds,.szlv-chk .szlv-det,.szlv-foot,.szlv-pill{font-size:12px}',
    '.szlv button{min-height:44px;padding:11px 18px;font-size:14px}',
    '.szlv input[type=text]{min-height:44px;font-size:13px}',
    '.szlv textarea{font-size:13px}',
    '.szlv-sub,.szlv-load,.szlv-detail,.szlv-state{font-size:13px}',
    '}'].join('');

  function injectCSS(){
    if(document.getElementById('szlv-css')) return;
    var st = document.createElement('style'); st.id='szlv-css'; st.textContent = CSS;
    document.head.appendChild(st);
  }

  /* Public mount: SZLVerify.mount('#id', {base})  ------------------------- */
  function mount(target, opts){
    opts = opts || {};
    var base = (opts.base || DEFAULT_BASE).replace(/\/+$/,'');
    var host = (typeof target==='string') ? document.querySelector(target) : target;
    if(!host) return null;
    injectCSS();
    host.classList.add('szlv');
    host.innerHTML =
      '<h3>ask the fabric — verify a receipt</h3>'+
      '<p class="szlv-sub">Paste a Khipu receipt / DSSE envelope / in-toto statement, '+
      'or fetch a public receipt by URL. Verdicts are the fabric\u2019s real, honest output '+
      '(unsigned \u2192 STRUCTURAL-ONLY, never a false green).</p>'+
      '<textarea class="szlv-ta" spellcheck="false"></textarea>'+
      '<div class="szlv-row">'+
        '<input type="text" class="szlv-url" placeholder="\u2026or a public receipt URL (https://\u2026/receipt.json)">'+
      '</div>'+
      '<div class="szlv-row">'+
        '<button class="szlv-go" type="button">Verify</button>'+
        '<button class="szlv-sample ghost" type="button">Load sample receipt</button>'+
      '</div>'+
      '<div class="szlv-out" aria-live="polite"></div>';

    var ta  = host.querySelector('.szlv-ta');
    var url = host.querySelector('.szlv-url');
    var out = host.querySelector('.szlv-out');
    var go  = host.querySelector('.szlv-go');
    var smp = host.querySelector('.szlv-sample');

    smp.addEventListener('click', function(){ ta.value = JSON.stringify(SAMPLE, null, 2); url.value=''; });

    go.addEventListener('click', function(){
      go.disabled = true;
      out.innerHTML = '<span class="szlv-load">calling <code>'+esc(base)+'/api/a11oy/v1/verify</code>\u2026</span>';
      var p, u = url.value.trim(), body = ta.value.trim();
      if(u){
        p = pull(base+'/api/a11oy/v1/verify?url='+encodeURIComponent(u), {method:'GET'});
      } else if(body){
        var parsed = null;
        try{ parsed = JSON.parse(body); }catch(e){
          out.innerHTML = '<div class="szlv-state muted">input is not valid JSON — paste a receipt object or use a URL.</div>';
          go.disabled = false; return;
        }
        p = pull(base+'/api/a11oy/v1/verify', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(parsed)});
      } else {
        out.innerHTML = '<div class="szlv-state muted">paste a receipt JSON, or enter a public receipt URL.</div>';
        go.disabled = false; return;
      }
      p.then(function(res){ out.innerHTML = renderResult(res); go.disabled = false; });
    });

    return { reload:function(){}, base:base };
  }

  var api = { mount: mount, pull: pull, _sample: SAMPLE, version: '1.0.0' };
  if (typeof module!=='undefined' && module.exports) module.exports = api;
  global.SZLVerify = api;
})(typeof window!=='undefined' ? window : this);
