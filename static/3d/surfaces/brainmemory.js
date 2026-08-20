// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainmemory.js — BRAIN MEMORY FRESHNESS · honest episodic decay proxy.
//
// A vertical FRESHNESS COLUMN over the estate knowledge-graph nodes: freshest at the top,
// stalest at the bottom. Each rung is one node, coloured by its honest verdict (FRESH / AGING /
// STALE) and sized by its freshness score. HONEST BY CONSTRUCTION: every value is read VERBATIM
// from the same-origin feed, which reuses the same honest brain graph and NEVER fabricates a
// timestamp or a decay curve.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/memory?top=:
//   ok, label (MODELED | STRUCTURAL-ONLY, VERBATIM), mode, recency_signal, recency_field,
//   weights{...}, node_count, verdict_counts{ FRESH, AGING, STALE },
//   ranking[]{ id, title, kind, community, degree, salience, freshness, verdict, label,
//              components{ recency|null, connectivity, salience } },
//   honest_note, doctrine{ locked_proven, lambda, trust_ceiling }.
//
// HONESTY LABEL: MODELED only when a real per-node recency timestamp exists; otherwise
//   STRUCTURAL-ONLY — a connectivity + salience PROXY, NOT a decay measurement. The score is
//   NEVER labelled MEASURED (there is no live decay meter). Labels are read VERBATIM and NEVER
//   upgraded. STALE nodes are flagged for RE-HARVEST, never silently trusted. No green "1.0 /
//   VERIFIED" state. Trust ceiling 0.97, NEVER 100%.
// COLOURS: proof-teal 0x3af4c8 (FRESH), violet-blue 0x8a6bff (AGING), grey 0x5a6b78 (STALE),
//   lattice-blue 0x5b8dee (column spine). Approved hues only — no green.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1, never a theorem; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainmemory";
const TITLE = "Brain Memory Freshness · honest episodic decay proxy (live, drift-proof)";

// same-origin, relative — no CDN, no cross-origin fetch.
const EP = "/api/a11oy/v1/brain/memory?top=40";

// data-viz hues — approved only; no green, no raw purple.
const C_FRESH = 0x3af4c8;  // proof-teal   — FRESH
const C_AGING = 0x8a6bff;  // violet-blue  — AGING
const C_STALE = 0x5a6b78;  // grey         — STALE (re-harvest)
const C_SPINE = 0x5b8dee;  // lattice-blue — freshness column spine
const C_GRID  = 0x1b3a44;  // floor colour

const SPAN_Y = 9.0;        // vertical extent of the freshness column (world units)
const TOP_Y  = 6.0;        // y of the freshest node

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _spine = null;         // THREE.Line — the freshness column spine
let _nodes = [];           // Array<{ mesh, conn, verdict }>
let _pulse = 0;            // descending-pulse phase

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,   // top honesty label VERBATIM (MODELED | STRUCTURAL-ONLY)
  mode:      null,
  recency:   null,   // boolean — is there a real recency signal?
  recField:  null,
  count:     null,   // node_count
  fresh:     null,   // verdict counts
  aging:     null,
  stale:     null,
  note:      null,
  trustCeil: null,
  lambda:    null,
  locked:    null,
  items:     [],     // [{ id, title, freshness, verdict, degree, salience, components }]
  state:     "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.5, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.5, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildSpine();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); },
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

function _buildSpine() {
  const THREE = _THREE;
  const g = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, TOP_Y, 0), new THREE.Vector3(0, TOP_Y - SPAN_Y, 0),
  ]);
  _spine = new THREE.Line(g, new THREE.LineBasicMaterial({
    color: C_SPINE, transparent: true, opacity: 0.4,
  }));
  _group.add(_spine);
}

