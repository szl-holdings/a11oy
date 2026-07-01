/* ============================================================================
 * SZL SDA — sda-fabric.js
 * Honest, vendored, 0-CDN runtime wiring:
 *   1. Live read of a11oy /v1/compute-pool with captured SNAPSHOT fallback.
 *   2. Optional live read of killinchu /mosaic feed -> COP score panel (LIVE label).
 *   3. Mount the "ask the fabric — verify a receipt" widget.
 *   4. Poll for an SDA validation figure and swap it in when present.
 * NEVER fabricates live status / numbers. Honest degradation per doctrine v11.
 * ==========================================================================*/
(function () {
  'use strict';
  var A11OY = 'https://a-11-oy.com';
  var POOL  = '/api/a11oy/v1/compute-pool';
  var KILLINCHU = 'https://szlholdings-killinchu.hf.space'; // estate killinchu surface (HF Space host)
  var MOSAIC_COP = '/api/killinchu/v1/mosaic/cop';          // fused COP + anomaly scores (PR #118)
  var TIMEOUT = 9000;

  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

  function pull(url, timeoutMs){
    var ctl = (typeof AbortController!=='undefined') ? new AbortController() : null;
    var to  = ctl ? setTimeout(function(){ try{ctl.abort();}catch(e){} }, timeoutMs||TIMEOUT) : null;
    return fetch(url, { signal: ctl ? ctl.signal : undefined, cache:'no-store' })
      .then(function(r){ if(to)clearTimeout(to); if(!r.ok) throw new Error('http '+r.status); return r.json(); })
      .catch(function(e){ if(to)clearTimeout(to); throw e; });
  }

  /* ---- compute-pool node list ---- */
  function nodeRow(n){
    var up = !!n.reachable;
    var sov = !!n.sovereign;
    var kindCls = sov ? 'sov' : (n.kind && n.kind.indexOf('hosted')===0 ? 'hosted' : '');
    var kindLabel = sov ? 'sovereign' : (n.kind || 'node');
    var meta = (n.endpoint ? esc(n.endpoint) : '') +
      (sov ? '' : (n.kind && n.kind.indexOf('hosted')===0 ? ' · hosted fallback — not compute you own' : ''));
    return '<li class="node">'+
      '<span class="ndot '+(up?'up':'down')+'" title="'+(up?'reachable':'unreachable')+'"></span>'+
      '<span class="ninfo"><span class="nname">'+esc(n.name||'node')+
        (up?'':' · <span style="color:#FF6B7A">unreachable</span>')+'</span>'+
        '<span class="nmeta">'+meta+'</span></span>'+
      '<span class="nkind '+kindCls+'">'+esc(kindLabel)+'</span>'+
    '</li>';
  }

  function renderPool(d, isLive){
    var list = document.getElementById('node-list');
    var srcBadge = document.getElementById('pool-src');
    var connBadge = document.getElementById('conn-badge');
    var connLabel = document.getElementById('conn-label');
    if(!list) return;

    var nodes = (d && d.nodes) || [];
    list.innerHTML = nodes.map(nodeRow).join('') || '<li class="node"><span class="ninfo"><span class="nname">No nodes reported.</span></span></li>';

    var c = (d && d.counts) || {};
    var summary = document.createElement('li');
    summary.className = 'node'; summary.style.background='transparent'; summary.style.border='none';
    summary.innerHTML = '<span class="ninfo"><span class="nmeta tabular">'+
      (c.nodes_reachable!=null?esc(c.nodes_reachable):'?')+'/'+(c.nodes_total!=null?esc(c.nodes_total):'?')+' reachable · '+
      (c.gpu_nodes_reachable!=null?esc(c.gpu_nodes_reachable):'?')+' GPU node(s) · sovereign_gpu_live='+
      esc(String((c.sovereign_gpu_live!=null)?c.sovereign_gpu_live:'?'))+'</span></span>';
    list.appendChild(summary);

    if(isLive){
      if(srcBadge){ srcBadge.textContent='LIVE'; srcBadge.classList.add('live'); }
      if(connBadge){ connBadge.classList.remove('snapshot'); }
      if(connLabel){ connLabel.textContent='FABRIC: LIVE'; }
    } else {
      if(srcBadge){ srcBadge.textContent='SNAPSHOT'; srcBadge.classList.remove('live'); }
      if(connBadge){ connBadge.classList.add('snapshot'); }
      if(connLabel){ connLabel.textContent='FABRIC: SNAPSHOT'; }
    }
  }

  function loadPool(){
    pull(A11OY+POOL)
      .then(function(d){ renderPool(d, true); })
      .catch(function(){
        pull('./assets/snapshot-compute-pool.json', 4000)
          .then(function(d){ renderPool(d, false); })
          .catch(function(){
            var list = document.getElementById('node-list');
            var connLabel = document.getElementById('conn-label');
            if(list) list.innerHTML = '<li class="node"><span class="ninfo"><span class="nname">Fabric unreachable.</span>'+
              '<span class="nmeta">Live read and snapshot both unavailable — status not shown rather than faked.</span></span></li>';
            if(connLabel) connLabel.textContent='FABRIC: UNREACHABLE';
          });
      });
  }

  /* ---- killinchu /mosaic COP feed (LIVE upgrade of the demo COP) ----
   * If killinchu's /mosaic/cop is reachable, push real anomaly scores into the
   * COP panel and re-label the COP badges LIVE. Otherwise the demo stands,
   * clearly labelled. NEVER fakes a live read. */
  function loadMosaicCOP(){
    pull(KILLINCHU+MOSAIC_COP)
      .then(function(d){
        var tracks = (d && (d.tracks || d.cop || d.fused)) || [];
        var norm = tracks.map(function(t){
          return { id: t.track_id || t.id || ('T-'+(t.fused_track_id||'?')),
                   score: (t.anomaly_score!=null?t.anomaly_score:(t.score!=null?t.score:0)) };
        }).filter(function(t){ return t.id; });
        if (norm.length && window.SDA_COP && window.SDA_COP.setTracks){
          window.SDA_COP.setTracks(norm);
          markCopLive();
        }
      })
      .catch(function(){ /* keep honest DEMO label; no fabrication */ });
  }
  function markCopLive(){
    ['cop-src','cop-feed-src'].forEach(function(id){
      var b=document.getElementById(id); if(b){ b.textContent='LIVE · killinchu /mosaic'; b.classList.add('live'); }
    });
    var note=document.getElementById('cop-demo-note');
    if(note){ note.innerHTML='<strong>Live read.</strong> The COP panel is showing real anomaly scores from the killinchu <code>/api/killinchu/v1/mosaic/cop</code> endpoint. Track motion remains an illustrative rendering; the scores and verdicts are live.'; }
  }

  /* ---- SDA validation figure swap-in (silent HEAD probe; no 404 noise) ---- */
  function tryFigure(){
    var img = document.getElementById('sda-fig-img');
    if(!img) return;
    fetch('assets/sda_validation.png', { method:'HEAD', cache:'no-store' })
      .then(function(r){ if(!r.ok) throw new Error('absent'); return r; })
      .then(function(){
        img.onload = function(){
          img.style.display='block';
          var stage=document.querySelector('.cop-stage');
          var note=document.getElementById('cop-demo-note');
          var src=document.getElementById('cop-src');
          if(stage) stage.parentNode && stage.parentNode.insertBefore(img, stage);
          if(note){ note.innerHTML='<strong>SZL SDA validation figure.</strong> Produced by the khipu-sda-core validation harness.'; }
          if(src){ src.textContent='SZL SDA — VALIDATION'; src.classList.add('live'); }
        };
        img.src='assets/sda_validation.png';
      })
      .catch(function(){ /* keep honest labelled demo COP */ });
  }

  function boot(){
    loadPool();
    loadMosaicCOP();
    tryFigure();
    if (window.SZLVerify && typeof window.SZLVerify.mount === 'function') {
      try { window.SZLVerify.mount('#verify-mount', { base: A11OY }); } catch(e){}
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
