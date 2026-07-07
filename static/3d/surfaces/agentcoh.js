// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/agentcoh.js — MULTI-AGENT MEMORY COHERENCE organ (NEW AXIS) for the
// holographic frontier ring, clean-room-inspired by (NOT a reproduction of) the
// TOKEN COHERENCE idea (arXiv:2603.15183, Parakhin): naive multi-agent LLM
// orchestration rebroadcasts full shared state on every update, costing O(n·S·|D|);
// this maps onto SHARED-MEMORY CACHE COHERENCE — an artifact held by several agents
// is a cache line held by several cores. This organ ports the MESI protocol
// (Modified/Exclusive/Shared/Invalid + LAZY INVALIDATION) to artifacts.
//
// Visual: a grid of MESI state LANES — one row per (agent, artifact) cache entry —
// advancing left-to-right along the operation trace. Each cell's colour encodes its
// MESI state; invalidation events flash on the writer→peer links. A side panel shows
// the naive-vs-MESI cost curve as write_fraction sweeps, and the three invariant
// PASS/FAIL lights (mesi_buggy surfaces a stale-read FAIL). Honesty label "MODELED"
// is read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors episodic.js / graphmem.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   timeline[]            — per-artifact { artifact, lanes:[{agent, states:[...]}] }
//   naive / mesi          — { coordinator, cost, invalidations, refetches, ... }
//   invariants            — { single_writer, monotonic_versioning, bounded_staleness }
//   cost_curve[]          — { write_fraction, naive_cost, mesi_cost, savings_ratio }
//   invalidation_events[] — { step, artifact, from, to }
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Token Coherence (MESI→artifact protocol; Parakhin): https://arxiv.org/abs/2603.15183
//   Multi-Agent Memory from a Computer Architecture Perspective (Yu et al.):
//     https://arxiv.org/abs/2603.10062
//   Governed Shared Memory for Multi-Agent LLM Systems: https://arxiv.org/abs/2606.24535
//
// HONESTY LABELS: MODELED (toy deterministic sim of the MESI→artifact coherence
//   MECHANISM; integer-versioned dict entries; cost is a counted token/byte proxy, not
//   measured LLM tokens; invariants via in-sim assertions, NOT a TLA+ checker; no
//   LangGraph/CrewAI/AutoGen). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (Shared / Exclusive lanes + naive cost), violet-blue
//   0x8a6bff (Modified writer lane + invalidation flash — data-viz only), proof-teal
//   0x3af4c8 (MESI cost / invariant-PASS accent), greys for Invalid / degraded / no-data.
//   Purple BANNED as UI/background.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored r170 through the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

import { createShowcase } from "./_showcase.js";

const ID    = "agentcoh";
const TITLE = "Multi-Agent Memory Coherence · MESI→artifact (live)";

// Endpoint on the dedicated killinchu Space (isolated compute), reached cross-origin.
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/agentcoh/sync?seed=42&num_agents=3&num_artifacts=4&write_fraction=0.35&mode=mesi";

// data-viz hues — purple BANNED
const C_SHARED = 0x5b8dee;  // lattice-blue (Shared / Exclusive lane + naive cost bar)
const C_MOD    = 0x8a6bff;  // violet-blue (Modified writer lane + invalidation flash — data-viz only)
const C_ACCENT = 0x3af4c8;  // proof-teal (MESI cost bar / invariant-PASS accent)
const C_DIM    = 0x42505d;  // grey (Invalid lane / degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

const N_ART   = 4;    // artifact rows (matches endpoint default cap of visualization)
const N_AGENT = 3;    // agent sub-lanes per artifact
const N_STEP  = 24;   // visible trace steps (columns) along the x-axis
const SPAN_X  = 18;   // world-unit span of the trace axis
const LANE_DY = 0.9;  // vertical spacing between agent lanes
const ART_DY  = 3.4;  // vertical spacing between artifact blocks

let _stage = null, _THREE = null, _ctx = null, _group = null, _overlay = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;
let _show = null;

