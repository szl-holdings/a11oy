// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainconstitution.js — BRAIN CONSTITUTION · the honest ruleset the brain is graded
// against on every query. The capstone over the brain-honesty surfaces: it renders an explicit
// ARTICLE ring — one PILLAR per Article the brain must honour (grounding sufficiency, calibrated
// confidence, honest corroboration, contradictions surfaced, traceable to source, freshness
// honesty, coverage gaps admitted, doctrine invariants) — and grades each COMPLIANT / VIOLATED /
// UNAVAILABLE. A CORE orb carries the overall verdict CONSTITUTIONAL / IN-VIOLATION /
// INSUFFICIENT-SIGNAL. Pure knowledge-graph honesty/governance; it advances NO detection / fusion
// / effector / targeting / cueing capability.
//
// A VIOLATED Article is drawn plainly (violet), never dressed up as compliance; an UNAVAILABLE
// Article (its sibling surface not importable this request) reads grey, never a fabricated pass.
// The core is NEVER teal ("CONSTITUTIONAL") while any pillar is violet ("VIOLATED").
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/constitution (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, modeled_compliance,
//   articles[]{ article, title, result (COMPLIANT|VIOLATED|UNAVAILABLE), evaluable },
//   summary{ articles_total, articles_evaluable, compliant, violated, unavailable,
//            violated_articles, min_articles_required },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived compliance verdict,
//   not a measurement). The per-Article results it renders are read VERBATIM; no compliance is
//   fabricated — a VIOLATED Article is drawn as a violation, an UNAVAILABLE one as grey. No green
//   "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (CONSTITUTIONAL / COMPLIANT),
//   lattice-blue 0x5b8dee (INSUFFICIENT-SIGNAL / frame), violet-blue 0x8a6bff (IN-VIOLATION /
//   VIOLATED), grey 0x42505d (UNAVAILABLE / init). No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainconstitution";
const TITLE = "Brain Constitution · the honest ruleset the brain is graded against (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ compliance endpoint.
const EP = "/api/a11oy/v1/brain/constitution";

// verdict / result hues — approved palette only, no green
const C_OK       = 0x3af4c8;  // proof-teal   — CONSTITUTIONAL / COMPLIANT
const C_MID      = 0x5b8dee;  // lattice-blue — INSUFFICIENT-SIGNAL / frame
const C_VIOL     = 0x8a6bff;  // violet-blue  — IN-VIOLATION / VIOLATED
const C_NEUTRAL  = 0x42505d;  // grey         — UNAVAILABLE / init
const C_GRID     = 0x1b3a44;  // floor colour

// overall verdict -> core colour
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "CONSTITUTIONAL")      return C_OK;
  if (s === "IN-VIOLATION")        return C_VIOL;
  if (s === "INSUFFICIENT-SIGNAL") return C_MID;
  return C_NEUTRAL;                       // init / unknown
}
// per-Article result -> pillar colour (VERBATIM; a violation is never softened to compliance)
function _resultColor(r) {
  const s = String(r || "").toUpperCase();
  if (s === "COMPLIANT")   return C_OK;
  if (s === "VIOLATED")    return C_VIOL;
  if (s === "UNAVAILABLE") return C_NEUTRAL;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the verdict core orb
let _pillars = [];            // Array<{ mesh, n, result }>
let _spin = 0;

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,  // top honesty label VERBATIM (MODELED)
  verdict:   null,  // CONSTITUTIONAL | IN-VIOLATION | INSUFFICIENT-SIGNAL
  compliance: null, // MODELED ratio in [0,0.97], never MEASURED, never 1.0
  total:     null,
  evaluable: null,
  compliant: null,
  violated:  null,
  unavailable: null,
  violatedArts: [],
  minReq:    null,
  articles:  [],    // [{ n, result }]
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
  _stage.camera.position.set(0, 5.0, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.2, 0); _stage.controls.update(); } } catch (_) {}
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
  _core.position.set(0, 4.6, 0);
  _group.add(_core);

  // lattice ring beneath the core (the constitution base rail)
  const pts = [];
  const R = 5.6;
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

