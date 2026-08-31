// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/agentos.js — AGENT OS MAP · live, self-honest operator's-eye map of the agent OS.
//
// concept spark: Agentic-OS mapping, @Av1dlive on X
// https://x.com/Av1dlive/status/2074796427595874636 — we borrow the single-operator-map idea
// (one map of the whole agent OS: a daily loop, a trust ledger, standing goals, optional loops).
// We do NOT copy their diagrams or claim Fable-5 specifics. agentos composes ONLY our own
// governed components and reads every node/edge and every verdict LIVE from the running estate.
//
// A NODE/EDGE GRAPH: one mesh per agent-OS node (standing goals, daily loop, trust ledger,
// optional loops), coloured by its LIVE honesty verdict; edges are the control/data flow
// between them. A STATE PLATE at the top carries the estate's single map state — OPERATING /
// DEGRADED / HALTED-HONEST — read VERBATIM from the aggregate. HONEST BY CONSTRUCTION: node
// presence is derived from the live surface registry and each verdict is sourced from the
// honestywall aggregate — never a hand-drawn diagram.
//
// DATA: live snapshot from GET /api/a11oy/v1/govern/agentos (PURE READ, mints nothing):
//   ok, label (MODELED), state, state_reason,
//   nodes[ { id, title, kind, verdict, backing, backing_kind } ],
//   edges[ { src, dst, flow, label } ],
//   summary{ nodes_present, edges_present, verdict_counts, honestywall_reachable, honestywall_verdict },
//   doctrine{ lambda, locked_proven, trust_ceiling, trust_100_percent, adds_to_locked_8 }.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived composed view,
//   not a measurement). Per-node verdicts are read VERBATIM and NEVER upgraded. The map is
//   NEVER OPERATING if any node is VIOLATED. No green "1.0 / VERIFIED" state. Trust 0.97, not 100%.
// COLOURS: proof-teal 0x3af4c8 (intact/operating), amber 0xf4b23a (degraded/unknown), crimson
//   0xff5964 (violated/halted), grey 0x42505d (neutral), lattice-blue 0x5b8dee (frame/control),
//   violet-blue 0x8a6bff (standing-goals accent). PURPLE BANNED except 0x8a6bff. No green.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: COMPOSES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Lambda stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "agentos";
const TITLE = "Agent OS Map · self-honest operator's-eye map (live, drift-proof)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ live-map endpoint.
const EP = "/api/a11oy/v1/govern/agentos";

// verdict / state hues — purple BANNED (except 0x8a6bff), no green
const C_INTACT   = 0x3af4c8;  // proof-teal   — INTACT / OPERATING
const C_DEGRADED = 0xf4b23a;  // amber        — DEGRADED / UNKNOWN
const C_VIOLATED = 0xff5964;  // crimson      — VIOLATED / HALTED-HONEST
const C_NEUTRAL  = 0x42505d;  // grey         — neutral / init
const C_FRAME    = 0x5b8dee;  // lattice-blue — frame / control edges
const C_GOALS    = 0x8a6bff;  // violet-blue  — standing-goals accent (only approved purple)
const C_GRID     = 0x1b3a44;  // floor colour

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "INTACT")   return C_INTACT;
  if (s === "VIOLATED") return C_VIOLATED;
  if (s === "UNKNOWN" || s === "DEGRADED") return C_DEGRADED;
  return C_NEUTRAL;
}
function _stateColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "OPERATING")     return C_INTACT;
  if (s === "HALTED-HONEST") return C_VIOLATED;
  return C_DEGRADED;  // DEGRADED / init
}

// deterministic layout position (x,y,z) by node kind — an operator's-eye stack: standing goals
// at the top, the daily loop in the middle, the trust ledger below, optional loops in an arc.
function _layout(node, optIndex, optCount) {
  const kind = String(node.kind || "");
  if (kind === "goals")  return [0, 6.0, 0];
  if (kind === "loop")   return [0, 3.0, 0];
  if (kind === "ledger") return [0, 0.2, 0];
  // optional_loop — spread along an arc beneath the daily loop
  const n = Math.max(1, optCount);
  const span = 12.0;
  const step = n > 1 ? span / (n - 1) : 0;
  const x = n > 1 ? -span / 2 + step * optIndex : 0;
  return [x, 1.6, -4.2];
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _plate = null;            // THREE.Mesh — the map-state plate
let _nodes = [];              // Array<{ id, mesh, verdict, pos }>
let _edges = [];              // Array<{ line, flow }>

// live state (all read from JSON; nothing invented)
const S = {
  label:   null,   // top honesty label VERBATIM (MODELED)
  state:   null,   // OPERATING | DEGRADED | HALTED-HONEST
  reason:  null,
  nodes:   [],
  edges:   [],
  present: null,
  vc:      {},     // verdict_counts
  hwReach: null,
  hwVerd:  null,
  trustCeil: null,
  lambda:  null,
  locked:  null,
  mode:    "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.2, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.6, -1); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlate();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.mode = m.state; _paintOverlay(); _paintPlate(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildPlate() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(7.2, 1.2, 0.6);
  _plate = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_DEGRADED, emissive: C_DEGRADED, emissiveIntensity: 0.35,
    transparent: true, opacity: 0.9,
  }));
  _plate.position.set(0, 8.4, 0);
  _group.add(_plate);
}

