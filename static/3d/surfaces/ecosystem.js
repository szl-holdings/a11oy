// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/ecosystem.js — HARNESS · live ecosystem-status dashboard (Wave 30 · Dev 3).
//
// One honest control surface for the whole a11oy estate, rendered LIVE from REAL
// endpoints (never hardcoded, never fabricated). Three concentric rings + a HUD:
//
//   • MODEL ROSTER  — every model in the LLM hub, each with a per-model WIRED/STUB
//                     chip read straight from /llm/registry  (api_key_wired flag).
//                     A model is WIRED only if its api_env_var is present at runtime;
//                     otherwise it is an honest STUB. The count is whatever the registry
//                     returns THIS request (10 today, 20 once Dev 2's roster lands) —
//                     the surface never assumes a number.
//   • FLEET NODES   — omen + betterwithage, each LIVE or OFFLINE with MEASURED joules +
//                     watts + GPU name, from /energy/mesh. A node is LIVE only when its
//                     meter responded live THIS request; otherwise it is shown OFFLINE
//                     honestly, joules null, never a guessed number.
//   • ENERGY + SEAL — fleet-total MEASURED joules with provenance (meter URL) from
//                     /energy/mesh, and the Allodial sovereignty SEAL score from
//                     /allodial/summary + /allodial/score.
//
// DOCTRINE (v11, non-negotiable, all honesty read straight from the JSON):
//   * MEASURED only when the meter reported live this request; else UNAVAILABLE/OFFLINE.
//   * WIRED (green) only when api_key_wired is true; else STUB (gray/structural).
//   * Λ is Conjecture 1 — advisory, gray, NEVER green. This surface emits no Λ verdict.
//   * The only purple used is the approved violet-blue accent 0x8a6bff (data-viz only).
//   * No fabricated joule, no fabricated wired=true. Degrades gracefully; never crashes.
//
// EVERY value on screen traces to a REAL a11oy endpoint:
//   GET /api/a11oy/v1/llm/registry        — model roster + per-model api_key_wired + wired_count
//   GET /api/a11oy/v1/energy/mesh          — per-node LIVE/OFFLINE + MEASURED watts/joules + GPU name
//   GET /api/a11oy/v1/allodial/summary     — SEAL 0-4 assurance scale + sovereignty dimensions
//   GET /api/a11oy/v1/allodial/score       — Allodial 𝒜 sovereignty score (0..100) + posture
//
// 0 runtime CDN: three resolves through the page importmap to /static/3d/vendor/.

const ID = "ecosystem";
const TITLE = "Harness · Ecosystem Status";

const EP_REGISTRY = "/api/a11oy/v1/llm/registry";
const EP_MESH = "/api/a11oy/v1/energy/mesh";
const EP_ALLODIAL = "/api/a11oy/v1/allodial/summary";
const EP_SEAL = "/api/a11oy/v1/allodial/score";

// palette — matches the estate. Green = WIRED/LIVE, gray = STUB/OFFLINE/structural,
// amber = degraded/MODELED, violet-blue = the approved 0x8a6bff accent (data-viz only).
const C_WIRED = 0x2fd07a;   // WIRED / LIVE — green
const C_STUB = 0x8a97a3;    // STUB / OFFLINE / structural — gray
const C_AMBER = 0xe8c074;   // degraded / MODELED — amber/gold
const C_TEAL = 0x39d3c4;    // structural accent — teal
const C_ACCENT = 0x8a6bff;  // approved violet-blue accent (data-viz only)
const C_CORE = 0x6fb1ff;    // hub core — blue

// ring radii (world units)
const R_MODELS = 8.4;
const R_NODES = 4.6;

let _stage = null, _THREE = null, _ctx = null;
let _group = null, _overlay = null, _frameReg = false;
let _core = null, _modelNodes = [], _fleetNodes = [], _sealRing = null;
let _pollReg = null, _pollMesh = null, _pollAllo = null, _pollSeal = null;
let _badgeReg = null, _badgeMesh = null, _badgeAllo = null;

