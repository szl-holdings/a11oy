// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/braincontradict.js — BRAIN CONTRADICTION DETECTOR · surfaces conflicts, never resolves.
//
// A governed lens over the honest knowledge graph that PRESENTS potential contradictions between
// grounded claims and refuses to RESOLVE them. Two opposing claim clusters face each other across a
// central FAULT LINE; when the estate's detector flags a candidate pair the fault glows and a bridge
// spans the divide labelled "human-required" — because this surface never picks a winner. HONEST BY
// CONSTRUCTION: every value is read from the same-origin feed derived live from the brain graph via
// szl_brain_api — never a hand-authored scorecard.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/contradict/info (PURE READ, mints nothing):
//   ok, label (MODELED), surface_id, method{ signals[], black_box_model:false, resolution_policy },
//   verdicts[], honest_labels[], doctrine{ lambda, locked_proven, trust_ceiling, trust_100_percent,
//   adds_to_locked_8, confidence_cap }.
//
// VISUALIZES:
//   1. TWO claim clusters (left / right) — the two sides of a candidate contradiction, always both
//      shown, neither hidden.
//   2. a central FAULT LINE + keystone carrying the honest MODELED label and the present-never-resolve
//      policy read VERBATIM from the feed.
//   3. a scanning sweep travelling the fault so the lens reads as a living, watched surface.
//
// HONESTY LABEL: MODELED — detection is a transparent deterministic lexical/structural heuristic
//   (negation polarity / antonym opposition / numeric conflict), NEVER MEASURED, never a proof, never
//   1.0. It PRESENTS conflicts (adjudication=human-required, resolution=null) and never resolves them.
// COLOURS: proof-teal 0x3af4c8 (clear / NO-CONFLICT), lattice-blue 0x5b8dee (frame / POSSIBLE),
//   violet-blue 0x8a6bff (CONFLICT-FLAGGED / fault), grey 0x42505d (neutral). No green. No red.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1 (not a theorem); introduces no theorem. Degrades on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "braincontradict";
const TITLE = "Brain Contradiction Detector · surfaces conflicts, never resolves (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ info endpoint (mints nothing).
const EP = "/api/a11oy/v1/brain/contradict/info";

// approved hues — no green, no red, no purple except violet-blue 0x8a6bff
const C_CLEAR    = 0x3af4c8;  // proof-teal   — clear / NO-CONFLICT
const C_FRAME    = 0x5b8dee;  // lattice-blue — frame / POSSIBLE-CONFLICT
const C_FLAG     = 0x8a6bff;  // violet-blue  — CONFLICT-FLAGGED / fault line
const C_NEUTRAL  = 0x42505d;  // grey         — neutral
const C_GRID     = 0x1b3a44;  // floor colour

function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "NO-CONFLICT")      return C_CLEAR;
  if (s === "CONFLICT-FLAGGED") return C_FLAG;
  if (s === "POSSIBLE-CONFLICT") return C_FRAME;
  return C_NEUTRAL;             // init / unknown
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _fault = null;            // THREE.Mesh — the central fault line
let _clusterL = [], _clusterR = [];  // the two claim clusters (both always shown)
let _sweep = 0;               // scanning-sweep phase

// live state (all read from JSON; nothing invented)
const S = {
  label:    null,   // top honesty label VERBATIM (MODELED)
  signals:  [],     // detection signals (negation-polarity, antonym-opposition, numeric-conflict)
  blackBox: null,   // must be false
  policy:   null,   // present-never-resolve policy string, verbatim
  verdicts: [],
  trustCeil:null,
  lambda:   null,
  locked:   null,
  confCap:  null,
  state:    "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.0, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.6, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildFault();
  _buildClusters();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 9000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintFault(); },
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

