// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainconsensus.js — BRAIN CONSENSUS · honest corroboration of a brain grounding.
// Complements the grounding / uncertainty surfaces: this is about HOW MANY independent nodes
// support a claim and HOW BROADLY they agree — distinguishing a well-corroborated claim from a
// single-source one. NOT a truth guarantee.
//
// TWO measure PILLARS (distinct supporting nodes, distinct communities spanned), each height by
// its breadth in [0,1], stand under a VERDICT plate that reads CORROBORATED / WEAK-CORROBORATION
// / SINGLE-SOURCE. A single spine gauges the combined corroboration. HONEST BY CONSTRUCTION:
// every value is read from the same-origin feed, derived live from the honest brain grounding
// (szl_brain_api) — never a hand-authored number.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/consensus?q=&k= (PURE READ, mints nothing):
//   ok, label (MODELED), query, k, support_nodes_retrieved, verdict, single_source_risk,
//   corroboration, measures{ distinct_support_nodes, distinct_communities, node_breadth,
//   community_breadth, community_concentration }, doctrine{ lambda, locked_proven, trust_ceiling }.
//
// HONESTY LABEL: MODELED — a deterministic, explainable measure of how broadly the grounding is
//   distributed across the honest graph. CORROBORATION HONESTY, NOT A TRUTH GUARANTEE: it is NOT
//   P(claim true). The verdict is NEVER CORROBORATED when the single-source-risk flag is set.
//   Λ = Conjecture 1, never a theorem. Trust ceiling 0.97, never 100%. No green "verified" state.
// COLOURS (approved hues ONLY): proof-teal 0x3af4c8 (CORROBORATED), lattice-blue 0x5b8dee
//   (WEAK-CORROBORATION / frame), violet-blue 0x8a6bff (SINGLE-SOURCE / risk), greys (grid/idle).
//   No green, no red, no amber.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: reads only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22};
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "brainconsensus";
const TITLE = "Brain Consensus · honest corroboration of a brain grounding (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ consensus endpoint.
// A representative demo query drives the live gauge; the number shown is whatever the honest
// grounding yields for it (never a curated result).
const DEMO_Q = "estate thesis";
const DEMO_K = 12;
const EP = `/api/a11oy/v1/brain/consensus?q=${encodeURIComponent(DEMO_Q)}&k=${DEMO_K}`;

// verdict hues — approved palette only, no green/red/amber
const C_CORROB  = 0x3af4c8;  // proof-teal   — CORROBORATED
const C_WEAK    = 0x5b8dee;  // lattice-blue — WEAK-CORROBORATION / frame
const C_SINGLE  = 0x8a6bff;  // violet-blue  — SINGLE-SOURCE / risk
const C_NEUTRAL = 0x42505d;  // grey         — idle / no data
const C_GRID    = 0x1b3a44;  // floor colour

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "CORROBORATED")       return C_CORROB;
  if (s === "SINGLE-SOURCE")      return C_SINGLE;
  if (s === "WEAK-CORROBORATION") return C_WEAK;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _plate = null;            // THREE.Mesh — the verdict plate
let _spine = null;            // THREE.Mesh — combined-corroboration gauge
let _pillars = [];            // Array<{ mesh, name, u }>

// live state (all read from JSON; nothing invented)
const S = {
  label:   null,   // MODELED (verbatim)
  query:   null,
  k:       null,
  n:       null,   // support_nodes_retrieved
  corr:    null,   // combined corroboration [0,1]
  verdict: null,   // CORROBORATED | WEAK-CORROBORATION | SINGLE-SOURCE
  risk:    null,   // single_source_risk
  nodes:   null,   // distinct_support_nodes
  comms:   null,   // distinct_communities
  nodeB:   null,   // node_breadth [0,1]
  commB:   null,   // community_breadth [0,1]
  conc:    null,   // community_concentration
  trustCeil: null,
  lambda:  null,
  locked:  null,
  state:   "init",
};

// Fixed pillar layout — one per honest breadth measure (always the same 2, never padded).
const PILLARS = [
  { name: "node_breadth",      label: "node breadth" },
  { name: "community_breadth", label: "community breadth" },
];

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.2, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildPlate();
  _buildSpine();
  _buildPillars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintScene(); },
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

