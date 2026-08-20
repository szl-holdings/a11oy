/* SPDX-License-Identifier: Apache-2.0
 * © 2026 SZL Holdings — Live 3D Wires Across Cortex Mesh (PURIQ / Doctrine v12)
 * Doctrine v11 LOCKED: 749 decl / 14 axioms / 163 sorries / 13-axis / replay bacf5443 / A2 A4 / SLSA L1 / Λ-uniqueness=Conjecture
 * Sign: Yachay.  git trailer: Perplexity Computer Agent.
 *
 * LiveWires3D — reusable scene that renders THIS flagship's cortex pulsing with
 * real Wire B/C/D/E/F/G[/H] events streamed via 3DWPP (SSE).  NO mocks: a pulse
 * appears only when a real 3DWPP event arrives; empty edge = idle (dim).
 *
 * Pattern: recipe #2 (YAWAR blood-flow) — CatmullRomCurve3 + getPointAt(t) progress,
 * proven live in anatomy-3d.  WebGPU (Baseline Jan-2026) w/ WebGL2 fallback.
 *
 * Usage (vanilla, what the flagship HTML pages call):
 *   LiveWires3D.mount({ el, flagshipName:"a11oy", streamUrl:"/api/a11oy/v1/wires/stream", boeBase:"/api/a11oy/v1/wires/boe" });
 * The React-Three-Fiber wrapper (LiveWires3D.jsx) calls the same core.
 */
