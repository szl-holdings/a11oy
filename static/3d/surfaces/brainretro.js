// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainretro.js — BRAIN RETRO · the honest RETROSPECTIVE CALIBRATION record over the
// brain's OWN past answers. Every sibling brain-honesty surface answers one query in the present.
// This one looks BACK: it reads the append-only query-audit ledger (what the brain recorded it
// answered), re-runs the CURRENT grounding for those same queries, and compares. Of the past
// answers recorded as confident, how many are STILL grounded? Of the past abstentions, how many
// were justified (still ungrounded)? Pure knowledge-graph honesty/observability accounting; it
// advances NO detection / fusion / effector / targeting / cueing capability.
//
// NOT model training. NOT a reward signal. NOTHING is written back into any model or graph. NOT a
// claim of self-awareness, sentience, or consciousness — "self-honesty" here means exactly one
// mechanical thing: recompute-and-compare arithmetic over a recorded ledger.
//
// THE HONEST CAVEAT: the query-audit ledger is EPHEMERAL (in-memory, reset on every process
// restart). On a freshly started Space there is no history to calibrate against, so this surface
// honestly reads INSUFFICIENT-HISTORY — that is the expected state, not a failure, and it is
// stated plainly rather than dressed up as a persistent audit history.
//
// RENDER: one PILLAR per sampled past ledger entry, in a ring, coloured by its VERBATIM
// classification — CONFIRMED (proof-teal), DRIFTED (violet-blue, drawn tallest so a drift can
// never hide), STALE-UNKNOWN (grey stub, never a fabricated pass). A CORE orb carries the overall
// verdict WELL-CALIBRATED / DRIFT-DETECTED / INSUFFICIENT-HISTORY. The core is NEVER teal while
// any pillar is violet.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/retro (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, history_entries, ledger_status,
//   entries[]{ seq, classification (CONFIRMED|DRIFTED|STALE-UNKNOWN), drift_direction },
//   summary{ sampled, confirmed, drifted, stale_unknown, comparable, drift_over_claim,
//            drift_over_caution, min_history_required },
//   calibration{ calibration_rate, modeled_calibration, confident_recorded,
//                confident_still_grounded, confident_confirmed_rate, abstentions_recorded,
//                abstentions_still_justified, abstention_justified_rate },
//   doctrine{ locked_proven, lambda, trust_ceiling }.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived comparison view,
//   never a live measurement of semantic truth). Per-entry classifications are read VERBATIM; a
//   DRIFTED entry is drawn as drift, a STALE-UNKNOWN one as grey. A null rate renders "—", never
//   0.0 and never 1.0 by default. No green "1.0 / VERIFIED" state. Trust ceiling 0.97, never 100%.
// COLOURS (approved palette only, no green): proof-teal 0x3af4c8 (WELL-CALIBRATED / CONFIRMED),
//   lattice-blue 0x5b8dee (INSUFFICIENT-HISTORY / frame), violet-blue 0x8a6bff (DRIFT-DETECTED /
//   DRIFTED), grey 0x42505d (STALE-UNKNOWN / init). No amber, no crimson, no other purple.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: OBSERVES only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @
//   c7c0ba17; Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error.

import { createShowcase } from "./_showcase.js";

const ID    = "brainretro";
const TITLE = "Brain Retro · retrospective calibration of the brain's own past answers (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ calibration endpoint.
const EP = "/api/a11oy/v1/brain/retro";

// verdict / classification hues — approved palette only, no green
const C_OK      = 0x3af4c8;  // proof-teal   — WELL-CALIBRATED / CONFIRMED
const C_MID     = 0x5b8dee;  // lattice-blue — INSUFFICIENT-HISTORY / frame
const C_DRIFT   = 0x8a6bff;  // violet-blue  — DRIFT-DETECTED / DRIFTED
const C_NEUTRAL = 0x42505d;  // grey         — STALE-UNKNOWN / init
const C_GRID    = 0x1b3a44;  // floor colour

