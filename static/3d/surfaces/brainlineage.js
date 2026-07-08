// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainlineage.js — NODE-ORIGIN LINEAGE. For a query's top knowledge-graph nodes
// this surface renders HOW each node ENTERED the graph: a set of vertical ORIGIN ROOTS, one
// per node, each COLOURED by its origin verdict read VERBATIM (TRACED / PARTIAL-LINEAGE /
// UNKNOWN-ORIGIN) and SIZED by how many real origin fields it carries. A KEYSTONE at the top
// carries the aggregate verdict. A node with no source field is shown grey as UNKNOWN-ORIGIN —
// never a fabricated source.
//
// This is NODE-ORIGIN lineage of a knowledge-graph node (where a fact came from). It is DISTINCT
// from brainprovenance (which nodes supported an ANSWER). It is NOT cryptographic model/weapon
// attestation, NOT SLSA/in-toto/Rekor build attestation, and NOT any counter-UAS capability.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/lineage?q=&k= (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, verdict_reason, query, lineages[{id,title,verdict,label,
//   origin,node_label,community,origin_field_count,has_explicit_source}], aggregate{traced,
//   partial_lineage,unknown_origin,fraction_traced,...}, doctrine{lambda,locked_proven,...}.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived re-read of the
//   brain's own node fields, not a measurement). Per-node origin verdicts are read VERBATIM and
//   NEVER upgraded (a STRUCTURAL-ONLY node is never shown TRACED; an UNKNOWN-ORIGIN node is never
//   given a source). The aggregate is NEVER TRACED while any node's origin is UNKNOWN.
//   Λ = Conjecture 1 → grey, never green/theorem. locked-proven = exactly 8. No green "1.0".
// COLOURS: proof-teal 0x3af4c8 (TRACED / explicit source), lattice-blue 0x5b8dee (PARTIAL-LINEAGE
//   / structural + root frame), violet-blue 0x8a6bff (community accents), greys (UNKNOWN-ORIGIN).
//   No green. 0 RUNTIME CDN — three.js via the page importmap (ctx.THREE).
// DOCTRINE v11: re-reads only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22};
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "brainlineage";
const TITLE = "Brain Lineage · node-origin chain (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ endpoint.
const DEFAULT_Q = "brain graph harvest";
const EP = "/api/a11oy/v1/brain/lineage?q=" + encodeURIComponent(DEFAULT_Q) + "&k=12";

// verdict / label hues — purple only the approved 0x8a6bff, no green
const C_TRACED  = 0x3af4c8;  // proof-teal   — TRACED (explicit cited source)
const C_PARTIAL = 0x5b8dee;  // lattice-blue — PARTIAL-LINEAGE (structural only)
const C_COMM    = 0x8a6bff;  // violet-blue  — community accent
const C_UNKNOWN = 0x5a6570;  // grey         — UNKNOWN-ORIGIN (never a source)
const C_FRAME   = 0x5b8dee;  // lattice-blue — root frame
const C_GRID    = 0x1b3a44;  // floor colour

// map a VERBATIM verdict -> a root colour (never upgraded)
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "TRACED")          return C_TRACED;
  if (s === "PARTIAL-LINEAGE") return C_PARTIAL;
  return C_UNKNOWN;                       // UNKNOWN-ORIGIN / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _keystone = null;         // THREE.Mesh — the aggregate-verdict keystone
let _roots = [];              // Array<{ mesh, verdict, fields }>