// Build (or rebuild) the node/edge graph from the CURRENT feed (never a stale hard-coded set).
function _buildGraph() {
  const THREE = _THREE;
  _disposeGraph();

  const nodes = Array.isArray(S.nodes) ? S.nodes : [];
  if (!nodes.length) return;

  // assign layout positions
  const optNodes = nodes.filter((n) => String(n.kind) === "optional_loop");
  const pos = {};
  let oi = 0;
  nodes.forEach((n) => {
    if (String(n.kind) === "optional_loop") { pos[n.id] = _layout(n, oi, optNodes.length); oi++; }
    else { pos[n.id] = _layout(n, 0, optNodes.length); }
  });

  // edges first (so nodes render on top)
  (Array.isArray(S.edges) ? S.edges : []).forEach((e) => {
    const a = pos[e.src], b = pos[e.dst];
    if (!a || !b) return;   // never draw a dangling edge to an absent node
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(a[0], a[1], a[2]), new THREE.Vector3(b[0], b[1], b[2]),
    ]);
    const col = String(e.flow) === "data" ? C_INTACT : C_FRAME;
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({
      color: col, transparent: true, opacity: 0.42,
    }));
    _group.add(line);
    _edges.push({ line, flow: String(e.flow) });
  });

  // nodes
  nodes.forEach((n) => {
    const p = pos[n.id];
    if (!p) return;
    const isGoals = String(n.kind) === "goals";
    const base = _verdictColor(n.verdict);
    const geo = isGoals
      ? new THREE.BoxGeometry(1.7, 1.7, 1.7)
      : new THREE.SphereGeometry(0.95, 24, 24);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: base, emissive: base, emissiveIntensity: 0.3, transparent: true, opacity: 0.94,
    }));
    mesh.position.set(p[0], p[1], p[2]);
    _group.add(mesh);

    // a thin accent ring for the standing-goals node (violet-blue, the only approved purple)
    if (isGoals) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(1.5, 0.05, 8, 40),
        new THREE.MeshStandardMaterial({ color: C_GOALS, emissive: C_GOALS, emissiveIntensity: 0.5,
          transparent: true, opacity: 0.7 }));
      ring.position.set(p[0], p[1], p[2]);
      ring.rotation.x = Math.PI / 2;
      _group.add(ring);
      _nodes.push({ id: n.id + ":ring", mesh: ring, verdict: null, pos: p });
    }

    _nodes.push({ id: n.id, mesh, verdict: String(n.verdict || ""), pos: p });
  });
}

function _disposeGraph() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _nodes.forEach((n) => rm(n.mesh));
  _edges.forEach((e) => rm(e.line));
  _nodes = []; _edges = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label  = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.state  = j && j.state ? String(j.state).toUpperCase() : null;
  S.reason = j && j.state_reason ? String(j.state_reason) : null;
  S.nodes  = (j && Array.isArray(j.nodes)) ? j.nodes : [];
  S.edges  = (j && Array.isArray(j.edges)) ? j.edges : [];

  const sm = (j && j.summary) || {};
  S.present = typeof sm.nodes_present === "number" ? sm.nodes_present : null;
  S.vc      = (sm.verdict_counts && typeof sm.verdict_counts === "object") ? sm.verdict_counts : {};
  S.hwReach = typeof sm.honestywall_reachable === "boolean" ? sm.honestywall_reachable : null;
  S.hwVerd  = sm.honestywall_verdict != null ? String(sm.honestywall_verdict) : null;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildGraph();
  _paintPlate();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.10;

  const live = S.mode === "live";
  if (_plate) {
    const pulse = 0.35 + (live ? 0.25 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _plate.material.emissiveIntensity = pulse;
  }
  for (let i = 0; i < _nodes.length; i++) {
    const nd = _nodes[i];
    if (!nd.mesh || !nd.mesh.material) continue;
    const violated = nd.verdict === "VIOLATED";
    const base = violated ? 0.6 : (live ? 0.3 : 0.12);
    const wob = 0.15 * (0.5 + 0.5 * Math.sin(t * 0.002 + i));
    nd.mesh.material.emissiveIntensity = base + (live ? wob : 0);
    nd.mesh.material.opacity = live ? 0.94 : 0.4;
  }
}