// overall verdict -> core colour
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "WELL-CALIBRATED")      return C_OK;
  if (s === "DRIFT-DETECTED")       return C_DRIFT;
  if (s === "INSUFFICIENT-HISTORY") return C_MID;
  return C_NEUTRAL;                       // init / unknown
}
// per-entry classification -> pillar colour (VERBATIM; drift is never softened to confirmation)
function _clsColor(c) {
  const s = String(c || "").toUpperCase();
  if (s === "CONFIRMED")     return C_OK;
  if (s === "DRIFTED")       return C_DRIFT;
  if (s === "STALE-UNKNOWN") return C_NEUTRAL;
  return C_NEUTRAL;
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _core = null;             // THREE.Mesh — the verdict core orb
let _pillars = [];            // Array<{ mesh, seq, cls }>
let _spin = 0;

// live state (all read from JSON; nothing invented)
const S = {
  label:     null,  // top honesty label VERBATIM (MODELED)
  verdict:   null,  // WELL-CALIBRATED | DRIFT-DETECTED | INSUFFICIENT-HISTORY
  ledger:    null,  // ledger_status VERBATIM (READ | UNAVAILABLE)
  history:   null,  // recorded entries in the ephemeral ledger
  sampled:   null,
  confirmed: null,
  drifted:   null,
  stale:     null,
  comparable: null,
  overClaim:  null,
  overCaution: null,
  minReq:    null,
  rate:      null,  // raw honest count ratio (null = nothing comparable)
  modeled:   null,  // the same ratio capped at the 0.97 trust ceiling
  confRec:   null,
  confOk:    null,
  confRate:  null,
  absRec:    null,
  absOk:     null,
  absRate:   null,
  entries:   [],    // [{ seq, cls, dir }]
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
  _polls.push(ctx.live.poll(EP, 9000, _onData, {
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

  // lattice ring beneath the core — the retrospective timeline rail the past entries sit on
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

// Build (or rebuild) one PILLAR per sampled past ledger entry, in a ring, coloured by the VERBATIM
// classification. Called on each live snapshot so the ring always mirrors the CURRENT feed. An
// empty ephemeral ledger legitimately yields NO pillars — the honest INSUFFICIENT-HISTORY picture.
function _buildPillars() {
  const THREE = _THREE;
  _disposePillars();

  const rows = Array.isArray(S.entries) ? S.entries : [];
  const n = rows.length;
  if (!n) return;
  const R = 5.0;
  const geo = new THREE.BoxGeometry(0.72, 1.0, 0.72);

  for (let i = 0; i < n; i++) {
    const row = rows[i];
    const cls = String(row.cls || "").toUpperCase();
    const color = _clsColor(cls);
    // A DRIFTED entry stands tallest (drift must not hide); STALE-UNKNOWN is a short honest stub.
    const h = cls === "DRIFTED" ? 4.6 : (cls === "CONFIRMED" ? 3.2 : 1.1);
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * R, z = Math.sin(a) * R;

    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.26,
      transparent: true, opacity: cls === "STALE-UNKNOWN" ? 0.42 : 0.92,
    }));
    mesh.scale.y = h;
    mesh.position.set(x, h / 2, z);
    _group.add(mesh);

    _pillars.push({ mesh, seq: row.seq, cls });
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
// live data handler — read VERBATIM, never upgrade, never fabricate a calibration rate
// =============================================================================
function _onData(j) {
  // Top honesty label VERBATIM; absent live data this surface is MODELED (a derived comparison).
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.ledger  = j && j.ledger_status ? String(j.ledger_status).toUpperCase() : null;
  S.history = typeof (j && j.history_entries) === "number" ? j.history_entries : null;

  const sm = (j && j.summary) || {};
  S.sampled    = typeof sm.sampled === "number" ? sm.sampled : null;
  S.confirmed  = typeof sm.confirmed === "number" ? sm.confirmed : null;
  S.drifted    = typeof sm.drifted === "number" ? sm.drifted : null;
  S.stale      = typeof sm.stale_unknown === "number" ? sm.stale_unknown : null;
  S.comparable = typeof sm.comparable === "number" ? sm.comparable : null;
  S.overClaim  = typeof sm.drift_over_claim === "number" ? sm.drift_over_claim : null;
  S.overCaution = typeof sm.drift_over_caution === "number" ? sm.drift_over_caution : null;
  S.minReq     = typeof sm.min_history_required === "number" ? sm.min_history_required : null;

  const cb = (j && j.calibration) || {};
  // null stays null — "nothing comparable" is rendered "—", never 0.0 and never 1.0.
  S.rate     = typeof cb.calibration_rate === "number" ? cb.calibration_rate : null;
  S.modeled  = typeof cb.modeled_calibration === "number" ? cb.modeled_calibration : null;
  S.confRec  = typeof cb.confident_recorded === "number" ? cb.confident_recorded : null;
  S.confOk   = typeof cb.confident_still_grounded === "number" ? cb.confident_still_grounded : null;
  S.confRate = typeof cb.confident_confirmed_rate === "number" ? cb.confident_confirmed_rate : null;
  S.absRec   = typeof cb.abstentions_recorded === "number" ? cb.abstentions_recorded : null;
  S.absOk    = typeof cb.abstentions_still_justified === "number" ? cb.abstentions_still_justified : null;
  S.absRate  = typeof cb.abstention_justified_rate === "number" ? cb.abstention_justified_rate : null;

  const rows = Array.isArray(j && j.entries) ? j.entries : [];
  S.entries = rows.map((e) => ({
    seq: typeof e.seq === "number" ? e.seq : null,
    cls: e && e.classification ? String(e.classification).toUpperCase() : "STALE-UNKNOWN",
    dir: e && e.drift_direction ? String(e.drift_direction).toUpperCase() : null,
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
    const head = Math.floor(_spin * _pillars.length);
    for (let i = 0; i < _pillars.length; i++) {
      const p = _pillars[i];
      const near = i === head;
      // a DRIFTED pillar always glows hot (drift must never hide); others follow the sweep.
      const drift = p.cls === "DRIFTED";
      const base = drift ? 0.6 : (p.cls === "CONFIRMED" && live ? 0.26 : 0.12);
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
    chips: [{ label: "MODELED", text: "calibration", name: "lbl" },
            { label: "—", text: "verdict", name: "vrd" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'The brain looking <b>backwards at itself</b>. Every other honesty surface answers one ' +
    'question in the present; this one takes the queries the brain already answered (from the ' +
    'append-only <b>query-audit ledger</b>), <b>re-runs the grounding now</b>, and compares. Of ' +
    'the answers it recorded as confident, how many are <b>still grounded</b>? Of the times it ' +
    '<b>abstained</b>, was the abstention justified (still ungrounded)? Each past entry comes ' +
    'back <b>CONFIRMED</b>, <b>DRIFTED</b> (the recorded posture no longer holds — a real ' +
    'honesty risk when it was an over-claim), or <b>STALE-UNKNOWN</b> (not recomputable — ' +
    'excluded, never assumed correct). This is calibration <i>accounting</i>: not model ' +
    'training, not a reward signal, and no claim of self-awareness. ' +
    '<b>Honest caveat:</b> the ledger is <b>ephemeral</b> (in-memory, reset on restart), so a ' +
    'freshly started Space truthfully reads <b>INSUFFICIENT-HISTORY</b> — expected, not a fault. ' +
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
  grid.appendChild(kpiRow("br-verdict",  "verdict"));
  grid.appendChild(kpiRow("br-ledger",   "ledger (ephemeral)"));
  grid.appendChild(kpiRow("br-history",  "recorded entries"));
  grid.appendChild(kpiRow("br-sampled",  "sampled / comparable"));
  grid.appendChild(kpiRow("br-ok",       "confirmed"));
  grid.appendChild(kpiRow("br-drift",    "drifted (over-claim / over-caution)"));
  grid.appendChild(kpiRow("br-stale",    "stale-unknown (excluded)"));
  grid.appendChild(kpiRow("br-rate",     "calibration rate"));
  grid.appendChild(kpiRow("br-conf",     "confident still grounded"));
  grid.appendChild(kpiRow("br-abs",      "abstentions still justified"));
  grid.appendChild(kpiRow("br-locked",   "locked proofs"));
  grid.appendChild(kpiRow("br-ceil",     "trust ceiling"));
  grid.appendChild(kpiRow("br-lambda",   "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> WELL-CALIBRATED / CONFIRMED &nbsp; ' +
    '<span style="color:#5b8dee">■</span> INSUFFICIENT-HISTORY &nbsp; ' +
    '<span style="color:#8a6bff">■</span> DRIFT-DETECTED / DRIFTED &nbsp; ' +
    '<span style="color:#8494a1">■</span> STALE-UNKNOWN. ' +
    'MODELED · classifications read verbatim · a null rate shows “—”, never 0.0 and never 1.0.';
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
  pd.id = "br-plain";
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
    "<b>What this means:</b> most systems grade themselves on the answer they are giving " +
    "<i>right now</i>. This one goes back and <b>checks its own homework</b>. It keeps a list of " +
    "the questions it was asked and what it said, then asks the same questions again today and " +
    "compares. If it sounded sure and the evidence still holds, that entry is " +
    "<b>CONFIRMED</b>. If it sounded sure and the evidence no longer holds, that is " +
    "<b>DRIFTED</b> — the uncomfortable case, and it is shown, not buried. If it said “I don’t " +
    "know” and still doesn’t, that counts as a <b>justified</b> refusal, which is a win, not a " +
    "failure. Anything it cannot re-check is marked <b>STALE-UNKNOWN</b> and left out of the " +
    "score entirely — it will never quietly count an unverified old answer as correct. " +
    "<b>One important honesty note:</b> that list of past questions lives in memory only and is " +
    "wiped whenever the service restarts. So on a fresh start there is nothing to grade and this " +
    "reads <b>INSUFFICIENT-HISTORY</b>. That is the truthful answer, not a bug — it would be " +
    "easy to show a flattering number here instead, and that is exactly what it refuses to do. " +
    "None of this is training or self-awareness; it is bookkeeping. No “verified / 1.0” state; " +
    "confidence is capped at 0.97, never 100%.";
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
    _show.setChip("lbl", S.label || "MODELED", { text: "calibration" });
    _show.setChip("vrd", headline, { text: "verdict" });
  }
  _set("br-verdict", t || (S.verdict || "—"));
  _set("br-ledger",  t || (S.ledger || "—"));
  _set("br-history", t || (S.history != null
    ? S.history + (S.minReq != null ? " (min " + S.minReq + ")" : "") : "—"));
  _set("br-sampled", t || (S.sampled != null && S.comparable != null
    ? S.sampled + " / " + S.comparable : _n(S.sampled)));
  _set("br-ok",      t || _n(S.confirmed));
  _set("br-drift",   t || (S.drifted != null
    ? S.drifted + " (" + _n(S.overClaim) + " / " + _n(S.overCaution) + ")" : "—"));
  _set("br-stale",   t || _n(S.stale));
  _set("br-rate",    t || (S.rate != null
    ? String(S.rate) + (S.modeled != null ? " (capped " + S.modeled + ")" : "") : "—"));
  _set("br-conf",    t || (S.confRec != null
    ? _n(S.confOk) + " / " + S.confRec + (S.confRate != null ? "  (" + S.confRate + ")" : "")
    : "—"));
  _set("br-abs",     t || (S.absRec != null
    ? _n(S.absOk) + " / " + S.absRec + (S.absRate != null ? "  (" + S.absRate + ")" : "")
    : "—"));
  _set("br-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("br-ceil",    t || (S.trustCeil != null ? String(S.trustCeil) : "—"));
  _set("br-lambda",  t || (S.lambda || "—"));
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
  S.label = S.verdict = S.ledger = S.history = null;
  S.sampled = S.confirmed = S.drifted = S.stale = S.comparable = null;
  S.overClaim = S.overCaution = S.minReq = null;
  S.rate = S.modeled = null;
  S.confRec = S.confOk = S.confRate = null;
  S.absRec = S.absOk = S.absRate = null;
  S.entries = [];
  S.trustCeil = S.lambda = S.locked = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
