// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainprovenance.js — PER-ANSWER PROVENANCE LINEAGE. For a brain retrieval answer
// this surface renders the traceable CHAIN of exactly WHICH knowledge-graph nodes supported
// it: a vertical LINEAGE SPINE, one link per supporting node, ordered top→bottom by
// contribution (ppr), each link COLOURED by that node's OWN honest label read VERBATIM and
// SIZED by its contribution_weight. A KEYSTONE at the top carries the honest verdict —
// TRACEABLE / PARTIAL-PROVENANCE / UNTRACEABLE — read verbatim from the feed.
//
// This is SOURCE-LINEAGE provenance of an ANSWER only. It is NOT cryptographic model/weapon
// attestation, NOT SLSA/in-toto/Rekor build attestation, and NOT any counter-UAS capability.
//
// DATA: live snapshot from GET /api/a11oy/v1/brain/provenance?q=&k= (PURE READ, mints nothing):
//   ok, label (MODELED), verdict, verdict_reason, query, chain[{id,title,node_label,community,
//   contribution_weight}], coverage{harvested,modeled,unavailable,unlabelled,
//   fraction_traceable_to_source,...}, answer_label, doctrine{lambda,locked_proven,...}.
//
// HONESTY LABEL: MODELED — this surface's own top label is MODELED (a derived re-view of the
//   brain's own grounding, not a measurement). Per-node labels are read VERBATIM and NEVER
//   upgraded (a MODELED node is never shown as HARVESTED; UNAVAILABLE/unlabelled nodes are
//   never hidden). The verdict is NEVER TRACEABLE while any node is UNAVAILABLE/unlabelled.
//   Λ = Conjecture 1 → grey, never green/theorem. locked-proven = exactly 8. No green "1.0".
// COLOURS: proof-teal 0x3af4c8 (HARVESTED/LIVE source), lattice-blue 0x5b8dee (MODELED source
//   + spine frame), violet-blue 0x8a6bff (community accents), greys (UNAVAILABLE/unlabelled).
//   No green. 0 RUNTIME CDN — three.js via the page importmap (ctx.THREE).
// DOCTRINE v11: re-views only — adds NOTHING to the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22};
//   Λ stays Conjecture 1; introduces no theorem. Degrades grey on 404/error; label shown.

import { createShowcase } from "./_showcase.js";

const ID    = "brainprovenance";
const TITLE = "Brain Provenance · per-answer source-lineage chain (live)";

// same-origin, relative — no CDN, no cross-origin fetch. PURE-READ endpoint.
const DEFAULT_Q = "what proves the estate thesis";
const EP = "/api/a11oy/v1/brain/provenance?q=" + encodeURIComponent(DEFAULT_Q) + "&k=12";

// label / verdict hues — purple only the approved 0x8a6bff, no green
const C_HARVEST = 0x3af4c8;  // proof-teal   — HARVESTED / LIVE source
const C_MODELED = 0x5b8dee;  // lattice-blue — MODELED source
const C_COMM    = 0x8a6bff;  // violet-blue  — community accent
const C_UNAVAIL = 0x5a6570;  // grey         — UNAVAILABLE / unlabelled (never a source)
const C_FRAME   = 0x5b8dee;  // lattice-blue — spine frame
const C_GRID    = 0x1b3a44;  // floor colour

// map a VERBATIM node label -> a link colour (never upgraded)
function _labelColor(label) {
  const s = String(label || "").toUpperCase();
  if (s === "HARVESTED" || s === "LIVE") return C_HARVEST;
  if (s === "MODELED")                    return C_MODELED;
  return C_UNAVAIL;                        // UNAVAILABLE / unlabelled / other
}
function _verdictColor(v) {
  const s = String(v || "").toUpperCase();
  if (s === "TRACEABLE")          return C_HARVEST;
  if (s === "PARTIAL-PROVENANCE") return C_MODELED;
  return C_UNAVAIL;                        // UNTRACEABLE / init
}

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null, _plain = false;

let _keystone = null;         // THREE.Mesh — the verdict keystone
let _links = [];              // Array<{ mesh, label, weight }>

// live state (all read from JSON; nothing invented)
const S = {
  label:    null,   // top honesty label VERBATIM (MODELED)
  verdict:  null,   // TRACEABLE | PARTIAL-PROVENANCE | UNTRACEABLE
  reason:   null,
  query:    null,
  chain:    [],
  cov:      {},
  answerLbl:null,
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
  _stage.camera.position.set(0, 3.5, 19);
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
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildKeystone() {
  const THREE = _THREE;
  const g = new THREE.BoxGeometry(6.6, 1.2, 0.6);
  _keystone = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
    color: C_UNAVAIL, emissive: C_UNAVAIL, emissiveIntensity: 0.32,
    transparent: true, opacity: 0.9,
  }));
  _keystone.position.set(0, 8.4, 0);
  _group.add(_keystone);

  // lattice frame beneath the keystone (the spine's top rail)
  const rg = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-6, 7.7, 0), new THREE.Vector3(6, 7.7, 0),
  ]);
  const rail = new THREE.Line(rg, new THREE.LineBasicMaterial({
    color: C_FRAME, transparent: true, opacity: 0.4,
  }));
  _group.add(rail);
}

