// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// szl3d_boot.js — SHARED renderer factory for the holographic estate (Dev0 foundation).
//
// The other 9 surface devs import THIS so every tab shares one renderer setup:
//   * WebGPU first (three r170 `three/webgpu` WebGPURenderer), graceful WebGL2 fallback.
//     WebGPU is NOT production-safe on Linux/mobile yet (doctrine), so detection is
//     defensive: we only use it when navigator.gpu yields a real adapter+device, and
//     any failure falls back to WebGLRenderer with NO crash and an honest backend label.
//   * Standard scene + perspective camera + OrbitControls + auto-resize.
//   * Optional bloom/postprocessing pipeline for the 'holographic' look (UnrealBloomPass).
//
// 0 runtime CDN: all imports resolve through the page's importmap to /static/3d/vendor/.
// Honesty: this module renders pixels only. It NEVER invents data values — values come
// from szl3d_live.poll() and carry doctrine honesty labels (see szl3d_label.js).
//
// Import map every page must include (see VENDOR_MANIFEST.md):
//   "three"          -> /static/3d/vendor/three/three.module.min.js
//   "three/webgpu"   -> /static/3d/vendor/three/three.webgpu.min.js
//   "three/addons/"  -> /static/3d/vendor/three/addons/

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export const SZL3D_VERSION = "1.0.0";
export const THREE_REVISION = THREE.REVISION;

// ---------------------------------------------------------------------------
// WebGPU capability probe. Returns a real WebGPURenderer (already init()'d) when
// the platform supports it, else null. Never throws.
// ---------------------------------------------------------------------------
async function _tryWebGPU(canvas, opts) {
  if (typeof navigator === "undefined" || !("gpu" in navigator)) return null;
  try {
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) return null;
    // three r170 ships WebGPURenderer in the dedicated webgpu build only.
    const mod = await import("three/webgpu");
    const WebGPURenderer = mod.WebGPURenderer || (mod.default && mod.default.WebGPURenderer);
    if (!WebGPURenderer) return null;
    const renderer = new WebGPURenderer({ canvas, antialias: opts.antialias !== false, alpha: !!opts.alpha });
    await renderer.init(); // acquires the device; throws on failure -> caught below
    renderer._szlBackend = "webgpu";
    return renderer;
  } catch (e) {
    // Honest fallback path — log once, do not crash the surface.
    if (typeof console !== "undefined") console.warn("[szl3d] WebGPU unavailable, falling back to WebGL2:", e && e.message);
    return null;
  }
}

function _makeWebGL(canvas, opts) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: opts.antialias !== false,
    alpha: !!opts.alpha,
    powerPreference: opts.powerPreference || "high-performance",
  });
  renderer._szlBackend = "webgl2";
  return renderer;
}

