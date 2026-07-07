// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ringattn.js — RING-ATTENTION LONG-CONTEXT BLOCKWISE SIMULATOR organ for
// the holographic frontier ring. Renders a 3D RING of `devices` device nodes with
// KV blocks rotating around it (num_rotation_steps == devices); a running online-
// softmax accumulator glows proof-teal as each KV block is absorbed. A HUD shows
// per_device_memory_ratio, exact_match, and max_context_supported from a live
// snapshot at /api/killinchu/v1/ringattn/simulate. Honesty label "MODELED" is read
// VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors specdecode.js / testtime.js / interpretability.js
// exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   seq_len, devices, block_size, num_rotation_steps, per_device_memory_ratio,
//   exact_match, max_context_supported, rotation_trace[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Ring Attention with Blockwise Transformers for Near-Infinite Context:
//     Liu, Zaharia & Abbeel 2023, arXiv:2310.01889
//     https://arxiv.org/abs/2310.01889
//   Blockwise Parallel Transformer (the online-softmax blockwise trick):
//     Liu & Abbeel 2023, arXiv:2305.19370
//     https://arxiv.org/abs/2305.19370
//   Reference implementation: haoliuhl/ringattention
//     https://github.com/haoliuhl/ringattention
//
// HONESTY LABELS: MODELED (deterministic blockwise online-softmax simulation of
//   ring-attention's exact-attention accumulation; NOT a trained model or real
//   multi-device kernel; NEVER-CLAIMED-AS a production ring-attention
//   implementation). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (device nodes / ring), violet-blue 0x8a6bff
//   (rotating KV blocks), proof-teal 0x3af4c8 (online-softmax accumulator glow /
//   HUD accent), greys (degraded / rejected state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "ringattn";
const TITLE = "Ring Attention · Long-Context Blockwise Simulator (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin: https://a-11-oy.com).
// This keeps the ring-attention organ's rebuilds/faults isolated from the flagship.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/ringattn/simulate?seed=42&seq_len=4096&devices=8";

// data-viz hues — purple BANNED
const C_DEVICE  = 0x5b8dee;  // lattice-blue (device nodes / ring spine)
const C_KVBLOCK = 0x8a6bff;  // violet-blue (rotating KV block — data-viz only)
const C_ACCUM   = 0x3af4c8;  // proof-teal (online-softmax accumulator glow / HUD accent)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// ring layout geometry
const RING_RADIUS  = 6.0;   // world-units, radius of the device ring
const NODE_SIZE    = 0.34;  // device node sphere radius
const MAX_DEVICES  = 32;    // pre-allocated device-node cap (perf)
const KV_ORBIT_R   = RING_RADIUS + 1.1; // KV block travels slightly outside the ring

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles
let _floor       = null;
let _ringLine    = null;             // THREE.LineLoop — the ring spine
let _deviceMesh  = [];               // Array<THREE.Mesh> — device nodes around the ring
let _kvBlock     = null;             // THREE.Mesh — the rotating KV block marker
let _accumulator = null;             // THREE.Mesh — running online-softmax accumulator (glows)
let _accumPulsePhase = 0;

// live state
const S = {
  label:        null,
  seqLen:       null,   // seq_len
  devices:      null,   // devices
  blockSize:    null,   // block_size
  rotSteps:     null,   // num_rotation_steps
  memRatio:     null,   // per_device_memory_ratio
  exactMatch:   null,   // exact_match (bool)
  maxContext:   null,   // max_context_supported
  trace:        null,   // rotation_trace[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRing();
  _buildKvBlock();
  _buildAccumulator();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onRingAttn, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

function _ringPos(i, n, radius, y) {
  const a = (i / Math.max(1, n)) * Math.PI * 2;
  return [Math.cos(a) * radius, y, Math.sin(a) * radius];
}

// Pre-allocate a fixed ring of device-node meshes (MAX_DEVICES); toggle
// visibility / color in-place as live data arrives (no per-poll geometry churn).
function _buildRing() {
  const THREE = _THREE;

  // ring spine (visual guide at y=0)
  {
    const pts = [];
    const SEG = 96;
    for (let i = 0; i <= SEG; i++) {
      const a = (i / SEG) * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(a) * RING_RADIUS, 0, Math.sin(a) * RING_RADIUS));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_DEVICE, transparent: true, opacity: 0.35 });
    _ringLine = new THREE.Line(geo, mat);
    _group.add(_ringLine);
  }

  const nodeGeo = new THREE.IcosahedronGeometry(NODE_SIZE, 0);
  for (let i = 0; i < MAX_DEVICES; i++) {
    const mesh = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_DEVICE, emissive: C_DEVICE, emissiveIntensity: 0.35, transparent: true, opacity: 0.0 }),
    );
    mesh.visible = false;
    _group.add(mesh);
    _deviceMesh.push(mesh);
  }
}