function _buildPlate() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(6.6, 1.15, 0.6);
  _plate = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.32,
    transparent: true, opacity: 0.9,
  }));
  _plate.position.set(0, 6.4, 0);
  _group.add(_plate);

  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-6, 5.6, 0), new THREE.Vector3(6, 5.6, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_WEAK, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// A central spine whose lit height gauges the COMBINED corroboration (0 floor .. 1 full).
function _buildSpine() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(0.5, 5.0, 0.5);
  _spine = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_WEAK, emissive: C_WEAK, emissiveIntensity: 0.3,
    transparent: true, opacity: 0.55,
  }));
  _spine.position.set(0, 2.5, -2.2);
  _group.add(_spine);
}

// Pillars, one per honest breadth measure; height by that measure's breadth [0,1].
function _buildPillars() {
  const THREE = _THREE;
  const n = PILLARS.length;
  const totalW = 6.4;
  const step = totalW / n;
  const startX = -totalW / 2 + step / 2;
  const geo = new THREE.BoxGeometry(1.6, 1.0, 1.1);

  for (let i = 0; i < n; i++) {
    const x = startX + step * i;
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: C_WEAK, emissive: C_WEAK, emissiveIntensity: 0.26,
      transparent: true, opacity: 0.9,
    }));
    mesh.scale.y = 0.4;
    mesh.position.set(x, 0.2, 0);
    _group.add(mesh);
    _pillars.push({ mesh, name: PILLARS[i].name, u: 0 });
  }
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.query   = j && j.query != null ? String(j.query) : null;
  S.k       = j && typeof j.k === "number" ? j.k : null;
  S.n       = j && typeof j.support_nodes_retrieved === "number" ? j.support_nodes_retrieved : null;
  S.corr    = j && typeof j.corroboration === "number" ? j.corroboration : null;
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.risk    = j && typeof j.single_source_risk === "boolean" ? j.single_source_risk : null;

  const m = (j && j.measures) || {};
  const num = (name) => (typeof m[name] === "number") ? m[name] : null;
  S.nodes = num("distinct_support_nodes");
  S.comms = num("distinct_communities");
  S.nodeB = num("node_breadth");
  S.commB = num("community_breadth");
  S.conc  = num("community_concentration");

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _paintScene();
  _paintOverlay();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.07;
  const live = S.state === "live";
  if (_plate) {
    _plate.material.emissiveIntensity = 0.32 + (live ? 0.22 : 0.06) * (0.5 + 0.5 * Math.sin(t * 0.003));
  }
  for (let i = 0; i < _pillars.length; i++) {
    const p = _pillars[i];
    p.mesh.material.emissiveIntensity = (live ? 0.28 : 0.1) + (live ? 0.18 : 0.0) * (0.5 + 0.5 * Math.sin(t * 0.002 + i));
    p.mesh.material.opacity = live ? 0.92 : 0.4;
  }
}