// Build (or rebuild) one node per ranked item, freshest at the top. Called on each live
// snapshot so the column always mirrors the CURRENT feed (never a stale hard-coded set).
function _buildNodes() {
  const THREE = _THREE;
  _disposeNodes();
  const list = S.items;
  const n = list.length;
  if (!n) return;

  const haloGeo = new THREE.RingGeometry(0.30, 0.40, 22);
  const step = n > 1 ? SPAN_Y / (n - 1) : 0;

  for (let i = 0; i < n; i++) {
    const it = list[i];
    const y = TOP_Y - step * i;                 // freshest (i=0) at top
    const x = (i % 2 === 0) ? 1.1 : -1.1;        // alternate sides of the spine
    const color = _verdictColor(it.verdict);
    // size encodes freshness (honest: bigger = fresher), clamped to a visible range.
    const f = Math.max(0, Math.min(1, Number(it.freshness) || 0));
    const r = 0.16 + 0.24 * f;

    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(r, 16, 12),
      new THREE.MeshStandardMaterial({
        color, emissive: color, emissiveIntensity: 0.3, transparent: true, opacity: 0.92,
      }));
    mesh.position.set(x, y, 0);
    _group.add(mesh);

    // connector spine -> node
    const cg = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, y, 0), new THREE.Vector3(x, y, 0),
    ]);
    const conn = new THREE.Line(cg, new THREE.LineBasicMaterial({
      color: C_SPINE, transparent: true, opacity: 0.18,
    }));
    _group.add(conn);

    // STALE nodes get a warning halo (re-harvest candidates).
    let halo = null;
    if (it.verdict === "STALE") {
      halo = new THREE.Mesh(haloGeo, new THREE.MeshBasicMaterial({
        color: C_STALE, transparent: true, opacity: 0.5, side: THREE.DoubleSide,
      }));
      halo.position.copy(mesh.position);
      _group.add(halo);
    }

    _nodes.push({ mesh, conn, halo, verdict: it.verdict });
  }
}

function _verdictColor(v) {
  if (v === "FRESH") return C_FRESH;
  if (v === "AGING") return C_AGING;
  return C_STALE;
}

function _disposeNodes() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _nodes.forEach((nd) => { rm(nd.mesh); rm(nd.conn); rm(nd.halo); });
  _nodes = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label = (j && j.label ? String(j.label) : "STRUCTURAL-ONLY").toUpperCase();
  S.mode  = j && j.mode ? String(j.mode) : null;
  S.recency  = !!(j && j.recency_signal);
  S.recField = j && j.recency_field ? String(j.recency_field) : null;
  S.count = typeof (j && j.node_count) === "number" ? j.node_count : null;

  const vc = (j && j.verdict_counts) || {};
  S.fresh = typeof vc.FRESH === "number" ? vc.FRESH : null;
  S.aging = typeof vc.AGING === "number" ? vc.AGING : null;
  S.stale = typeof vc.STALE === "number" ? vc.STALE : null;

  S.note = j && j.honest_note ? String(j.honest_note) : null;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  const arr = Array.isArray(j && j.ranking) ? j.ranking : [];
  S.items = arr.map((e) => ({
    id: e && e.id,
    title: e && e.title,
    verdict: e && e.verdict,
    label: e && e.label,
    freshness: e && e.freshness,
    degree: e && e.degree,
    salience: e && e.salience,
    components: (e && e.components) || {},
  }));

  _buildNodes();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.10;

  const live = S.state === "live";
  if (_nodes.length) {
    _pulse = (t * 0.00018) % 1;
    const lead = Math.floor(_pulse * _nodes.length);
    for (let i = 0; i < _nodes.length; i++) {
      const nd = _nodes[i];
      const near = Math.abs(i - lead) <= 1;
      nd.mesh.material.emissiveIntensity = near && live ? 0.85 : (live ? 0.3 : 0.12);
      nd.mesh.material.opacity = live ? 0.92 : 0.4;
      if (nd.halo) { nd.halo.rotation.z += 0.01; nd.halo.material.opacity = live ? 0.5 : 0.2; }
    }
  }
}

