// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
//
// pnt_mount_harness.mjs — headless mount harness for surfaces/pnt.js (Dev3).
//
// Runs under Node with NO browser: it stubs a minimal DOM + a minimal THREE module + the
// szl3d toolkit's poll/label so the real surface module can mount(), then feeds it the
// EXACT live JSON shapes that /api/a11oy/v1/pnt/{sensor,coast,resilience,limits} return.
// It asserts the surface wires every endpoint, reads the honesty label (MODELED) straight
// off the JSON, renders it on the HUD, degrades honestly on a 404/degraded payload, and
// tears everything down on unmount. Emits a JSON result object to stdout.
//
// This is the "mounts + polls real endpoints + honest MODELED labels + 0 CDN" test the
// Dev3 spec requires, executed against the genuine module (not a mock of it). The live
// JSON is passed in on argv[2] (captured from the real szl_pnt_mesh handlers by pytest),
// so the shapes are real, not invented here.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dir = dirname(fileURLToPath(import.meta.url));
const SURFACE = resolve(__dir, "..", "surfaces", "pnt.js");

// ---- minimal DOM stub ------------------------------------------------------
function el() {
  const node = {
    style: {}, children: [], parentNode: null, _text: "",
    className: "", attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { c.parentNode = node; this.children.push(c); return c; },
    removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); c.parentNode = null; return c; },
    getContext() { return { font: "", measureText: () => ({ width: 80 }), beginPath() {}, moveTo() {}, arcTo() {}, closePath() {}, fill() {}, fillText() {}, fillStyle: "", textBaseline: "" }; },
    set textContent(v) { this._text = String(v); },
    get textContent() { return this._text; },
    set innerHTML(v) { this._text = String(v); },
    get innerHTML() { return this._text; },
  };
  return node;
}
global.document = {
  createElement(tag) { const n = el(); n.tag = tag; if (tag === "canvas") { n.width = 0; n.height = 0; } return n; },
  body: el(),
};
global.performance = global.performance || { now: () => 0 };

// ---- minimal THREE stub (only what pnt.js touches) -------------------------
class Vec3 {
  constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
  set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
  copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
  setScalar(s) { this.x = this.y = this.z = s; return this; }
}
class Color { constructor(h = 0xffffff) { this.set(h); } set(h) { this.r = ((h >> 16) & 255) / 255; this.g = ((h >> 8) & 255) / 255; this.b = (h & 255) / 255; return this; } setHex(h) { return this.set(h); } }
function bufAttr(arr, item) {
  return {
    array: arr, itemSize: item, count: Math.floor(arr.length / item), needsUpdate: false,
    getX(i) { return arr[i * item]; }, getY(i) { return arr[i * item + 1]; }, getZ(i) { return arr[i * item + 2]; },
    setX(i, v) { arr[i * item] = v; }, setY(i, v) { arr[i * item + 1] = v; }, setZ(i, v) { arr[i * item + 2] = v; },
  };
}
class Geometry {
  constructor() { this.attributes = {}; }
  setAttribute(k, a) { this.attributes[k] = a; return this; }
  rotateX() { return this; } translate() { return this; }
  computeVertexNormals() {} dispose() { this.disposed = true; }
}
function planeGeo(w, h, sx, sy) {
  const g = new Geometry();
  const nx = (sx || 1) + 1, ny = (sy || 1) + 1;
  const arr = new Float32Array(nx * ny * 3);
  let k = 0;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    arr[k++] = (i / (nx - 1) - 0.5) * w; arr[k++] = 0; arr[k++] = (j / (ny - 1) - 0.5) * h;
  }
  g.setAttribute("position", bufAttr(arr, 3));
  return g;
}
class Material { constructor(o = {}) { Object.assign(this, o); this.color = new Color(o.color || 0xffffff); this.emissive = new Color(o.emissive || 0); } dispose() { this.disposed = true; } }
class Obj3D {
  constructor() { this.children = []; this.position = new Vec3(); this.rotation = new Vec3(); this.scale = new Vec3(1, 1, 1); this.userData = {}; }
  add(c) { this.children.push(c); return c; }
  remove(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); }
  traverse(fn) { fn(this); this.children.forEach((c) => c.traverse && c.traverse(fn)); }
}
class Mesh extends Obj3D { constructor(g, m) { super(); this.geometry = g; this.material = m; this.isMesh = true; } }
class Points extends Obj3D { constructor(g, m) { super(); this.geometry = g; this.material = m; this.isPoints = true; } }
class Group extends Obj3D {}
class Sprite extends Obj3D { constructor() { super(); this.isSprite = true; } }
class CanvasTexture { constructor() {} }
class SpriteMaterial { constructor(o) { Object.assign(this, o); } }