// live state — every field is populated from a real endpoint or left honestly empty.
const S = {
  models: [], modelCount: 0, wiredCount: 0, regState: "init", regLabel: null,
  fleet: [], liveCount: 0, totalJoules: null, joulesLabel: null, meterUrl: null,
  meshState: "init",
  sealScale: null, sealScore: null, sealPosture: null, sealState: "init", sealFormula: null,
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);
  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 7, 20);
  try { _stage.setBloom(true); } catch (_) {}

  _buildCore();
  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING — every value traces to a real endpoint (doctrine) ----
  // Registry + mesh poll fastest (the two moving surfaces); allodial is near-static.
  _pollReg = ctx.live.poll(EP_REGISTRY, 10000, _onRegistry, {
    badge: _badgeReg,
    onState: (m) => { S.regState = m.state; if (m.state !== "live") _paintOverlay(); },
  });
  _pollMesh = ctx.live.poll(EP_MESH, 8000, _onMesh, {
    badge: _badgeMesh,
    onState: (m) => { S.meshState = m.state; if (m.state !== "live") _paintOverlay(); },
  });
  _pollAllo = ctx.live.poll(EP_ALLODIAL, 30000, _onAllodial, {
    badge: _badgeAllo,
    onState: (m) => { S.sealState = m.state; if (m.state !== "live") _paintOverlay(); },
  });
  // score endpoint has no honesty flag of its own; poll it plainly and read the number.
  _pollSeal = ctx.live.poll(EP_SEAL, 30000, _onSeal, {});

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.5, 1),
    new THREE.MeshStandardMaterial({ color: C_CORE, emissive: C_CORE, emissiveIntensity: 0.5, metalness: 0.4, roughness: 0.4, transparent: true, opacity: 0.92 }),
  );
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.95, 1),
    new THREE.MeshBasicMaterial({ color: C_CORE, wireframe: true, transparent: true, opacity: 0.26 }),
  );
  _core.add(core, shell);
  _core.core = core;
  _group.add(_core);
  try {
    _core.lbl = _ctx.label.billboard(_THREE, "STRUCTURAL-ONLY", { text: "a11oy hub · harness", scale: 0.5, position: [0, -2.4, 0] });
    _core.add(_core.lbl);
  } catch (_) {}
}

// Model roster ring — one node per model, colored WIRED (green) vs STUB (gray).
function _renderModelRing() {
  const THREE = _THREE;
  _modelNodes.forEach((n) => { try { _group.remove(n.mesh); } catch (_) {} try { if (n.label) _group.remove(n.label); } catch (_) {} });
  _modelNodes = [];
  const ms = S.models;
  ms.forEach((m, i) => {
    const ang = (i / Math.max(ms.length, 1)) * Math.PI * 2;
    const x = Math.cos(ang) * R_MODELS, z = Math.sin(ang) * R_MODELS;
    const wired = !!m.api_key_wired;
    const col = wired ? C_WIRED : C_STUB;
    const mesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.5, 0),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: wired ? 0.85 : 0.32, metalness: 0.35, roughness: 0.5, transparent: true, opacity: wired ? 0.95 : 0.72 }),
    );
    mesh.position.set(x, 1.0 + (i % 2) * 0.5, z);
    mesh.userData = { wired };
    _group.add(mesh);
    let label = null;
    try {
      // A model's WIRED/STUB status is a STRUCTURAL config fact (is the api_env_var
      // present at runtime?) — NOT a physical measurement. Per doctrine the honesty
      // token must therefore stay STRUCTURAL-ONLY (gray chip) for every model; we never
      // emit MEASURED here since no NVML/exporter reading backs a model row. The
      // WIRED-vs-STUB distinction is carried honestly by the node color (green/gray)
      // and by the roster panel chip text below.
      const tag = wired ? " · WIRED" : " · STUB";
      label = _ctx.label.billboard(_THREE, "STRUCTURAL-ONLY", {
        text: (m.model_id || m.display_name || "?") + tag, scale: 0.34, position: [x, 1.9 + (i % 2) * 0.5, z],
      });
      _group.add(label);
    } catch (_) {}
    _modelNodes.push({ mesh, label });
  });
}

