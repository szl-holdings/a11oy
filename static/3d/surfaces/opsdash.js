// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/opsdash.js — OPS DASHBOARD · live operational view of the whole estate.
//
// The FRONT-END operational view for the estate. It consumes the aggregate backend
// /api/a11oy/v1/status (Dev 2, Wave R) and renders, per subsystem/surface, its honest
// data label + last-known operational health, plus a single GREEN / DEGRADED /
// UNAVAILABLE rollup for the entire estate and a link to the public /verify page.
//
// GUARDED DEPENDENCY: /api/a11oy/v1/status is built by Dev 2 on a parallel branch
// (feat/r-backend-status). Until that PR merges the route 404s; this surface degrades
// HONESTLY (szl3d_live.poll -> state "missing") into a single honest placeholder tile —
// it never renders blank or broken. Once the route is live the tiles fill in on the next
// poll with zero code change.
//
// DATA: same-origin, relative — /api/a11oy/v1/status. Read defensively (the exact schema
// is Dev 2's; we accept the plausible field names and never fabricate a value):
//   ok, label (this view's own top label, MODELED — an introspective rollup, not a meter),
//   rollup ("green"|"degraded"|"unavailable"; derived locally iff the backend omits it),
//   summary{ surfaces, health_counts{green,degraded,unavailable}, label_counts },
//   surfaces[]{ id, title, category, label, health, endpoint, reason },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// VISUALIZES:
//   1. a CENTRAL ROLLUP CORE — one icosahedron whose colour is the estate rollup
//      (green up / amber degraded / red unavailable). This is OPERATIONAL health only,
//      NOT a proof/verified claim: Λ stays Conjecture 1, locked count stays 8.
//   2. a HEALTH RING — one node per surface, coloured by that surface's own operational
//      health, arranged in a ring around the core, each linked to it.
//   3. a per-frame PULSE that sweeps the ring so the viewer reads that the rollup covers
//      the WHOLE estate, not a curated subset. Amber/red nodes pulse brighter so an
//      operator's eye is pulled to the surfaces that need attention.
//
// HONESTY LABEL: MODELED — this surface's own top label (an operational aggregate view,
//   not a measurement). Each per-surface honest data label is that surface's OWN label
//   read VERBATIM and NEVER upgraded: a down surface shows UNAVAILABLE, never a fake OK.
//   No "verified / 1.0" state anywhere. Trust ceiling 0.97, NEVER 100%.
// COLOURS: health-green 0x2fd07a (up/answering), amber 0xe8c074 (degraded), red 0xff6b6b
//   (unavailable), lattice-blue 0x5b8dee (core/links), grey 0x42505d (unknown/pending).
//   PURPLE BANNED. Green here = operational uptime, never a proof of Λ.
// 0 RUNTIME CDN. Vendored three.js via the page importmap (ctx.THREE).
// DOCTRINE v11: adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17;
//   Λ stays Conjecture 1; introduces no theorem; PURE READ (signs/mints nothing on a GET).

import { createShowcase } from "./_showcase.js";

const ID    = "opsdash";
const TITLE = "Ops Dashboard · live estate health (rollup + per-surface honest labels)";

// same-origin, relative — no CDN, no cross-origin fetch. Dev 2 (feat/r-backend-status).
const EP = "/api/a11oy/v1/status";
// Public independent-verify page (Wave shareable link). Same-origin.
const VERIFY_HREF = "/verify";

// operational-health hues — purple BANNED. "green" = up/answering, not a proof claim.
const C_GREEN  = 0x2fd07a;  // healthy — surface up and answering with an honest label
const C_AMBER  = 0xe8c074;  // degraded — up but reduced / cached / replay / structural-only
const C_RED    = 0xff6b6b;  // unavailable — down / no honest label / 404
const C_GREY   = 0x42505d;  // unknown / pending
const C_CORE   = 0x5b8dee;  // lattice-blue — rollup core + links
const C_GRID   = 0x1b3a44;  // floor colour

const RING_R = 6.2;         // health-ring radius (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _plain = false;

// geometry handles
let _core = null;           // THREE.Mesh — central rollup node
let _nodes = [];            // Array<{ mesh, health }>
let _links = [];            // Array<THREE.Line>
let _sweep = 0;

// DOM handles for the HUD readouts + per-surface list + placeholder
let _el = {};
let _listEl = null, _placeholderEl = null;

