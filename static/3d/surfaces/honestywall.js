// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/honestywall.js — HONESTY WALL · live "can this system lie right now?" integrity wall.
//
// A WALL of bricks, one region per honesty status, sized by the live count of surfaces in that
// status this request. A KEYSTONE at the top carries the estate's single verdict — INTACT /
// DEGRADED / VIOLATED — read VERBATIM from the aggregate. HONEST BY CONSTRUCTION: every value is
// read from the same-origin feed, which is derived live from the Frontier Index catalog (surface
// registry + registered routes + each surface's OWN response) — never a hand-maintained scorecard.
//
// DATA: live snapshot from GET /api/a11oy/v1/govern/honestywall/status (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, verdict_reason,
//   summary{ surfaces, surfaces_by_status{NATIVE-OK,UNKNOWN,NO-MANIFEST,...}, label_counts,
//            invariants_satisfied, invariants_violated, reachable_violations, unknown_surfaces },
//   doctrine{ lambda, locked_proven, trust_ceiling, trust_100_percent, adds_to_locked_8 }.
//
// VISUALIZES:
//   1. a KEYSTONE plate whose colour is the verdict (teal INTACT / amber DEGRADED / red VIOLATED).
//   2. a WALL of bricks below it — one column per surface-status, height by count. The wall reads
//      solid (integrity) when INTACT, and a status region pulses red the instant it holds a
//      reachable violation.
//   3. a scanning sweep that travels the wall so the feed reads as a living, watched surface.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived aggregate digest, not
//   a measurement). Per-surface labels are read VERBATIM and NEVER upgraded. The verdict is NEVER
//   INTACT if anything is violated. No green "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS: proof-teal 0x3af4c8 (intact/native-ok), amber 0xf4b23a (degraded/unknown), crimson
//   0xff5964 (violated), grey 0x42505d (no-manifest/client-only), lattice-blue 0x5b8dee (frame).
//   PURPLE BANNED (except 0x8a6bff, unused here). No green.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "honestywall";
const TITLE = "Honesty Wall · can this system lie right now? (live, drift-proof)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ status endpoint.
const EP = "/api/a11oy/v1/govern/honestywall/status";

// verdict / status hues — purple BANNED, no green
const C_INTACT   = 0x3af4c8;  // proof-teal   — INTACT / native-ok
const C_DEGRADED = 0xf4b23a;  // amber        — DEGRADED / unknown
const C_VIOLATED = 0xff5964;  // crimson      — VIOLATED
const C_NEUTRAL  = 0x42505d;  // grey         — no-manifest / client-only
const C_FRAME    = 0x5b8dee;  // lattice-blue — wall frame
const C_GRID     = 0x1b3a44;  // floor colour

// map an honest status token -> a brick colour
function _statusColor(status) {
  const s = String(status || "").toUpperCase();
  if (s === "NATIVE-OK" || s === "OK") return C_INTACT;
  if (s === "UNKNOWN")                  return C_DEGRADED;
  if (s === "VIOLATED")                 return C_VIOLATED;
  return C_NEUTRAL;                     // NO-MANIFEST / anything else
}
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "INTACT")   return C_INTACT;
  if (s === "VIOLATED") return C_VIOLATED;
  return C_DEGRADED;                    // DEGRADED / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _keystone = null;         // THREE.Mesh — the verdict keystone
let _columns = [];            // Array<{ mesh, status, count, violated }>
let _sweep = 0;               // scanning-sweep phase

// live state (all read from JSON; nothing invented)
const S = {
  label:    null,   // top honesty label VERBATIM (MODELED)
  verdict:  null,   // INTACT | DEGRADED | VIOLATED
  reason:   null,
  surfaces: null,
  byStatus: {},     // { "NATIVE-OK": n, "UNKNOWN": n, "VIOLATED": n, ... }
  satisfied:null,
  violated: null,
  reachV:   null,   // reachable_violations
  unknown:  null,
  trustCeil:null,
  lambda:   null,
  locked:   null,
  state:    "init",
};

// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 4.5, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.2, 0); _stage.controls.update(); } } catch (_) {}
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
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildKeystone() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(6.4, 1.2, 0.6);
  _keystone = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_DEGRADED, emissive: C_DEGRADED, emissiveIntensity: 0.35,
    transparent: true, opacity: 0.9,
  }));
  _keystone.position.set(0, 6.2, 0);
  _group.add(_keystone);

  // lattice frame beneath the keystone (the wall's top rail)
  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-6, 5.4, 0), new THREE.Vector3(6, 5.4, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_FRAME, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// Build (or rebuild) one column per surface-status, height by count. Called on each live
// snapshot so the wall always mirrors the CURRENT feed (never a stale hard-coded set).
function _buildColumns() {
  const THREE = _THREE;
  _disposeColumns();

  const entries = Object.keys(S.byStatus).map((k) => [k, S.byStatus[k]])
    .filter((e) => typeof e[1] === "number" && e[1] > 0);
  const n = entries.length;
  if (!n) return;

  const maxCount = entries.reduce((m, e) => Math.max(m, e[1]), 1);
  const totalW = 11.0;
  const step = n > 1 ? totalW / n : 0;
  const startX = -totalW / 2 + step / 2;
  const brickGeo = new THREE.BoxGeometry(Math.min(1.6, step * 0.8), 1.0, 0.9);

  for (let i = 0; i < n; i++) {
    const [status, count] = entries[i];
    const color = _statusColor(status);
    const violated = String(status).toUpperCase() === "VIOLATED";
    const h = 0.6 + (count / maxCount) * 4.2;   // height by share
    const x = startX + step * i;

    const mesh = new THREE.Mesh(brickGeo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.28, transparent: true, opacity: 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, 0);
    _group.add(mesh);

    _columns.push({ mesh, status, count, violated });
  }
}

function _disposeColumns() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _columns.forEach((c) => rm(c.mesh));
  _columns = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.reason  = j && j.verdict_reason ? String(j.verdict_reason) : null;

  const sm = (j && j.summary) || {};
  S.surfaces  = typeof sm.surfaces === "number" ? sm.surfaces : null;
  S.byStatus  = (sm.surfaces_by_status && typeof sm.surfaces_by_status === "object") ? sm.surfaces_by_status : {};
  S.satisfied = typeof sm.invariants_satisfied === "number" ? sm.invariants_satisfied : null;
  S.violated  = typeof sm.invariants_violated === "number" ? sm.invariants_violated : null;
  S.reachV    = typeof sm.reachable_violations === "number" ? sm.reachable_violations : null;
  S.unknown   = typeof sm.unknown_surfaces === "number" ? sm.unknown_surfaces : null;

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildColumns();
  _paintKeystone();
  _paintOverlay();
  _paintList();
}

// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00005) * 0.08;

  const live = S.state === "live";
  if (_keystone) {
    const pulse = 0.35 + (live ? 0.25 : 0.08) * (0.5 + 0.5 * Math.sin(t * 0.003));
    _keystone.material.emissiveIntensity = pulse;
  }
  if (_columns.length) {
    _sweep = (t * 0.0002) % 1;
    const lead = Math.floor(_sweep * _columns.length);
    for (let i = 0; i < _columns.length; i++) {
      const c = _columns[i];
      const near = Math.abs(i - lead) <= 0;
      // a violated region always glows hot; others follow the sweep when live.
      const base = c.violated ? 0.6 : (live ? 0.28 : 0.12);
      c.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.85) : base;
      c.mesh.material.opacity = live ? 0.92 : 0.4;
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
    chips: [{ label: "MODELED", text: "integrity", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'A live integrity wall answering one question: <b>can this system lie right now?</b> For every ' +
    'registered surface it reads that surface’s <b>own</b> honest data label <b>VERBATIM</b> and the ' +
    'estate’s honesty invariants (locked-8 exact, Λ = Conjecture 1 <b>not</b> a theorem, trust ceiling ' +
    '≤ 0.97, no consciousness claim, writer ≠ judge), then rolls them into ONE verdict — ' +
    '<b>INTACT / DEGRADED / VIOLATED</b>. <b>Never INTACT if anything is violated</b>; labels are ' +
    'never upgraded. Honest by construction — derived live from the Frontier Index, never a ' +
    'hand-maintained scorecard. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("hw-verdict", "verdict"));
  grid.appendChild(kpiRow("hw-surf",    "surfaces observed"));
  grid.appendChild(kpiRow("hw-sat",     "invariants satisfied"));
  grid.appendChild(kpiRow("hw-viol",    "invariants violated"));
  grid.appendChild(kpiRow("hw-reach",   "reachable violations"));
  grid.appendChild(kpiRow("hw-unk",     "UNKNOWN this request"));
  grid.appendChild(kpiRow("hw-locked",  "locked proofs"));
  grid.appendChild(kpiRow("hw-trust",   "trust ceiling"));
  grid.appendChild(kpiRow("hw-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable per-status list (text mirror of the wall).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:170px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> native-ok / INTACT &nbsp; ' +
    '<span style="color:#f4b23a">■</span> UNKNOWN / degraded &nbsp; ' +
    '<span style="color:#ff5964">■</span> VIOLATED &nbsp; ' +
    '<span style="color:#8494a1">■</span> no-manifest. ' +
    'MODELED · labels read verbatim, never upgraded · never INTACT if violated.';
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
  pd.id = "hw-plain";
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
    "<b>What this means:</b> a single, honest read on whether the platform is currently telling the " +
    "truth about itself. It walks every live feature, reads that feature’s <b>own</b> honesty label " +
    "word-for-word, and checks the house rules (only 8 proofs are locked; Λ is a conjecture, not a " +
    "proven theorem; confidence is capped at 0.97, never 100%). If everything holds it reads " +
    "<b>INTACT</b>; if some features couldn’t be reached it reads <b>DEGRADED</b>; and if even one " +
    "rule is broken it reads <b>VIOLATED</b> — it can <b>never</b> claim INTACT while something is " +
    "wrong. Because the wall is generated from the running app itself, it cannot quietly disagree " +
    "with what is actually wired. No “verified / 1.0” state.";
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
  const keys = Object.keys(S.byStatus).sort();
  keys.forEach((k) => {
    const count = S.byStatus[k];
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:66%";
    left.textContent = k;
    const val = document.createElement("b");
    const hex = "#" + _statusColor(k).toString(16).padStart(6, "0");
    val.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums";
    val.textContent = String(count);
    row.appendChild(left); row.appendChild(val);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "integrity" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("hw-verdict", vrd + (S.reason && S.state === "live" ? "" : ""));
  _set("hw-surf",   t || _n(S.surfaces));
  _set("hw-sat",    t || _n(S.satisfied));
  _set("hw-viol",   t || _n(S.violated));
  _set("hw-reach",  t || _n(S.reachV));
  _set("hw-unk",    t || _n(S.unknown));
  _set("hw-locked", t || (S.locked != null ? String(S.locked) : "—"));
  _set("hw-trust",  t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("hw-lambda", t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeColumns();
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
  _keystone = null; _columns = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false; _sweep = 0;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.reason = null;
  S.surfaces = S.satisfied = S.violated = S.reachV = S.unknown = null;
  S.byStatus = {};
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