// =============================================================================
function _paintPlate() {
  if (!_plate) return;
  const col = _stateColor(S.mode === "live" ? S.state : null);
  _plate.material.color.setHex(col);
  _plate.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "composed", name: "lbl" },
            { label: "—", text: "state", name: "stt" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A live operator’s-eye map of the whole agent OS, composed <b>only</b> from our own ' +
    'governed components: a <b>daily loop</b>, a <b>trust ledger</b>, <b>standing goals</b>, and ' +
    'optional loops. Node presence is derived from the live surface registry; each node’s ' +
    'honesty verdict is read <b>VERBATIM</b> from the honesty-wall aggregate. The map reads ' +
    '<b>OPERATING</b> only when every node is INTACT, <b>DEGRADED</b> when a backing is UNKNOWN, ' +
    'and <b>HALTED-HONEST</b> the instant any node is VIOLATED — it can <b>never</b> render green ' +
    'while something is wrong. Honest by construction, not a hand-drawn diagram. 0 runtime CDN.';
  host.appendChild(sub);

  const spark = document.createElement("div");
  spark.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;border-left:2px solid #8a6bff;padding-left:7px";
  spark.innerHTML =
    'concept spark: Agentic-OS mapping, <b>@Av1dlive on X</b> — we borrow the ' +
    'single-operator-map idea; we do not copy their diagrams or claim Fable-5 specifics. ' +
    'agentos composes only our own governed components.';
  host.appendChild(spark);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";
  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:62%;overflow-wrap:anywhere";
    v.textContent = "—";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }
  grid.appendChild(kpiRow("ao-state",  "map state"));
  grid.appendChild(kpiRow("ao-nodes",  "nodes present"));
  grid.appendChild(kpiRow("ao-intact", "nodes INTACT"));
  grid.appendChild(kpiRow("ao-unk",    "nodes UNKNOWN"));
  grid.appendChild(kpiRow("ao-viol",   "nodes VIOLATED"));
  grid.appendChild(kpiRow("ao-hw",     "honesty-wall verdict"));
  grid.appendChild(kpiRow("ao-locked", "locked proofs"));
  grid.appendChild(kpiRow("ao-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("ao-lambda", "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable per-node list (text mirror of the graph).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:170px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">●</span> INTACT / OPERATING &nbsp; ' +
    '<span style="color:#f4b23a">●</span> UNKNOWN / degraded &nbsp; ' +
    '<span style="color:#ff5964">●</span> VIOLATED / halted &nbsp; ' +
    '<span style="color:#8a6bff">◯</span> standing goals. ' +
    'MODELED · verdicts read verbatim, never upgraded · never OPERATING if violated.';
  card.appendChild(leg);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ao-plain";
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
  pd.innerHTML =
    "<b>What this means:</b> one honest map of how the agent system actually runs — a daily " +
    "loop, a trust ledger, the standing goals it must obey, and the optional loops it can call. " +
    "Every box is a real, running part of our own platform (nothing is drawn by hand), and each " +
    "one shows whether it is currently honest. If every part checks out the map reads " +
    "<b>OPERATING</b>; if a part can’t be reached it reads <b>DEGRADED</b>; and if any part " +
    "breaks a house rule the whole map reads <b>HALTED-HONEST</b> — it will <b>never</b> claim " +
    "OPERATING while something is wrong. No “verified / 1.0” state.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _n(v) { return v == null ? "—" : String(v); }

function _paintList() {
  const wrap = _el["list"];
  if (!wrap) return;
  wrap.innerHTML = "";
  (Array.isArray(S.nodes) ? S.nodes : []).forEach((n) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:66%";
    left.textContent = String(n.title || n.id);
    const val = document.createElement("b");
    const hex = "#" + _verdictColor(n.verdict).toString(16).padStart(6, "0");
    val.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums";
    val.textContent = String(n.verdict || "—");
    row.appendChild(left); row.appendChild(val);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.mode);
  const stt = t || (S.state || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "composed" });
    _show.setChip("stt", stt, { text: "state" });
  }
  _set("ao-state",  stt);
  _set("ao-nodes",  t || _n(S.present));
  _set("ao-intact", t || _n(S.vc && S.vc.INTACT != null ? S.vc.INTACT : null));
  _set("ao-unk",    t || _n(S.vc && S.vc.UNKNOWN != null ? S.vc.UNKNOWN : null));
  _set("ao-viol",   t || _n(S.vc && S.vc.VIOLATED != null ? S.vc.VIOLATED : null));
  _set("ao-hw",     t || (S.hwVerd || "—"));
  _set("ao-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("ao-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("ao-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeGraph();
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _plate = null; _nodes = []; _edges = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.state = S.reason = null;
  S.nodes = []; S.edges = [];
  S.present = null; S.vc = {}; S.hwReach = null; S.hwVerd = null;
  S.trustCeil = S.lambda = S.locked = null; S.mode = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