// live state (all read from JSON; nothing invented)
const S = {
  label:    null,   // top honesty label VERBATIM (MODELED)
  verdict:  null,   // TRACED | PARTIAL-LINEAGE | UNKNOWN-ORIGIN
  reason:   null,
  query:    null,
  lineages: [],
  agg:      {},
  lambda:   null,
  locked:   null,
  trustCeil:null,
  state:    "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 3.5, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildKeystone();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _paintKeystone(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(42, 42, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildKeystone() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(6.6, 1.2, 0.6);
  _keystone = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_UNKNOWN, emissive: C_UNKNOWN, emissiveIntensity: 0.32,
    transparent: true, opacity: 0.9,
  }));
  _keystone.position.set(0, 8.4, 0);
  _group.add(_keystone);

  // lattice frame beneath the keystone (the top rail the roots hang from)
  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-7, 7.7, 0), new THREE.Vector3(7, 7.7, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_FRAME, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// Build (or rebuild) the origin roots: one vertical root per node, spread left→right,
// colour = verbatim origin verdict, height/width = origin_field_count (how deep the origin
// chain is). Rebuilt on each snapshot so the roots always mirror the CURRENT nodes.
function _buildRoots() {
  const THREE = _THREE;
  _disposeRoots();

  const rows = Array.isArray(S.lineages) ? S.lineages : [];
  const n = rows.length;
  if (!n) return;

  const maxF = rows.reduce((m, e) => Math.max(m, (typeof e.origin_field_count === "number" ? e.origin_field_count : 1)), 1);
  const span = 13.0;
  const step = n > 1 ? span / (n - 1) : 0;
  const x0 = -span / 2;

  for (let i = 0; i < n; i++) {
    const e = rows[i];
    const color = _verdictColor(e.verdict);
    const fc = typeof e.origin_field_count === "number" ? e.origin_field_count : 1;
    const h = 1.4 + (fc / maxF) * 5.4;          // root depth by origin-field count
    const x = x0 + i * step;
    const y = 7.0 - h / 2;

    const geo = new THREE.BoxGeometry(0.72, h, 0.72);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.30, transparent: true, opacity: 0.92,
    }));
    mesh.position.set(x, y, 0);
    _group.add(mesh);

    // a community accent bead at the root tip (violet-blue), only when a community is set
    if (e.community !== null && e.community !== undefined && e.community !== "") {
      const bg = new THREE.SphereGeometry(0.16, 12, 12);
      const bead = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({
        color: C_COMM, emissive: C_COMM, emissiveIntensity: 0.4, transparent: true, opacity: 0.85,
      }));
      bead.position.set(x, y - h / 2 - 0.3, 0);
      _group.add(bead);
      _roots.push({ mesh: bead, verdict: e.verdict, fields: 0, accent: true });
    }

    _roots.push({ mesh, verdict: e.verdict, fields: fc });
  }
}

function _disposeRoots() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _roots.forEach((c) => rm(c.mesh));
  _roots = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label    = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict  = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.reason   = j && j.verdict_reason ? String(j.verdict_reason) : null;
  S.query    = j && j.query ? String(j.query) : null;
  S.lineages = (j && Array.isArray(j.lineages)) ? j.lineages : [];
  S.agg      = (j && j.aggregate && typeof j.aggregate === "object") ? j.aggregate : {};

  const d = (j && j.doctrine) || {};
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;

  _buildRoots();
  _paintKeystone();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.06;

  const live = S.state === "live";
  if (_keystone) {
    const pulse = 0.32 + (live ? 0.25 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _keystone.material.emissiveIntensity = pulse;
  }
  if (_roots.length) {
    const phase = (t * 0.0003) % 1;
    const lead = Math.floor(phase * _roots.length);
    for (let i = 0; i < _roots.length; i++) {
      const c = _roots[i];
      const near = Math.abs(i - lead) <= 0;
      const base = c.accent ? 0.4 : (live ? 0.30 : 0.12);
      c.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.8) : base;
      c.mesh.material.opacity = live ? 0.92 : 0.42;
    }
  }
}