// Fleet ring — one node per fleet node, colored LIVE (green) vs OFFLINE (gray).
function _renderFleetRing() {
  const THREE = _THREE;
  _fleetNodes.forEach((n) => { try { _group.remove(n.mesh); } catch (_) {} try { if (n.label) _group.remove(n.label); } catch (_) {} });
  _fleetNodes = [];
  const fs = S.fleet;
  fs.forEach((n, i) => {
    const ang = (i / Math.max(fs.length, 1)) * Math.PI * 2 + Math.PI / 4;
    const x = Math.cos(ang) * R_NODES, z = Math.sin(ang) * R_NODES;
    const live = !!n.live;
    const col = live ? C_WIRED : C_STUB;
    // node size scales with normalized draw when live+measured; fixed when offline.
    const base = 0.7 + (typeof n.draw === "number" ? 0.5 * n.draw : 0);
    const mesh = new THREE.Mesh(
      new THREE.IcosahedronGeometry(base, 0),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: live ? 0.9 : 0.3, metalness: 0.45, roughness: 0.4, transparent: true, opacity: live ? 0.95 : 0.7 }),
    );
    mesh.position.set(x, 1.4, z);
    mesh.userData = { live };
    _group.add(mesh);
    let label = null;
    try {
      // joules label is MEASURED only when the node reported a live number this tick.
      const measured = live && typeof n.joules === "number";
      label = _ctx.label.billboard(_THREE, measured ? "MEASURED" : "STRUCTURAL-ONLY", {
        text: (n.name || "node") + (live ? " · LIVE" : " · OFFLINE"), scale: 0.4, position: [x, 2.8, z],
      });
      _group.add(label);
    } catch (_) {}
    _fleetNodes.push({ mesh, label });
  });
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onRegistry(json, meta) {
  S.regLabel = meta.label || S.regLabel;
  if (!json || !Array.isArray(json.models)) { _paintOverlay(); return; }
  S.models = json.models;
  S.modelCount = (typeof json.model_count === "number") ? json.model_count : json.models.length;
  S.wiredCount = (typeof json.wired_count === "number") ? json.wired_count
    : json.models.filter((m) => m.api_key_wired).length;
  _renderModelRing();
  _paintOverlay();
}

function _onMesh(json, meta) {
  if (!json) { _paintOverlay(); return; }
  S.fleet = Array.isArray(json.nodes) ? json.nodes : [];
  S.liveCount = (typeof json.live_count === "number") ? json.live_count
    : S.fleet.filter((n) => n.live).length;
  // total_joules is MEASURED only when the mesh label says so — read the label verbatim.
  S.totalJoules = (typeof json.total_joules === "number") ? json.total_joules : null;
  S.joulesLabel = json.joules_label || json.label || null;
  S.meterUrl = json.meter_url || null;
  _renderFleetRing();
  _paintOverlay();
}

function _onAllodial(json, meta) {
  if (!json) { _paintOverlay(); return; }
  S.sealScale = json.seal_scale || null;
  _paintOverlay();
}

function _onSeal(json, meta) {
  if (!json) { _paintOverlay(); return; }
  S.sealScore = (typeof json.score === "number") ? json.score : null;
  S.sealPosture = json.posture || null;
  S.sealFormula = json.formula || null;
  _renderSealRing();
  _paintOverlay();
}