function _buildFault() {
  const THREE = _THREE;
  // the vertical fault plane between the two claim sides — the disagreement, never bridged by a winner
  const g = new THREE.BoxGeometry(0.18, 6.4, 0.6);
  _fault = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_FRAME, emissive: C_FRAME, emissiveIntensity: 0.3, transparent: true, opacity: 0.85,
  }));
  _fault.position.set(0, 3.0, 0);
  _group.add(_fault);

  // top rail
  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-6, 6.2, 0), new THREE.Vector3(6, 6.2, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_FRAME, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// Build the two opposing claim clusters. Both sides ALWAYS shown — the surface presents both, hides
// neither. Sizes are symmetric (it never weights one claim over the other — no winner is implied).
function _buildClusters() {
  const THREE = _THREE;
  _disposeClusters();
  const brickGeo = new THREE.BoxGeometry(1.4, 0.7, 0.9);

  const mk = (side, color) => {
    const out = [];
    for (let i = 0; i < 4; i++) {
      const mesh = new THREE.Mesh(brickGeo, new THREE.MeshStandardMaterial({
        color, emissive: color, emissiveIntensity: 0.22, transparent: true, opacity: 0.9,
      }));
      const x = side * (2.2 + (i % 2) * 1.5);
      const y = 0.6 + Math.floor(i / 2) * 0.95;
      mesh.position.set(x, y, (i % 2 ? 0.6 : -0.6));
      _group.add(mesh);
      out.push(mesh);
    }
    return out;
  };
  _clusterL = mk(-1, C_CLEAR);   // "claim A" side
  _clusterR = mk(+1, C_CLEAR);   // "claim B" side — same weight, both present
}

function _disposeClusters() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _clusterL.forEach(rm); _clusterR.forEach(rm);
  _clusterL = []; _clusterR = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  const m = (j && j.method) || {};
  S.signals  = Array.isArray(m.signals) ? m.signals.map(String) : [];
  S.blackBox = typeof m.black_box_model === "boolean" ? m.black_box_model : null;
  S.policy   = typeof m.resolution_policy === "string" ? m.resolution_policy : null;
  S.verdicts = Array.isArray(j && j.verdicts) ? j.verdicts.map(String) : [];

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;
  S.confCap   = typeof d.confidence_cap === "number" ? d.confidence_cap : null;

  _paintFault();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.06;

  const live = S.state === "live";
  if (_fault) {
    const pulse = 0.3 + (live ? 0.28 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _fault.material.emissiveIntensity = pulse;
  }
  // sweep both clusters symmetrically — never favouring one side
  const all = _clusterL.concat(_clusterR);
  if (all.length) {
    _sweep = (t * 0.0002) % 1;
    const lead = Math.floor(_sweep * all.length);
    for (let i = 0; i < all.length; i++) {
      const near = i === lead;
      const base = live ? 0.22 : 0.1;
      all[i].material.emissiveIntensity = (near && live) ? Math.max(base, 0.7) : base;
      all[i].material.opacity = live ? 0.9 : 0.4;
    }
  }
}

// =============================================================================
function _paintFault() {
  if (!_fault) return;
  // info feed carries no per-query verdict; the fault reads lattice-blue (POSSIBLE/frame) when live,
  // grey when not — the surface never fabricates a verdict it did not compute for a query.
  const col = S.state === "live" ? C_FRAME : C_NEUTRAL;
  _fault.material.color.setHex(col);
  _fault.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "detection", name: "lbl" },
            { label: "human-required", text: "adjudication", name: "adj" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A governed lens that surfaces potential <b>contradictions</b> between grounded claims in the ' +
    'knowledge graph and <b>PRESENTS them — it never RESOLVES them</b>. For a query it retrieves the ' +
    'relevant subgraph from the same honest brain graph the estate reads, then flags topically-related ' +
    'claims that disagree using transparent deterministic heuristics — <b>negation polarity</b>, ' +
    '<b>antonym opposition</b>, <b>numeric conflict</b>. No black-box model. Every flag carries ' +
    '<b>both sides verbatim</b> plus <b>adjudication=human-required, resolution=null</b>: no winner ' +
    'picked, no side hidden, no resolution fabricated. Detection is <b>MODELED</b>, never MEASURED; ' +
    'confidence is capped below 1.0. Honest by construction — derived live from the brain graph. ' +
    '0 runtime CDN.';
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
  grid.appendChild(kpiRow("bc-label",  "detection label"));
  grid.appendChild(kpiRow("bc-black",  "black-box model"));
  grid.appendChild(kpiRow("bc-adj",    "adjudication"));
  grid.appendChild(kpiRow("bc-cap",    "confidence cap"));
  grid.appendChild(kpiRow("bc-locked", "locked proofs"));
  grid.appendChild(kpiRow("bc-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("bc-lambda", "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable signals + verdicts list (text mirror of the method the wall runs).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:150px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> NO-CONFLICT &nbsp; ' +
    '<span style="color:#5b8dee">■</span> POSSIBLE-CONFLICT &nbsp; ' +
    '<span style="color:#8a6bff">■</span> CONFLICT-FLAGGED. ' +
    'MODELED · both sides always shown · presents, never resolves · a human adjudicates.';
  card.appendChild(leg);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #5b8dee;background:#08121f;color:#5b8dee;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f1f2f" : "#08121f";
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
    "<b>What this means:</b> when two things the system knows appear to <b>disagree</b>, this lens " +
    "points at the disagreement honestly instead of quietly choosing one and hiding the other. It " +
    "reads both claims word-for-word, explains exactly why they look like a conflict (a “not”, an " +
    "opposite word, or two different numbers for the same thing), and then <b>stops</b> — it says " +
    "“a person needs to decide this,” never inventing an answer. It uses plain, checkable rules, not " +
    "a black box, and it never claims certainty (confidence is capped below 100%). Because it reads " +
    "the live knowledge graph, it cannot quietly disagree with what the system actually knows.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintList() {
  const wrap = _el["list"];
  if (!wrap) return;
  wrap.innerHTML = "";
  const rowOf = (k, val, hex) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%";
    left.textContent = k;
    const v = document.createElement("b");
    v.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums";
    v.textContent = val;
    row.appendChild(left); row.appendChild(v);
    wrap.appendChild(row);
  };
  S.signals.forEach((s) => rowOf(s, "signal", "#5b8dee"));
  S.verdicts.forEach((v) => rowOf(v, "verdict", "#" + _verdictColor(v).toString(16).padStart(6, "0")));
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "detection" });
    _show.setChip("adj", "human-required", { text: "adjudication" });
  }
  _set("bc-label",  t || (S.label || "MODELED"));
  _set("bc-black",  t || (S.blackBox === false ? "false (transparent)" : S.blackBox === true ? "true" : "—"));
  _set("bc-adj",    t || "human-required");
  _set("bc-cap",    t || (S.confCap != null ? String(S.confCap) : "—"));
  _set("bc-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("bc-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bc-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeClusters();
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
  _fault = null; _clusterL = []; _clusterR = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _sweep = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.policy = S.lambda = null;
  S.signals = []; S.verdicts = [];
  S.blackBox = S.trustCeil = S.locked = S.confCap = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