// geometry handles
let _cells = [];        // Array<THREE.Mesh> — one cell per (artifact, agent, step)
let _links = null;      // THREE.LineSegments — invalidation event links
let _flash = [];        // per-cell flash timer (invalidation highlight)

// live state
const S = {
  label:       null,
  timeline:    null,   // Array<{artifact, lanes:[{agent, states:[...]}]}>
  naive:       null,   // {coordinator, cost, ...}
  mesi:        null,   // {coordinator, cost, invalidations, refetches, ...}
  invariants:  null,   // {single_writer, monotonic_versioning, bounded_staleness, all_hold}
  costCurve:   null,   // Array<{write_fraction, naive_cost, mesi_cost, savings_ratio}>
  invEvents:   null,   // Array<{step, artifact, from, to}>
  mode:        null,
  state:       "init",
};

// map a MESI state string to a data-viz colour
function _stateColor(st, live) {
  if (!live) return C_DIM;
  if (st === "Modified")  return C_MOD;
  if (st === "Exclusive") return C_SHARED;
  if (st === "Shared")    return C_SHARED;
  if (st === "Invalid")   return C_DIM;
  return C_DIM;
}

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 26);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 3, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCells();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onSync, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintCells(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildCells() {
  const THREE = _THREE;
  const geo = new THREE.BoxGeometry(0.5, 0.28, 0.5);
  _cells = [];
  _flash = [];
  // rows: artifact block (N_ART), each with N_AGENT lanes; columns: N_STEP trace steps
  for (let art = 0; art < N_ART; art++) {
    for (let ag = 0; ag < N_AGENT; ag++) {
      for (let st = 0; st < N_STEP; st++) {
        const mat = new THREE.MeshStandardMaterial({
          color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.12,
          metalness: 0.2, roughness: 0.6,
        });
        const mesh = new THREE.Mesh(geo, mat);
        const x = (st / (N_STEP - 1)) * SPAN_X - SPAN_X / 2;
        const y = art * ART_DY + ag * LANE_DY + 0.6;
        mesh.position.set(x, y, 0);
        mesh.userData = { art, ag, st };
        _group.add(mesh);
        _cells.push(mesh);
        _flash.push(0);
      }
    }
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onSync(j) {
  // read honesty label VERBATIM — never upgrade
  S.label      = (j.label || "MODELED").toUpperCase();
  S.timeline   = Array.isArray(j.timeline) ? j.timeline : null;
  S.naive      = j.naive || null;
  S.mesi       = j.mesi || null;
  S.invariants = j.invariants || null;
  S.costCurve  = Array.isArray(j.cost_curve) ? j.cost_curve : null;
  S.invEvents  = Array.isArray(j.invalidation_events) ? j.invalidation_events : null;
  S.mode       = j.mode || null;

  _paintCells();
  _paintOverlay();
}

// =============================================================================
// geometry updater — colours each cell by its MESI state at that trace step
// =============================================================================
function _cellIndex(art, ag, st) {
  return (art * N_AGENT + ag) * N_STEP + st;
}

function _paintCells() {
  const live = S.state === "live";
  const tl = S.timeline || [];

  // default: dim everything
  _cells.forEach((mesh) => {
    mesh.material.color.setHex(C_DIM);
    mesh.material.emissive.setHex(C_DIM);
    mesh.material.emissiveIntensity = 0.1;
    mesh.scale.set(1, 1, 1);
  });

  if (tl.length) {
    for (let art = 0; art < Math.min(N_ART, tl.length); art++) {
      const lanes = (tl[art] && tl[art].lanes) || [];
      for (let ag = 0; ag < Math.min(N_AGENT, lanes.length); ag++) {
        const states = (lanes[ag] && lanes[ag].states) || [];
        for (let st = 0; st < N_STEP; st++) {
          const stName = states[st];
          if (stName === undefined) continue;
          const mesh = _cells[_cellIndex(art, ag, st)];
          if (!mesh) continue;
          const col = _stateColor(stName, live);
          mesh.material.color.setHex(col);
          mesh.material.emissive.setHex(col);
          const isMod = live && stName === "Modified";
          const isInv = stName === "Invalid";
          mesh.material.emissiveIntensity = live ? (isMod ? 0.85 : (isInv ? 0.08 : 0.35)) : 0.1;
          mesh.scale.set(1, isMod ? 2.0 : (isInv ? 0.5 : 1.0), 1);
        }
      }
    }
  }

  // rebuild invalidation-event links (writer step -> flash on the invalidated lanes)
  if (_links) { _group.remove(_links); _links.geometry.dispose(); _links.material.dispose(); _links = null; }
  const evs = S.invEvents || [];
  if (live && evs.length) {
    const THREE = _THREE;
    const pts = [];
    evs.forEach((e) => {
      if (e.step >= N_STEP || e.artifact >= N_ART) return;
      if (e.from >= N_AGENT || e.to >= N_AGENT) return;
      const a = _cells[_cellIndex(e.artifact, e.from, e.step)];
      const b = _cells[_cellIndex(e.artifact, e.to, e.step)];
      if (!a || !b) return;
      pts.push(a.position.clone(), b.position.clone());
      const bi = _cellIndex(e.artifact, e.to, e.step);
      _flash[bi] = 60;
    });
    if (pts.length) {
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      _links = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: C_MOD, transparent: true, opacity: 0.4 }));
      _group.add(_links);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.12;
  const live = S.state === "live";
  for (let i = 0; i < _cells.length; i++) {
    if (_flash[i] > 0) {
      _flash[i] -= 1;
      const f = _flash[i] / 60;
      const col = live ? C_MOD : C_DIM;
      _cells[i].material.emissive.setHex(col);
      _cells[i].material.emissiveIntensity = Math.max(_cells[i].material.emissiveIntensity, 0.2 + 0.8 * f);
    }
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,460px)",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial",
    color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A grid of <b>MESI state lanes</b> \u2014 one row per (agent, artifact) cache entry \u2014 ' +
    'advancing along a fixed seeded op trace. Two coordinators run the SAME trace: ' +
    '<b>naive broadcast</b> (re-sends the full artifact to all agents on every write) vs ' +
    '<b>MESI-ACS</b> (lazy invalidation + on-demand re-fetch). Three invariants are ' +
    'asserted; <b>mesi_buggy</b> drops an invalidation to expose a stale read. Honesty ' +
    'label <b>MODELED</b> (Token-Coherence-inspired \u2014 not a reproduction). 0 runtime CDN.';
  _overlay.appendChild(sub);

  const brow = document.createElement("div");
  brow.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap";
  if (_badge && _badge.el) brow.appendChild(_badge.el);
  _overlay.appendChild(brow);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "agentcoh";
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
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:60%";
    v.textContent = "\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("ac-mode",   "mode"));
  grid.appendChild(kpiRow("ac-naive",  "naive-broadcast cost"));
  grid.appendChild(kpiRow("ac-mesi",   "MESI-ACS cost"));
  grid.appendChild(kpiRow("ac-save",   "cost saved (this trace)"));
  grid.appendChild(kpiRow("ac-inv",    "invariants (SW / MV / BS)"));
  grid.appendChild(kpiRow("ac-label",  "honesty label"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Token Coherence arXiv:2603.15183 (Parakhin) \u00b7 Multi-Agent Memory / Comp-Arch arXiv:2603.10062 (Yu et al.) \u00b7 Governed Shared Memory arXiv:2606.24535. MODELED \u00b7 not claimed-as.";
  card.appendChild(fn);
  _overlay.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  _overlay.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "ac-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  _overlay.appendChild(pd);

  // Fold the legacy panel into the shared showcase overlay (surfaces/_showcase.js):
  // title + live badge + doctrine legend live in the always-visible chrome; the
  // descriptive text + KPI card become the collapsible body so the 3D scene is the star.
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    legend: true,
  });
  _overlay.style.position = "static";
  _overlay.style.left = _overlay.style.top = "auto";
  _overlay.style.maxWidth = "none";
  _overlay.style.font = "inherit";
  if (_overlay.firstChild) _overlay.removeChild(_overlay.firstChild); // drop duplicate title
  _show.body.appendChild(_overlay);
  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const nc = (S.naive && typeof S.naive.cost === "number") ? String(S.naive.cost) : "loading\u2026";
  const mc = (S.mesi && typeof S.mesi.cost === "number") ? String(S.mesi.cost) : "loading\u2026";
  let save = "loading\u2026";
  if (S.naive && S.mesi && S.naive.cost) {
    save = (100 * (1 - S.mesi.cost / S.naive.cost)).toFixed(0) + "%";
  }
  const allHold = S.invariants ? (S.invariants.all_hold ? "all HOLD" : "one FAILS (see BS)") : "loading\u2026";
  pd.innerHTML =
    "<b>What this means:</b> When several AI agents share the same working memory, the " +
    "naive fix is to re-send the entire shared state to everyone on every change \u2014 " +
    "expensive and slow (here it costs <b>" + nc + "</b> proxy units on this trace). " +
    "Borrowing a 40-year-old trick from computer CPUs (the <b>MESI cache-coherence " +
    "protocol</b>), we instead send tiny \u201cyour copy is stale\u201d notices and only re-fetch " +
    "the full data when an agent actually reads it \u2014 dropping the cost to <b>" + mc + "</b> " +
    "(about <b>" + save + "</b> cheaper) while still guaranteeing only one agent writes at a " +
    "time, versions never go backwards, and reads are never too stale (" + allHold + "). " +
    "The <b>mesi_buggy</b> mode deliberately skips one \u201cstale\u201d notice so you can watch a " +
    "guarantee break. " +
    "<br><br><b>Honesty (MODELED):</b> Inspired-not-real. This is a toy deterministic " +
    "simulation of the MESI\u2192artifact coherence MECHANISM, not the paper\u2019s Artifact " +
    "Coherence System. \u201cArtifacts\u201d are integer-versioned dict entries over 3\u20134 items and " +
    "a handful of agents; \u201ccost\u201d is a counted token/byte proxy, not measured LLM tokens; " +
    "invariants are checked by in-sim assertions, NOT the paper\u2019s TLA+ model checker (no " +
    "~2,400-state exploration); there is no LangGraph/CrewAI/AutoGen integration. It " +
    "demonstrates WHY lazy invalidation beats full-state rebroadcast while preserving " +
    "single-writer safety, monotonic versioning and bounded staleness on a constructed " +
    "trace; it does NOT reproduce Token Coherence\u2019s 84\u201395% measured savings or prove the " +
    "Token Coherence Theorem. <b>NEW AXIS:</b> this is a distributed-consistency protocol " +
    "(\u2260 graphmem retrieval, \u2260 single-agent memory organs, \u2260 governance policy).";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _invLetter(x) {
  if (!x || !x.status) return "\u2014";
  return x.status === "PASS" ? "\u2713" : "\u2717";
}

function _paintOverlay() {
  const t = _tok(S.state);
  _set("ac-mode",  t || (S.mode || "\u2014"));
  _set("ac-naive", t || (S.naive && typeof S.naive.cost === "number" ? String(S.naive.cost) : "\u2014"));
  _set("ac-mesi",  t || (S.mesi && typeof S.mesi.cost === "number" ? String(S.mesi.cost) : "\u2014"));
  let save = "\u2014";
  if (S.naive && S.mesi && S.naive.cost) {
    save = (100 * (1 - S.mesi.cost / S.naive.cost)).toFixed(1) + "%";
  }
  _set("ac-save",  t || save);
  let inv = "\u2014";
  if (S.invariants) {
    inv = _invLetter(S.invariants.single_writer) + " " +
          _invLetter(S.invariants.monotonic_versioning) + " " +
          _invLetter(S.invariants.bounded_staleness);
  }
  _set("ac-inv",   t || inv);
  // honesty label verbatim — never upgraded
  _set("ac-label", t || (S.label || "MODELED"));
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
  _group = _overlay = _show = null;
  _cells = []; _flash = []; _links = null;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.timeline = S.naive = S.mesi = S.invariants = null;
  S.costCurve = S.invEvents = S.mode = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