// SEAL ring — an arc whose sweep encodes the sovereignty score (0..100), teal accent.
function _renderSealRing() {
  const THREE = _THREE;
  if (_sealRing) { try { _group.remove(_sealRing); } catch (_) {} _sealRing = null; }
  if (typeof S.sealScore !== "number") return;
  const frac = Math.max(0, Math.min(1, S.sealScore / 100));
  const R = 11.0;
  _sealRing = new THREE.Group();
  const seg = 96;
  const lit = Math.round(seg * frac);
  for (let i = 0; i < seg; i++) {
    const ang = (i / seg) * Math.PI * 2 - Math.PI / 2;
    const on = i < lit;
    const dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 8, 8),
      new THREE.MeshBasicMaterial({ color: on ? C_ACCENT : C_STUB, transparent: true, opacity: on ? 0.9 : 0.28 }),
    );
    dot.position.set(Math.cos(ang) * R, 0.4, Math.sin(ang) * R);
    _sealRing.add(dot);
  }
  _group.add(_sealRing);
}

// =========================================================================================
// per-frame animation — gentle, non-decorative (conveys "live")
// =========================================================================================
function _onFrame() {
  if (_core && _core.core) {
    _core.rotation.y += 0.003;
    const s = 1 + 0.04 * Math.sin(performance.now() * 0.0025);
    _core.core.scale.setScalar(s);
  }
  _group && (_group.rotation.y += 0.0008);
  _modelNodes.forEach((n, i) => { n.mesh.rotation.y += 0.01 + i * 0.0004; });
  _fleetNodes.forEach((n) => { n.mesh.rotation.y += 0.006; });
}

// =========================================================================================
// DOM overlay (HUD) — the honest, high-contrast status board (WCAG AA)
// =========================================================================================
let _el = {};
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "9px",
    maxWidth: "min(94%,500px)", maxHeight: "calc(100% - 28px)", overflowY: "auto",
    font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 14px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML = 'One honest control surface for the estate, rendered LIVE from real ' +
    'endpoints — <b>no hardcoded numbers</b>. Chips read straight from the JSON: ' +
    '<span style="color:#2fd07a">green</span> = wired/live, ' +
    '<span style="color:#8a97a3">gray</span> = stub/offline/structural, ' +
    '<span style="color:#e8c074">amber</span> = degraded. Λ is advisory (Conjecture 1), never green.';
  _overlay.appendChild(sub);

  // live badges row (one per polled endpoint) — state read from szl3d_live.poll.
  _badgeReg = ctx.live.createBadge();
  _badgeMesh = ctx.live.createBadge();
  _badgeAllo = ctx.live.createBadge();
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#6fb1ff"; return s; };
  badgeRow.appendChild(tag("registry")); badgeRow.appendChild(_badgeReg.el);
  badgeRow.appendChild(tag("fleet")); badgeRow.appendChild(_badgeMesh.el);
  badgeRow.appendChild(tag("allodial")); badgeRow.appendChild(_badgeAllo.el);
  _overlay.appendChild(badgeRow);

  // ── MODEL ROSTER panel ──────────────────────────────────────────────────
  _el.models = _panel("model roster · /llm/registry");
  _overlay.appendChild(_el.models.wrap);

  // ── FLEET NODES panel ───────────────────────────────────────────────────
  _el.fleet = _panel("fleet nodes · /energy/mesh");
  _overlay.appendChild(_el.fleet.wrap);

  // ── ENERGY + SEAL panel ─────────────────────────────────────────────────
  _el.energy = _panel("energy + sovereignty · /energy/mesh · /allodial/*");
  _overlay.appendChild(_el.energy.wrap);

  // honesty legend (shared doctrine chips) + provenance footnote
  const lg = ctx.label.legend(); lg.style.opacity = "0.9"; _overlay.appendChild(lg);

  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Provenance: model roster + per-model api_key_wired from GET /api/a11oy/v1/llm/registry " +
    "(WIRED only if the model's api_env_var is present at runtime). Fleet LIVE/OFFLINE + MEASURED watts/joules " +
    "+ GPU name from GET /api/a11oy/v1/energy/mesh (NVML meter; UNAVAILABLE when unreachable, never fabricated). " +
    "Sovereignty SEAL score 𝒜 from GET /api/a11oy/v1/allodial/{summary,score} (EU Cloud Sovereignty Framework " +
    "SEAL 0-4 + HHI lock-in penalty). Λ = Conjecture 1 (advisory, never green). trust < 100%.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

