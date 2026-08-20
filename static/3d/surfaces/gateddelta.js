// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/gateddelta.js — GATED DELTA-RULE LINEAR ATTENTION organ for the
// holographic frontier ring. Renders the associative-memory "register file" of a
// linear-attention layer: one node per register (key), lit by how well each update
// rule recalls that register's LAST written value. Delta-rule registers glow
// proof-teal (near-exact in-place overwrite), gated-delta registers glow lattice-
// blue (direction kept, magnitude adaptively decayed), and plain linear-attention
// error rises as a grey column (writes accumulate, overwrites collide). A HUD shows
// per-policy recall error / cosine, the gate retention, and the chunk-parallel
// invariant (chunked delta state == sequential state) from the live snapshot at
// /api/a11oy/v1/gateddelta/recall. Honesty label "MODELED" is read VERBATIM from
// the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors kvcache.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   seq_len, dim, n_keys, chunk, gate, beta, n_overwrites,
//   linear_recall_error, delta_recall_error, gated_recall_error,
//   linear_recall_cos, delta_recall_cos, gated_recall_cos, gated_retention,
//   delta_vs_linear_gain, chunk_max_state_diff, state_track_acc{}, per_register[]
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; VERIFY real):
//   Gated DeltaNet — Yang, Kautz, Hatamizadeh 2024, arXiv:2412.06464
//   Parallel Delta Rule — Yang et al. 2024, arXiv:2406.06484
//   DeltaProduct (state-tracking) — Siems et al. 2025, arXiv:2502.10297
//   GLA — Yang et al. 2023, arXiv:2312.06635
//
// HONESTY LABELS: MODELED (deterministic simulation of the delta-rule / gated-delta
//   / linear-attention state updates over a synthetic key/value write trace; NOT a
//   real trained model or GPU). Read verbatim from JSON; never upgraded here.
// COLOURS: proof-teal 0x3af4c8 (delta rule / HUD accent), lattice-blue 0x5b8dee
//   (gated delta), greys (linear-attention error / degraded state). Purple BANNED.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "gateddelta";
const TITLE = "Gated Delta-Rule Linear Attention · state recall (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted twin (same-origin, szl_gated_delta.py):
// real delta-rule / gated-delta / linear-attention state updates over a seeded key/value
// write trace (label MODELED, read verbatim). No cross-origin dependency.
const EP = "/api/a11oy/v1/gateddelta/recall?seed=42&seq_len=48&dim=8&n_keys=6&chunk=8&gate=0.98&beta=1.0";

// data-viz hues — purple BANNED
const C_DELTA   = 0x3af4c8;  // proof-teal (delta rule / HUD accent)
const C_GATED   = 0x5b8dee;  // lattice-blue (gated delta)
const C_LINEAR  = 0x5a6570;  // grey (linear-attention error)
const C_DIM     = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID    = 0x1b3a44;  // floor / link colour

// register-row layout geometry
const REG_GAP    = 1.1;   // world-units between register nodes along X
const MAX_REGS   = 16;    // cap on registers rendered (perf; backend clamps n_keys<=16)
const BASE_Y     = 0.4;   // resting height of a register node

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _spine    = null;                 // THREE.Line — the register-file spine
let _regMesh  = [];                   // Array<THREE.Mesh> — one delta node per register
let _errBar   = [];                   // Array<THREE.Mesh> — linear-attention error column per reg
let _marker   = null;                 // THREE.Mesh — HUD pulsing marker (gate retention cue)