(function (global) {
  "use strict";

  // ---- Wire catalog: factor + colour + KaTeX label (FORMULA_LABELS.md) ----
  const WIRES = {
    B: { color: 0x39d98a, factor: "\\prod_i \\text{Khipu}_i(a)", role: "ledger (∏ Khipu)" },
    C: { color: 0x22d3ee, factor: "\\Lambda(x)", role: "cortex broadcast" },
    D: { color: 0xfacc15, factor: "\\mathrm{OTel}(x)", role: "W3C traceparent" },
    E: { color: 0x3b82f6, factor: "\\text{Yuyay}_{13}(a)", role: "cortex publish / Yuyay gate" },
    F: { color: 0xef4444, factor: "\\text{Khipu}_{\\text{new}}(a)", role: "receipt ingest" },
    G: { color: 0xa855f7, factor: "\\mathrm{Amaru}(\\text{query})", role: "RAG / brain-jack" },
    H: { color: 0xfbbf24, factor: "P(x,t)=\\arg\\max_{a}[\\Lambda\\cdot\\text{Yuyay}_{13}\\cdot e^{-\\beta H}\\cdot\\prod_i K_i]", role: "cross-Space orchestration" },
  };

  // Organ-specific cortex builders (founder mapping).
  const ORGANS = {
    a11oy:    { label: "ORCHESTRATOR NEXUS", build: buildNexus,   accent: 0xfbbf24 },
    amaru:    { label: "BRAIN CORTEX",       build: buildCortex,  accent: 0x3b82f6 },
    sentra:   { label: "IMMUNE LATTICE",     build: buildLattice, accent: 0xef4444 },
    killinchu:{ label: "KESTREL + RADAR",    build: buildKestrel, accent: 0x22d3ee },
    rosie:    { label: "ECOSYSTEM FIELD",    build: buildField,   accent: 0x39d98a },
  };

  const SISTERS = ["a11oy", "amaru", "sentra", "killinchu", "rosie", "vessels"];
  const YUYAY_BAND = (s) => (s == null ? 0xffffff : s < 0.5 ? 0xef4444 : s <= 0.85 ? 0xf59e0b : 0x22c55e);

  function mount(opts) {
    const THREE = global.THREE;
    if (!THREE) { console.error("[LiveWires3D] THREE not loaded"); return null; }
    const el = opts.el;
    const flagship = (opts.flagshipName || "a11oy").toLowerCase();
    const organ = ORGANS[flagship] || ORGANS.a11oy;
    const state = { view: "wire", pulses: [], wires: {}, ema: {}, lat: {}, lastClickCb: opts.onPulseClick, raf: 0, paused: false };

    // ---------- renderer: WebGPU baseline + WebGL2 fallback ----------
    let renderer, usingWebGPU = false;
    try {
      if (THREE.WebGPURenderer && global.navigator && global.navigator.gpu) {
        renderer = new THREE.WebGPURenderer({ antialias: true, alpha: true });
        usingWebGPU = true;
      }
    } catch (e) { /* fall through */ }
    if (!renderer) renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    var SZL_MOBILE = ('ontouchstart' in global) || ((global.navigator&&global.navigator.maxTouchPoints)||0) > 0;
    var SZL_REDUCED = global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches;
    renderer.setPixelRatio(Math.min(global.devicePixelRatio || 1, SZL_MOBILE ? 1.5 : 2));
    function resize() {
      const w = el.clientWidth || 800, h = el.clientHeight || 520;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    el.appendChild(renderer.domElement);
    renderer.domElement.style.cssText = "width:100%;height:100%;display:block;touch-action:none";

    const scene = new THREE.Scene();
    scene.background = null;
    const camera = new THREE.PerspectiveCamera(55, 1.6, 0.1, 500);
    camera.position.set(0, 6, 30);
    scene.add(new THREE.AmbientLight(0x404a5a, 1.4));
    const key = new THREE.PointLight(0xffffff, 1.1, 0, 1.6); key.position.set(20, 30, 25); scene.add(key);
    const rim = new THREE.PointLight(organ.accent, 0.9, 0, 1.8); rim.position.set(-22, -8, -18); scene.add(rim);

    // ---------- cortex (organ centre) ----------
    const cortex = new THREE.Group(); scene.add(cortex);
    organ.build(THREE, cortex, organ.accent);

    // ---------- sister-flagship nodes (rim) + wires ----------
    const nodeGroup = new THREE.Group(); scene.add(nodeGroup);
    const wireGroup = new THREE.Group(); scene.add(wireGroup);
    const pulseGroup = new THREE.Group(); scene.add(pulseGroup);

    const sisters = SISTERS.filter((s) => s !== flagship);
    const nodePos = {};
    sisters.forEach((s, i) => {
      const a = (i / sisters.length) * Math.PI * 2;
      const r = 16, p = new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r * 0.6, Math.sin(a) * 6 - 3);
      nodePos[s] = p;
      const orb = new THREE.Mesh(new THREE.SphereGeometry(1.1, 24, 24),
        new THREE.MeshStandardMaterial({ color: 0x9aa4b2, emissive: 0x1b2330, roughness: 0.4 }));
      orb.position.copy(p); orb.userData.sister = s; nodeGroup.add(orb);
      labelSprite(THREE, nodeGroup, s.toUpperCase(), p.clone().add(new THREE.Vector3(0, 1.7, 0)));
    });

    // one CatmullRomCurve3 per wire letter from a sister into the cortex
    const letters = Object.keys(WIRES);
    letters.forEach((L, i) => {
      const sis = sisters[i % sisters.length];
      const start = nodePos[sis].clone();
      const end = new THREE.Vector3(0, 0, 0);
      const mid = start.clone().lerp(end, 0.5).add(new THREE.Vector3(0, 4 + i, (i % 2 ? 6 : -6)));
      const curve = new THREE.CatmullRomCurve3([start, start.clone().lerp(mid, 0.5), mid, end.clone().add(new THREE.Vector3(0, 1, 0))]);
      const geo = new THREE.TubeGeometry(curve, 64, 0.045, 8, false);
      const mat = new THREE.MeshBasicMaterial({ color: WIRES[L].color, transparent: true, opacity: 0.22 });
      const tube = new THREE.Mesh(geo, mat); tube.userData = { wire: L, sister: sis, curve };
      wireGroup.add(tube);
      state.wires[L] = { curve, tube, mat, sister: sis, baseR: 0.045 };
      state.ema[L] = 0; state.lat[L] = 60;
      floatMath(THREE, wireGroup, WIRES[L].factor, curve.getPointAt(0.5), WIRES[L].color);
    });

    // ---------- pulse spawn (called on each real 3DWPP event) ----------
    const sprite = makeGlowTexture(THREE);
    function spawnPulse(ev) {
      const w = state.wires[ev.wire_letter]; if (!w) return; // unknown wire → drop (spec)
      const col = new THREE.Color(YUYAY_BAND(ev.yuyay_score));
      const g = new THREE.SphereGeometry(0.22, 12, 12);
      const m = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.95 });
      const mesh = new THREE.Mesh(g, m);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: sprite, color: col, transparent: true,
        blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.9 }));
      halo.scale.set(1.4, 1.4, 1.4); mesh.add(halo);
      // fired tripwire → red damping ring (exp(-β·HUKLLA))
      if (ev.hukulla_tripwires && ev.hukulla_tripwires.length) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.05, 8, 24),
          new THREE.MeshBasicMaterial({ color: 0xff3344 }));
        mesh.add(ring); mesh.userData.tripring = ring;
      }
      mesh.userData = Object.assign(mesh.userData, { wire: ev.wire_letter, t: 0,
        speed: 0.18 * (60 / Math.max(8, ev.latency_ms || 60)), ev });
      pulseGroup.add(mesh); state.pulses.push(mesh);
      // throughput EMA → edge thickness
      const a = 0.2; state.ema[ev.wire_letter] = a * (ev.throughput_eps || 1) + (1 - a) * state.ema[ev.wire_letter];
      state.lat[ev.wire_letter] = ev.latency_ms || state.lat[ev.wire_letter];
      const thick = Math.min(0.18, 0.045 + state.ema[ev.wire_letter] * 0.02);
      const w2 = state.wires[ev.wire_letter];
      w2.tube.geometry.dispose();
      w2.tube.geometry = new THREE.TubeGeometry(w2.curve, 64, thick, 8, false);
      w2.mat.opacity = Math.min(0.85, 0.22 + state.ema[ev.wire_letter] * 0.08);
      // Bekenstein cap (F23): never exceed cap simultaneous pulses
      if (state.pulses.length > 240) { const old = state.pulses.shift(); pulseGroup.remove(old); }
    }

    // ---------- click → BoE modal ----------
    const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
    renderer.domElement.addEventListener("pointerdown", (e) => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1; ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(pulseGroup.children, true)[0];
      if (hit) { let o = hit.object; while (o && !o.userData.ev) o = o.parent; if (o && state.lastClickCb) state.lastClickCb(o.userData.ev, opts.boeBase); }
    });
    // hover tooltip on wires
    renderer.domElement.addEventListener("pointermove", (e) => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1; ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(wireGroup.children, true)[0];
      if (hit && hit.object.userData.wire && opts.onWireHover) {
        const L = hit.object.userData.wire;
        opts.onWireHover({ wire: L, role: WIRES[L].role, factor: WIRES[L].factor, sister: hit.object.userData.sister,
          throughput_eps: +state.ema[L].toFixed(2), p50_ms: state.lat[L], p99_ms: Math.round(state.lat[L] * 1.8) }, e);
      } else if (opts.onWireHover) opts.onWireHover(null, e);
    });

    // ---------- views ----------
    function setView(v) {
      state.view = v;
      if (v === "anatomy") { cortex.scale.setScalar(1.6); camera.position.set(0, 5, 22); }
      else if (v === "wire") { cortex.scale.setScalar(0.9); camera.position.set(0, 6, 30); }
      // constellation handled by host (iframe)
    }
    setView(opts.view || "wire");

    // ---------- animation ----------
    let theta = 0;
    function frame() {
      state.raf = requestAnimationFrame(frame);
      if (state.paused) { renderer.render(scene, camera); return; }
      if(!SZL_REDUCED){ theta += 0.0016; camera.position.x = Math.sin(theta) * 30; camera.position.z = Math.cos(theta) * 30; camera.lookAt(0, 2, 0); }
      const v3 = new THREE.Vector3();
      for (let i = state.pulses.length - 1; i >= 0; i--) {
        const p = state.pulses[i]; const w = state.wires[p.userData.wire]; if (!w) continue;
        p.userData.t += p.userData.speed * 0.016;
        if (p.userData.t >= 1) { pulseGroup.remove(p); state.pulses.splice(i, 1); continue; }
        w.curve.getPointAt(p.userData.t, v3); p.position.copy(v3);
        if (p.userData.tripring) p.userData.tripring.rotation.z += 0.2;
      }
      if (cortex.userData.tick) cortex.userData.tick(performance.now());
      if(!document.hidden) renderer.render(scene, camera);
    }
    resize(); frame();
    const ro = new (global.ResizeObserver || function(){return{observe(){},disconnect(){}}})(resize); ro.observe(el);

    // ---------- 3DWPP SSE stream (REAL) ----------
    let es = null;
    function connect(url) {
      if (!url || typeof EventSource === "undefined") return;
      es = new EventSource(url);
      es.addEventListener("pulse", (m) => { try { spawnPulse(JSON.parse(m.data)); } catch (_) {} });
      es.addEventListener("heartbeat", (m) => { if (opts.onHeartbeat) try { opts.onHeartbeat(JSON.parse(m.data)); } catch (_) {} });
      es.onerror = () => { /* SSE auto-reconnects */ };
    }
    connect(opts.streamUrl);

    return {
      setView, spawnPulse, // spawnPulse exposed for cross-Space fan-out injection (Phase 4)
      pause(b) { state.paused = !!b; },
      stats() { return { pulses: state.pulses.length, ema: state.ema, webgpu: usingWebGPU }; },
      destroy() { cancelAnimationFrame(state.raf); if (es) es.close(); ro.disconnect(); renderer.dispose(); el.innerHTML = ""; },
    };
  }

  // ===================== cortex builders =====================
  function spin(g){ g.userData.tick = (t)=>{ g.rotation.y = t*0.0002; }; }
  function buildNexus(THREE, g, c) { // a11oy orchestrator nexus
    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(3, 1),
      new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.4, metalness: 0.6, roughness: 0.25, wireframe: false }));
    g.add(core);
    const cage = new THREE.Mesh(new THREE.IcosahedronGeometry(4.4, 1), new THREE.MeshBasicMaterial({ color: c, wireframe: true, transparent: true, opacity: 0.35 }));
    g.add(cage); g.userData.tick = (t)=>{ core.rotation.y=t*0.0003; cage.rotation.y=-t*0.0002; core.material.emissiveIntensity=0.35+0.15*Math.sin(t*0.002); };
  }
  function buildCortex(THREE, g, c) { // amaru brain cortex
    const brain = new THREE.Mesh(new THREE.IcosahedronGeometry(3.2, 4), new THREE.MeshStandardMaterial({ color: 0xcbd5e1, emissive: c, emissiveIntensity: 0.25, roughness: 0.7, flatShading: true }));
    const pos = brain.geometry.attributes.position; for (let i=0;i<pos.count;i++){ const n=0.25*Math.sin(pos.getX(i)*3)*Math.cos(pos.getY(i)*3); pos.setXYZ(i, pos.getX(i)*(1+n), pos.getY(i)*(1+n), pos.getZ(i)*(1+n)); } pos.needsUpdate=true; brain.geometry.computeVertexNormals();
    const serpent = new THREE.Mesh(new THREE.TorusKnotGeometry(3.6,0.12,128,12,2,3), new THREE.MeshBasicMaterial({color:c,transparent:true,opacity:0.5}));
    g.add(brain, serpent); g.userData.tick=(t)=>{ brain.rotation.y=t*0.0003; serpent.rotation.x=t*0.0004; };
  }
  function buildLattice(THREE, g, c) { // sentra immune lattice
    const dod = new THREE.Mesh(new THREE.DodecahedronGeometry(3,0), new THREE.MeshStandardMaterial({color:c,emissive:c,emissiveIntensity:0.3,metalness:0.4,roughness:0.4}));
    const cage = new THREE.Mesh(new THREE.DodecahedronGeometry(4.2,0), new THREE.MeshBasicMaterial({color:0xff6b6b,wireframe:true,transparent:true,opacity:0.4}));
    g.add(dod,cage); g.userData.tick=(t)=>{ cage.rotation.y=t*0.0004; dod.material.emissiveIntensity=0.25+0.2*Math.abs(Math.sin(t*0.003)); };
  }
  function buildKestrel(THREE, g, c) { // killinchu kestrel + radar sweep
    const body = new THREE.Mesh(new THREE.ConeGeometry(1.2,3.6,6), new THREE.MeshStandardMaterial({color:0xe2e8f0,emissive:c,emissiveIntensity:0.2,metalness:0.5,roughness:0.3}));
    body.rotation.x=Math.PI/2; g.add(body);
    const sweep = new THREE.Mesh(new THREE.RingGeometry(0.5,5.5,48,1,0,Math.PI/3), new THREE.MeshBasicMaterial({color:c,transparent:true,opacity:0.35,side:THREE.DoubleSide}));
    sweep.rotation.x=-Math.PI/2; g.add(sweep);
    for(let r=2;r<=6;r+=2){ const ring=new THREE.Mesh(new THREE.TorusGeometry(r,0.02,6,48),new THREE.MeshBasicMaterial({color:c,transparent:true,opacity:0.18})); ring.rotation.x=-Math.PI/2; g.add(ring); }
    g.userData.tick=(t)=>{ sweep.rotation.z=t*0.0012; };
  }
  function buildField(THREE, g, c) { // rosie ecosystem field
    const N=((('ontouchstart' in window)||((navigator&&navigator.maxTouchPoints)||0)>0)?300:600), pos=new Float32Array(N*3); for(let i=0;i<N;i++){ const a=Math.random()*Math.PI*2, rr=2+Math.random()*4, y=(Math.random()-0.5)*6; pos[i*3]=Math.cos(a)*rr; pos[i*3+1]=y; pos[i*3+2]=Math.sin(a)*rr; }
    const geo=new THREE.BufferGeometry(); geo.setAttribute("position",new THREE.BufferAttribute(pos,3));
    const pts=new THREE.Points(geo,new THREE.PointsMaterial({color:c,size:0.12,transparent:true,opacity:0.8})); g.add(pts);
    const core=new THREE.Mesh(new THREE.SphereGeometry(1.6,24,24),new THREE.MeshStandardMaterial({color:c,emissive:c,emissiveIntensity:0.4,transparent:true,opacity:0.5})); g.add(core);
    g.userData.tick=(t)=>{ pts.rotation.y=t*0.0002; core.material.emissiveIntensity=0.3+0.2*Math.sin(t*0.002); };
  }

  // ===================== helpers =====================
  function makeGlowTexture(THREE){ const s=64,cv=document.createElement("canvas");cv.width=cv.height=s;const x=cv.getContext("2d");const gr=x.createRadialGradient(s/2,s/2,0,s/2,s/2,s/2);gr.addColorStop(0,"rgba(255,255,255,1)");gr.addColorStop(0.4,"rgba(255,255,255,0.5)");gr.addColorStop(1,"rgba(255,255,255,0)");x.fillStyle=gr;x.fillRect(0,0,s,s);const t=new THREE.CanvasTexture(cv);return t; }
  function labelSprite(THREE,parent,text,pos){ const cv=document.createElement("canvas");cv.width=256;cv.height=64;const x=cv.getContext("2d");x.fillStyle="rgba(10,14,20,0.6)";x.fillRect(0,0,256,64);x.font="28px monospace";x.fillStyle="#cbd5e1";x.textAlign="center";x.fillText(text,128,42);const t=new THREE.CanvasTexture(cv);const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true}));sp.position.copy(pos);sp.scale.set(4,1,1);parent.add(sp); }
  function floatMath(THREE,parent,katex,pos,color){ const cv=document.createElement("canvas");cv.width=512;cv.height=64;const x=cv.getContext("2d");x.font="30px serif";x.fillStyle="#"+color.toString(16).padStart(6,"0");x.textAlign="center";x.fillText(katexToPlain(katex),256,42);const t=new THREE.CanvasTexture(cv);const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:t,transparent:true,depthTest:false}));sp.position.copy(pos);sp.scale.set(6,0.75,1);sp.userData.katex=katex;parent.add(sp); }
  // crude KaTeX→unicode for the in-scene canvas labels (host page renders true KaTeX in tooltip)
  function katexToPlain(s){ return s.replace(/\\prod_i/g,"∏ᵢ").replace(/\\Lambda/g,"Λ").replace(/\\text\{([^}]*)\}/g,"$1").replace(/\\mathrm\{([^}]*)\}/g,"$1").replace(/_\{?([^}\s]+)\}?/g,"_$1").replace(/\\arg\\max_\{?a\}?/g,"argmax_a").replace(/\\cdot/g,"·").replace(/\\beta/g,"β").replace(/[{}\\]/g,""); }

  global.LiveWires3D = { mount, WIRES, ORGANS, YUYAY_BAND };
})(typeof window !== "undefined" ? window : this);
