// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainhealth.js — BRAIN HEALTH · live "can the brain be trusted for this query
// right now?" rollup. The brain's equivalent of the Honesty Wall, scoped STRICTLY to
// knowledge-graph honesty — it advances no detection / fusion / effector / targeting capability.
//
// A ring of PILLARS, one per brain-honesty component (grounding, freshness, provenance,
// contradiction, uncertainty). Each pillar's height is its component's numeric value; its
// colour is its honesty signal, read VERBATIM from that component's OWN response. A CORE orb at
// the centre carries the single rollup verdict — TRUSTWORTHY / DEGRADED / UNTRUSTWORTHY /
// INSUFFICIENT-SIGNAL. HONEST BY CONSTRUCTION: every value is read from the same-origin feed
// derived live from the AVAILABLE sibling surfaces; a sibling not present is drawn GREY
// (UNAVAILABLE), never fabricated.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/health (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, verdict_reason, modeled_trust,
//   summary{ components_total, components_available, components_unavailable,
//            available_keys, unavailable_keys, signals, adverse },
//   components[]{ key, title, available, label, value, signal, adverse_reason },
//   doctrine{ lambda, locked_proven, trust_ceiling, trust_100_percent, adds_to_locked_8 }.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived rollup digest, not
//   a measurement). Per-component labels are read VERBATIM and NEVER upgraded. The verdict is
//   NEVER TRUSTWORTHY if any available component abstains / is insufficient / conflict-flagged /
//   stale-dominant. No green "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (trustworthy / OK), lattice-blue
//   0x5b8dee (degraded / indeterminate / frame), violet-blue 0x8a6bff (untrustworthy / adverse),
//   grey 0x42505d (unavailable / insufficient). No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainhealth";
const TITLE = "Brain Health · can the brain be trusted for this query right now? (live rollup)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ rollup endpoint.
const EP = "/api/a11oy/v1/brain/health";

// signal / verdict hues — approved palette only, no green
const C_OK       = 0x3af4c8;  // proof-teal   — TRUSTWORTHY / signal OK
const C_DEGRADED = 0x5b8dee;  // lattice-blue — DEGRADED / INDETERMINATE / frame
const C_ADVERSE  = 0x8a6bff;  // violet-blue  — UNTRUSTWORTHY / adverse signal
const C_NEUTRAL  = 0x42505d;  // grey         — UNAVAILABLE / INSUFFICIENT-SIGNAL
const C_GRID     = 0x1b3a44;  // floor colour

// map an honest per-component signal token -> a pillar colour
function _signalColor(available, signal) {
  if (!available) return C_NEUTRAL;
  const s = String(signal || "").toUpperCase();
  if (s === "OK")       return C_OK;
  if (s === "ADVERSE")  return C_ADVERSE;
  return C_DEGRADED;                     // INDETERMINATE / unknown
}
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "TRUSTWORTHY")   return C_OK;
  if (s === "UNTRUSTWORTHY") return C_ADVERSE;
  if (s === "DEGRADED")      return C_DEGRADED;
  return C_NEUTRAL;                       // INSUFFICIENT-SIGNAL / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the rollup-verdict core orb
let _pillars = [];            // Array<{ mesh, key, available, signal }>
let _spin = 0;

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,   // top honesty label VERBATIM (MODELED)
  verdict:   null,   // TRUSTWORTHY | DEGRADED | UNTRUSTWORTHY | INSUFFICIENT-SIGNAL
  reason:    null,
  trust:     null,   // modeled_trust (<= 0.97) or null
  total:     null,
  avail:     null,
  unavail:   null,
  components: [],     // per-component entries, read verbatim
  trustCeil: null,
  lambda:    null,
  locked:    null,
  state:     "init",
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

  // lattice ring beneath the core (the rollup's base rail)
  const pts = [];
  const R = 5.2;
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * R, 0.02, Math.sin(a) * R));
  }
  const rg = new THREE.BufferGeometry().setFromPoints(pts);
  const ring = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_DEGRADED, transparent: true, opacity: 0.4,
  }));
  _group.add(ring);
}

// Build (or rebuild) one pillar per component, in a ring, height by value. Called on each
// live snapshot so the ring always mirrors the CURRENT feed (never a stale hard-coded set).
function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();

  const comps = Array.isArray(S.components) ? S.components : [];
  const n = comps.length;
  if (!n) return;

  const R = 4.6;
  const geo = new THREE.BoxGeometry(0.9, 1.0, 0.9);

  for (let i = 0; i < n; i++) {
    const c = comps[i] || {};
    const available = !!c.available;
    const signal = c.signal;
    const val = (typeof c.value === "number" && isFinite(c.value)) ? c.value : null;
    // height: by value when present, else a short "stub" so an UNAVAILABLE pillar still reads.
    const h = available && val != null ? 0.5 + Math.max(0, Math.min(1, val)) * 4.0 : 0.5;
    const color = _signalColor(available, signal);
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: available ? 0.92 : 0.4,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, z);
    _group.add(mesh);

    _pillars.push({ mesh, key: c.key, available, signal });
  }
}

