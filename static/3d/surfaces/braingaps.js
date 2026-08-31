// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/braingaps.js — BRAIN GAPS · a live map of what the brain does NOT know.
// The mirror image of the coverage surfaces: it renders where the live knowledge graph is
// THIN or EMPTY — sparse communities, weakly-connected island nodes, and the share of nodes
// with no real honesty label. Pure honesty/observability over the knowledge graph; it advances
// no detection / fusion / effector / targeting / cueing capability.
//
// A ring of GAP BARS, one per structural gap metric (island share, thin-community share,
// weak-label share). Each bar's height is that MEASURED fraction; a taller bar means MORE gap.
// A CORE orb at the centre carries the estate-wide verdict — WELL-COVERED / PATCHY / SPARSE.
// When a query is supplied the core instead reflects the per-topic verdict — COVERED / THIN /
// GAP — and a GAP is drawn plainly (violet), never dressed up as coverage.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/gaps (PURE READ, mints nothing):
//   ok, label, estate_verdict, query,
//   gaps{ label (MEASURED), estate_verdict, metrics{ node_count, island_count, isolated_count,
//         island_share, thin_community_count, thin_community_share, community_count,
//         weak_label_count, weak_label_share, label_distribution },
//     topic{ label (MODELED), query, verdict, match_count, best_connected_degree } }.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived gap map + verdict,
//   not a measurement). The structural counts it renders are MEASURED and read VERBATIM; no
//   coverage is fabricated — a topic the graph cannot ground is drawn as a GAP. No green
//   "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (WELL-COVERED / COVERED),
//   lattice-blue 0x5b8dee (PATCHY / THIN / frame), violet-blue 0x8a6bff (SPARSE / GAP),
//   grey 0x42505d (UNAVAILABLE / init). No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "braingaps";
const TITLE = "Brain Gaps · an honest map of what the brain does NOT know (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ gap-map endpoint.
const EP = "/api/a11oy/v1/brain/gaps";

// verdict hues — approved palette only, no green
const C_OK       = 0x3af4c8;  // proof-teal   — WELL-COVERED / COVERED
const C_MID      = 0x5b8dee;  // lattice-blue — PATCHY / THIN / frame
const C_GAP      = 0x8a6bff;  // violet-blue  — SPARSE / GAP
const C_NEUTRAL  = 0x42505d;  // grey         — UNAVAILABLE / init
const C_GRID     = 0x1b3a44;  // floor colour

// estate verdict -> core colour
function _estateColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "WELL-COVERED") return C_OK;
  if (s === "PATCHY")       return C_MID;
  if (s === "SPARSE")       return C_GAP;
  return C_NEUTRAL;                       // init / unknown
}
// per-topic verdict -> core colour (when a query is supplied)
function _topicColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "COVERED") return C_OK;
  if (s === "THIN")    return C_MID;
  if (s === "GAP")     return C_GAP;
  return C_NEUTRAL;
}
// a gap-fraction bar's colour: more gap = hotter (teal -> blue -> violet)
function _gapColor(frac) {
  if (typeof frac !== "number" || !isFinite(frac)) return C_NEUTRAL;
  if (frac >= 0.5) return C_GAP;
  if (frac > 0.0)  return C_MID;
  return C_OK;                            // zero gap on this axis reads teal
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the verdict core orb
let _bars = [];               // Array<{ mesh, key, frac }>
let _spin = 0;

// The gap axes we render as bars (each a MEASURED fraction in [0,1]; more = more gap).
const _AXES = [
  { key: "island_share",         label: "island share (deg≤1)" },
  { key: "thin_community_share", label: "thin-community share" },
  { key: "weak_label_share",     label: "weak-label share" },
];

// live state (all read from JSON; nothing invented)
const S = {
  label:      null,  // top honesty label VERBATIM (MODELED)
  estate:     null,  // WELL-COVERED | PATCHY | SPARSE
  query:      null,  // the topic asked, if any
  topicVerd:  null,  // COVERED | THIN | GAP (only when query supplied)
  topicMatch: null,  // match_count for the topic
  nodeCount:  null,
  islandCount: null,
  isolated:   null,
  thinCount:  null,
  commCount:  null,
  weakCount:  null,
  fracs:      {},    // key -> MEASURED fraction
  trustCeil:  null,
  lambda:     null,
  locked:     null,
  state:      "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 5.0, 17);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
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
  const g = new THREE.IcosahedronGeometry(1.5, 1);
  _core = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_NEUTRAL, emissive: C_NEUTRAL, emissiveIntensity: 0.35,
    transparent: true, opacity: 0.9, flatShading: true,
  }));
  _core.position.set(0, 4.4, 0);
  _group.add(_core);

  // lattice ring beneath the core (the gap-map base rail)
  const pts = [];
  const R = 5.2;
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