// ---------------------------------------------------------------------------
// boot(container, opts) -> Promise<Stage>
//
// container : DOM element (or canvas). If an element, a <canvas> is created inside.
// opts:
//   webgpu       (bool, default true)  attempt WebGPU first
//   forceWebGL   (bool, default false) skip WebGPU entirely (used by the fallback selftest)
//   bloom        (bool|object, default false) enable the holographic bloom pass
//                 object: {strength, radius, threshold}
//   background   (THREE.Color|number|null) scene background (default 0x05070d)
//   cameraFov, cameraNear, cameraFar, cameraPos:[x,y,z]
//   antialias, alpha, powerPreference, pixelRatioCap (default 2)
//   orbit        (bool, default true) attach OrbitControls
//
// Returns a Stage object:
//   { renderer, scene, camera, controls, backend, composer|null, bloomPass|null,
//     start(loop?), stop(), resize(), render(), dispose(), setBloom(on), onFrame(fn) }
// ---------------------------------------------------------------------------
export async function boot(container, opts = {}) {
  if (!container) throw new Error("szl3d.boot: container is required");
  const isCanvas = (typeof HTMLCanvasElement !== "undefined") && (container instanceof HTMLCanvasElement);
  const host = isCanvas ? container.parentElement || document.body : container;
  const canvas = isCanvas ? container : document.createElement("canvas");
  if (!isCanvas) {
    canvas.style.display = "block";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    host.appendChild(canvas);
  }

  let renderer = null;
  if (!opts.forceWebGL && opts.webgpu !== false) {
    renderer = await _tryWebGPU(canvas, opts);
  }
  if (!renderer) renderer = _makeWebGL(canvas, opts);
  const backend = renderer._szlBackend;

  const pixelRatioCap = opts.pixelRatioCap || 2;
  renderer.setPixelRatio(Math.min((typeof window !== "undefined" ? window.devicePixelRatio : 1) || 1, pixelRatioCap));

  const scene = new THREE.Scene();
  if (opts.background !== null) {
    scene.background = new THREE.Color(opts.background == null ? 0x05070d : opts.background);
  }

  const camera = new THREE.PerspectiveCamera(
    opts.cameraFov || 55, 1, opts.cameraNear || 0.1, opts.cameraFar || 4000,
  );
  const cp = opts.cameraPos || [0, 6, 18];
  camera.position.set(cp[0], cp[1], cp[2]);
  camera.lookAt(0, 0, 0);

  let controls = null;
  if (opts.orbit !== false && typeof renderer.domElement !== "undefined") {
    try {
      controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;
      controls.dampingFactor = 0.08;
    } catch (_) { controls = null; }
  }

  // Default holographic lighting so a freshly-booted scene is never pitch black.
  const amb = new THREE.AmbientLight(0xffffff, 0.35);
  const key = new THREE.DirectionalLight(0x8fd7ff, 1.1);
  key.position.set(8, 16, 10);
  scene.add(amb, key);

  // -------- optional bloom/postprocessing (holographic glow) --------
  // Bloom uses the WebGL EffectComposer. On the WebGPU backend three exposes a
  // different post pipeline (PostProcessing/TSL); to keep the foundation honest and
  // identical across the fallback we only wire EffectComposer bloom on WebGL2 and
  // expose setBloom() as a no-op-safe toggle elsewhere.
  let composer = null, bloomPass = null, renderPass = null, outputPass = null;
  const bloomReq = !!opts.bloom;
  async function _buildComposer() {
    if (backend !== "webgl2") return; // see note above; WebGPU bloom is a per-surface opt-in TODO
    const { EffectComposer } = await import("three/addons/postprocessing/EffectComposer.js");
    const { RenderPass } = await import("three/addons/postprocessing/RenderPass.js");
    const { UnrealBloomPass } = await import("three/addons/postprocessing/UnrealBloomPass.js");
    const { OutputPass } = await import("three/addons/postprocessing/OutputPass.js");
    composer = new EffectComposer(renderer);
    renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);
    const b = (typeof opts.bloom === "object" && opts.bloom) || {};
    bloomPass = new UnrealBloomPass(
      new THREE.Vector2(1, 1),
      b.strength != null ? b.strength : 0.9,
      b.radius != null ? b.radius : 0.5,
      b.threshold != null ? b.threshold : 0.15,
    );
    composer.addPass(bloomPass);
    outputPass = new OutputPass();
    composer.addPass(outputPass);
  }
  if (bloomReq) { try { await _buildComposer(); } catch (e) { if (console) console.warn("[szl3d] bloom unavailable:", e && e.message); } }

  // -------- sizing --------
  function _size() {
    const w = Math.max(1, host.clientWidth || canvas.clientWidth || 1);
    const h = Math.max(1, host.clientHeight || canvas.clientHeight || 1);
    renderer.setSize(w, h, false);
    if (composer) composer.setSize(w, h);
    if (bloomPass && bloomPass.resolution) bloomPass.resolution.set(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  const _frameCbs = [];
  function onFrame(fn) { if (typeof fn === "function") _frameCbs.push(fn); }

  function render() {
    if (controls) controls.update();
    for (let i = 0; i < _frameCbs.length; i++) { try { _frameCbs[i](stage); } catch (_) {} }
    if (composer) composer.render();
    else renderer.render(scene, camera);
  }

  let _raf = 0, _running = false;
  function start(loopFn) {
    if (loopFn) onFrame(loopFn);
    _running = true;
    const tick = () => {
      if (!_running) return;
      render();
      _raf = (typeof requestAnimationFrame !== "undefined") ? requestAnimationFrame(tick) : 0;
    };
    tick();
  }
  function stop() {
    _running = false;
    if (_raf && typeof cancelAnimationFrame !== "undefined") cancelAnimationFrame(_raf);
    _raf = 0;
  }

  function setBloom(on) {
    if (bloomPass) bloomPass.enabled = !!on;
  }

  function dispose() {
    stop();
    try { if (controls) controls.dispose(); } catch (_) {}
    try { if (composer && composer.dispose) composer.dispose(); } catch (_) {}
    try { renderer.dispose(); } catch (_) {}
    if (typeof window !== "undefined") window.removeEventListener("resize", _size);
  }

  if (typeof window !== "undefined") window.addEventListener("resize", _size);
  _size();

  const stage = {
    renderer, scene, camera, controls, backend,
    composer, bloomPass,
    THREE,
    start, stop, render, resize: _size, dispose, setBloom, onFrame,
    hasBloom: () => !!bloomPass,
  };
  return stage;
}

// Synchronous capability hint (no device acquisition) for UIs that want to show
// the likely backend before boot resolves. Honest: presence of navigator.gpu is
// necessary-not-sufficient; boot() may still fall back.
export function probeBackend() {
  const gpu = (typeof navigator !== "undefined") && ("gpu" in navigator);
  return { webgpuLikely: !!gpu, three: THREE.REVISION, szl3d: SZL3D_VERSION };
}

export default { boot, probeBackend, SZL3D_VERSION, THREE_REVISION, THREE };