// =============================================================================
function _paintKeystone() {
  if (!_keystone) return;
  const col = _verdictColor(S.state === "live" ? S.verdict : null);
  _keystone.material.color.setHex(col);
  _keystone.material.emissive.setHex(col);
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "lineage", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'For a query’s top knowledge-graph nodes, <b>how each node ENTERED the graph</b> — its ' +
    'harvest/origin metadata chain, read <b>VERBATIM</b> from the node’s own real fields. Each ' +
    'node gets an honest verdict: <b>TRACED</b> (explicit cited source) / <b>PARTIAL-LINEAGE</b> ' +
    '(structural only) / <b>UNKNOWN-ORIGIN</b> (no source field). A node with no source is shown ' +
    '<b>UNKNOWN — never a fabricated source</b>; the aggregate is <b>never TRACED while any origin ' +
    'is UNKNOWN</b>. This is <b>node-origin lineage</b> — NOT per-answer provenance, NOT ' +
    'build/model attestation, NOT counter-UAS. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bl-verdict", "aggregate verdict"));
  grid.appendChild(kpiRow("bl-nodes",   "nodes"));
  grid.appendChild(kpiRow("bl-traced",  "TRACED nodes"));
  grid.appendChild(kpiRow("bl-partial", "PARTIAL-LINEAGE nodes"));
  grid.appendChild(kpiRow("bl-unknown", "UNKNOWN-ORIGIN nodes"));
  grid.appendChild(kpiRow("bl-fractr",  "fraction traced"));
  grid.appendChild(kpiRow("bl-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bl-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable node list (text mirror of the roots).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:170px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> TRACED (explicit source) &nbsp; ' +
    '<span style="color:#5b8dee">■</span> PARTIAL-LINEAGE (structural) &nbsp; ' +
    '<span style="color:#8a6bff">●</span> community &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNKNOWN-ORIGIN. ' +
    'MODELED · origins read verbatim, never upgraded · UNKNOWN never fabricated.';
  card.appendChild(leg);

  const pl = document.createElement("button");
  pl.textContent = "◑ what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #5b8dee;background:#08121f;color:#5b8dee;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2233" : "#08121f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "bl-plain";
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
    "<b>What this means:</b> every fact in the brain’s knowledge graph came from somewhere. This " +
    "traces, for each node, <b>how it got in</b> — reading only the real origin fields the node " +
    "actually carries. If a node names a real source it reads <b>TRACED</b>; if only its place in " +
    "the structure is known it reads <b>PARTIAL-LINEAGE</b>; if it records no source at all it " +
    "reads <b>UNKNOWN-ORIGIN</b> — and we say so plainly rather than <b>inventing a source</b>. " +
    "This is about where a fact came from — it is not a security seal on a model or a build, and " +
    "it is separate from tracing which facts backed a given answer. No “verified / 1.0” state.";
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
  const rows = Array.isArray(S.lineages) ? S.lineages : [];
  rows.forEach((e) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:58%";
    left.textContent = (e.title || e.id || "?");
    const val = document.createElement("b");
    const vrd = e.verdict ? String(e.verdict) : "UNKNOWN-ORIGIN";
    const hex = "#" + _verdictColor(e.verdict).toString(16).padStart(6, "0");
    val.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums;text-align:right;max-width:42%;overflow-wrap:anywhere";
    const origin = e.origin ? String(e.origin) : "UNKNOWN";
    val.textContent = vrd + " · " + origin;
    row.appendChild(left); row.appendChild(val);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  const agg = S.agg || {};
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "lineage" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bl-verdict", vrd);
  _set("bl-nodes",   t || _n(agg.total_nodes != null ? agg.total_nodes : (S.lineages ? S.lineages.length : null)));
  _set("bl-traced",  t || _n(agg.traced));
  _set("bl-partial", t || _n(agg.partial_lineage));
  _set("bl-unknown", t || _n(agg.unknown_origin));
  _set("bl-fractr",  t || (typeof agg.fraction_traced === "number" ? agg.fraction_traced.toFixed(3) : "—"));
  _set("bl-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bl-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeRoots();
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
  _keystone = null; _roots = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.reason = S.query = null;
  S.lineages = []; S.agg = {};
  S.lambda = S.locked = S.trustCeil = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
