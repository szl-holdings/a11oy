// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — replit-sync/hf_spaces/hf_sda_space/assets/cop.js
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/* ============================================================================
 * SZL SDA — cop.js
 * The Common Operating Picture canvas: fused tracks as moving blips, anomaly
 * overlay coloured by score, and a sensor-fusion convergence for one object.
 * Plus the per-track anomaly-score panel.
 *
 * HONESTY: this is an explicit DEMONSTRATION on illustrative tracks. It runs
 * SDA's *real scoring shape* (ensemble + graph -> score in [0,1] -> Λ verdict),
 * but the track data is synthetic and clearly labelled DEMO. It NEVER fabricates
 * a "live" badge: sda-fabric.js flips it to LIVE only on a real endpoint read.
 * 0 runtime CDN · system fonts · prefers-reduced-motion honoured.
 * ==========================================================================*/
(function () {
  'use strict';

  var canvas = document.getElementById('cop-canvas');
  var panel  = document.getElementById('score-panel');
  if (!canvas || !panel) return;

  var ctx = canvas.getContext('2d');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- palette (must match style.css) ---- */
  var COL = {
    benign:'#3DD6FF', elevated:'#FFB454', anomaly:'#9D8BFF', fused:'#28E0D0',
    grid:'rgba(40,224,208,0.10)', ring:'rgba(40,224,208,0.22)',
    ink:'#9FC2C1', faint:'#6E8C8B'
  };

  /* ---- demo tracks: stable ids, honest illustrative kinematics ----
   * Each track has a baseline anomaly "target" score; the visible score
   * jitters slightly around it (demo), and the Λ verdict is derived from it.
   * track T-104 is the injected anomaly (maneuver+weave); T-106 elevated. */
  var TRACKS = [
    { id:'T-101', score:0.12, x:0.18, y:0.30, vx: 0.0006, vy: 0.0004, weave:0 },
    { id:'T-102', score:0.18, x:0.62, y:0.22, vx:-0.0005, vy: 0.0006, weave:0 },
    { id:'T-103', score:0.09, x:0.40, y:0.70, vx: 0.0007, vy:-0.0003, weave:0 },
    { id:'T-104', score:0.83, x:0.30, y:0.52, vx: 0.0010, vy: 0.0006, weave:1 }, // ANOMALY
    { id:'T-105', score:0.22, x:0.78, y:0.62, vx:-0.0004, vy:-0.0005, weave:0 },
    { id:'T-106', score:0.47, x:0.55, y:0.45, vx: 0.0006, vy: 0.0005, weave:0 }  // elevated
  ];
  // sensor-fusion demo object (two noisy reports -> one fused track)
  var FUSE = { x:0.50, y:0.84, vx:0.0008, vy:-0.0002 };

  function verdict(s){ return s >= 0.6 ? 'deny' : (s >= 0.4 ? 'advisory' : 'allow'); }
  function colourFor(s){ return s >= 0.6 ? COL.anomaly : (s >= 0.4 ? COL.elevated : COL.benign); }

  /* ---- DPR-aware sizing ---- */
  var W=0, H=0, DPR=1;
  function resize(){
    var r = canvas.getBoundingClientRect();
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  /* ---- radar field backdrop ---- */
  function drawField(t){
    ctx.clearRect(0,0,W,H);
    var cx = W*0.5, cy = H*0.5;
    var R = Math.min(W,H)*0.46;
    // range rings
    ctx.strokeStyle = COL.ring; ctx.lineWidth = 1;
    for (var k=1;k<=3;k++){ ctx.beginPath(); ctx.arc(cx,cy,R*k/3,0,Math.PI*2); ctx.stroke(); }
    // cross-hairs
    ctx.strokeStyle = COL.grid;
    ctx.beginPath(); ctx.moveTo(cx-R,cy); ctx.lineTo(cx+R,cy);
    ctx.moveTo(cx,cy-R); ctx.lineTo(cx,cy+R); ctx.stroke();
    // sweep wedge (skipped under reduced motion)
    if (!reduce){
      var a = (t*0.0006) % (Math.PI*2);
      var g = ctx.createRadialGradient(cx,cy,0,cx,cy,R);
      g.addColorStop(0,'rgba(40,224,208,0.16)');
      g.addColorStop(1,'rgba(40,224,208,0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.moveTo(cx,cy);
      ctx.arc(cx,cy,R,a,a+0.5); ctx.closePath(); ctx.fill();
    }
  }

  /* ---- a blip ---- */
  function drawBlip(tr, t){
    var x = tr.x*W, y = tr.y*H;
    var s = tr.score;
    var c = colourFor(s);
    // trail
    ctx.strokeStyle = c; ctx.globalAlpha = 0.28; ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (var i=0;i<8;i++){
      var px = (tr.x - tr.vx*i*16)*W, py=(tr.y - tr.vy*i*16)*H;
      if(i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);
    }
    ctx.stroke(); ctx.globalAlpha = 1;
    // anomaly ring (only elevated/anomaly), pulsing
    if (s >= 0.4){
      var pr = reduce ? 11 : 9 + Math.sin(t*0.004 + tr.x*9)*3;
      ctx.strokeStyle = c; ctx.globalAlpha = 0.8; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(x,y,pr,0,Math.PI*2); ctx.stroke(); ctx.globalAlpha=1;
    }
    // core dot
    ctx.fillStyle = c;
    ctx.shadowColor = c; ctx.shadowBlur = 10;
    ctx.beginPath(); ctx.arc(x,y,4.2,0,Math.PI*2); ctx.fill();
    ctx.shadowBlur = 0;
    // label
    ctx.fillStyle = COL.ink; ctx.font = '12px Calibri, system-ui, sans-serif';
    ctx.textAlign='left'; ctx.fillText(tr.id, x+9, y+3);
  }

  /* ---- sensor-fusion convergence (two noisy reports -> one fused) ---- */
  function drawFusion(t){
    var bx = FUSE.x*W, by = FUSE.y*H;
    var jit = reduce ? 0 : Math.sin(t*0.003);
    // sensor A report (cyan, noisy above)
    var ax = bx, ay = by - 10 + jit*5;
    // sensor B report (violet, noisy below)
    var vx2 = bx, vy2 = by + 10 - jit*5;
    ctx.globalAlpha = 0.85;
    ctx.fillStyle = COL.benign; ctx.beginPath(); ctx.arc(ax,ay,3,0,Math.PI*2); ctx.fill();
    ctx.fillStyle = COL.anomaly; ctx.beginPath(); ctx.arc(vx2,vy2,3,0,Math.PI*2); ctx.fill();
    // association lines into fused estimate
    ctx.strokeStyle = COL.fused; ctx.setLineDash([3,3]); ctx.lineWidth = 1;
    ctx.globalAlpha = 0.6;
    ctx.beginPath(); ctx.moveTo(ax,ay); ctx.lineTo(bx,by);
    ctx.moveTo(vx2,vy2); ctx.lineTo(bx,by); ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha = 1;
    // fused track marker (teal square)
    ctx.fillStyle = COL.fused; ctx.shadowColor = COL.fused; ctx.shadowBlur = 10;
    ctx.fillRect(bx-4,by-4,8,8); ctx.shadowBlur = 0;
    ctx.fillStyle = COL.fused; ctx.font = '12px Calibri, system-ui, sans-serif';
    ctx.textAlign='center'; ctx.fillText('fused', bx, by+20);
  }

  /* ---- advance demo kinematics, bounce inside field ---- */
  function step(dt){
    for (var i=0;i<TRACKS.length;i++){
      var tr = TRACKS[i];
      tr.x += tr.vx*dt; tr.y += tr.vy*dt;
      if (tr.weave){ tr.y += Math.sin((perfT+i)*0.004)*0.0015; } // anomalous weave
      if (tr.x<0.06||tr.x>0.94) tr.vx*=-1;
      if (tr.y<0.06||tr.y>0.94) tr.vy*=-1;
      tr.x=Math.max(0.06,Math.min(0.94,tr.x)); tr.y=Math.max(0.06,Math.min(0.94,tr.y));
    }
    FUSE.x += FUSE.vx*dt; FUSE.y += FUSE.vy*dt;
    if (FUSE.x<0.1||FUSE.x>0.9) FUSE.vx*=-1;
    if (FUSE.y<0.5||FUSE.y>0.92) FUSE.vy*=-1;
  }

  /* ---- score panel render (DOM) ---- */
  var rows = {};
  function buildPanel(){
    panel.innerHTML = '';
    TRACKS.slice().sort(function(a,b){return b.score-a.score;}).forEach(function(tr){
      var row = document.createElement('div'); row.className='score-row';
      var v = verdict(tr.score), c = colourFor(tr.score);
      row.innerHTML =
        '<span class="tid">'+tr.id+'</span>'+
        '<span class="bar-wrap"><span class="bar" style="width:'+Math.round(tr.score*100)+'%;background:'+c+';box-shadow:0 0 8px '+c+'"></span></span>'+
        '<span class="sval" style="color:'+c+'">'+tr.score.toFixed(2)+'</span>'+
        '<span class="vd '+v+'">'+v+'</span>';
      panel.appendChild(row);
      rows[tr.id] = row;
    });
  }

  /* allow sda-fabric.js to push REAL endpoint scores in (re-labels handled there) */
  window.SDA_COP = {
    setTracks: function(list){
      if (!Array.isArray(list) || !list.length) return;
      // map live tracks onto demo positions where ids match; keep motion
      list.forEach(function(L){
        var found=false;
        for (var i=0;i<TRACKS.length;i++){ if(TRACKS[i].id===L.id){ TRACKS[i].score=clamp01(L.score); found=true; } }
        if(!found && TRACKS.length){ TRACKS[0].id=L.id; TRACKS[0].score=clamp01(L.score); }
      });
      buildPanel();
    }
  };
  function clamp01(n){ n=Number(n); return isFinite(n)?Math.max(0,Math.min(1,n)):0; }

  /* ---- loop ---- */
  var perfT = 0, last = 0, raf=null;
  function loop(now){
    var dt = Math.min(48, now-last); last=now; perfT=now;
    step(dt);
    drawField(now);
    drawFusion(now);
    for (var i=0;i<TRACKS.length;i++) drawBlip(TRACKS[i], now);
    raf = requestAnimationFrame(loop);
  }
  function drawStatic(){
    drawField(0); drawFusion(0);
    for (var i=0;i<TRACKS.length;i++) drawBlip(TRACKS[i], 0);
  }

  function boot(){
    resize(); buildPanel();
    if (reduce){ drawStatic(); }
    else { last = performance.now(); raf = requestAnimationFrame(loop);
      document.addEventListener('visibilitychange', function(){
        if (document.hidden){ if(raf) cancelAnimationFrame(raf); raf=null; }
        else if(!raf){ last=performance.now(); raf=requestAnimationFrame(loop); }
      });
    }
  }
  var rzT=null;
  window.addEventListener('resize', function(){ clearTimeout(rzT); rzT=setTimeout(function(){ resize(); if(reduce) drawStatic(); }, 150); });
  window.addEventListener('orientationchange', function(){ setTimeout(function(){ resize(); if(reduce) drawStatic(); }, 200); });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