// =============================================================================
function _paintScene() {
  const live = S.state === "live";
  const col = _verdictColor(live ? S.verdict : null);
  if (_plate) { _plate.material.color.setHex(col); _plate.material.emissive.setHex(col); }

  if (_spine) {
    const u = (live && typeof S.corr === "number") ? S.corr : 0;
    const h = 0.3 + u * 4.7;                  // gauge height by combined corroboration
    _spine.scale.y = h / 5.0;
    _spine.position.y = h / 2;
    _spine.material.color.setHex(col);
    _spine.material.emissive.setHex(col);
  }

  const vals = { node_breadth: S.nodeB, community_breadth: S.commB };
  for (const p of _pillars) {
    const u = (live && typeof vals[p.name] === "number") ? vals[p.name] : 0;
    p.u = u;
    const h = 0.4 + u * 4.4;                  // height by breadth measure
    p.mesh.scale.y = h;
    p.mesh.position.y = h / 2;
    // broad breadth glows in the corroborated hue; low breadth stays in the frame hue.
    const pcol = !live ? C_NEUTRAL : (u >= 0.5 ? C_CORROB : C_WEAK);
    p.mesh.material.color.setHex(pcol);
    p.mesh.material.emissive.setHex(pcol);
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "corroboration", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'Honest <b>corroboration</b> of a brain grounding. It reads the same real grounding subgraph ' +
    'the brain already serves and measures <b>how many distinct nodes</b> support the query and ' +
    '<b>how many distinct communities</b> they span — because cross-community agreement is ' +
    'stronger than a single clique restating itself — into a verdict: <b>CORROBORATED / ' +
    'WEAK-CORROBORATION / SINGLE-SOURCE</b>. A <b>single-source-risk</b> flag fires when support ' +
    'collapses to one node or one community, and the verdict is <b>never CORROBORATED</b> while ' +
    'that flag is set. This is <b>corroboration honesty, not a truth guarantee</b> — Λ = ' +
    'Conjecture 1, advisory. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bc-verdict", "verdict"));
  grid.appendChild(kpiRow("bc-corr",    "corroboration [0,1]"));
  grid.appendChild(kpiRow("bc-risk",    "single-source risk"));
  grid.appendChild(kpiRow("bc-query",   "query"));
  grid.appendChild(kpiRow("bc-n",       "support nodes"));
  grid.appendChild(kpiRow("bc-nodes",   "· distinct nodes"));
  grid.appendChild(kpiRow("bc-comms",   "· distinct communities"));
  grid.appendChild(kpiRow("bc-nodeB",   "· node breadth"));
  grid.appendChild(kpiRow("bc-commB",   "· community breadth"));
  grid.appendChild(kpiRow("bc-conc",    "· community concentration"));
  grid.appendChild(kpiRow("bc-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bc-trust",   "trust ceiling"));
  grid.appendChild(kpiRow("bc-lambda",  "Λ"));
  card.appendChild(grid);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> CORROBORATED &nbsp; ' +
    '<span style="color:#5b8dee">■</span> WEAK-CORROBORATION &nbsp; ' +
    '<span style="color:#8a6bff">■</span> SINGLE-SOURCE (risk). ' +
    'MODELED · corroboration honesty, not a truth guarantee · never CORROBORATED while single-source-risk set.';
  card.appendChild(leg);
  host.appendChild(card);

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
  pd.id = "bc-plain";
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
    "<b>What this means:</b> an honest read on <b>how many independent sources</b> back what the " +
    "brain just retrieved. If several distinct nodes from several distinct topic clusters support " +
    "the query, the claim is <b>CORROBORATED</b>. If the support is broad but all sits in one " +
    "cluster, it is <b>WEAK-CORROBORATION</b> — the sources may just be echoing one another. If it " +
    "all rests on a single node, it is <b>SINGLE-SOURCE</b>, and the panel openly flags the risk. " +
    "It can <b>never</b> read CORROBORATED while support collapses to one node or one cluster. This " +
    "measures the <b>breadth of support</b> — it is <b>not</b> a promise the claim is true.";
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
function _f(v) { return typeof v === "number" ? v.toFixed(3) : "—"; }

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "corroboration" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bc-verdict", vrd);
  _set("bc-corr",    t || _f(S.corr));
  _set("bc-risk",    t || (S.risk == null ? "—" : (S.risk ? "YES — single source" : "no")));
  _set("bc-query",   t || (S.query != null ? (S.query || "(empty)") : "—"));
  _set("bc-n",       t || _n(S.n));
  _set("bc-nodes",   t || _n(S.nodes));
  _set("bc-comms",   t || _n(S.comms));
  _set("bc-nodeB",   t || _f(S.nodeB));
  _set("bc-commB",   t || _f(S.commB));
  _set("bc-conc",    t || _f(S.conc));
  _set("bc-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bc-trust",   t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bc-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

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
          ms.forEach((mm) => { if (mm.dispose) mm.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _plate = _spine = null; _pillars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.query = S.verdict = null;
  S.k = S.n = S.corr = S.risk = S.nodes = S.comms = null;
  S.nodeB = S.commB = S.conc = null;
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