// Build (or rebuild) the lineage spine: one link per chain node, top→bottom by
// contribution, colour = verbatim label, width = contribution_weight. Rebuilt on each
// snapshot so the spine always mirrors the CURRENT chain (never a stale set).
function _buildSpine() {
  const THREE = _THREE;
  _disposeLinks();

  const chain = Array.isArray(S.chain) ? S.chain : [];
  const n = chain.length;
  if (!n) return;

  const maxW = chain.reduce((m, e) => Math.max(m, (typeof e.contribution_weight === "number" ? e.contribution_weight : 0)), 1e-6);
  const topY = 7.0;
  const gap = Math.min(1.1, 12.0 / n);

  for (let i = 0; i < n; i++) {
    const e = chain[i];
    const color = _labelColor(e.node_label);
    const w = typeof e.contribution_weight === "number" ? e.contribution_weight : 0;
    const width = 1.2 + (w / maxW) * 4.6;   // link width by contribution share
    const y = topY - i * gap;

    const geo = new THREE.BoxGeometry(width, gap * 0.62, 0.8);
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color, emissive: color, emissiveIntensity: 0.30, transparent: true, opacity: 0.92,
    }));
    mesh.position.set(0, y, 0);
    _group.add(mesh);

    // a community accent bead to the side (violet-blue), present only when a community is set
    if (e.community !== null && e.community !== undefined) {
      const bg = new THREE.SphereGeometry(0.14, 12, 12);
      const bead = new THREE.Mesh(bg, new THREE.MeshStandardMaterial({
        color: C_COMM, emissive: C_COMM, emissiveIntensity: 0.4, transparent: true, opacity: 0.85,
      }));
      bead.position.set(width / 2 + 0.4, y, 0);
      _group.add(bead);
      _links.push({ mesh: bead, label: e.node_label, weight: 0, accent: true });
    }

    _links.push({ mesh, label: e.node_label, weight: w });
  }
}

function _disposeLinks() {
  const rm = (o) => {
    if (!o) return;
    try {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach((m) => m.dispose && m.dispose()); }
      if (_group) _group.remove(o);
    } catch (_) {}
  };
  _links.forEach((c) => rm(c.mesh));
  _links = [];
}