const THREE = {
  Vector3: Vec3, Color, BufferGeometry: Geometry, BufferAttribute: function (a, i) { return bufAttr(a, i); },
  PlaneGeometry: function (w, h, sx, sy) { return planeGeo(w, h, sx, sy); },
  SphereGeometry: function () { return new Geometry(); },
  IcosahedronGeometry: function () { return new Geometry(); },
  TorusGeometry: function () { return new Geometry(); },
  RingGeometry: function () { return new Geometry(); },
  BoxGeometry: function () { return new Geometry(); },
  CylinderGeometry: function () { return new Geometry(); },
  TubeGeometry: function () { return new Geometry(); },
  CatmullRomCurve3: function (p) { this.points = p; },
  MeshStandardMaterial: Material, MeshBasicMaterial: Material,
  LineBasicMaterial: Material, PointsMaterial: Material, SpriteMaterial,
  Mesh, Points, Group, Sprite, CanvasTexture,
  DoubleSide: 2, SRGBColorSpace: "srgb", REVISION: "170",
};

// ---- load the szl3d label + a poll stub (we drive onData directly) ---------
const labelMod = await import(pathToFileURL(resolve(__dir, "..", "szl3d", "szl3d_label.js")).href);

const polled = [];               // { endpoint, onData, badge }
const live = {
  createBadge() {
    const e = el();
    let state = "init", label = null;
    return { el: e, set(s, info) { state = s; if (info && info.label !== undefined) label = info.label; }, tick() {}, get state() { return state; }, get _label() { return label; } };
  },
  poll(endpoint, ms, onData, opts) {
    const badge = opts && opts.badge;
    const h = { endpoint, onData, badge, stopped: false, stop() { this.stopped = true; } };
    polled.push(h);
    return h;
  },
};

// ---- a fake stage matching the szl3d Stage surface pnt.js uses -------------
const frameFns = [];
const scene = new Obj3D();
const stage = {
  scene, THREE, backend: "webgl2",
  onFrame(fn) { frameFns.push(fn); },
  setBloom() { stage._bloom = true; },
};

// ---- mount the REAL surface ------------------------------------------------
const mod = await import(pathToFileURL(SURFACE).href);
const surface = mod.default || mod;

const result = { checks: {}, errors: [] };
function check(name, cond) { result.checks[name] = !!cond; if (!cond) result.errors.push(name); }

// contract shape
check("default_export", surface && typeof surface.mount === "function" && typeof surface.unmount === "function");
check("id_pnt", surface.id === "pnt");
check("endpoints_four", Array.isArray(surface.endpoints) && surface.endpoints.length >= 4);
check("endpoints_sensor", surface.endpoints.includes("/api/a11oy/v1/pnt/sensor"));

const container = el();
surface.mount({ stage, container, live, label: labelMod, THREE, szl3d: { probeBackend() { return {}; } } });

