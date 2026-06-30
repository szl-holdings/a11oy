/* ============================================================================
 * a11oy_landing.js — holographic hero for the a11oy front door.
 *
 * THE MOTIF: a "governed inference field" — a holographic glass governance core
 * (fresnel icosahedron) wrapped by an instanced-particle shell whose points are
 * gated inference tokens streaming inward and being sealed at the core. The core
 * pulses on the advisory Λ trust-ceiling; particles that "pass the gate" brighten
 * to holo-teal, the rest dim — a literal picture of deny-by-default governance.
 *
 * SOVEREIGN: Three.js r160 (MIT) + nothing else, vendored in-image under
 * /hero/vendor3d (importmap in a11oy_landing.html). 0 runtime CDN. Bloom is faked
 * with additive fresnel + a layered glow sprite (no postprocessing dependency).
 *
 * HONESTY DOCTRINE v11: Λ = Conjecture 1 (advisory, NOT a theorem). Nothing here
 * fabricates a number — the scene is a motif; all live figures are fetched and
 * labelled by a11oy_landing.html. locked-proven kernel = EXACTLY 8.
 *
 * PERF: capped DPR, instanced points (single draw call), 60fps target. Honors
 * prefers-reduced-motion (renders one static frame) and downshifts particle count
 * on small / low-DPR devices.
 *
 * VISUAL FIX (2026-06-30): Tamed the canvas from blinding-cyan flood to a
 * restrained, elegant dark field. Key changes:
 *  - Core glow opacity: clamped to 0.40 max (was 0.92) — whispers, doesn't shout
 *  - Halo sprite: opacity 0.10 (was 0.55), scale 7×7 (was 9×9)
 *  - Particle alpha: gate-pass 0.45 (was 0.95), denied 0.18 (was 0.40)
 *  - Canvas renderer alpha: transparent over deep near-black page bg (#05070d)
 *  - Colors desaturated: teal at 30% brightness, dim at near-black for particles
 *  - Net effect: holographic mesh whispers on deep dark, never floods
 *
 * Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
 * ========================================================================== */
import * as THREE from "three";

const REDUCED = window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MOBILE = Math.min(window.innerWidth, window.innerHeight) < 720 ||
  /Mobi|Android/i.test(navigator.userAgent);

// Desaturated, restrained palette — hairlines on near-black, not bright floods
const TEAL = new THREE.Color(0x1a6b63);  // deep teal — was 0x39d8c8 (too bright)
const DEEP = new THREE.Color(0x2a3578);  // muted violet — was 0x6a7bff (too bright)
const DIM  = new THREE.Color(0x0a0f1c);  // near-black for denied particles