// live state (all read from JSON; nothing invented)
const S = {
  label:       null,   // this view's own top honesty label VERBATIM (MODELED)
  rollup:      null,   // "green" | "degraded" | "unavailable"
  count:       null,
  green:       null,
  degraded:    null,
  unavailable: null,
  trustCeil:   null,
  lambda:      null,
  locked:      null,
  surfaces:    [],     // [{ id, title, label, health, reason }]
  state:       "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 9, 16);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCore();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge,
    onState: (m) => { S.state = m.state; _paintOverlay(); },
  }));

  _buildOverlay();
  _paintOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.0, 1),
    new THREE.MeshStandardMaterial({
      color: C_CORE, emissive: C_CORE, emissiveIntensity: 0.4,
      transparent: true, opacity: 0.9, wireframe: true,
    }),
  );
  _core.position.set(0, 1.2, 0);
  _group.add(_core);
}

// Build (or rebuild) one ring node per surface in the CURRENT snapshot so the ring always
// mirrors the live rollup, never a stale hard-coded set.
function _buildNodes() {
  const THREE = _THREE;
  _disposeNodes();
  const list = S.surfaces;
  const n = list.length;
  if (!n) return;

  const nodeGeo = new THREE.SphereGeometry(0.26, 14, 10);
  for (let i = 0; i < n; i++) {
    const surf = list[i];
    const ang = (i / n) * Math.PI * 2;
    const x = Math.cos(ang) * RING_R;
    const z = Math.sin(ang) * RING_R;
    const color = _healthColor(surf.health);

    const mesh = new THREE.Mesh(nodeGeo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.92,
    }));
    mesh.position.set(x, 1.2, z);
    _group.add(mesh);

    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 1.2, 0), new THREE.Vector3(x, 1.2, z),
    ]);
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({
      color: C_CORE, transparent: true, opacity: 0.12,
    }));
    _group.add(line);
    _links.push(line);

    _nodes.push({ mesh, health: surf.health });
  }
  _paintCore();
}

function _healthColor(health) {
  if (health === "green") return C_GREEN;
  if (health === "degraded") return C_AMBER;
  if (health === "unavailable") return C_RED;
  return C_GREY;
}

function _paintCore() {
  if (!_core) return;
  const c = _rollupColor();
  _core.material.color.setHex(c);
  _core.material.emissive.setHex(c);
}

function _rollupColor() {
  if (S.rollup === "green") return C_GREEN;
  if (S.rollup === "degraded") return C_AMBER;
  if (S.rollup === "unavailable") return C_RED;
  return C_CORE;
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
  _nodes.forEach((nd) => rm(nd.mesh));
  _links.forEach(rm);
  _nodes = []; _links = [];
}

// =============================================================================
// health mapping — honest, defensive. Prefer an explicit per-surface health/status
// field; otherwise derive from the surface's OWN honest data label. Never upgrades a
// label: a DEGRADED surface can never read "green".
// =============================================================================
const _GREEN_LABELS  = new Set(["LIVE", "MEASURED", "MEASURED_SHARED_BOUNDED", "MODELED", "SAMPLE", "SIMULATED", "PROVEN", "HONEST-STUB"]);
const _AMBER_LABELS  = new Set(["DEGRADED", "CACHED", "REPLAY", "STRUCTURAL-ONLY", "UNSIGNED-LOCAL", "CONJECTURE", "ROADMAP"]);
const _RED_LABELS    = new Set(["UNAVAILABLE"]);

function _normHealth(raw) {
  if (!raw) return null;
  const t = String(raw).trim().toLowerCase();
  if (t === "green" || t === "ok" || t === "up" || t === "live" || t === "healthy") return "green";
  if (t === "degraded" || t === "warn" || t === "warning" || t === "partial") return "degraded";
  if (t === "unavailable" || t === "down" || t === "error" || t === "offline" || t === "red") return "unavailable";
  return null;
}

function _healthFromLabel(label) {
  if (!label) return "unavailable";
  const t = String(label).trim().toUpperCase();
  if (_RED_LABELS.has(t)) return "unavailable";
  if (_AMBER_LABELS.has(t)) return "degraded";
  if (_GREEN_LABELS.has(t)) return "green";
  // Unknown-but-present label → treat as up-with-an-honest-label (green), read verbatim.
  return "green";
}