// live state
const S = {
  label:            null,
  seqLen:           null,
  dim:              null,
  nKeys:            null,
  chunk:            null,
  gate:             null,
  beta:             null,
  nOverwrites:      null,
  linearErr:        null,   // linear_recall_error
  deltaErr:         null,   // delta_recall_error
  gatedErr:         null,   // gated_recall_error
  linearCos:        null,
  deltaCos:         null,
  gatedCos:         null,
  gatedRetention:   null,
  deltaVsLinear:    null,   // delta_vs_linear_gain
  chunkDiff:        null,   // chunk_max_state_diff
  trackAcc:         null,   // state_track_acc {}
  perReg:           null,   // per_register[]
  state:            "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(4, 6, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(4, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildRegisterRow();
  _buildMarker();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onGatedDelta, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(36, 36, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

// Pre-allocate a fixed register file: MAX_REGS slots. Each slot has a delta/gated
// node (recall quality) + a linear-attention error column. Toggled in-place as
// live data arrives (no per-poll geometry churn).
function _buildRegisterRow() {
  const THREE = _THREE;

  // register-file spine along X
  {
    const pts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(REG_GAP * (MAX_REGS - 1) + 1, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_DELTA, transparent: true, opacity: 0.4 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }

  const nodeGeo = new THREE.IcosahedronGeometry(0.22, 0);
  const barGeo  = new THREE.BoxGeometry(0.22, 1.0, 0.22);
  for (let r = 0; r < MAX_REGS; r++) {
    const x = r * REG_GAP;
    const node = new THREE.Mesh(
      nodeGeo,
      new THREE.MeshStandardMaterial({ color: C_DELTA, emissive: C_DELTA, emissiveIntensity: 0.3, transparent: true, opacity: 0.0 }),
    );
    node.position.set(x, BASE_Y, 0);
    node.visible = false;
    _group.add(node);
    _regMesh.push(node);

    const bar = new THREE.Mesh(
      barGeo,
      new THREE.MeshStandardMaterial({ color: C_LINEAR, emissive: C_LINEAR, emissiveIntensity: 0.15, transparent: true, opacity: 0.0 }),
    );
    bar.position.set(x, 0.5, -1.1);
    bar.visible = false;
    _group.add(bar);
    _errBar.push(bar);
  }
}

function _buildMarker() {
  const THREE = _THREE;
  _marker = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.3, 1),
    new THREE.MeshStandardMaterial({ color: C_GATED, emissive: C_GATED, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _marker.position.set(0, -1.0, 0);
  _group.add(_marker);
}

// =============================================================================
// live data handler
// =============================================================================
function _onGatedDelta(j) {
  // read honesty label VERBATIM — never upgrade
  S.label          = (j.label || "MODELED").toUpperCase();
  S.seqLen         = typeof j.seq_len              === "number" ? j.seq_len              : null;
  S.dim            = typeof j.dim                  === "number" ? j.dim                  : null;
  S.nKeys          = typeof j.n_keys               === "number" ? j.n_keys               : null;
  S.chunk          = typeof j.chunk                === "number" ? j.chunk                : null;
  S.gate           = typeof j.gate                 === "number" ? j.gate                 : null;
  S.beta           = typeof j.beta                 === "number" ? j.beta                 : null;
  S.nOverwrites    = typeof j.n_overwrites         === "number" ? j.n_overwrites         : null;
  S.linearErr      = typeof j.linear_recall_error  === "number" ? j.linear_recall_error  : null;
  S.deltaErr       = typeof j.delta_recall_error   === "number" ? j.delta_recall_error   : null;
  S.gatedErr       = typeof j.gated_recall_error   === "number" ? j.gated_recall_error   : null;
  S.linearCos      = typeof j.linear_recall_cos    === "number" ? j.linear_recall_cos    : null;
  S.deltaCos       = typeof j.delta_recall_cos     === "number" ? j.delta_recall_cos     : null;
  S.gatedCos       = typeof j.gated_recall_cos     === "number" ? j.gated_recall_cos     : null;
  S.gatedRetention = typeof j.gated_retention      === "number" ? j.gated_retention      : null;
  S.deltaVsLinear  = typeof j.delta_vs_linear_gain === "number" ? j.delta_vs_linear_gain : null;
  S.chunkDiff      = typeof j.chunk_max_state_diff === "number" ? j.chunk_max_state_diff : null;
  S.trackAcc       = (j.state_track_acc && typeof j.state_track_acc === "object") ? j.state_track_acc : null;
  S.perReg         = Array.isArray(j.per_register) ? j.per_register : null;

  _updateRegisterRow();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the register file from live data
// =============================================================================
function _updateRegisterRow() {
  const live = S.state === "live";
  const regs = live && S.perReg && S.perReg.length ? S.perReg.slice(0, MAX_REGS) : [];

  for (let r = 0; r < MAX_REGS; r++) {
    const node = _regMesh[r];
    const bar  = _errBar[r];
    if (!live || r >= regs.length) {
      node.visible = false;
      bar.visible = false;
      continue;
    }
    node.visible = true;
    bar.visible = true;
    const rec = regs[r];

    // delta node: taller + proof-teal when recall is faithful (low delta_err, high cos).
    const deltaGood = typeof rec.delta_cos === "number" ? Math.max(0, rec.delta_cos) : 0;
    node.material.color.setHex(C_DELTA);
    node.material.emissive.setHex(C_DELTA);
    node.material.emissiveIntensity = 0.3 + 0.5 * deltaGood;
    node.material.opacity = 0.95;
    node.position.y = BASE_Y + deltaGood * 0.9;
    // gated ring cue: scale by gated magnitude retention (fades for stale registers)
    const ret = typeof rec.gated_retention === "number" ? Math.min(1.2, rec.gated_retention) : 1.0;
    node.scale.setScalar(0.7 + 0.5 * ret);

    // linear-attention error column: height grows with lin_err (overwrite collision).
    const le = typeof rec.lin_err === "number" ? rec.lin_err : 0;
    const h = Math.max(0.05, Math.min(4.0, le));
    bar.scale.y = h;
    bar.position.y = h * 0.5;
    // blend grey -> lattice-blue by write count so heavily-overwritten regs read hot
    const writes = typeof rec.writes === "number" ? rec.writes : 1;
    bar.material.color.setHex(writes > 1 ? C_GATED : C_LINEAR);
    bar.material.emissive.setHex(writes > 1 ? C_GATED : C_LINEAR);
    bar.material.emissiveIntensity = writes > 1 ? 0.35 : 0.12;
    bar.material.opacity = 0.55;
  }

  // spine degrades to grey when not live
  _spine.material.color.setHex(live ? C_DELTA : C_DIM);
  _spine.material.opacity = live ? 0.4 : 0.15;

  if (_marker) {
    if (live && S.gatedRetention != null) {
      _marker.material.color.setHex(C_GATED);
      _marker.material.emissive.setHex(C_GATED);
      _marker.material.opacity = 0.85;
      const x = Math.min(REG_GAP * (MAX_REGS - 1), (S.gatedRetention || 0) * REG_GAP * (MAX_REGS - 1));
      _marker.position.set(x, -1.0, 0);
    } else {
      _marker.material.color.setHex(C_DIM);
      _marker.material.emissive.setHex(C_DIM);
      _marker.material.opacity = 0.3;
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.12;
  if (_marker) {
    _marker.rotation.y += 0.025;
    _marker.rotation.x += 0.012;
    const pulse = 1.0 + 0.15 * Math.sin(t * 0.004);
    _marker.scale.setScalar(pulse);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MODELED", text: "delta-rule recall", name: "gd" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'A linear-attention layer keeps an associative-memory <b>state matrix</b> that maps a ' +
      'key to a recalled value. <b>Plain linear attention</b> just ADDS every write, so ' +
      're-writing a key accumulates values and a later read of an overwritten key is wrong. ' +
      'The <b>delta rule</b> (a Householder reflection I − β k kᵀ) first ' +
      'REMOVES the old association then writes the new one — recalling the LAST write ' +
      'exactly. <b>Gated delta</b> adds a data-dependent decay gate α so stale memories ' +
      'fade (magnitude × α per step) while identity is kept. HUD also verifies the ' +
      'chunk-parallel invariant (chunked state == sequential state). Honesty label ' +
      '<b>MODELED</b> (deterministic simulation on a synthetic key/value trace; NOT a real ' +
      'trained model or GPU). 0 runtime CDN.',
    citations:
      "Gated DeltaNet — Yang et al. arXiv:2412.06464 · Parallel Delta — arXiv:2406.06484 · " +
      "DeltaProduct — arXiv:2502.10297 · GLA — arXiv:2312.06635. MODELED · not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["gd-seqlen"]   = _show.addField("seq_len (writes)");
  _el["gd-dims"]     = _show.addField("dim × n_keys (state / registers)");
  _el["gd-overw"]    = _show.addField("overwrites in trace");
  _el["gd-linerr"]   = _show.addField("linear-attention recall error");
  _el["gd-deltaerr"] = _show.addField("delta-rule recall error — MODELED");
  _el["gd-gatederr"] = _show.addField("gated-delta recall error");
  _el["gd-gatedcos"] = _show.addField("gated-delta recall cosine (direction)");
  _el["gd-retention"]= _show.addField("gate retention (α magnitude decay)");
  _el["gd-gain"]     = _show.addField("delta vs linear error gain");
  _el["gd-chunk"]    = _show.addField("chunk≡sequential state diff");
  _el["gd-track"]    = _show.addField("state-tracking acc (lin/delta/gated)");
  _el["gd-label"]    = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const le = S.linearErr != null ? S.linearErr.toFixed(2) : "loading…";
  const de = S.deltaErr  != null ? S.deltaErr.toFixed(3)  : "loading…";
  const gr = S.gatedRetention != null ? (S.gatedRetention * 100).toFixed(0) + "%" : "loading…";
  return (
    "<b>What this means:</b> Imagine a whiteboard where the model writes down “variable X = value” " +
    "as it reads. If it just KEEPS ADDING new values without erasing the old one, then asking " +
    "“what is X now?” gives a garbled sum — that is plain linear attention, and here its recall " +
    "is off by <b>" + le + "</b>. The <b>delta rule</b> ERASES the old value of X before writing the " +
    "new one, so it recalls the latest value almost perfectly (error <b>" + de + "</b>). The " +
    "<b>gated</b> version also lets very old, untouched notes gently fade — here it keeps about " +
    "<b>" + gr + "</b> of a note's strength while never confusing which note is which. This view is a " +
    "<b>MODELED</b> deterministic simulation of those write/erase rules on a synthetic trace, not a " +
    "run of a real trained model.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("gd-seqlen",   t || (S.seqLen != null ? String(S.seqLen) : "—"));
  _set("gd-dims",     t || ((S.dim != null && S.nKeys != null) ? (S.dim + " × " + S.nKeys) : "—"));
  _set("gd-overw",    t || (S.nOverwrites != null ? String(S.nOverwrites) : "—"));
  _set("gd-linerr",   t || fx(S.linearErr, 3));
  _set("gd-deltaerr", t || fx(S.deltaErr, 4));
  _set("gd-gatederr", t || fx(S.gatedErr, 4));
  _set("gd-gatedcos", t || fx(S.gatedCos, 4));
  _set("gd-retention",t || (S.gatedRetention != null ? (S.gatedRetention * 100).toFixed(1) + "%" : "—"));
  _set("gd-gain",     t || (S.deltaVsLinear != null ? "−" + fx(S.deltaVsLinear, 3) + " err" : "—"));
  _set("gd-chunk",    t || (S.chunkDiff != null ? S.chunkDiff.toExponential(1) : "—"));
  _set("gd-track",    t || (S.trackAcc ? [S.trackAcc.linear, S.trackAcc.delta, S.trackAcc.gated].map((x) => fx(x, 2)).join(" / ") : "—"));
  // honesty label verbatim — never upgraded
  _set("gd-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("gd", S.label || "MODELED", { text: "delta-rule recall" }); _show.refreshPlain(); }
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
  _spine = null; _regMesh = []; _errBar = []; _marker = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.dim = S.nKeys = S.chunk = S.gate = S.beta = null;
  S.nOverwrites = S.linearErr = S.deltaErr = S.gatedErr = null;
  S.linearCos = S.deltaCos = S.gatedCos = S.gatedRetention = null;
  S.deltaVsLinear = S.chunkDiff = S.trackAcc = S.perReg = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