// =============================================================================
// live data handler — read VERBATIM, never upgrade
// =============================================================================
function _onData(j) {
  S.label   = (j && j.label ? String(j.label) : "MODELED").toUpperCase();
  S.verdict = j && j.verdict ? String(j.verdict).toUpperCase() : null;
  S.reason  = j && j.verdict_reason ? String(j.verdict_reason) : null;
  S.query   = j && j.query ? String(j.query) : null;
  S.chain   = (j && Array.isArray(j.chain)) ? j.chain : [];
  S.cov     = (j && j.coverage && typeof j.coverage === "object") ? j.coverage : {};
  S.answerLbl = j && j.answer_label ? String(j.answer_label) : null;

  const d = (j && j.doctrine) || {};
  S.lambda    = typeof d.lambda === "string" ? d.lambda : null;
  S.locked    = typeof d.locked_proven === "number" ? d.locked_proven : null;
  S.trustCeil = typeof d.trust_ceiling === "number" ? d.trust_ceiling : null;

  _buildSpine();
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
  if (_links.length) {
    const phase = (t * 0.0003) % 1;
    const lead = Math.floor(phase * _links.length);
    for (let i = 0; i < _links.length; i++) {
      const c = _links[i];
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
    'For a brain answer, the traceable <b>chain of exactly which knowledge-graph nodes supported ' +
    'it</b> — each node’s own honest label read <b>VERBATIM</b>, ordered by contribution. ' +
    'An honest coverage statement (<b>HARVESTED</b> vs <b>MODELED</b> vs <b>UNAVAILABLE</b>) and ' +
    'one verdict: <b>TRACEABLE / PARTIAL-PROVENANCE / UNTRACEABLE</b>. <b>Never TRACEABLE while ' +
    'any node is UNAVAILABLE/unlabelled</b>; labels are never upgraded. This is <b>source-lineage ' +
    'of an answer</b> — NOT build/model attestation, NOT counter-UAS. 0 runtime CDN.';
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
  grid.appendChild(kpiRow("bp-verdict", "verdict"));
  grid.appendChild(kpiRow("bp-chain",   "chain length"));
  grid.appendChild(kpiRow("bp-harv",    "HARVESTED nodes"));
  grid.appendChild(kpiRow("bp-mod",     "MODELED nodes"));
  grid.appendChild(kpiRow("bp-unav",    "UNAVAILABLE nodes"));
  grid.appendChild(kpiRow("bp-unlbl",   "unlabelled nodes"));
  grid.appendChild(kpiRow("bp-trace",   "traceable-to-source"));
  grid.appendChild(kpiRow("bp-answer",  "answer label"));
  grid.appendChild(kpiRow("bp-locked",  "locked proofs"));
  grid.appendChild(kpiRow("bp-lambda",  "Λ"));
  card.appendChild(grid);
  host.appendChild(card);

  // scrollable chain list (text mirror of the spine).
  const listWrap = document.createElement("div");
  listWrap.style.cssText = "display:flex;flex-direction:column;gap:4px;max-height:170px;overflow:auto";
  _el["list"] = listWrap;
  host.appendChild(listWrap);

  const leg = document.createElement("div");
  leg.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.6";
  leg.innerHTML =
    '<span style="color:#3af4c8">■</span> HARVESTED / LIVE source &nbsp; ' +
    '<span style="color:#5b8dee">■</span> MODELED source &nbsp; ' +
    '<span style="color:#8a6bff">●</span> community &nbsp; ' +
    '<span style="color:#8494a1">■</span> UNAVAILABLE / unlabelled. ' +
    'MODELED · labels read verbatim, never upgraded · never TRACEABLE if any node UNAVAILABLE.';
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
  pd.id = "bp-plain";
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
    "<b>What this means:</b> when the brain answers a question, this traces the answer back to the " +
    "exact pieces of knowledge it stood on. Each piece keeps its own honest label word-for-word — " +
    "<b>HARVESTED</b> (real gathered source), <b>MODELED</b> (a derived view), or <b>UNAVAILABLE</b> " +
    "(nothing solid there). If every supporting piece is a real source it reads <b>TRACEABLE</b>; if " +
    "some are unavailable it reads <b>PARTIAL-PROVENANCE</b>; if none are, <b>UNTRACEABLE</b>. It can " +
    "<b>never</b> claim TRACEABLE while something is unavailable. This is about where an answer came " +
    "from — it is not a security seal on a model or a build. No “verified / 1.0” state.";
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
  const chain = Array.isArray(S.chain) ? S.chain : [];
  chain.forEach((e) => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;gap:8px;font-size:10.5px;border-bottom:1px solid #12202b;padding:2px 0";
    const left = document.createElement("span");
    left.style.cssText = "color:#c9d6df;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:60%";
    left.textContent = (e.title || e.id || "?");
    const val = document.createElement("b");
    const lbl = e.node_label ? String(e.node_label) : "UNLABELLED";
    const hex = "#" + _labelColor(e.node_label).toString(16).padStart(6, "0");
    val.style.cssText = "color:" + hex + ";font-variant-numeric:tabular-nums";
    const w = typeof e.contribution_weight === "number" ? e.contribution_weight.toFixed(3) : "—";
    val.textContent = lbl + " · " + w;
    row.appendChild(left); row.appendChild(val);
    wrap.appendChild(row);
  });
}

function _paintOverlay() {
  const t = _tok(S.state);
  const vrd = t || (S.verdict || "—");
  const cov = S.cov || {};
  if (_show) {
    _show.setChip("lbl", S.label || "MODELED", { text: "lineage" });
    _show.setChip("vrd", vrd, { text: "verdict" });
  }
  _set("bp-verdict", vrd);
  _set("bp-chain",   t || _n(S.chain ? S.chain.length : null));
  _set("bp-harv",    t || _n(cov.harvested));
  _set("bp-mod",     t || _n(cov.modeled));
  _set("bp-unav",    t || _n(cov.unavailable));
  _set("bp-unlbl",   t || _n(cov.unlabelled));
  _set("bp-trace",   t || (typeof cov.fraction_traceable_to_source === "number" ? cov.fraction_traceable_to_source.toFixed(3) : "—"));
  _set("bp-answer",  t || (S.answerLbl || "—"));
  _set("bp-locked",  t || (S.locked != null ? String(S.locked) : "—"));
  _set("bp-lambda",  t || (S.lambda || "—"));
  if (_plain) _applyPlain();
}

// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    _disposeLinks();
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
  _keystone = null; _links = [];
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.verdict = S.reason = S.query = null;
  S.chain = []; S.cov = {}; S.answerLbl = null;
  S.lambda = S.locked = S.trustCeil = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