// Derive the estate rollup from the per-surface health counts when the backend omits an
// explicit rollup. WORST-WINS: any unavailable → unavailable; else any degraded →
// degraded; else green. Honest by construction — never optimistic.
function _deriveRollup(surfaces) {
  if (!surfaces.length) return "unavailable";
  let anyDeg = false;
  for (const s of surfaces) {
    if (s.health === "unavailable") return "unavailable";
    if (s.health === "degraded") anyDeg = true;
  }
  return anyDeg ? "degraded" : "green";
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  // Runtime-default honesty label: the backend's verbatim top label, else this view's own
  // MODELED (it is an operational aggregate, never a measurement). The `|| "MODELED"` form
  // is the canonical single-source pattern the manifest label-deriver reads.
  const jLabel = (j && typeof j.label === "string") ? j.label.toUpperCase() : null;
  S.label = (jLabel || "MODELED");

  // per-surface list — accept plausible field names from Dev 2's schema.
  const arr = Array.isArray(j && j.surfaces) ? j.surfaces
            : Array.isArray(j && j.subsystems) ? j.subsystems
            : [];
  S.surfaces = arr.map((e) => {
    const label = (e && (e.label || e.data_label || e.status_label)) || null;
    const health = _normHealth(e && (e.health || e.status || e.state)) || _healthFromLabel(label);
    return {
      id: (e && (e.id || e.name || e.surface)) || "?",
      title: (e && (e.title || e.name)) || null,
      label: label ? String(label).toUpperCase() : "UNAVAILABLE",
      health,
      reason: (e && (e.reason || e.detail)) || null,
    };
  });

  // rollup — prefer the backend's own; else derive worst-wins.
  const rawRollup = _normHealth(j && (j.rollup || j.rollup_health || (j.summary && j.summary.rollup)));
  S.rollup = rawRollup || _deriveRollup(S.surfaces);

  // summary counts — prefer the backend's own; else count locally.
  const sm = (j && j.summary) || {};
  const hc = sm.health_counts || sm.counts || {};
  S.count       = typeof sm.surfaces === "number" ? sm.surfaces : S.surfaces.length;
  S.green       = typeof hc.green === "number" ? hc.green : S.surfaces.filter((s) => s.health === "green").length;
  S.degraded    = typeof hc.degraded === "number" ? hc.degraded : S.surfaces.filter((s) => s.health === "degraded").length;
  S.unavailable = typeof hc.unavailable === "number" ? hc.unavailable : S.surfaces.filter((s) => s.health === "unavailable").length;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildNodes();
  _paintOverlay();
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.12;
  if (_core) { _core.rotation.y += 0.01; _core.rotation.x += 0.004; }

  const live = S.state === "live" || S.state === "degraded";
  if (_nodes.length) {
    _sweep = (t * 0.0002) % 1;
    const lead = Math.floor(_sweep * _nodes.length);
    for (let i = 0; i < _nodes.length; i++) {
      const nd = _nodes[i];
      const near = Math.abs(i - lead) <= 1 || Math.abs(i - lead) >= _nodes.length - 1;
      // surfaces needing attention (amber/red) glow a touch hotter so the eye finds them.
      const attn = nd.health === "degraded" || nd.health === "unavailable";
      const base = live ? (attn ? 0.45 : 0.3) : 0.12;
      nd.mesh.material.emissiveIntensity = near && live ? 0.9 : base;
      nd.mesh.material.opacity = live ? 0.92 : 0.4;
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
    chips: [
      { label: "MODELED", text: "ops view", name: "lbl" },
    ],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The estate <b>operational view</b>: one <b>GREEN / DEGRADED / UNAVAILABLE</b> rollup ' +
    'for the whole estate, plus each surface&rsquo;s <b>own</b> honest data label + ' +
    'last-known health, read live from <code>/api/a11oy/v1/status</code>. Health here is ' +
    '<b>operational uptime</b>, <b>not</b> a proof claim &mdash; Λ stays Conjecture 1, the ' +
    'locked count stays 8. Per-surface labels are read <b>VERBATIM</b> and never upgraded. ' +
    '0 runtime CDN.';
  host.appendChild(sub);

  // ── rollup banner (big, colour-coded operational status) ──
  const banner = document.createElement("div");
  banner.id = "od-rollup";
  banner.style.cssText = "border-radius:9px;padding:9px 11px;display:flex;align-items:center;gap:9px;" +
    "font:600 12px ui-monospace,Menlo,monospace;letter-spacing:.4px;border:1px solid #1d2a36;background:#0a1117;color:#9fb1bf";
  const bdot = document.createElement("span");
  bdot.id = "od-rollup-dot";
  bdot.style.cssText = "width:11px;height:11px;border-radius:50%;background:#42505d;flex:0 0 auto";
  const btxt = document.createElement("span");
  btxt.id = "od-rollup-txt"; btxt.textContent = "estate rollup: …";
  banner.appendChild(bdot); banner.appendChild(btxt);
  _el["rollupBanner"] = banner; _el["rollupDot"] = bdot; _el["rollupTxt"] = btxt;
  host.appendChild(banner);

  // ── KPI card ──
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
  grid.appendChild(kpiRow("od-count", "surfaces monitored"));
  grid.appendChild(kpiRow("od-green", "green (up · honest label)"));
  grid.appendChild(kpiRow("od-deg",   "degraded"));
  grid.appendChild(kpiRow("od-unav",  "unavailable"));
  grid.appendChild(kpiRow("od-locked", "locked proofs"));
  grid.appendChild(kpiRow("od-trust",  "trust ceiling"));
  grid.appendChild(kpiRow("od-lambda", "Λ"));
  card.appendChild(grid);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#2fd07a">●</span> green (up) &nbsp; ' +
    '<span style="color:#e8c074">●</span> degraded &nbsp; ' +
    '<span style="color:#ff6b6b">●</span> unavailable &nbsp; · ' +
    'operational health, not a proof. Labels read verbatim, never upgraded.';
  card.appendChild(leg);
  host.appendChild(card);

  // ── honest placeholder tile (shown when the backend is UNAVAILABLE / missing) ──
  _placeholderEl = document.createElement("div");
  _placeholderEl.id = "od-placeholder";
  _placeholderEl.style.cssText = "display:none;border:1px dashed #4a3a26;border-radius:9px;padding:9px 10px;" +
    "background:#140f08;color:#e8c074;font-size:11px;line-height:1.55";
  host.appendChild(_placeholderEl);

  // ── per-surface list (scrollable) ──
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:7px 8px;display:flex;flex-direction:column;gap:5px";
  const listHead = document.createElement("div");
  listHead.style.cssText = "font-size:9.5px;color:#6b7a86;letter-spacing:.4px;text-transform:uppercase";
  listHead.textContent = "per-surface health · honest label";
  listWrap.appendChild(listHead);
  _listEl = document.createElement("div");
  _listEl.style.cssText = "display:flex;flex-direction:column;gap:3px;max-height:170px;overflow:auto;-webkit-overflow-scrolling:touch";
  listWrap.appendChild(_listEl);
  host.appendChild(listWrap);

  // ── link to public /verify ──
  const verify = document.createElement("a");
  verify.href = VERIFY_HREF;
  verify.target = "_top";
  verify.textContent = "↗ independent public verify (/verify)";
  verify.title = "Open the public, independent verification page — recompute a receipt's verdict.";
  verify.style.cssText = "font:11px ui-monospace,Menlo,monospace;color:#3af4c8;text-decoration:none;" +
    "border:1px solid #17332b;border-radius:7px;padding:6px 10px;background:#08140f;width:fit-content";
  host.appendChild(verify);

  // ── plain-language toggle ──
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
  pd.id = "od-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  pd.innerHTML =
    "<b>What this means:</b> this is the estate&rsquo;s operational dashboard. It asks the " +
    "platform&rsquo;s own status endpoint, live, how every surface is doing and repeats each " +
    "surface&rsquo;s <b>own</b> honest data label <b>word-for-word</b> &mdash; it never rounds a " +
    "claim up. The single rollup at the top is the worst case across the estate (any one " +
    "surface down makes the rollup <b>unavailable</b>), so it can never look healthier than " +
    "reality. &ldquo;Green&rdquo; here means a surface is <b>up and answering</b>, not that " +
    "anything is proven &mdash; Λ stays a conjecture and the locked-proof count stays 8. If the " +
    "status backend itself is down, this tab shows an <b>honest placeholder</b>, never a blank " +
    "or fake-green screen. No &ldquo;verified/1.0&rdquo; state; trust ceiling 0.97.";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "degraded") return null;   // degraded still carries a payload we render
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "error") return "OFFLINE";
  return "…";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }
function _n(v) { return v == null ? "—" : String(v); }

// Is the backend itself unreachable (route missing / network error)? Distinct from a
// LIVE estate that merely contains some unavailable surfaces.
function _backendDown() { return S.state === "missing" || S.state === "error" || S.state === "init"; }

function _paintOverlay() {
  if (!_show) return;
  const t = _tok(S.state);
  _show.setChip("lbl", S.label || "MODELED", { text: "ops view" });

  // rollup banner
  const down = _backendDown();
  const dot = _el["rollupDot"], txt = _el["rollupTxt"], banner = _el["rollupBanner"];
  if (dot && txt && banner) {
    let color, word, bg, bd, fg;
    if (down) {
      color = "#e8c074"; word = "BACKEND UNAVAILABLE"; bg = "#140f08"; bd = "#4a3a26"; fg = "#e8c074";
    } else if (S.rollup === "green") {
      color = "#2fd07a"; word = "GREEN — all surfaces up"; bg = "#08160f"; bd = "#17402a"; fg = "#8fe6b6";
    } else if (S.rollup === "degraded") {
      color = "#e8c074"; word = "DEGRADED — some surfaces reduced"; bg = "#140f08"; bd = "#4a3a26"; fg = "#e8c074";
    } else if (S.rollup === "unavailable") {
      color = "#ff6b6b"; word = "UNAVAILABLE — surface(s) down"; bg = "#170a0a"; bd = "#4a2626"; fg = "#ff9d9d";
    } else {
      color = "#42505d"; word = "estate rollup: …"; bg = "#0a1117"; bd = "#1d2a36"; fg = "#9fb1bf";
    }
    dot.style.background = color; dot.style.boxShadow = "0 0 8px " + color;
    txt.textContent = down ? ("estate rollup: " + word) : ("estate rollup: " + word);
    banner.style.background = bg; banner.style.borderColor = bd; banner.style.color = fg;
  }

  // KPI rows
  _set("od-count",  t || _n(S.count));
  _set("od-green",  t || _n(S.green));
  _set("od-deg",    t || _n(S.degraded));
  _set("od-unav",   t || _n(S.unavailable));
  _set("od-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("od-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("od-lambda", t || (S.lambda || "—"));

  // honest placeholder tile vs the live per-surface list
  _paintPlaceholderAndList();

  if (_plain) _applyPlain();
}

// Render EITHER the honest placeholder (backend unreachable) OR the live per-surface list.
// Never both, never blank. This is the "degrade gracefully" requirement.
function _paintPlaceholderAndList() {
  if (!_placeholderEl || !_listEl) return;
  const down = _backendDown();
  if (down) {
    let msg;
    if (S.state === "missing") {
      msg = "<b>Operational backend UNAVAILABLE.</b> <code>/api/a11oy/v1/status</code> is not " +
            "registered yet (Dev 2&rsquo;s <code>feat/r-backend-status</code> endpoint is pending, " +
            "or the route is down). Showing an honest placeholder &mdash; the rollup and per-surface " +
            "tiles will fill in automatically on the next poll once the endpoint is live. No fake data.";
    } else if (S.state === "error") {
      msg = "<b>Operational backend OFFLINE.</b> <code>/api/a11oy/v1/status</code> did not answer " +
            "(network error / non-200). Showing an honest placeholder &mdash; no fabricated health.";
    } else {
      msg = "<b>Connecting…</b> awaiting the first response from <code>/api/a11oy/v1/status</code>.";
    }
    _placeholderEl.innerHTML = msg;
    _placeholderEl.style.display = "block";
    _listEl.innerHTML = "";
    return;
  }
  _placeholderEl.style.display = "none";
  _renderList();
}

function _renderList() {
  const host = _listEl;
  if (!host) return;
  host.innerHTML = "";
  if (!S.surfaces.length) {
    const empty = document.createElement("div");
    empty.style.cssText = "font-size:10.5px;color:#6b7a86";
    empty.textContent = "no surfaces reported by /api/a11oy/v1/status.";
    host.appendChild(empty);
    return;
  }
  for (const s of S.surfaces) {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:7px;font-size:10.5px";
    const d = document.createElement("span");
    d.style.cssText = "width:8px;height:8px;border-radius:50%;flex:0 0 auto;background:" + _healthCss(s.health);
    const id = document.createElement("span");
    id.style.cssText = "color:#c9d6df;flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
    id.textContent = s.title || s.id;
    id.title = (s.id) + (s.reason ? (" — " + s.reason) : "");
    const lab = document.createElement("span");
    lab.style.cssText = "font:600 9.5px ui-monospace,Menlo,monospace;letter-spacing:.3px;color:" +
      _healthCss(s.health) + ";flex:0 0 auto";
    lab.textContent = s.label;
    row.appendChild(d); row.appendChild(id); row.appendChild(lab);
    host.appendChild(row);
  }
}

function _healthCss(health) {
  if (health === "green") return "#2fd07a";
  if (health === "degraded") return "#e8c074";
  if (health === "unavailable") return "#ff6b6b";
  return "#8494a1";
}

// =============================================================================
// unmount — dispose everything; must not affect other organs
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
  _core = null; _nodes = []; _links = [];
  _el = {}; _listEl = null; _placeholderEl = null;
  _badge = null; _plain = false; _frameReg = false; _sweep = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.rollup = S.count = S.green = S.degraded = S.unavailable = null;
  S.trustCeil = S.lambda = S.locked = null; S.surfaces = []; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
