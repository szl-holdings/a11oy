// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainagent.js — BRAIN AGENT · an honesty-gated agentic graph reasoner. It renders the
// bounded, deterministic WALK the brain takes over its own knowledge graph for a query: an ordered
// PATH of hop-beads (one per traversal step) plus a CORE orb carrying the overall verdict. Each hop
// is coloured by its action/outcome read VERBATIM from the feed — an EXPAND (accepted evidence)
// reads teal, a BACKTRACK (the honesty gate refused an ungrounded/contradicted/untraceable/uncertain
// hop) reads violet, a STOP reads grey/blue. No hop is ever recoloured to look accepted when the
// gate refused it. Pure knowledge-graph reasoning honesty; it advances NO detection / fusion /
// effector / targeting / cueing capability, and makes NO sentience claim.
//
// The CORE is teal only for ANSWER-GROUNDED; PARTIAL and the two ABSTAINED verdicts never read as a
// grounded answer. An absent sibling guard shows as UNAVAILABLE in the HUD, never a fabricated pass.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/agent (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, modeled_confidence, seeds[], cited_node_ids[],
//   trace[]{ step, node, action (EXPAND|FOLLOW|BACKTRACK|STOP), accepted, reason, score },
//   budget{ max_steps, max_nodes, steps_used, nodes_visited, min_evidence_required },
//   summary{ seeds, nodes_visited, accepted, rejected, stop_reason },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// HONESTY LABEL: MODELED — this surface reasons over MODELED retrieval; it is not a MEASURED answer.
//   The per-hop actions it renders are read VERBATIM; no accept is fabricated. No green "1.0 /
//   VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (ANSWER-GROUNDED / EXPAND-accepted),
//   lattice-blue 0x5b8dee (PARTIAL / STOP / frame), violet-blue 0x8a6bff (ABSTAINED / BACKTRACK),
//   grey 0x42505d (UNAVAILABLE / init). No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainagent";
const TITLE = "Brain Agent · honesty-gated agentic graph reasoner (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ traversal endpoint.
const EP = "/api/a11oy/v1/brain/agent?max_steps=24&max_nodes=16";

// verdict / action hues — approved palette only, no green
const C_OK      = 0x3af4c8;  // proof-teal   — ANSWER-GROUNDED / EXPAND-accepted
const C_MID     = 0x5b8dee;  // lattice-blue — PARTIAL / STOP / frame
const C_ABST    = 0x8a6bff;  // violet-blue  — ABSTAINED / BACKTRACK
const C_NEUTRAL = 0x42505d;  // grey         — UNAVAILABLE / init
const C_GRID    = 0x1b3a44;  // floor colour

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "ANSWER-GROUNDED") return C_OK;
  if (s === "PARTIAL")         return C_MID;
  if (s === "ABSTAINED-BUDGET" || s === "ABSTAINED-INSUFFICIENT") return C_ABST;
  return C_NEUTRAL;
}
// per-hop action -> bead colour (VERBATIM; a refused hop is never recoloured to look accepted)
function _hopColor(action, accepted) {
  const a = String(action || "").toUpperCase();
  if (a === "EXPAND" && accepted) return C_OK;
  if (a === "BACKTRACK")          return C_ABST;
  if (a === "STOP")               return C_MID;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the verdict core orb
let _beads = [];              // Array<{ mesh, action, accepted }>
let _spin = 0;

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,
  verdict:    null,
  confidence: null,
  seeds:      null,
  cited:      null,
  visited:    null,
  accepted:   null,
  rejected:   null,
  stepsUsed:  null,
  maxSteps:   null,
  nodesVisited: null,
  maxNodes:   null,
  minReq:     null,
  stopReason: null,
  trust:      null,
  lambda:     null,
  locked:     null,
  hops:       [],   // [{ action, accepted }]
  state:      "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 5.2, 19);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.4, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintCore(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildCore() {
  const THREE = _THREE;
  const g = new THREE.IcosahedronGeometry(1.4, 1);
  _core = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.35,
    transparent: true, opacity: 0.9, flatShading: true,
  }));
  _core.position.set(0, 5.4, 0);
  _group.add(_core);

  // lattice ring beneath the core (the traversal base rail)
  const pts = [];
  const R = 6.2;
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * R, 0.02, Math.sin(a) * R));
  }
  const rg = new THREE.BufferGeometry().setFromPoints(pts);
  const ring = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_MID, transparent: true, opacity: 0.4,
  }));
  _group.add(ring);
}