// small styled panel factory (title + body container)
function _panel(titleText) {
  const wrap = document.createElement("div");
  wrap.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:8px;padding:9px;display:flex;flex-direction:column;gap:6px";
  const t = document.createElement("div");
  t.style.cssText = "font:600 11px ui-monospace,monospace;color:#39d3c4;letter-spacing:.3px";
  t.textContent = titleText;
  const body = document.createElement("div");
  body.style.cssText = "font:11px ui-sans-serif;color:#cdd9e2;line-height:1.5";
  wrap.appendChild(t); wrap.appendChild(body);
  return { wrap, body };
}

// row helper: a status chip + label, high-contrast (WCAG AA on the dark panel).
function _statusRow(chipText, chipColor, chipFg, text) {
  const row = document.createElement("div");
  row.style.cssText = "display:flex;align-items:center;gap:8px;padding:2px 0;border-top:1px solid #12202b";
  const chip = document.createElement("span");
  chip.textContent = chipText;
  chip.style.cssText = "font:600 9.5px ui-monospace,monospace;letter-spacing:.4px;padding:2px 7px;border-radius:5px;" +
    "flex:0 0 auto;color:" + chipFg + ";background:" + chipColor + ";border:1px solid rgba(255,255,255,.14)";
  const lab = document.createElement("span");
  lab.style.cssText = "font:11px ui-monospace,monospace;color:#cdd9e2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap";
  lab.textContent = text;
  row.appendChild(chip); row.appendChild(lab);
  return row;
}

function _esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function _paintOverlay() {
  _paintModels();
  _paintFleet();
  _paintEnergy();
}

function _paintModels() {
  const b = _el.models && _el.models.body;
  if (!b) return;
  b.innerHTML = "";
  if (!S.models.length) {
    b.textContent = (S.regState === "live") ? "registry returned no models"
      : "awaiting live registry (" + S.regState + ")…";
    return;
  }
  const head = document.createElement("div");
  head.style.cssText = "font:11px ui-monospace,monospace;color:#eef3f6;margin-bottom:2px";
  // headline count is read verbatim from wired_count / model_count.
  head.innerHTML = "<b>" + S.wiredCount + "</b> wired · <b>" + (S.modelCount - S.wiredCount) +
    "</b> stub · <b>" + S.modelCount + "</b> total models";
  b.appendChild(head);
  S.models.forEach((m) => {
    const wired = !!m.api_key_wired;
    const chipTxt = wired ? "WIRED" : "STUB";
    const col = wired ? C_hex(C_WIRED) : C_hex(C_STUB);
    const fg = wired ? "#04130b" : "#0a0e12";
    const provider = m.provider_slug ? " (" + m.provider_slug + ")" : "";
    const env = m.api_env_var ? " · " + m.api_env_var : "";
    b.appendChild(_statusRow(chipTxt, col, fg, (m.model_id || m.display_name || "?") + provider + env));
  });
}