// Build (or rebuild) one bar per gap axis, in a ring, height by the MEASURED fraction. Called
// on each live snapshot so the ring always mirrors the CURRENT feed (never a hard-coded set).
function _buildBars() {
  const THREE = _THREE;
  _disposeBars();

  const n = _AXES.length;
  const R = 4.6;
  const geo = new THREE.BoxGeometry(0.9, 1.0, 0.9);

  for (let i = 0; i < n; i++) {
    const ax = _AXES[i];
    const frac = (typeof S.fracs[ax.key] === "number" && isFinite(S.fracs[ax.key]))
      ? Math.max(0, Math.min(1, S.fracs[ax.key])) : null;
    // height: by fraction when present, else a short "stub" so an empty axis still reads.
    const h = frac != null ? 0.5 + frac * 4.0 : 0.5;
    const color = frac != null ? _gapColor(frac) : C_NEUTRAL;
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: frac != null ? 0.92 : 0.4,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, z);
    _group.add(mesh);

    _bars.push({ mesh, key: ax.key, frac });
  }
}

function _disposeBars() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _bars.forEach((b) => rm(b.mesh));
  _bars = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade, never fabricate coverage
// =============================================================================
function _onData(j) {
  // Top honesty label VERBATIM; absent live data this surface is MODELED (a derived gap map).
  S.label   = (j.label || "MODELED").toUpperCase();
  S.estate  = j && j.estate_verdict ? String(j.estate_verdict).toUpperCase() : null;
  S.query   = j && j.query ? String(j.query) : "";

  const g = (j && j.gaps) || {};
  const m = (g && g.metrics) || {};
  S.nodeCount  = typeof m.node_count === "number" ? m.node_count : null;
  S.islandCount = typeof m.island_count === "number" ? m.island_count : null;
  S.isolated   = typeof m.isolated_count === "number" ? m.isolated_count : null;
  S.thinCount  = typeof m.thin_community_count === "number" ? m.thin_community_count : null;
  S.commCount  = typeof m.community_count === "number" ? m.community_count : null;
  S.weakCount  = typeof m.weak_label_count === "number" ? m.weak_label_count : null;

  S.fracs = {};
  _AXES.forEach((ax) => {
    const v = m[ax.key];
    if (typeof v === "number" && isFinite(v)) S.fracs[ax.key] = v;
  });

  const tp = (g && g.topic) || null;
  S.topicVerd  = tp && tp.verdict ? String(tp.verdict).toUpperCase() : null;
  S.topicMatch = tp && typeof tp.match_count === "number" ? tp.match_count : null;

  const d = (g && g.doctrine) || (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildBars();
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
  if (_bars.length) {
    _spin = (t * 0.0002) % 1;
    const lead = Math.floor(_spin * _bars.length);
    for (let i = 0; i < _bars.length; i++) {
      const b = _bars[i];
      const near = i === lead;
      // a materially gappy bar (>=0.5) always glows hot; others follow the sweep when live.
      const gappy = typeof b.frac === "number" && b.frac >= 0.5;
      const base = gappy ? 0.6 : (b.frac != null && live ? 0.26 : 0.12);
      b.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.85) : base;
    }
  }
}