// Build (or rebuild) one BEAD per trace hop, along an ascending spiral (the ordered walk); colour
// by the VERBATIM per-hop action/outcome. A connecting line traces the path the reasoner took.
function _buildBeads() {
  const THREE = _THREE;
  _disposeBeads();

  const hops = Array.isArray(S.hops) ? S.hops : [];
  const n = hops.length;
  if (!n) return;

  const geo = new THREE.SphereGeometry(0.34, 16, 16);
  const R = 4.6;
  const path = [];
  for (let i = 0; i < n; i++) {
    const hop = hops[i];
    const color = _hopColor(hop.action, hop.accepted);
    const a = (i / Math.max(1, n)) * Math.PI * 2 * 1.4;   // >1 turn so order reads as a spiral
    const y = 0.6 + (i / Math.max(1, n)) * 4.2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.3,
      transparent: true, opacity: hop.action === "BACKTRACK" ? 0.6 : 0.95,
    }));
    mesh.position.set(x, y, z);
    _group.add(mesh);
    path.push(new THREE.Vector3(x, y, z));
    _beads.push({ mesh, action: hop.action, accepted: hop.accepted });
  }

  if (path.length >= 2) {
    const pg = new THREE.BufferGeometry().setFromPoints(path);
    const line = new THREE.Line(pg, new THREE.LineBasicMaterial({
      color: C_MID, transparent: true, opacity: 0.35,
    }));
    _group.add(line);
    _beads.push({ mesh: line, action: "PATH", accepted: false });
  }
}

function _disposeBeads() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _beads.forEach((b) => rm(b.mesh));
  _beads = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade, never fabricate an accept
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.confidence = (j && typeof j.modeled_confidence === "number") ? j.modeled_confidence : null;
  S.seeds = Array.isArray(j && j.seeds) ? j.seeds.length : null;
  S.cited = Array.isArray(j && j.cited_node_ids) ? j.cited_node_ids.length : null;

  const b = (j && j.budget) || {};
  S.stepsUsed = typeof b.steps_used === "number" ? b.steps_used : null;
  S.maxSteps  = typeof b.max_steps === "number" ? b.max_steps : null;
  S.nodesVisited = typeof b.nodes_visited === "number" ? b.nodes_visited : null;
  S.maxNodes  = typeof b.max_nodes === "number" ? b.max_nodes : null;
  S.minReq    = typeof b.min_evidence_required === "number" ? b.min_evidence_required : null;

  const sm = (j && j.summary) || {};
  S.visited  = typeof sm.nodes_visited === "number" ? sm.nodes_visited : S.nodesVisited;
  S.accepted = typeof sm.accepted === "number" ? sm.accepted : null;
  S.rejected = typeof sm.rejected === "number" ? sm.rejected : null;
  S.stopReason = typeof sm.stop_reason === "string" ? sm.stop_reason : null;

  const trace = Array.isArray(j && j.trace) ? j.trace : [];
  S.hops = trace.map((h) => ({
    action: h && h.action ? String(h.action).toUpperCase() : "STOP",
    accepted: !!(h && h.accepted),
  }));

  const d = (j && j.doctrine) || {};
  S.trust  = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda = typeof d.lambda === "string" ? d.lambda : null;
  S.locked = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildBeads();
  _paintCore();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.08;

  const live = S.state === "live";
  if (_core) {
    _core.rotation.y += 0.004; _core.rotation.x += 0.0015;
    const pulse = 0.35 + (live ? 0.25 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _core.material.emissiveIntensity = pulse;
  }
  if (_beads.length) {
    _spin = (t * 0.00025) % 1;
    const walk = _beads.filter((b) => b.action !== "PATH");
    const lead = Math.floor(_spin * Math.max(1, walk.length));
    for (let i = 0; i < walk.length; i++) {
      const b = walk[i];
      const near = i === lead;
      // a BACKTRACK bead never glows as though accepted; accepted EXPAND beads follow the sweep.
      const back = b.action === "BACKTRACK";
      const base = back ? 0.18 : (b.accepted && live ? 0.3 : 0.12);
      if (b.mesh.material) b.mesh.material.emissiveIntensity = (near && live && !back) ? Math.max(base, 0.85) : base;
    }
  }
}