export function mountHero(canvas) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({
      canvas, antialias: !MOBILE, alpha: true, powerPreference: "high-performance",
    });
  } catch (e) {
    return { ok: false, reason: String(e) };
  }
  if (!renderer.getContext()) return { ok: false, reason: "no-webgl" };

  const DPR = Math.min(window.devicePixelRatio || 1, MOBILE ? 1.5 : 2);
  renderer.setPixelRatio(DPR);
  renderer.setClearColor(0x000000, 0); // fully transparent — page bg shows through

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
  camera.position.set(0, 0, 7.2);

  const root = new THREE.Group();
  scene.add(root);

  // ---- Governance core: fresnel-shaded glass icosahedron --------------------
  const coreGeo = new THREE.IcosahedronGeometry(1.55, MOBILE ? 2 : 4);
  const coreMat = new THREE.ShaderMaterial({
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    uniforms: {
      uTime: { value: 0 },
      uLambda: { value: 0.97 },     // advisory Λ ceiling (Conjecture 1)
      uTeal: { value: new THREE.Vector3(TEAL.r, TEAL.g, TEAL.b) },
      uDeep: { value: new THREE.Vector3(DEEP.r, DEEP.g, DEEP.b) },
    },
    vertexShader: /* glsl */`
      varying vec3 vN; varying vec3 vView;
      uniform float uTime;
      void main(){
        vN = normalize(normalMatrix * normal);
        vec3 p = position;
        // gentle breathing displacement along the normal
        float w = sin(uTime*0.8 + position.y*2.0)*0.03
                + sin(uTime*1.3 + position.x*3.0)*0.02;
        p += normal * w;
        vec4 mv = modelViewMatrix * vec4(p,1.0);
        vView = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      varying vec3 vN; varying vec3 vView;
      uniform float uTime; uniform float uLambda;
      uniform vec3 uTeal; uniform vec3 uDeep;
      void main(){
        float fres = pow(1.0 - max(dot(normalize(vN), normalize(vView)), 0.0), 2.4);
        // Λ-pulse: the shell breathes gently — restrained, not flooding
        float pulse = 0.5 + 0.5*sin(uTime*1.6);
        // TAMED: glow multiplier capped — elegant whisper, not a bright flood
        float glow = fres * (0.28 + 0.18*pulse) * uLambda;
        vec3 col = mix(uDeep, uTeal, fres);
        // max alpha 0.40 — ensures the dark page bg always dominates
        gl_FragColor = vec4(col * glow, clamp(glow,0.0,0.40));
      }`,
  });
  const core = new THREE.Mesh(coreGeo, coreMat);
  root.add(core);

  // wire lattice over the core (deny-by-default cage) — very dim hairlines
  const cage = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.62, 1)),
    new THREE.LineBasicMaterial({ color: 0x1a4a46, transparent: true, opacity: 0.14 })
  );
  root.add(cage);

  // ---- Inference field: instanced particle shell ---------------------------
  const COUNT = REDUCED ? 1400 : (MOBILE ? 2600 : 7000);
  const pGeo = new THREE.BufferGeometry();
  const pos = new Float32Array(COUNT * 3);
  const seed = new Float32Array(COUNT);       // per-particle phase
  const radius = new Float32Array(COUNT);     // home radius
  const gate = new Float32Array(COUNT);       // 1 = passed gate, 0 = denied
  for (let i = 0; i < COUNT; i++) {
    // even-ish sphere distribution (golden spiral)
    const t = i / COUNT;
    const phi = Math.acos(1 - 2 * t);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const r = 2.4 + Math.random() * 2.6;
    pos[i*3+0] = Math.sin(phi) * Math.cos(theta) * r;
    pos[i*3+1] = Math.cos(phi) * r;
    pos[i*3+2] = Math.sin(phi) * Math.sin(theta) * r;
    seed[i] = Math.random() * Math.PI * 2;
    radius[i] = r;
    gate[i] = Math.random() < 0.62 ? 1.0 : 0.0;  // ~Λ share pass the gate
  }
  pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pGeo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
  pGeo.setAttribute("aRadius", new THREE.BufferAttribute(radius, 1));
  pGeo.setAttribute("aGate", new THREE.BufferAttribute(gate, 1));

  const pMat = new THREE.ShaderMaterial({
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    uniforms: {
      uTime: { value: 0 },
      uDpr: { value: DPR },
      uTeal: { value: new THREE.Vector3(TEAL.r, TEAL.g, TEAL.b) },
      uDim: { value: new THREE.Vector3(DIM.r, DIM.g, DIM.b) },
    },
    vertexShader: /* glsl */`
      attribute float aSeed; attribute float aRadius; attribute float aGate;
      uniform float uTime; uniform float uDpr;
      varying float vGate; varying float vTw;
      void main(){
        vGate = aGate;
        // tokens drift inward then reset — a stream toward the governed core
        float flow = fract(uTime*0.06 + aSeed*0.16);
        float r = mix(aRadius, 1.75, flow*flow);
        vec3 p = normalize(position) * r;
        // subtle orbital sway
        p.x += sin(uTime*0.5 + aSeed)*0.05;
        p.y += cos(uTime*0.4 + aSeed*1.3)*0.05;
        vTw = 0.6 + 0.4*sin(uTime*3.0 + aSeed*6.0);
        vec4 mv = modelViewMatrix * vec4(p,1.0);
        float size = (aGate>0.5 ? 5.5 : 2.6) * uDpr;
        gl_PointSize = size * (300.0 / -mv.z);
        gl_Position = projectionMatrix * mv;
      }`,
    fragmentShader: /* glsl */`
      precision highp float;
      varying float vGate; varying float vTw;
      uniform vec3 uTeal; uniform vec3 uDim;
      void main(){
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        if (d > 0.5) discard;
        float a = smoothstep(0.5, 0.0, d);
        vec3 col = mix(uDim, uTeal, vGate) * (vGate>0.5 ? vTw : 0.5);
        // TAMED: max alpha 0.45 gate-pass, 0.18 denied — subtle field on dark bg
        gl_FragColor = vec4(col, a * (vGate>0.5 ? 0.45 : 0.18));
      }`,
  });
  const points = new THREE.Points(pGeo, pMat);
  root.add(points);

  // ---- soft additive halo sprite (fake bloom) — very restrained -----------
  // TAMED: opacity 0.10 (was 0.55), scale 7×7 (was 9×9) — barely perceptible glow
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: makeHaloTexture(), transparent: true, blending: THREE.AdditiveBlending,
    depthWrite: false, opacity: 0.10, color: 0x1a6b63,
  }));
  halo.scale.set(7, 7, 1);
  scene.add(halo);

  // ---- resize ---------------------------------------------------------------
  function resize() {
    const r = canvas.getBoundingClientRect();
    const w = Math.max(1, r.width), h = Math.max(1, r.height);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener("resize", resize, { passive: true });

  // ---- pointer parallax -----------------------------------------------------
  let px = 0, py = 0, tx = 0, ty = 0;
  if (!REDUCED) {
    window.addEventListener("pointermove", (e) => {
      tx = (e.clientX / window.innerWidth - 0.5);
      ty = (e.clientY / window.innerHeight - 0.5);
    }, { passive: true });
  }

  // ---- render loop ----------------------------------------------------------
  const clock = new THREE.Clock();
  let raf = 0, running = true;

  function frame() {
    if (!running) return;
    const t = clock.getElapsedTime();
    coreMat.uniforms.uTime.value = t;
    pMat.uniforms.uTime.value = t;
    px += (tx - px) * 0.04; py += (ty - py) * 0.04;
    root.rotation.y = t * 0.12 + px * 0.6;
    root.rotation.x = py * 0.4;
    cage.rotation.y = -t * 0.05;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(frame);
  }

  if (REDUCED) {
    coreMat.uniforms.uTime.value = 1.2;
    pMat.uniforms.uTime.value = 1.2;
    renderer.render(scene, camera);
  } else {
    // pause when the hero scrolls out of view (battery + perf)
    const io = new IntersectionObserver((ents) => {
      for (const en of ents) {
        if (en.isIntersecting && !running) { running = true; clock.start(); frame(); }
        else if (!en.isIntersecting && running) { running = false; cancelAnimationFrame(raf); }
      }
    }, { threshold: 0.01 });
    io.observe(canvas);
    frame();
  }

  return { ok: true, renderer, setLambda(v){ coreMat.uniforms.uLambda.value = v; } };
}

// radial-gradient halo texture, built in-canvas (no asset, no CDN)
// TAMED: core stop 0.18 (was 0.55) — barely-visible glow ring on dark bg
function makeHaloTexture() {
  const s = 256;
  const c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(s/2, s/2, 0, s/2, s/2, s/2);
  grad.addColorStop(0.0, "rgba(26,107,99,0.18)");   // was rgba(57,216,200,0.55)
  grad.addColorStop(0.25, "rgba(26,107,99,0.06)");  // was rgba(57,216,200,0.18)
  grad.addColorStop(1.0, "rgba(26,107,99,0.0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}
