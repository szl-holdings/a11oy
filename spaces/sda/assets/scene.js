// VENDORED FROM szl-holdings/platform@e87ad75ec8e280e2fe3a3e8f49c5c0b6c2eec4ea — replit-sync/hf_spaces/hf_sda_space/assets/scene.js
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
/* ============================================================================
 * SZL SDA — scene.js  (ES module, three.js MIT vendored locally)
 * A quiet ambient backdrop: a drifting field of "track" points with a faint
 * sweep, suggesting a domain-awareness picture. Decorative only — never encodes
 * a real detection. Mobile: DPR capped, paused off-screen / reduced-motion.
 * ==========================================================================*/
import * as THREE from 'three';

(function () {
  'use strict';
  var canvas = document.getElementById('sda-canvas');
  if (!canvas) return;

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var renderer, scene, camera, points, raf = null, running = false;
  var W = window.innerWidth, H = window.innerHeight;

  function dpr(){ return Math.min(W < 760 ? 1.5 : 1.75, window.devicePixelRatio || 1); }

  try {
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: W >= 760, alpha: true, powerPreference: 'low-power' });
  } catch (e) { return; } // WebGL unavailable: CSS gradient backdrop remains, page intact.

  renderer.setPixelRatio(dpr());
  renderer.setSize(W, H, false);

  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 100);
  camera.position.set(0, 0, 20);

  var N = W < 760 ? 1300 : 2400;
  var pos = new Float32Array(N * 3);
  var col = new Float32Array(N * 3);
  var base = new Float32Array(N * 3);
  var cBenign = new THREE.Color(0x3DD6FF);
  var cFused  = new THREE.Color(0x28E0D0);
  var cAnom   = new THREE.Color(0x9D8BFF);

  var i, x, y, z, r, a;
  for (i = 0; i < N; i++) {
    // distribute in a soft disc (a "domain" of tracks)
    a = Math.random() * Math.PI * 2;
    r = Math.sqrt(Math.random()) * 16;
    x = Math.cos(a) * r;
    y = Math.sin(a) * r * 0.62;
    z = (Math.random() - 0.5) * 6;
    base[i*3]=x; base[i*3+1]=y; base[i*3+2]=z;
    pos[i*3]=x; pos[i*3+1]=y; pos[i*3+2]=z;
    // a few violet "anomalies" sprinkled in, mostly benign cyan, occasional teal
    var rnd = Math.random();
    var c = rnd > 0.93 ? cAnom : (rnd > 0.80 ? cFused : cBenign);
    col[i*3]=c.r; col[i*3+1]=c.g; col[i*3+2]=c.b;
  }

  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  var mat = new THREE.PointsMaterial({ size: 0.09, vertexColors: true, transparent: true,
    opacity: 0.66, depthWrite: false, blending: THREE.AdditiveBlending });
  points = new THREE.Points(geo, mat);
  scene.add(points);

  var t0 = performance.now();
  function frame(now) {
    var t = (now - t0) / 1000;
    var p = geo.attributes.position.array;
    for (i = 0; i < N; i++) {
      var bx = base[i*3], by = base[i*3+1], bz = base[i*3+2];
      p[i*3]   = bx + Math.sin(t*0.25 + by*0.2) * 0.10;
      p[i*3+1] = by + Math.cos(t*0.22 + bx*0.15) * 0.08;
      p[i*3+2] = bz + Math.sin(t*0.4 + i*0.04) * 0.14;
    }
    geo.attributes.position.needsUpdate = true;
    points.rotation.z = Math.sin(t*0.04) * 0.05;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(frame);
  }

  function start(){ if(running) return; running=true; t0=performance.now(); raf=requestAnimationFrame(frame); }
  function stop(){ running=false; if(raf) cancelAnimationFrame(raf); raf=null; }
  function renderOnce(){ renderer.render(scene, camera); }

  function onResize(){
    W = window.innerWidth; H = window.innerHeight;
    camera.aspect = W/H; camera.updateProjectionMatrix();
    renderer.setPixelRatio(dpr()); renderer.setSize(W,H,false);
    if(!running) renderOnce();
  }
  window.addEventListener('resize', onResize);
  window.addEventListener('orientationchange', onResize);

  if (reduce) {
    renderOnce();
  } else {
    start();
    document.addEventListener('visibilitychange', function(){
      if (document.hidden) stop(); else start();
    });
  }
})();