// =============================================================================
function _paintCore() {
  if (!_core) return;
  const col = (S.state === "live") ? _verdictColor(S.verdict) : C_NEUTRAL;
  _core.material.color.setHex(col);
  _core.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "reasoning", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A bounded, deterministic <b>agentic reasoner</b> that walks the brain’s own knowledge graph ' +
    'one node at a time to answer a query — choosing <b>EXPAND / FOLLOW / BACKTRACK / STOP</b> by ' +
    'pure graph heuristics (no model call). Every candidate hop passes an <b>honesty gate</b> built ' +
    'from the sibling brain-honesty surfaces (grounding, provenance, contradiction, uncertainty): ' +
    'an ungrounded, untraceable, contradicted, or too-uncertain hop is <b>refused</b> and the reason ' +
    'recorded; an absent guard reads <b>UNAVAILABLE</b>, never a fabricated pass. Within an explicit ' +
    '<b>budget</b> it either assembles a grounded evidence set or <b>abstains</b> ' +
    '(ABSTAINED-BUDGET / ABSTAINED-INSUFFICIENT) rather than answer under-grounded. Strictly ' +
    'knowledge-graph reasoning honesty; no sentience claim. 0 runtime CDN.';
  host.appendChild(sub);

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
  grid.appendChild(kpiRow("ba-verdict",  "verdict"));
  grid.appendChild(kpiRow("ba-conf",     "modeled confidence"));
  grid.appendChild(kpiRow("ba-seeds",    "seeds"));
  grid.appendChild(kpiRow("ba-cited",    "grounded (cited)"));
  grid.appendChild(kpiRow("ba-visited",  "nodes visited / budget"));
  grid.appendChild(kpiRow("ba-steps",    "steps used / budget"));
  grid.appendChild(kpiRow("ba-rejected", "gate-rejected hops"));
  grid.appendChild(kpiRow("ba-stop",     "stop reason"));
  grid.appendChild(kpiRow("ba-locked",   "locked proofs"));
  grid.appendChild(kpiRow("ba-lambda",   "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> ANSWER-GROUNDED / EXPAND &nbsp; ' +
    '<span style="color:#5b8dee">■</span> PARTIAL / STOP &nbsp; ' +
    '<span style="color:#8a6bff">■</span> ABSTAINED / BACKTRACK &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNAVAILABLE. ' +
    'MODELED · hop actions read verbatim · a refused hop is never recoloured as accepted.';
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
  pd.id = "ba-plain";
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
    "<b>What this means:</b> ask the brain a question and it doesn’t just look things up — it " +
    "<b>reasons across its own knowledge map</b>, stepping from one fact to the next. Before it " +
    "trusts any step it runs an <b>honest check</b>: is this fact actually grounded, traceable to a " +
    "source, free of contradictions, and not too shaky? If a step fails the check it <b>backs off</b> " +
    "and tries another route instead of pretending. It works within a fixed <b>budget</b> of steps, " +
    "and if it can’t reach a well-supported answer in time it <b>says so</b> — it abstains rather " +
    "than making something up. It is not conscious and makes no such claim; confidence is capped at " +
    "0.97, never 100%.";
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

function _paintOverlay() {
  const t = _tok(S.state);
  const headline = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "reasoning" });
    _show.setChip("vrd", headline, { text: "verdict" });
  }
  _set("ba-verdict", t || (S.verdict || "—"));
  _set("ba-conf",    t || (S.confidence != null ? String(S.confidence) : "—"));
  _set("ba-seeds",   t || _n(S.seeds));
  _set("ba-cited",   t || _n(S.cited));
  _set("ba-visited", t || (S.visited != null && S.maxNodes != null
    ? S.visited + " / " + S.maxNodes : _n(S.visited)));
  _set("ba-steps",   t || (S.stepsUsed != null && S.maxSteps != null
    ? S.stepsUsed + " / " + S.maxSteps : _n(S.stepsUsed)));
  _set("ba-rejected", t || _n(S.rejected));
  _set("ba-stop",    t || (S.stopReason || "—"));
  _set("ba-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("ba-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeBeads();
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
  _core = null; _beads = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.confidence = null;
  S.seeds = S.cited = S.visited = S.accepted = S.rejected = null;
  S.stepsUsed = S.maxSteps = S.nodesVisited = S.maxNodes = S.minReq = null;
  S.stopReason = S.trust = S.lambda = S.locked = null;
  S.hops = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