// =============================================================================
function _paintCore() {
  if (!_core) return;
  // when a topic is asked, the core reflects the per-topic verdict; else the estate verdict.
  const useTopic = !!(S.query && S.topicVerd);
  const col = (S.state === "live")
    ? (useTopic ? _topicColor(S.topicVerd) : _estateColor(S.estate))
    : C_NEUTRAL;
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
    chips: [{ label: "MODELED", text: "gap map", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A live map of <b>what the brain does NOT know.</b> It reads the knowledge graph and reports, ' +
    'without flattery, where it is <b>thin or empty</b>: sparse communities, weakly-connected ' +
    '<b>island</b> nodes (degree ≤ 1), and the share of nodes carrying <b>no real honesty ' +
    'label</b>. For a query it grades the topic <b>COVERED / THIN / GAP</b> — and a <b>GAP</b> ' +
    'is drawn plainly, <b>never</b> dressed up as coverage. Estate verdict: <b>WELL-COVERED / ' +
    'PATCHY / SPARSE</b> (a SPARSE graph is never softened). Structural counts are MEASURED and ' +
    'read verbatim; labels are never upgraded. Strictly knowledge-graph honesty. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bg-estate",  "estate verdict"));
  grid.appendChild(kpiRow("bg-topic",   "topic verdict"));
  grid.appendChild(kpiRow("bg-nodes",   "nodes"));
  grid.appendChild(kpiRow("bg-islands", "islands (deg≤1)"));
  grid.appendChild(kpiRow("bg-iso",     "isolated (deg=0)"));
  grid.appendChild(kpiRow("bg-thin",    "thin communities"));
  grid.appendChild(kpiRow("bg-weak",    "weak-label nodes"));
  grid.appendChild(kpiRow("bg-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bg-ceil",    "trust ceiling"));
  grid.appendChild(kpiRow("bg-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> WELL-COVERED / COVERED &nbsp; ' +
    '<span style="color:#5b8dee">■</span> PATCHY / THIN &nbsp; ' +
    '<span style="color:#8a6bff">■</span> SPARSE / GAP &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNAVAILABLE. ' +
    'MODELED · structural counts MEASURED, read verbatim · coverage is never fabricated (a GAP is a GAP).';
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
  pd.id = "bg-plain";
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
    "<b>What this means:</b> an honest read of the brain’s <b>blind spots</b>. Instead of showing " +
    "off what it knows, it shows where it is <b>thin or empty</b> — little clusters of knowledge " +
    "with almost nothing in them, facts that connect to nothing else, and nodes that never got a " +
    "trustworthy label. Ask it about a topic and it will tell you plainly whether it actually has " +
    "grounding (<b>COVERED</b>), only a shaky bit (<b>THIN</b>), or <b>nothing at all</b> " +
    "(<b>GAP</b>). It will <b>never</b> pretend to cover a topic it can’t. Overall it reads " +
    "<b>WELL-COVERED</b>, <b>PATCHY</b>, or <b>SPARSE</b>, and a sparse graph is never softened. " +
    "No “verified / 1.0” state; confidence is capped at 0.97, never 100%.";
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
  // the headline verdict: topic verdict when a query is asked, else estate verdict.
  const useTopic = !!(S.query && S.topicVerd);
  const headline = t || (useTopic ? S.topicVerd : (S.estate || "—"));
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "gap map" });
    _show.setChip("vrd", headline, { text: useTopic ? "topic" : "estate" });
  }
  _set("bg-estate", t || (S.estate || "—"));
  _set("bg-topic",  t || (useTopic
    ? (S.topicVerd + (S.topicMatch != null ? " · " + S.topicMatch + " match" : ""))
    : "—"));
  _set("bg-nodes",   t || _n(S.nodeCount));
  _set("bg-islands", t || _n(S.islandCount));
  _set("bg-iso",     t || _n(S.isolated));
  _set("bg-thin",    t || (S.thinCount != null && S.commCount != null
    ? S.thinCount + " / " + S.commCount : _n(S.thinCount)));
  _set("bg-weak",    t || _n(S.weakCount));
  _set("bg-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bg-ceil",    t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bg-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeBars();
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
  _core = null; _bars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.estate = S.query = S.topicVerd = null;
  S.topicMatch = S.nodeCount = S.islandCount = S.isolated = null;
  S.thinCount = S.commCount = S.weakCount = null;
  S.fracs = {};
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