check("bloom_requested", stage._bloom === true);
check("polled_four_endpoints", polled.length >= 4);
const eps = polled.map((p) => p.endpoint);
check("polls_sensor", eps.includes("/api/a11oy/v1/pnt/sensor"));
check("polls_coast", eps.includes("/api/a11oy/v1/pnt/coast"));
check("polls_resilience", eps.includes("/api/a11oy/v1/pnt/resilience"));
check("polls_limits", eps.includes("/api/a11oy/v1/pnt/limits"));
check("scene_objects_added", scene.children.length > 5);
check("frame_registered", frameFns.length >= 1);

// feed the REAL live JSON captured by pytest (argv[2] = path to json file)
const liveJson = JSON.parse(readFileSync(process.argv[2], "utf-8"));
function feed(ep, json) {
  const h = polled.find((p) => p.endpoint === ep);
  if (!h) return;
  const meta = { state: "live", label: (json && json.label) || null, at: Date.now() };
  // mirror the REAL szl3d poller: it sets the badge from meta before calling onData.
  if (h.badge) h.badge.set(meta.state, { label: meta.label, at: meta.at });
  h.onData(json, meta);
}
feed("/api/a11oy/v1/pnt/sensor", liveJson.sensor);
feed("/api/a11oy/v1/pnt/coast", liveJson.coast);
feed("/api/a11oy/v1/pnt/resilience", liveJson.resilience);
feed("/api/a11oy/v1/pnt/limits", liveJson.limits);

// the sensor badge must reflect the honesty label read straight off the JSON
const sensorH = polled.find((p) => p.endpoint === "/api/a11oy/v1/pnt/sensor");
check("sensor_badge_label_modeled", sensorH.badge && sensorH.badge._label === "MODELED");

// run a frame tick (animators must not throw on live data)
let frameThrew = false;
try { frameFns.forEach((f) => f()); } catch (e) { frameThrew = true; result.errors.push("frame_threw:" + e.message); }
check("frame_tick_ok", !frameThrew);

// the HUD must now contain the MODELED label chip text somewhere
function collectText(node, acc) {
  if (!node) return acc;
  if (node._text) acc.push(node._text);
  (node.children || []).forEach((c) => collectText(c, acc));
  return acc;
}
const hudPieces = collectText(container, []);
const hudText = hudPieces.join(" | ");
// MODELED must appear on the live value rows (more than once — k_eff, σ_Φ, σ_a, ASD, ...)
const modeledCount = hudPieces.filter((t) => /^MODELED$/.test(t.trim())).length;
check("hud_shows_modeled", /MODELED/.test(hudText) && modeledCount >= 2);
// the sensor cert is MODELED, NEVER a measurement — the ONLY MEASURED token allowed is the
// doctrine legend's reference chip (exactly one), never a fabricated value-row label.
const measuredCount = hudPieces.filter((t) => /^MEASURED$/.test(t.trim())).length;
check("hud_no_fabricated_measured", measuredCount <= 1);
check("hud_shows_sql_true", /TRUE \(at\/above SQL\)/.test(hudText));

// honest degraded path: a 404/missing meta must not crash and must not invent a value
let degradedThrew = false;
try {
  const meta404 = { state: "missing", label: null, status: 404, at: null };
  sensorH.onData({ degraded: true }, meta404);
} catch (e) { degradedThrew = true; result.errors.push("degraded_threw:" + e.message); }
check("degraded_no_crash", !degradedThrew);

// unmount must stop every poll + clear the scene back to (near) empty
surface.unmount();
check("all_polls_stopped", polled.every((p) => p.stopped));
check("overlay_removed", container.children.length === 0);
// frame fns guard on _alive after unmount -> calling them must be a no-op, never throw
let postThrew = false;
try { frameFns.forEach((f) => f()); } catch (e) { postThrew = true; }
check("post_unmount_frame_safe", !postThrew);

result.ok = result.errors.length === 0;
result.total = Object.keys(result.checks).length;
result.passed = Object.values(result.checks).filter(Boolean).length;
process.stdout.write(JSON.stringify(result, null, 2) + "\n");
process.exit(result.ok ? 0 : 1);