function _buildKvBlock() {
  const THREE = _THREE;
  _kvBlock = new THREE.Mesh(
    new THREE.BoxGeometry(0.5, 0.5, 0.5),
    new THREE.MeshStandardMaterial({ color: C_KVBLOCK, emissive: C_KVBLOCK, emissiveIntensity: 0.45, transparent: true, opacity: 0.9 }),
  );
  _kvBlock.position.set(KV_ORBIT_R, 0.6, 0);
  _kvBlock.visible = false;
  _group.add(_kvBlock);
}

function _buildAccumulator() {
  const THREE = _THREE;
  // The running online-softmax accumulator sits at the ring's center and
  // glows proof-teal as blocks are absorbed (running_sum growth cue).
  _accumulator = new THREE.Mesh(
    new THREE.SphereGeometry(0.55, 20, 16),
    new THREE.MeshStandardMaterial({
      color: C_ACCUM, emissive: C_ACCUM, emissiveIntensity: 0.4,
      wireframe: true, transparent: true, opacity: 0.75,
    }),
  );
  _accumulator.position.set(0, 1.4, 0);
  _group.add(_accumulator);
}

// =============================================================================
// live data handler
// =============================================================================
function _onRingAttn(j) {
  // read honesty label VERBATIM — never upgrade
  S.label      = (j.label || "MODELED").toUpperCase();
  S.seqLen     = typeof j.seq_len                   === "number" ? j.seq_len                   : null;
  S.devices    = typeof j.devices                   === "number" ? j.devices                   : null;
  S.blockSize  = typeof j.block_size                === "number" ? j.block_size                : null;
  S.rotSteps   = typeof j.num_rotation_steps        === "number" ? j.num_rotation_steps         : null;
  S.memRatio   = typeof j.per_device_memory_ratio   === "number" ? j.per_device_memory_ratio    : null;
  S.exactMatch = typeof j.exact_match               === "boolean" ? j.exact_match               : null;
  S.maxContext = typeof j.max_context_supported     === "number" ? j.max_context_supported      : null;
  S.trace      = Array.isArray(j.rotation_trace) ? j.rotation_trace : null;

  _updateRing();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the ring + rotating KV block + accumulator
// =============================================================================
function _updateRing() {
  const live = S.state === "live";
  const n = live && S.devices ? Math.min(S.devices, MAX_DEVICES) : 0;

  for (let i = 0; i < MAX_DEVICES; i++) {
    const mesh = _deviceMesh[i];
    if (i >= n) { mesh.visible = false; continue; }
    mesh.visible = true;
    const [x, y, z] = _ringPos(i, n, RING_RADIUS, 0.6);
    mesh.position.set(x, y, z);
    const color = live ? C_DEVICE : C_DIM;
    mesh.material.color.setHex(color);
    mesh.material.emissive.setHex(color);
    mesh.material.opacity = live ? 0.9 : 0.25;
    mesh.material.emissiveIntensity = live ? 0.35 : 0.08;
  }

  _ringLine.material.color.setHex(live ? C_DEVICE : C_DIM);
  _ringLine.material.opacity = live ? 0.35 : 0.12;

  if (_kvBlock) {
    _kvBlock.visible = live && n > 0;
    _kvBlock.material.color.setHex(live ? C_KVBLOCK : C_DIM);
    _kvBlock.material.emissive.setHex(live ? C_KVBLOCK : C_DIM);
  }

  if (_accumulator) {
    if (live && S.exactMatch != null) {
      const color = S.exactMatch ? C_ACCUM : C_DIM; // exact -> teal; mismatch (never expected) -> grey, never red/purple
      _accumulator.material.color.setHex(color);
      _accumulator.material.emissive.setHex(color);
      _accumulator.material.opacity = 0.8;
    } else {
      _accumulator.material.color.setHex(C_DIM);
      _accumulator.material.emissive.setHex(C_DIM);
      _accumulator.material.opacity = 0.25;
    }
  }
}

// =============================================================================
// per-frame animation — KV block rotates around the ring; accumulator pulses
// as each rotation step is "absorbed" (proof-teal glow intensifies)
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.10;

  const live = S.state === "live";
  const n = live && S.devices ? Math.min(S.devices, MAX_DEVICES) : 0;

  if (_kvBlock && n > 0) {
    // one full rotation every ~ (devices * 900ms), i.e. slower with more devices
    // (visually implies num_rotation_steps == devices).
    const periodMs = Math.max(2000, n * 900);
    const phase = (t % periodMs) / periodMs; // 0..1
    const a = phase * Math.PI * 2;
    _kvBlock.position.set(Math.cos(a) * KV_ORBIT_R, 0.6 + 0.15 * Math.sin(t * 0.006), Math.sin(a) * KV_ORBIT_R);
    _kvBlock.rotation.x += 0.03;
    _kvBlock.rotation.y += 0.02;

    // pulse the accumulator once per rotation step as a block is "absorbed"
    const stepPhase = (phase * n) % 1.0;
    _accumPulsePhase = stepPhase;
  }

  if (_accumulator) {
    _accumulator.rotation.y += 0.015;
    const basePulse = 1.0 + 0.12 * Math.sin(t * 0.004);
    const stepGlow = live ? 1.0 + 0.25 * Math.exp(-6.0 * _accumPulsePhase) : 1.0;
    _accumulator.scale.setScalar(basePulse * stepGlow);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "ring attention", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Q/K/V are sharded across a logical <b>ring of devices</b>; KV blocks rotate around the ' +
    'ring in <b>num_rotation_steps = devices</b> steps while a running <b>online-softmax</b> ' +
    'accumulator (max/sum) absorbs each block. Result is provably <b>identical</b> to full ' +
    'attention (<b>exact_match</b>) at <b>1/devices</b> memory per device. Honesty label ' +
    '<b>MODELED</b> (deterministic blockwise simulation; NOT a real multi-device kernel). 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#3af4c8;box-shadow:0 0 7px #3af4c8";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#3af4c8;letter-spacing:.3px";
  nm.textContent = "ring attention";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";

  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:58%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("ra-seqlen",  "seq_len (context tokens)"));
  grid.appendChild(kpiRow("ra-devices", "devices (ring size)"));
  grid.appendChild(kpiRow("ra-block",   "block_size"));
  grid.appendChild(kpiRow("ra-steps",   "num_rotation_steps"));
  grid.appendChild(kpiRow("ra-memratio","per_device_memory_ratio \u2014 MODELED"));
  grid.appendChild(kpiRow("ra-exact",   "exact_match (blockwise == full)"));
  grid.appendChild(kpiRow("ra-maxctx",  "max_context_supported"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Liu, Zaharia & Abbeel arXiv:2310.01889 (Ring Attention) \u00b7 Liu & Abbeel arXiv:2305.19370 (Blockwise Parallel Transformer) \u00b7 github.com/haoliuhl/ringattention. MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ra-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const seqLen = S.seqLen  != null ? S.seqLen.toLocaleString() : "loading\u2026";
  const dev    = S.devices != null ? String(S.devices) : "loading\u2026";
  const ratio  = S.memRatio!= null ? "1/" + Math.round(1 / S.memRatio) : "loading\u2026";
  const exact  = S.exactMatch === true ? "exactly the same" : S.exactMatch === false ? "different (unexpected)" : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> Long documents mean huge Q/K/V matrices that don't fit on one " +
    "chip. Ring Attention splits the sequence (<b>" + seqLen + " tokens</b>) across a ring of " +
    "<b>" + dev + " devices</b>: each device keeps only its own slice and passes its key/value " +
    "block to the next device in the ring, one step at a time. A running \u201conline-softmax\u201d " +
    "tally (a running maximum and running sum) is updated after each block arrives, so the " +
    "final answer comes out <b>" + exact + "</b> as if one giant device had computed the whole " +
    "thing at once \u2014 while each device only ever needs <b>" + ratio + "</b> of the memory a " +
    "single device would need for the full sequence. Plain: same exact answer, spread across " +
    "many machines, using far less memory each. This view is a <b>MODELED</b> deterministic " +
    "simulation of that accumulation math, not a real multi-GPU run.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("ra-seqlen",   t || (S.seqLen  != null ? S.seqLen.toLocaleString() : "\u2014"));
  _set("ra-devices",  t || (S.devices != null ? String(S.devices) : "\u2014"));
  _set("ra-block",    t || (S.blockSize != null ? String(S.blockSize) : "\u2014"));
  _set("ra-steps",    t || (S.rotSteps  != null ? String(S.rotSteps) : "\u2014"));
  _set("ra-memratio", t || (S.memRatio  != null ? ("1/" + Math.round(1 / S.memRatio) + " (" + fx(S.memRatio, 4) + ")") : "\u2014"));
  _set("ra-exact",    t || (S.exactMatch === true ? "TRUE (exact)" : S.exactMatch === false ? "FALSE" : "\u2014"));
  _set("ra-maxctx",   t || (S.maxContext != null ? S.maxContext.toLocaleString() + " tokens" : "\u2014"));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "ring attention" });
  if (_plain) _applyPlain();
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _floor = null; _ringLine = null; _deviceMesh = []; _kvBlock = null; _accumulator = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false; _accumPulsePhase = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.devices = S.blockSize = S.rotSteps = null;
  S.memRatio = S.exactMatch = S.maxContext = S.trace = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