// =============================================================================
// overlay (HUD)
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "STRUCTURAL-ONLY", text: "freshness", name: "lbl" }],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A deterministic, explainable <b>memory-freshness</b> score per knowledge-graph node — ' +
    'freshest at the top. If a <b>real per-node recency timestamp</b> exists the score is ' +
    '<b>MODELED</b> (recency ⊕ structure); otherwise it is <b>STRUCTURAL-ONLY</b>: a ' +
    'connectivity + salience <b>proxy</b>, <b>not</b> a decay measurement. No timestamp or ' +
    'decay half-life is ever fabricated. <b>STALE</b> nodes are flagged for <b>re-harvest</b>, ' +
    'never silently trusted. Labels read VERBATIM, never upgraded. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bm-recency", "recency signal"));
  grid.appendChild(kpiRow("bm-count",   "nodes scored"));
  grid.appendChild(kpiRow("bm-fresh",   "FRESH"));
  grid.appendChild(kpiRow("bm-aging",   "AGING"));
  grid.appendChild(kpiRow("bm-stale",   "STALE (re-harvest)"));
  grid.appendChild(kpiRow("bm-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bm-trust",   "trust ceiling"));
  grid.appendChild(kpiRow("bm-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable ranked list (text mirror of the column; verbatim verdicts + freshness).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:190px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> FRESH &nbsp; ' +
    '<span style="color:#8a6bff">■</span> AGING &nbsp; ' +
    '<span style="color:#8494a1">■</span> STALE (re-harvest) &nbsp; · size = freshness. ' +
    'STRUCTURAL-ONLY proxy · never MEASURED, never upgraded.';
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
  pd.id = "bm-plain";
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
    "<b>What this means:</b> a live, honest read on which pieces of the platform’s knowledge " +
    "are likely to be <b>going stale</b>. Ideally we would know exactly when each fact was last " +
    "refreshed — but the estate graph does <b>not</b> carry that timestamp, so instead of " +
    "inventing one, this view is honest about it: it labels the score <b>STRUCTURAL-ONLY</b> " +
    "and uses how well-connected and load-bearing each node is as a <b>proxy</b> for how likely " +
    "it is to still be current. Weakly-connected nodes are flagged <b>STALE</b> and should be " +
    "<b>re-harvested</b>, never blindly trusted. The moment a real recency timestamp does exist, " +
    "the view upgrades itself to MODELED and says so. No “verified/1.0” state; trust ceiling 0.97.";
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
  S.items.forEach((it) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:64%";
    const f = (typeof it.freshness === "number") ? it.freshness.toFixed(3) : "—";
    left.textContent = (it.id || "?") + "  ·  f=" + f;
    const lab = document.createElement("b");
    const col = it.verdict === "FRESH" ? "#3af4c8" : (it.verdict === "AGING" ? "#8a6bff" : "#8494a1");
    lab.style.cssText = "color:" + col + ";font-variant-numeric:tabular-nums";
    lab.textContent = it.verdict || "—";
    row.appendChild(left); row.appendChild(lab);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  if (_show) _show.setChip("lbl", S.label || "STRUCTURAL-ONLY", { text: "freshness" });
  _set("bm-recency", t || (S.recency ? ("yes (" + (S.recField || "field") + ")") : "no — STRUCTURAL-ONLY"));
  _set("bm-count",   t || _n(S.count));
  _set("bm-fresh",   t || _n(S.fresh));
  _set("bm-aging",   t || _n(S.aging));
  _set("bm-stale",   t || _n(S.stale));
  _set("bm-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bm-trust",   t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bm-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeNodes();
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
  _spine = null; _nodes = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _pulse = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.mode = S.recField = null; S.recency = null;
  S.count = S.fresh = S.aging = S.stale = null; S.note = null;
  S.trustCeil = S.lambda = S.locked = null; S.items = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
