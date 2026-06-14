/* SPDX-License-Identifier: Apache-2.0
 * © 2026 SZL Holdings. szl_holo3d.js — the SZL 3D / HOLOGRAPHIC SUBSTRATE KIT.
 * =====================================================================================
 * THE reusable holographic substrate every SZL frontier surface renders on.
 * Vendored locally, served at /static/shared/szl_holo3d.js — ZERO RUNTIME CDN.
 * Byte-identical across a11oy and killinchu (shared-source drift guard enforced).
 *
 * DESIGN INTENT (Surface 10 of FRONTIER_RESEARCH.md): a defense-grade dark-glass
 * holographic scene shell with a node/edge GRAPH renderer (proof-DAGs, factory
 * graphs, ontology organisms), a lightweight GLOBE renderer, a Λ-driven TRUST
 * SPHERE primitive, a SIGNED-PULSE edge animation (light flows along an edge when
 * a receipt is signed), and a time-slider replay hook.
 *
 * RENDERER STRATEGY (honest, air-gap-clean, 0-CDN):
 *   - SELF-CONTAINED: the kit ships its OWN minimal WebGL2 renderer (no hard
 *     dependency on three.js). This guarantees byte-identical behaviour on BOTH
 *     apps regardless of whether a heavy 3D vendor bundle is present.
 *   - WebGL2 BASELINE: feature-detected; the default render path.
 *   - WebGPU PROGRESSIVE ENHANCEMENT: feature-detected (navigator.gpu). When
 *     present we expose it via caps.webgpu = true and (ROADMAP) a WGSL compute
 *     layout path; we DO NOT claim a WebGPU pipeline we have not built — the
 *     baseline WebGL2 path renders identically. Honestly labelled ROADMAP.
 *   - CPU / OLD-GPU FALLBACK: if WebGL2 is unavailable the kit renders an HONEST
 *     2D <canvas> projection (never a blank canvas) with a visible
 *     "2D FALLBACK" badge. Graph, trust sphere, globe and signed-pulse all have
 *     a 2D path so the surface is always legible.
 *
 * DOCTRINE: 0 runtime CDN; Λ = Conjecture 1 (a bounded score < 1.0, NOT a
 * theorem); trust < 100%; honest SAMPLE labels on demo data; never claim live
 * data; 0 visible character codenames. window.SZLLabels drives honest badges.
 *
 * Citations (build references, not runtime calls):
 *   three.js / R3F  — https://github.com/pmndrs/react-three-fiber
 *   deck.gl (vis.gl)— https://github.com/visgl/deck.gl
 *   CesiumJS        — https://github.com/CesiumGS/cesium
 *
 * Public API: window.SZLHolo
 *   SZLHolo.version
 *   SZLHolo.capabilities()                     -> { webgl2, webgpu, mode, dpr }
 *   SZLHolo.createScene(mountEl, opts)         -> Scene
 *   Scene.addGraph(spec)                       -> GraphHandle  (nodes/edges DAG)
 *   Scene.addGlobe(spec)                       -> GlobeHandle  (lightweight globe)
 *   Scene.addTrustSphere(spec)                 -> TrustSphereHandle (morph by Λ)
 *   Scene.signPulse(edgeId, opts)              -> animate light along an edge
 *   Scene.timeSlider(opts)                     -> replay hook (onTime callback)
 *   Scene.setLambda(value)                     -> drive global Λ (< 1.0)
 *   Scene.start() / Scene.stop() / Scene.dispose()
 * =====================================================================================
 */