function _paintFleet() {
  const b = _el.fleet && _el.fleet.body;
  if (!b) return;
  b.innerHTML = "";
  if (!S.fleet.length) {
    b.textContent = (S.meshState === "live") ? "mesh returned no nodes"
      : "awaiting live fleet mesh (" + S.meshState + ")…";
    return;
  }
  const head = document.createElement("div");
  head.style.cssText = "font:11px ui-monospace,monospace;color:#eef3f6;margin-bottom:2px";
  head.innerHTML = "<b>" + S.liveCount + "</b> / " + S.fleet.length + " nodes live this request";
  b.appendChild(head);
  S.fleet.forEach((n) => {
    const live = !!n.live;
    const chipTxt = live ? "LIVE" : "OFFLINE";
    const col = live ? C_hex(C_WIRED) : C_hex(C_STUB);
    const fg = live ? "#04130b" : "#0a0e12";
    // watts/joules shown ONLY when present (MEASURED); else an honest dash.
    const w = (typeof n.watts === "number") ? n.watts.toFixed(2) + " W" : "— W";
    const j = (typeof n.joules === "number") ? Math.round(n.joules).toLocaleString() + " J" : "— J";
    const gpu = n.name || n.role || "node";
    const jl = n.joules_label ? " [" + n.joules_label + "]" : "";
    b.appendChild(_statusRow(chipTxt, col, fg, gpu + " · " + w + " · " + j + jl));
  });
}

function _paintEnergy() {
  const b = _el.energy && _el.energy.body;
  if (!b) return;
  b.innerHTML = "";
  // fleet-total joules with its honest label + meter provenance.
  const totLabel = S.joulesLabel || (S.meshState === "live" ? "UNAVAILABLE" : "…");
  const totVal = (typeof S.totalJoules === "number")
    ? Math.round(S.totalJoules).toLocaleString() + " J" : "— J (not fabricated)";
  const jr = document.createElement("div");
  jr.style.cssText = "font:11px ui-monospace,monospace;color:#eef3f6;line-height:1.6";
  jr.innerHTML = "fleet-total joules: <b>" + _esc(totVal) + "</b> " +
    "<span style='color:" + (totLabel === "MEASURED" ? "#2fd07a" : "#e8c074") + "'>[" + _esc(totLabel) + "]</span>";
  b.appendChild(jr);
  if (S.meterUrl) {
    const mp = document.createElement("div");
    mp.style.cssText = "font:10px ui-monospace,monospace;color:#5b6c78";
    mp.textContent = "provenance: meter " + S.meterUrl;
    b.appendChild(mp);
  }
  // Allodial SEAL score — sovereignty posture.
  const sr = document.createElement("div");
  sr.style.cssText = "font:11px ui-monospace,monospace;color:#eef3f6;line-height:1.6;margin-top:4px;border-top:1px solid #12202b;padding-top:4px";
  if (typeof S.sealScore === "number") {
    const posture = S.sealPosture || "";
    sr.innerHTML = "Allodial sovereignty score 𝒜: <b style='color:#8a6bff'>" + S.sealScore + "</b> / 100" +
      (posture ? " · <span style='color:#9fb1bf'>" + _esc(posture) + "</span>" : "");
    b.appendChild(sr);
    if (S.sealFormula) {
      const f = document.createElement("div");
      f.style.cssText = "font:10px ui-monospace,monospace;color:#5b6c78";
      f.textContent = S.sealFormula;
      b.appendChild(f);
    }
  } else {
    sr.textContent = "Allodial score: awaiting /allodial/score (" + S.sealState + ")…";
    b.appendChild(sr);
  }
}

// convert a 0xRRGGBB number to a #rrggbb css string.
function C_hex(n) { return "#" + (n & 0xffffff).toString(16).padStart(6, "0"); }

// =========================================================================================
// unmount — release everything (polls, DOM, GPU resources)
// =========================================================================================
function unmount() {
  [_pollReg, _pollMesh, _pollAllo, _pollSeal].forEach((p) => { try { if (p) p.stop(); } catch (_) {} });
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach((m) => { if (m.map && m.map.dispose) m.map.dispose(); if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _pollReg = _pollMesh = _pollAllo = _pollSeal = null;
  _overlay = _group = _core = _sealRing = null;
  _modelNodes = []; _fleetNodes = [];
  _badgeReg = _badgeMesh = _badgeAllo = null; _el = {};
  S.models = []; S.fleet = []; S.sealScore = null; S.sealScale = null;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_REGISTRY, EP_MESH, EP_ALLODIAL, EP_SEAL], mount, unmount };