function _disposePillars() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _pillars.forEach((p) => rm(p.mesh));
  _pillars = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.reason  = j && j.verdict_reason ? String(j.verdict_reason) : null;
  S.trust   = j && typeof j.modeled_trust === "number" ? j.modeled_trust : null;

  const sm = (j && j.summary) || {};
  S.total   = typeof sm.components_total === "number" ? sm.components_total : null;
  S.avail   = typeof sm.components_available === "number" ? sm.components_available : null;
  S.unavail = typeof sm.components_unavailable === "number" ? sm.components_unavailable : null;

  S.components = Array.isArray(j && j.components) ? j.components : [];

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildPillars();
  _paintCore();
  _paintOverlay();
  _paintList();
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
  if (_pillars.length) {
    _spin = (t * 0.0002) % 1;
    const lead = Math.floor(_spin * _pillars.length);
    for (let i = 0; i < _pillars.length; i++) {
      const p = _pillars[i];
      const near = i === lead;
      const adverse = String(p.signal || "").toUpperCase() === "ADVERSE";
      // an adverse pillar always glows hot; others follow the sweep when live.
      const base = adverse ? 0.6 : (p.available && live ? 0.26 : 0.12);
      p.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.85) : base;
    }
  }
}

// =============================================================================
function _paintCore() {
  if (!_core) return;
  const col = _verdictColor(S.state === "live" ? S.verdict : null);
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
    chips: [{ label: "MODELED", text: "brain trust", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A live rollup answering one question: <b>can the brain be trusted for this query right ' +
    'now?</b> For every brain-honesty surface it reads that surface’s <b>own</b> signal and ' +
    'honest label <b>VERBATIM</b> — grounding confidence, memory freshness, source provenance, ' +
    'contradiction flag, uncertainty — then rolls the <b>available</b> ones into ONE verdict: ' +
    '<b>TRUSTWORTHY / DEGRADED / UNTRUSTWORTHY / INSUFFICIENT-SIGNAL</b>. A sibling that isn’t ' +
    'present is drawn <b>UNAVAILABLE</b> (never fabricated). <b>Never TRUSTWORTHY</b> if any ' +
    'available component abstains / is insufficient / conflict-flagged / stale-dominant; labels ' +
    'are never upgraded. Strictly knowledge-graph honesty. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bh-verdict", "verdict"));
  grid.appendChild(kpiRow("bh-trust",   "modeled trust (≤0.97)"));
  grid.appendChild(kpiRow("bh-total",   "components total"));
  grid.appendChild(kpiRow("bh-avail",   "available"));
  grid.appendChild(kpiRow("bh-unavail", "UNAVAILABLE"));
  grid.appendChild(kpiRow("bh-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bh-ceil",    "trust ceiling"));
  grid.appendChild(kpiRow("bh-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable per-component list (text mirror of the ring).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:170px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> OK / TRUSTWORTHY &nbsp; ' +
    '<span style="color:#5b8dee">■</span> INDETERMINATE / degraded &nbsp; ' +
    '<span style="color:#8a6bff">■</span> adverse / UNTRUSTWORTHY &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNAVAILABLE. ' +
    'MODELED · labels read verbatim, never upgraded · never TRUSTWORTHY if any component abstains.';
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
  pd.id = "bh-plain";
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
    "<b>What this means:</b> a single, honest read on whether the brain can be trusted to answer " +
    "a given question right now. It checks the brain’s own honesty signals — is the answer " +
    "grounded, is the memory fresh, is the source traceable, is anything contradictory, how " +
    "uncertain is it — and reads each one word-for-word. If enough of those are present and all " +
    "look good it reads <b>TRUSTWORTHY</b>; if some couldn’t be reached it reads " +
    "<b>DEGRADED</b>; if even one says “I should abstain / this conflicts / this is stale” it " +
    "reads <b>UNTRUSTWORTHY</b>; and if too few signals are available at all it honestly says " +
    "<b>INSUFFICIENT-SIGNAL</b>. It can <b>never</b> claim TRUSTWORTHY while a signal is bad. " +
    "Confidence is capped at 0.97, never 100%. No “verified / 1.0” state.";
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
  (Array.isArray(S.components) ? S.components : []).forEach((c) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:58%";
    left.textContent = (c.key || "?") + " · " + (c.label || "UNAVAILABLE");
    const val = document.createElement("b");
    const hex = "#" + _signalColor(!!c.available, c.signal).toString(16).padStart(6, "0");
    val.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums";
    val.textContent = !c.available ? "UNAVAILABLE"
      : (c.signal || "—") + (typeof c.value === "number" ? " · " + c.value : "");
    row.appendChild(left); row.appendChild(val);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "brain trust" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bh-verdict", vrd);
  _set("bh-trust",   t || (S.trust != null ? String(S.trust) : "—"));
  _set("bh-total",   t || _n(S.total));
  _set("bh-avail",   t || _n(S.avail));
  _set("bh-unavail", t || _n(S.unavail));
  _set("bh-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bh-ceil",    t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bh-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposePillars();
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
  _core = null; _pillars = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _spin = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.reason = null;
  S.trust = S.total = S.avail = S.unavail = null;
  S.components = [];
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