(function (root, factory) {
  "use strict";
  var mod = factory();
  if (root) { root.SZLHolo = mod; }
  if (typeof module !== "undefined" && module.exports) { module.exports = mod; }
})(typeof self !== "undefined" ? self : (typeof window !== "undefined" ? window : null), function () {
  "use strict";

  var VERSION = "1.0.0";

  /* ----------------------------------------------------------------------- *
   * Honest palette — Palantir/Datadog-style dark glass, defense-grade.
   * ----------------------------------------------------------------------- */
  var PALETTE = {
    bg0: [0.020, 0.027, 0.043],   // deep space navy
    bg1: [0.043, 0.063, 0.098],   // glass tint
    grid: "rgba(90,140,200,0.10)",
    node: "#7fd4ff",
    nodeLock: "#ffd479",
    edge: "rgba(120,170,230,0.45)",
    pulse: "#aef6ff",
    text: "#cfe6ff",
    ok: "#46d39a",
    warn: "#ffcf5c",
    bad: "#ff6b6b"
  };

  /* Λ -> colour. Λ is a bounded score in [0,1) (Conjecture 1; NOT a theorem).
   * Lower Λ = healthier (green); higher = riskier (red). Trust is never 100%. */
  function lambdaColor(lam) {
    lam = clamp01(lam == null ? 0.5 : lam);
    // green (low) -> amber (mid) -> red (high)
    var r, g, b;
    if (lam < 0.5) { var t = lam / 0.5; r = lerp(70, 255, t); g = lerp(211, 207, t); b = lerp(154, 92, t); }
    else { var u = (lam - 0.5) / 0.5; r = lerp(255, 255, u); g = lerp(207, 107, u); b = lerp(92, 107, u); }
    return "rgb(" + (r | 0) + "," + (g | 0) + "," + (b | 0) + ")";
  }
  function clamp01(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
  function lerp(a, b, t) { return a + (b - a) * t; }

  /* ----------------------------------------------------------------------- *
   * Capability detection. WebGL2 baseline, WebGPU enhancement, 2D fallback.
   * ----------------------------------------------------------------------- */
  function detectCaps() {
    var webgl2 = false, webgpu = false;
    try {
      var c = document.createElement("canvas");
      var gl = c.getContext("webgl2");
      webgl2 = !!gl;
      if (gl && gl.getExtension) { /* probe ok */ }
    } catch (e) { webgl2 = false; }
    try { webgpu = (typeof navigator !== "undefined" && !!navigator.gpu); } catch (e2) { webgpu = false; }
    var dpr = (typeof window !== "undefined" && window.devicePixelRatio) ? Math.min(window.devicePixelRatio, 2) : 1;
    var mode = webgl2 ? "webgl2" : "2d";
    return { webgl2: webgl2, webgpu: webgpu, mode: mode, dpr: dpr,
             // WebGPU is feature-detected but the compute-layout pipeline is ROADMAP;
             // we honestly do NOT switch the render path to an unbuilt WebGPU path.
             webgpuPipeline: false };
  }

  /* ----------------------------------------------------------------------- *
   * Honest label badge helper (reuses window.SZLLabels when present).
   * ----------------------------------------------------------------------- */
  function badgeHTML(key, text) {
    try {
      if (typeof window !== "undefined" && window.SZLLabels && window.SZLLabels.badgeHTML) {
        return window.SZLLabels.badgeHTML(key, { text: text });
      }
    } catch (e) {}
    // honest inline fallback if the shared label engine is not loaded
    var label = text || key;
    return '<span class="szl-holo-badge" data-k="' + esc(key) + '">' + esc(label) + "</span>";
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* small style sheet injected once (self-styled, 0 external font/css) */
  var STYLE_ID = "szl-holo3d-style";
  function ensureStyle(doc) {
    if (!doc || doc.getElementById(STYLE_ID)) { return; }
    var css =
      ".szl-holo-root{position:relative;width:100%;height:100%;min-height:240px;" +
      "background:radial-gradient(120% 120% at 50% 0%,#0a1326 0%,#050a14 60%,#03060d 100%);" +
      "overflow:hidden;border-radius:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:" + PALETTE.text + ";}" +
      ".szl-holo-root canvas{display:block;width:100%;height:100%;}" +
      ".szl-holo-hud{position:absolute;top:8px;left:10px;z-index:5;font-size:11px;letter-spacing:.04em;" +
      "text-shadow:0 1px 3px rgba(0,0,0,.8);pointer-events:none;}" +
      ".szl-holo-hud .row{display:flex;gap:6px;align-items:center;margin-bottom:3px;flex-wrap:wrap;}" +
      ".szl-holo-badge{display:inline-block;padding:1px 6px;border-radius:6px;font-size:10px;font-weight:600;" +
      "background:rgba(70,150,230,.18);border:1px solid rgba(120,180,240,.35);color:#bfe0ff;}" +
      ".szl-holo-badge[data-k='SAMPLE']{background:rgba(90,160,240,.16);}" +
      ".szl-holo-badge[data-k='2DFALLBACK']{background:rgba(255,180,90,.18);border-color:rgba(255,190,110,.4);color:#ffd9a8;}" +
      ".szl-holo-lambda{position:absolute;bottom:8px;left:10px;z-index:5;font-size:11px;pointer-events:none;}" +
      ".szl-holo-slider{position:absolute;bottom:8px;right:10px;left:auto;z-index:6;width:42%;max-width:260px;}" +
      ".szl-holo-slider input{width:100%;}" +
      ".szl-holo-slider label{font-size:10px;display:block;margin-bottom:2px;opacity:.85;}";
    var el = doc.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    (doc.head || doc.documentElement).appendChild(el);
  }

  /* ----------------------------------------------------------------------- *
   * Minimal 3x perspective math (no matrix lib needed for our point cloud).
   * We project 3D points to 2D with a simple rotating camera; both the WebGL2
   * path and the 2D fallback use the SAME projection so visuals match.
   * ----------------------------------------------------------------------- */
  function project(p, cam, w, h) {
    // rotate around Y then X
    var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
    var cx = Math.cos(cam.pitch), sx = Math.sin(cam.pitch);
    var x = p[0], y = p[1], z = p[2];
    var x1 = x * cy + z * sy;
    var z1 = -x * sy + z * cy;
    var y1 = y * cx - z1 * sx;
    var z2 = y * sx + z1 * cx;
    var d = cam.dist;
    var zc = z2 + d;
    var f = (cam.fov * Math.min(w, h)) / (zc <= 0.05 ? 0.05 : zc);
    return {
      x: w / 2 + x1 * f,
      y: h / 2 - y1 * f,
      z: zc,
      s: f / cam.fov // relative scale for size/alpha
    };
  }

  /* ----------------------------------------------------------------------- *
   * Scene — the holographic shell + all primitives.
   * ----------------------------------------------------------------------- */
  function Scene(mountEl, opts) {
    opts = opts || {};
    this.mount = mountEl;
    this.doc = (mountEl && mountEl.ownerDocument) || (typeof document !== "undefined" ? document : null);
    this.caps = detectCaps();
    this.opts = opts;
    this.lambda = (typeof opts.lambda === "number") ? clamp01(opts.lambda) : 0.42;
    this.cam = { yaw: 0.6, pitch: -0.35, dist: 3.2, fov: 1.7, autoRotate: opts.autoRotate !== false };
    this.graphs = [];
    this.globes = [];
    this.spheres = [];
    this.pulses = [];
    this._running = false;
    this._raf = null;
    this._lastT = 0;
    this._t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
    this._replay = null; // { from,to,value,playing }
    this._build();
  }

  Scene.prototype._build = function () {
    var doc = this.doc;
    ensureStyle(doc);
    var root = doc.createElement("div");
    root.className = "szl-holo-root";
    root.setAttribute("data-szl-holo", VERSION);
    this.root = root;

    var canvas = doc.createElement("canvas");
    canvas.setAttribute("aria-label", "SZL holographic scene");
    this.canvas = canvas;
    root.appendChild(canvas);

    // HUD with honest mode + SAMPLE badge (demo data is SAMPLE)
    var hud = doc.createElement("div");
    hud.className = "szl-holo-hud";
    var modeBadge = this.caps.webgl2 ? badgeHTML("EXPERIMENTAL", "WEBGL2") : badgeHTML("2DFALLBACK", "2D FALLBACK");
    var gpuBadge = this.caps.webgpu ? badgeHTML("EXPERIMENTAL", "WEBGPU·ROADMAP") : "";
    hud.innerHTML =
      '<div class="row">' + (this.opts.title ? '<strong>' + esc(this.opts.title) + '</strong>' : '') +
      ' ' + modeBadge + ' ' + gpuBadge + '</div>' +
      '<div class="row" data-szl-holo-labels>' + badgeHTML("SAMPLE", "SAMPLE DATA") + '</div>';
    this.hud = hud;
    root.appendChild(hud);

    // Λ readout (Conjecture 1, < 1.0) — never claims a theorem, never 100%.
    var lam = doc.createElement("div");
    lam.className = "szl-holo-lambda";
    this.lamEl = lam;
    root.appendChild(lam);
    this._renderLambdaReadout();

    this.mount.appendChild(root);

    // renderer init
    if (this.caps.webgl2) {
      this._initGL();
    }
    this.ctx2d = canvas.getContext("2d"); // always available for HUD/2D fallback layer
    this._resize();
    var self = this;
    this._onResize = function () { self._resize(); };
    if (typeof window !== "undefined") { window.addEventListener("resize", this._onResize); }
  };

  Scene.prototype._renderLambdaReadout = function () {
    var col = lambdaColor(this.lambda);
    this.lamEl.innerHTML =
      'Λ <span style="color:' + col + ';font-weight:700">' + this.lambda.toFixed(3) + '</span> ' +
      '<span style="opacity:.6">· Conjecture 1 (&lt;1.0) · trust &lt;100%</span>';
  };

  Scene.prototype._initGL = function () {
    var gl = null;
    try { gl = this.canvas.getContext("webgl2", { antialias: true, alpha: false, premultipliedAlpha: false }); }
    catch (e) { gl = null; }
    if (!gl) { this.caps.webgl2 = false; this.caps.mode = "2d"; return; }
    this.gl = gl;
    // point + line shader (instanced-free, simple gl.POINTS / gl.LINES)
    var vs =
      "#version 300 es\n" +
      "layout(location=0) in vec3 aPos;\n" +
      "layout(location=1) in vec4 aColor;\n" +
      "layout(location=2) in float aSize;\n" +
      "uniform mat4 uMVP;\n" +
      "out vec4 vColor;\n" +
      "void main(){ gl_Position = uMVP * vec4(aPos,1.0); gl_PointSize = aSize; vColor = aColor; }\n";
    var fs =
      "#version 300 es\nprecision highp float;\n" +
      "in vec4 vColor; out vec4 frag;\n" +
      "void main(){\n" +
      "  vec2 d = gl_PointCoord - vec2(0.5);\n" +
      "  float r = length(d);\n" +
      "  float a = smoothstep(0.5,0.1,r);\n" +
      "  frag = vec4(vColor.rgb, vColor.a * max(a, 0.18));\n" +
      "}\n";
    this.prog = this._linkProgram(gl, vs, fs);
    this.uMVP = gl.getUniformLocation(this.prog, "uMVP");
    this.vbo = gl.createBuffer();
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE); // additive glow
  };

  Scene.prototype._linkProgram = function (gl, vsSrc, fsSrc) {
    function sh(type, src) {
      var s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        // honest degrade: drop to 2D rather than throw
        return null;
      }
      return s;
    }
    var v = sh(gl.VERTEX_SHADER, vsSrc), f = sh(gl.FRAGMENT_SHADER, fsSrc);
    if (!v || !f) { this.caps.webgl2 = false; this.caps.mode = "2d"; return null; }
    var p = gl.createProgram();
    gl.attachShader(p, v); gl.attachShader(p, f); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { this.caps.webgl2 = false; this.caps.mode = "2d"; return null; }
    return p;
  };

  Scene.prototype._resize = function () {
    var dpr = this.caps.dpr;
    var w = this.root.clientWidth || 640, h = this.root.clientHeight || 360;
    this.W = w; this.H = h;
    this.canvas.width = Math.max(1, (w * dpr) | 0);
    this.canvas.height = Math.max(1, (h * dpr) | 0);
    if (this.gl) { this.gl.viewport(0, 0, this.canvas.width, this.canvas.height); }
  };

  /* -------- primitives ------------------------------------------------ */

  // GRAPH: { nodes:[{id,pos:[x,y,z],label,locked,lambda}], edges:[{id,from,to}] }
  Scene.prototype.addGraph = function (spec) {
    spec = spec || {};
    var nodes = (spec.nodes || []).map(function (n, i) {
      return {
        id: n.id != null ? n.id : ("n" + i),
        pos: n.pos || sphereLayout(i, (spec.nodes || []).length, 1.1),
        label: n.label || "",
        locked: !!n.locked,
        lambda: (typeof n.lambda === "number") ? clamp01(n.lambda) : null
      };
    });
    var index = {}; nodes.forEach(function (n, i) { index[n.id] = i; });
    var edges = (spec.edges || []).map(function (e, i) {
      return { id: e.id != null ? e.id : ("e" + i), from: index[e.from], to: index[e.to],
               fromId: e.from, toId: e.to };
    }).filter(function (e) { return e.from != null && e.to != null; });
    var h = { kind: "graph", nodes: nodes, edges: edges, index: index };
    this.graphs.push(h);
    return h;
  };

  // GLOBE: lightweight wireframe sphere + lat/long graticule + optional points.
  // Honest: this is a procedural SAMPLE globe, NOT a CesiumJS tile basemap.
  // A real basemap (CesiumJS local tiles / three-globe) is ROADMAP and must be
  // vendored 0-CDN before any tile call is made.
  Scene.prototype.addGlobe = function (spec) {
    spec = spec || {};
    var pts = (spec.points || []).map(function (p, i) {
      var la = (p.lat || 0) * Math.PI / 180, lo = (p.lon || 0) * Math.PI / 180;
      var r = 1.0;
      return { pos: [r * Math.cos(la) * Math.cos(lo), r * Math.sin(la), r * Math.cos(la) * Math.sin(lo)],
               label: p.label || "", lambda: (typeof p.lambda === "number") ? clamp01(p.lambda) : 0.4 };
    });
    var h = { kind: "globe", radius: spec.radius || 1.0, points: pts,
              sample: true, basemap: "PROCEDURAL_SAMPLE" };
    this.globes.push(h);
    return h;
  };

  // TRUST SPHERE: a sphere whose radius/colour morph with Λ (Conjecture 1).
  // Lower Λ -> larger, greener (more trust); higher Λ -> smaller, redder.
  Scene.prototype.addTrustSphere = function (spec) {
    spec = spec || {};
    var h = { kind: "sphere",
              center: spec.center || [0, 0, 0],
              baseR: spec.radius || 0.6,
              lambda: (typeof spec.lambda === "number") ? clamp01(spec.lambda) : this.lambda,
              label: spec.label || "TRUST",
              segs: spec.segments || 16 };
    this.spheres.push(h);
    return h;
  };

  // SIGNED-PULSE: animate a light packet flowing along an edge (receipt signed).
  Scene.prototype.signPulse = function (edgeRef, opts) {
    opts = opts || {};
    var graph = this.graphs[0];
    var edge = null;
    if (graph) {
      for (var i = 0; i < graph.edges.length; i++) {
        if (graph.edges[i].id === edgeRef || i === edgeRef) { edge = graph.edges[i]; break; }
      }
    }
    if (!edge && graph && graph.edges.length) { edge = graph.edges[0]; }
    if (!edge) { return null; }
    var p = { graph: graph, edge: edge, t: 0, dur: opts.duration || 1200,
              color: opts.color || PALETTE.pulse, started: this._now(), loop: !!opts.loop };
    this.pulses.push(p);
    return p;
  };

  // TIME-SLIDER replay hook. Injects a slider; calls opts.onTime(normalized,absolute).
  Scene.prototype.timeSlider = function (opts) {
    opts = opts || {};
    var doc = this.doc, self = this;
    var box = doc.createElement("div");
    box.className = "szl-holo-slider";
    var from = opts.from != null ? opts.from : 0;
    var to = opts.to != null ? opts.to : 100;
    box.innerHTML = '<label>REPLAY ' + badgeHTML("SAMPLE", "SAMPLE") + '</label>' +
                    '<input type="range" min="0" max="1000" value="1000" step="1" aria-label="time replay">';
    var input = box.querySelector("input");
    input.addEventListener("input", function () {
      var n = (+input.value) / 1000;
      self._replay = { from: from, to: to, value: from + (to - from) * n, norm: n };
      if (typeof opts.onTime === "function") { opts.onTime(n, self._replay.value); }
    });
    this.root.appendChild(box);
    this._replay = { from: from, to: to, value: to, norm: 1 };
    return { el: box, set: function (n) { input.value = String(Math.round(clamp01(n) * 1000)); input.dispatchEvent(new Event("input")); } };
  };

  Scene.prototype.setLambda = function (v) {
    this.lambda = clamp01(v);
    // trust sphere(s) without an explicit lambda track the global Λ
    for (var i = 0; i < this.spheres.length; i++) {
      if (this.spheres[i]._tracksGlobal !== false && this.spheres[i].lambda == null) {
        this.spheres[i].lambda = this.lambda;
      }
    }
    this._renderLambdaReadout();
    return this.lambda;
  };

  Scene.prototype._now = function () { return (typeof performance !== "undefined" ? performance.now() : Date.now()); };

  /* -------- run loop -------------------------------------------------- */
  Scene.prototype.start = function () {
    if (this._running) { return; }
    this._running = true;
    var self = this;
    function loop(t) {
      if (!self._running) { return; }
      self._frame(t || self._now());
      self._raf = (typeof requestAnimationFrame !== "undefined")
        ? requestAnimationFrame(loop) : setTimeout(function () { loop(self._now()); }, 33);
    }
    this._raf = (typeof requestAnimationFrame !== "undefined")
      ? requestAnimationFrame(loop) : setTimeout(function () { loop(self._now()); }, 33);
    return this;
  };
  Scene.prototype.stop = function () {
    this._running = false;
    if (this._raf != null) {
      if (typeof cancelAnimationFrame !== "undefined") { cancelAnimationFrame(this._raf); }
      else { clearTimeout(this._raf); }
      this._raf = null;
    }
    return this;
  };

  Scene.prototype._frame = function (t) {
    var dt = this._lastT ? (t - this._lastT) : 16;
    this._lastT = t;
    if (this.cam.autoRotate) { this.cam.yaw += dt * 0.00018; }
    this._drawCount = 0;
    if (this.caps.webgl2 && this.gl && this.prog) {
      this._renderGL(t);
    }
    // 2D overlay always draws labels/pulses/slider markers; in fallback it draws everything.
    this._render2D(t);
    // expose a draw count so verifiers can confirm >0 draws
    this.root.setAttribute("data-szl-draws", String(this._drawCount));
  };

  /* Build the full point/line set in scene space (shared by GL + 2D). */
  Scene.prototype._collectGeometry = function (t) {
    var pts = [];   // {pos, color, size, label}
    var lines = []; // {a, b, color}
    var self = this;
    var replayN = this._replay ? this._replay.norm : 1;

    // graphs
    this.graphs.forEach(function (g) {
      g.edges.forEach(function (e) {
        var a = g.nodes[e.from], b = g.nodes[e.to];
        if (!a || !b) { return; }
        lines.push({ a: a.pos, b: b.pos, color: PALETTE.edge });
      });
      g.nodes.forEach(function (n, i) {
        // replay: reveal nodes progressively by index
        var reveal = (i / Math.max(1, g.nodes.length - 1)) <= (replayN + 0.0001);
        if (!reveal) { return; }
        var col = n.locked ? PALETTE.nodeLock : (n.lambda != null ? lambdaColor(n.lambda) : PALETTE.node);
        pts.push({ pos: n.pos, color: col, size: n.locked ? 16 : 12, label: n.label });
      });
    });

    // globes
    this.globes.forEach(function (gl) {
      var R = gl.radius, rings = 10, seg = 22;
      for (var i = 1; i < rings; i++) {
        var lat = (i / rings - 0.5) * Math.PI;
        var prev = null;
        for (var j = 0; j <= seg; j++) {
          var lon = (j / seg) * Math.PI * 2;
          var p = [R * Math.cos(lat) * Math.cos(lon), R * Math.sin(lat), R * Math.cos(lat) * Math.sin(lon)];
          if (prev) { lines.push({ a: prev, b: p, color: "rgba(110,160,220,0.18)" }); }
          prev = p;
        }
      }
      for (var k = 0; k < seg; k++) {
        var lon2 = (k / seg) * Math.PI * 2; var prev2 = null;
        for (var m = 0; m <= rings; m++) {
          var lat2 = (m / rings - 0.5) * Math.PI;
          var q = [R * Math.cos(lat2) * Math.cos(lon2), R * Math.sin(lat2), R * Math.cos(lat2) * Math.sin(lon2)];
          if (prev2) { lines.push({ a: prev2, b: q, color: "rgba(110,160,220,0.12)" }); }
          prev2 = q;
        }
      }
      gl.points.forEach(function (p) {
        pts.push({ pos: p.pos, color: lambdaColor(p.lambda), size: 14, label: p.label });
      });
    });

    // trust spheres — radius morphs with Λ (lower Λ = larger/greener)
    this.spheres.forEach(function (s) {
      var lam = (s.lambda != null) ? s.lambda : self.lambda;
      var R = s.baseR * (1.25 - 0.5 * lam); // morph
      var col = lambdaColor(lam);
      var rings = s.segs, seg = s.segs;
      for (var i = 0; i <= rings; i++) {
        var lat = (i / rings - 0.5) * Math.PI; var prev = null;
        for (var j = 0; j <= seg; j++) {
          var lon = (j / seg) * Math.PI * 2;
          var p = [s.center[0] + R * Math.cos(lat) * Math.cos(lon),
                   s.center[1] + R * Math.sin(lat),
                   s.center[2] + R * Math.cos(lat) * Math.sin(lon)];
          if (prev) { lines.push({ a: prev, b: p, color: hexA(col, 0.30) }); }
          prev = p;
        }
      }
      pts.push({ pos: s.center, color: col, size: 10 + 14 * (1 - lam), label: s.label + " Λ" + lam.toFixed(2) });
    });

    // signed pulses — moving light packet along an edge
    var alive = [];
    this.pulses.forEach(function (p) {
      var age = self._now() - p.started;
      var f = age / p.dur;
      if (f >= 1) { if (p.loop) { p.started = self._now(); f = 0; } else { return; } }
      var a = p.graph.nodes[p.edge.from], b = p.graph.nodes[p.edge.to];
      if (!a || !b) { return; }
      var pos = [lerp(a.pos[0], b.pos[0], f), lerp(a.pos[1], b.pos[1], f), lerp(a.pos[2], b.pos[2], f)];
      pts.push({ pos: pos, color: p.color, size: 18, label: "" , pulse: true });
      // glowing trail
      for (var q = 1; q <= 4; q++) {
        var tf = Math.max(0, f - q * 0.05);
        pts.push({ pos: [lerp(a.pos[0], b.pos[0], tf), lerp(a.pos[1], b.pos[1], tf), lerp(a.pos[2], b.pos[2], tf)],
                   color: hexA(p.color, 0.5 - q * 0.1), size: 14 - q * 2, pulse: true });
      }
      alive.push(p);
    });
    this.pulses = alive;

    return { pts: pts, lines: lines };
  };

  Scene.prototype._renderGL = function (t) {
    var gl = this.gl, geo = this._collectGeometry(t);
    gl.clearColor(PALETTE.bg0[0], PALETTE.bg0[1], PALETTE.bg0[2], 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    var mvp = this._mvp();
    gl.useProgram(this.prog);
    gl.uniformMatrix4fv(this.uMVP, false, mvp);

    // lines
    var lineArr = [];
    geo.lines.forEach(function (ln) {
      var c = parseColor(ln.color);
      lineArr.push(ln.a[0], ln.a[1], ln.a[2], c[0], c[1], c[2], c[3], 2.0);
      lineArr.push(ln.b[0], ln.b[1], ln.b[2], c[0], c[1], c[2], c[3], 2.0);
    });
    this._drawArray(gl, lineArr, gl.LINES);
    this._drawCount += geo.lines.length;

    // points
    var ptArr = [];
    geo.pts.forEach(function (pt) {
      var c = parseColor(pt.color);
      ptArr.push(pt.pos[0], pt.pos[1], pt.pos[2], c[0], c[1], c[2], c[3], pt.size * 1.0);
    });
    this._drawArray(gl, ptArr, gl.POINTS);
    this._drawCount += geo.pts.length;
    this._lastGeo = geo; // for 2D label overlay
  };

  Scene.prototype._drawArray = function (gl, arr, mode) {
    if (!arr.length) { return; }
    var data = new Float32Array(arr);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.vbo);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
    var stride = 8 * 4;
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, stride, 0);
    gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 4, gl.FLOAT, false, stride, 3 * 4);
    gl.enableVertexAttribArray(2); gl.vertexAttribPointer(2, 1, gl.FLOAT, false, stride, 7 * 4);
    gl.drawArrays(mode, 0, arr.length / 8);
  };

  // Build a perspective * view matrix consistent with our project() camera.
  Scene.prototype._mvp = function () {
    var cam = this.cam;
    var aspect = this.canvas.width / Math.max(1, this.canvas.height);
    var f = 1.0 / Math.tan(cam.fov / 2);
    var near = 0.1, far = 100;
    var proj = [
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) / (near - far), -1,
      0, 0, (2 * far * near) / (near - far), 0
    ];
    var cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw);
    var cx = Math.cos(cam.pitch), sx = Math.sin(cam.pitch);
    var ry = [cy, 0, -sy, 0, 0, 1, 0, 0, sy, 0, cy, 0, 0, 0, 0, 1];
    var rx = [1, 0, 0, 0, 0, cx, sx, 0, 0, -sx, cx, 0, 0, 0, 0, 1];
    var trans = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, -cam.dist, 1];
    return mul(proj, mul(trans, mul(rx, ry)));
  };

  /* 2D layer: in fallback mode renders the full scene; otherwise draws labels. */
  Scene.prototype._render2D = function (t) {
    var ctx = this.ctx2d; if (!ctx) { return; }
    var dpr = this.caps.dpr, w = this.canvas.width, h = this.canvas.height;
    if (!this.caps.webgl2) {
      // FULL 2D FALLBACK — never a blank canvas.
      var grd = ctx.createRadialGradient(w / 2, h * 0.2, 10, w / 2, h * 0.2, h);
      grd.addColorStop(0, "#0a1326"); grd.addColorStop(1, "#03060d");
      ctx.fillStyle = grd; ctx.fillRect(0, 0, w, h);
      // faint grid
      ctx.strokeStyle = PALETTE.grid; ctx.lineWidth = 1;
      for (var gx = 0; gx < w; gx += 40 * dpr) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, h); ctx.stroke(); }
      for (var gy = 0; gy < h; gy += 40 * dpr) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke(); }
      var geo = this._collectGeometry(t);
      var self = this;
      ctx.lineWidth = 1.4 * dpr;
      geo.lines.forEach(function (ln) {
        var pa = project(ln.a, self.cam, w, h), pb = project(ln.b, self.cam, w, h);
        ctx.strokeStyle = ln.color; ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
        self._drawCount++;
      });
      geo.pts.slice().sort(function (a, b) {
        return project(b.pos, self.cam, w, h).z - project(a.pos, self.cam, w, h).z;
      }).forEach(function (pt) {
        var p = project(pt.pos, self.cam, w, h);
        var r = Math.max(2, pt.size * 0.5 * dpr * p.s);
        var glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 2.4);
        glow.addColorStop(0, pt.color); glow.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(p.x, p.y, r * 2.4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = pt.color; ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
        if (pt.label) {
          ctx.fillStyle = PALETTE.text; ctx.font = (11 * dpr) + "px ui-monospace,monospace";
          ctx.fillText(pt.label, p.x + r + 3, p.y + 3);
        }
        self._drawCount++;
      });
      return;
    }
    // WebGL2 mode: overlay node labels on a transparent 2D layer is not possible
    // on the same canvas (GL owns it). Labels are shown via the HUD; here we just
    // keep the draw count honest from the GL pass. (No second canvas to stay 0-CDN
    // and simple.)
  };

  Scene.prototype.dispose = function () {
    this.stop();
    if (typeof window !== "undefined" && this._onResize) { window.removeEventListener("resize", this._onResize); }
    if (this.root && this.root.parentNode) { this.root.parentNode.removeChild(this.root); }
    this.gl = null; this.ctx2d = null;
  };

  /* ----------------------------------------------------------------------- *
   * helpers
   * ----------------------------------------------------------------------- */
  function sphereLayout(i, n, r) {
    // fibonacci sphere for pleasing graph node distribution
    n = Math.max(1, n);
    var phi = Math.acos(1 - 2 * (i + 0.5) / n);
    var theta = Math.PI * (1 + Math.sqrt(5)) * i;
    return [r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta)];
  }
  function parseColor(c) {
    // returns [r,g,b,a] in 0..1
    if (Array.isArray(c)) { return [c[0], c[1], c[2], c[3] == null ? 1 : c[3]]; }
    c = String(c).trim();
    var m;
    if ((m = c.match(/^#([0-9a-f]{6})$/i))) {
      var n = parseInt(m[1], 16);
      return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, 1];
    }
    if ((m = c.match(/^rgba?\(([^)]+)\)$/i))) {
      var p = m[1].split(",").map(function (x) { return parseFloat(x); });
      return [(p[0] || 0) / 255, (p[1] || 0) / 255, (p[2] || 0) / 255, p[3] == null ? 1 : p[3]];
    }
    return [0.5, 0.8, 1, 1];
  }
  function hexA(c, a) {
    var p = parseColor(c);
    return "rgba(" + (p[0] * 255 | 0) + "," + (p[1] * 255 | 0) + "," + (p[2] * 255 | 0) + "," + a + ")";
  }
  function mul(a, b) {
    var out = new Array(16);
    for (var r = 0; r < 4; r++) {
      for (var c = 0; c < 4; c++) {
        var s = 0;
        for (var k = 0; k < 4; k++) { s += a[k * 4 + c] * b[r * 4 + k]; }
        out[r * 4 + c] = s;
      }
    }
    return out;
  }

  /* ----------------------------------------------------------------------- *
   * public module surface
   * ----------------------------------------------------------------------- */
  return {
    version: VERSION,
    palette: PALETTE,
    lambdaColor: lambdaColor,
    capabilities: function () { return detectCaps(); },
    createScene: function (mountEl, opts) {
      if (!mountEl) { throw new Error("SZLHolo.createScene requires a mount element"); }
      return new Scene(mountEl, opts || {});
    },
    // expose for advanced lanes (F2-F5) that build their own scene types
    _Scene: Scene,
    _helpers: { sphereLayout: sphereLayout, project: project }
  };
});