// Build (or rebuild) one PILLAR per Article, in a ring; colour by the VERBATIM per-Article result,
// height a fixed governance column (an Article is a rule, not a magnitude). Called on each live
// snapshot so the ring always mirrors the CURRENT feed (never a hard-coded Article set).
function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();

  const arts = Array.isArray(S.articles) ? S.articles : [];
  const n = arts.length;
  if (!n) return;
  const R = 5.0;
  const geo = new THREE.BoxGeometry(0.8, 1.0, 0.8);

  for (let i = 0; i < n; i++) {
    const art = arts[i];
    const result = String(art.result || "").toUpperCase();
    const color = _resultColor(result);
    // VIOLATED pillars stand tallest (they must not hide); UNAVAILABLE are short stubs (honest).
    const h = result === "VIOLATED" ? 4.6 : (result === "COMPLIANT" ? 3.4 : 1.2);
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: result === "UNAVAILABLE" ? 0.42 : 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, z);
    _group.add(mesh);

    _pillars.push({ mesh, n: art.n, result });
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
// live data handler — read VERBATIM, never upgrade, never fabricate compliance
// =============================================================================
function _onData(j) {
  // Top honesty label VERBATIM; absent live data this surface is MODELED (a derived verdict).
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.compliance = (j && typeof j.modeled_compliance === "number") ? j.modeled_compliance : null;

  const sm = (j && j.summary) || {};
  S.total     = typeof sm.articles_total === "number" ? sm.articles_total : null;
  S.evaluable = typeof sm.articles_evaluable === "number" ? sm.articles_evaluable : null;
  S.compliant = typeof sm.compliant === "number" ? sm.compliant : null;
  S.violated  = typeof sm.violated === "number" ? sm.violated : null;
  S.unavailable = typeof sm.unavailable === "number" ? sm.unavailable : null;
  S.violatedArts = Array.isArray(sm.violated_articles) ? sm.violated_articles : [];
  S.minReq    = typeof sm.min_articles_required === "number" ? sm.min_articles_required : null;

  const arts = Array.isArray(j && j.articles) ? j.articles : [];
  S.articles = arts.map((a) => ({
    n: typeof a.article === "number" ? a.article : null,
    result: a && a.result ? String(a.result).toUpperCase() : "UNAVAILABLE",
  }));

  const d = (j && j.doctrine) || {};
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;

  _buildPillars();
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
  if (_pillars.length) {
    _spin = (t * 0.0002) % 1;
    const lead = Math.floor(_spin * _pillars.length);
    for (let i = 0; i < _pillars.length; i++) {
      const p = _pillars[i];
      const near = i === lead;
      // a VIOLATED pillar always glows hot (a violation must never hide); others follow the sweep.
      const viol = p.result === "VIOLATED";
      const base = viol ? 0.6 : (p.result === "COMPLIANT" && live ? 0.26 : 0.12);
      p.mesh.material.emissiveIntensity = (near && live) ? Math.max(base, 0.85) : base;
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
    chips: [{ label: "MODELED", text: "compliance", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The brain’s explicit, machine-checkable <b>constitution</b>: an ordered set of ' +
    '<b>ARTICLES</b> it must honour on every query — never answer when grounding is ' +
    'insufficient, never claim confident when uncertainty is high, disclose single-source claims, ' +
    'surface contradictions, keep every answer traceable, flag stale knowledge, admit coverage ' +
    'gaps, and keep the doctrine invariants (Λ stays Conjecture 1, locked-8, trust 0.97). ' +
    'Each Article is graded <b>COMPLIANT / VIOLATED / UNAVAILABLE</b> against whatever sibling ' +
    'honesty surfaces are importable; an absent surface reads <b>UNAVAILABLE</b>, never a ' +
    'fabricated pass. The estate is <b>never CONSTITUTIONAL while any evaluable Article is ' +
    'VIOLATED</b>. Strictly knowledge-graph honesty/governance. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bc-verdict",  "verdict"));
  grid.appendChild(kpiRow("bc-compl",    "modeled compliance"));
  grid.appendChild(kpiRow("bc-articles", "articles (evaluable/total)"));
  grid.appendChild(kpiRow("bc-ok",       "compliant"));
  grid.appendChild(kpiRow("bc-viol",     "violated"));
  grid.appendChild(kpiRow("bc-unavail",  "unavailable"));
  grid.appendChild(kpiRow("bc-violarts", "violated articles"));
  grid.appendChild(kpiRow("bc-locked",   "locked proofs"));
  grid.appendChild(kpiRow("bc-ceil",     "trust ceiling"));
  grid.appendChild(kpiRow("bc-lambda",   "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> CONSTITUTIONAL / COMPLIANT &nbsp; ' +
    '<span style="color:#5b8dee">■</span> INSUFFICIENT-SIGNAL &nbsp; ' +
    '<span style="color:#8a6bff">■</span> IN-VIOLATION / VIOLATED &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNAVAILABLE. ' +
    'MODELED · per-Article results read verbatim · compliance is never fabricated (a VIOLATION is a VIOLATION).';
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
    "<b>What this means:</b> the brain has a written <b>rulebook</b> — a constitution — " +
    "and this surface grades it against that rulebook on every question. The rules are common " +
    "sense: don’t answer if you don’t really know, don’t sound sure when you " +
    "aren’t, say when a claim rests on a single source, surface disagreements instead of " +
    "quietly picking a side, keep every answer traceable to where it came from, flag stale facts, " +
    "and admit what it doesn’t cover. Each rule comes back <b>COMPLIANT</b>, <b>VIOLATED</b>, " +
    "or <b>UNAVAILABLE</b> (the checker for that rule isn’t wired in this build — shown " +
    "honestly, never faked as a pass). If <b>any</b> rule is broken, the whole thing reads " +
    "<b>IN-VIOLATION</b> — it will never call itself compliant while a rule is broken. No " +
    "“verified / 1.0” state; confidence is capped at 0.97, never 100%.";
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
    _show.setChip("lbl", S.label || "MODELED", { text: "compliance" });
    _show.setChip("vrd", headline, { text: "verdict" });
  }
  _set("bc-verdict", t || (S.verdict || "—"));
  _set("bc-compl",   t || (S.compliance != null ? String(S.compliance) : "—"));
  _set("bc-articles", t || (S.evaluable != null && S.total != null
    ? S.evaluable + " / " + S.total : _n(S.total)));
  _set("bc-ok",      t || _n(S.compliant));
  _set("bc-viol",    t || _n(S.violated));
  _set("bc-unavail", t || _n(S.unavailable));
  _set("bc-violarts", t || (S.violatedArts && S.violatedArts.length
    ? S.violatedArts.map((n) => "Art" + n).join(", ") : "none"));
  _set("bc-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bc-ceil",    t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("bc-lambda",  t || (S.lambda || "—"));
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
  S.label = S.verdict = S.compliance = null;
  S.total = S.evaluable = S.compliant = S.violated = S.unavailable = null;
  S.violatedArts = []; S.minReq = null; S.articles = [];
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
