// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/harness.js — GOVERNED MODEL HARNESS holographic surface (Wave F · Team 1).
//
// Technique modeled (NOT claimed-as): the community "clone Fable 5 into Opus 4.8"
//   behavior-transfer move — load a model's instruction/behavior layer into another
//   model to transfer DISPOSITION (autonomy, grounding, voice), never capability.
//   SZL's differentiator is the governance layer no leak-harness ships: provenance
//   sha256, Λ-gate at apply time, ECDSA-P256 DSSE signed receipt, forum ingest.
//   Inspiration (citable, non-leaked): Anthropic "Prompting Claude Fable 5" +
//   github.com/HalalifyMusic/fable-mode. No leaked prompt text is stored/shipped.
//
// EVERY value on screen traces to a REAL a11oy endpoint (doctrine v11 — never fabricate):
//   * GET  /api/a11oy/v1/harness/profiles        — profile roster + provenance + availability
//   * POST /api/a11oy/v1/harness/apply           — Λ-gated apply → signed receipt (the demo)
//
// The scene: a ring of PROFILE nodes (color = availability, badge = honesty label),
// a central TARGET-MODEL core, an APPLY beam that fires profile→model on demand, and
// a floating RECEIPT panel that shows the live signed provenance receipt. Honesty
// labels are read straight from the JSON. Degrades gracefully; no crash, no fake data.
//
// 0 runtime CDN: three resolves through the page importmap to /static/3d/vendor/.

const ID = "harness";
const TITLE = "Governed Model Harness · Behavior Transfer";
const EP_PROFILES = "/api/a11oy/v1/harness/profiles";
const EP_APPLY = "/api/a11oy/v1/harness/apply";

// palette (matches the estate)
const C_AVAIL = 0x39d3c4;   // available profile — teal
const C_UNAVAIL = 0x8a6a3a; // unavailable — dim gold
const C_MODEL = 0xe8c074;   // target model core — gold
const C_BEAM = 0x6fb1ff;    // apply beam — blue
const C_DIM = 0x4a5a68;

let _stage = null, _THREE = null, _ctx = null;
let _group = null, _overlay = null, _frameReg = false;
let _profileNodes = [];      // { mesh, label, id, available }
let _modelCore = null, _beam = null, _billboard = null;
let _poll = null, _badge = null;

const S = {
  profiles: [],           // public views from the roster
  label: null, state: "init", degraded: false,
  selectedProfile: null,  // id
  selectedModel: "claude_opus_4_8",
  lastReceipt: null, lastResponse: null, applyState: "idle",
};

// =========================================================================================
// mount
// =========================================================================================
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  const THREE = _THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);
  if (_stage.camera && _stage.camera.position) _stage.camera.position.set(0, 6, 17);
  try { _stage.setBloom(true); } catch (_) {}

  _buildModelCore();
  _buildBeam();
  try {
    _billboard = ctx.label.billboard(THREE, "MODELED", { text: "behavior transfer · not capability", scale: 0.6, position: [0, 6.2, 0] });
    _group.add(_billboard);
  } catch (_) {}

  _buildOverlay();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  // ---- LIVE WIRING (doctrine: every value traces to a real endpoint) ----
  _poll = ctx.live.poll(EP_PROFILES, 8000, _onProfiles, {
    badge: _badge,
    onState: (m) => { S.state = m.state; S.label = m.label || S.label; if (m.state !== "live") _paintOverlay(); },
  });

  return { id: ID, started: true };
}

// =========================================================================================
// scene builders
// =========================================================================================
function _buildModelCore() {
  const THREE = _THREE;
  _modelCore = new THREE.Group();
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.3, 1),
    new THREE.MeshStandardMaterial({ color: C_MODEL, emissive: C_MODEL, emissiveIntensity: 0.55, metalness: 0.4, roughness: 0.4, transparent: true, opacity: 0.92 }),
  );
  const shell = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.7, 1),
    new THREE.MeshBasicMaterial({ color: C_MODEL, wireframe: true, transparent: true, opacity: 0.28 }),
  );
  _modelCore.add(core, shell);
  _modelCore.core = core;
  _group.add(_modelCore);
  try {
    _modelCore.lbl = _ctx.label.billboard(_THREE, "TARGET", { text: S.selectedModel, scale: 0.5, position: [0, -2.1, 0] });
    _modelCore.add(_modelCore.lbl);
  } catch (_) {}
}

function _buildBeam() {
  const THREE = _THREE;
  // an apply beam that fires from the selected profile node into the model core
  const geo = new THREE.CylinderGeometry(0.06, 0.18, 1, 12, 1, true);
  const mat = new THREE.MeshBasicMaterial({ color: C_BEAM, transparent: true, opacity: 0.0, side: THREE.DoubleSide, depthWrite: false });
  _beam = new THREE.Mesh(geo, mat);
  _beam.visible = false;
  _group.add(_beam);
}

function _renderProfileRing() {
  const THREE = _THREE;
  // clear old
  _profileNodes.forEach((n) => { try { _group.remove(n.mesh); } catch (_) {} try { if (n.label) _group.remove(n.label); } catch (_) {} });
  _profileNodes = [];

  const profs = S.profiles;
  const R = 6.2;
  profs.forEach((p, i) => {
    const ang = (i / Math.max(profs.length, 1)) * Math.PI * 2;
    const x = Math.cos(ang) * R, z = Math.sin(ang) * R;
    const available = !!(p.availability && p.availability.available);
    const col = available ? C_AVAIL : C_UNAVAIL;
    const mesh = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.7, 0),
      new THREE.MeshStandardMaterial({ color: col, emissive: col, emissiveIntensity: available ? 0.6 : 0.25, metalness: 0.35, roughness: 0.45, transparent: true, opacity: available ? 0.95 : 0.55 }),
    );
    mesh.position.set(x, 1.2 + (i % 2) * 0.4, z);
    mesh.userData = { id: p.id, available };
    _group.add(mesh);

    let label = null;
    try {
      const honesty = p.honesty_label || "MODELED";
      label = _ctx.label.billboard(_THREE, honesty, { text: p.id, scale: 0.42, position: [x, 2.4 + (i % 2) * 0.4, z] });
      _group.add(label);
    } catch (_) {}
    _profileNodes.push({ mesh, label, id: p.id, available });
  });

  // default selection = first available profile
  if (!S.selectedProfile && profs.length) {
    const firstAvail = profs.find((p) => p.availability && p.availability.available) || profs[0];
    S.selectedProfile = firstAvail.id;
  }
  _highlightSelected();
}

function _highlightSelected() {
  _profileNodes.forEach((n) => {
    const on = n.id === S.selectedProfile;
    try { n.mesh.scale.setScalar(on ? 1.35 : 1.0); } catch (_) {}
  });
}

// =========================================================================================
// live-data handlers — read REAL values; never invent
// =========================================================================================
function _onProfiles(json, meta) {
  S.degraded = !!meta.degraded;
  S.label = meta.label || (json && json.honest_note ? "LIVE" : null) || S.label;
  if (!json || !Array.isArray(json.profiles)) { _paintOverlay(); return; }
  S.profiles = json.profiles;
  _renderProfileRing();
  _paintOverlay();
  if (_billboard && _ctx) {
    try {
      _group.remove(_billboard);
      _billboard = _ctx.label.billboard(_THREE, "MODELED", {
        text: `${json.available_count}/${json.profile_count} profiles available`, scale: 0.58, position: [0, 6.2, 0],
      });
      _group.add(_billboard);
    } catch (_) {}
  }
}

// POST apply → signed receipt (the governed demo)
async function _fireApply() {
  if (!S.selectedProfile) return;
  S.applyState = "applying";
  _paintOverlay();
  _animateBeam();
  try {
    const res = await fetch(EP_APPLY, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ profile_id: S.selectedProfile, model_id: S.selectedModel, prompt: (_el.prompt && _el.prompt.value) || "Demonstrate the applied behavior profile." }),
    });
    if (!res.ok) { S.applyState = "error(" + res.status + ")"; _paintOverlay(); return; }
    const json = await res.json();
    S.lastReceipt = json.harness_receipt || null;
    S.lastResponse = json.response || null;
    S.applyState = json.harness_state || "done";
    if (json.model_selected && json.model_selected.display_name && _modelCore) {
      try {
        _modelCore.remove(_modelCore.lbl);
        _modelCore.lbl = _ctx.label.billboard(_THREE, "TARGET", { text: json.model_selected.display_name, scale: 0.5, position: [0, -2.1, 0] });
        _modelCore.add(_modelCore.lbl);
      } catch (_) {}
    }
    _paintOverlay();
    _paintReceipt();
  } catch (e) {
    S.applyState = "error";
    _paintOverlay();
  }
}

function _animateBeam() {
  if (!_beam) return;
  const node = _profileNodes.find((n) => n.id === S.selectedProfile);
  if (!node) return;
  const THREE = _THREE;
  const from = node.mesh.position.clone();
  const to = new THREE.Vector3(0, 1.2, 0);
  const mid = from.clone().add(to).multiplyScalar(0.5);
  const len = from.distanceTo(to);
  _beam.position.copy(mid);
  _beam.scale.set(1, len, 1);
  _beam.lookAt(to);
  _beam.rotateX(Math.PI / 2);
  _beam.visible = true;
  _beam.userData.t = 0;
}

// =========================================================================================
// per-frame animation
// =========================================================================================
function _onFrame() {
  if (_modelCore && _modelCore.core) {
    _modelCore.rotation.y += 0.004;
    const s = 1 + 0.05 * Math.sin(performance.now() * 0.003);
    _modelCore.core.scale.setScalar(s);
  }
  _profileNodes.forEach((n, i) => { n.mesh.rotation.y += 0.01 + i * 0.001; });
  if (_beam && _beam.visible) {
    _beam.userData.t = (_beam.userData.t || 0) + 0.03;
    const t = _beam.userData.t;
    _beam.material.opacity = Math.max(0, 0.85 * (1 - Math.abs(Math.sin(t))));
    if (t > Math.PI) { _beam.visible = false; _beam.material.opacity = 0; }
  }
}

// =========================================================================================
// DOM overlay (HUD)
// =========================================================================================
let _el = {};
function _buildOverlay() {
  const ctx = _ctx;
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "8px",
    maxWidth: "min(94%,460px)", font: "12px ui-sans-serif,system-ui,Segoe UI,Roboto,Arial", color: "#eef3f6",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;letter-spacing:.4px";
  h.textContent = TITLE;
  _overlay.appendChild(h);

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.5";
  sub.innerHTML = 'Governed <b>behavior transfer</b>: run model X with behavior profile Y — ' +
    'Λ-gated, provenance-signed, receipted. Transfers <span style="color:#39d3c4">disposition</span>, ' +
    'NOT capability (honest ceiling). Bodies referenced by path/env — never inlined; no leaked prompt shipped.';
  _overlay.appendChild(sub);

  _badge = ctx.live.createBadge();
  const badgeRow = document.createElement("div");
  badgeRow.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;align-items:center";
  const tag = (t) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:10px ui-monospace,monospace;color:#6fb1ff"; return s; };
  badgeRow.appendChild(tag("profiles")); badgeRow.appendChild(_badge.el);
  _overlay.appendChild(badgeRow);

  // profile roster (with provenance + license badges)
  _el.roster = document.createElement("div");
  _el.roster.style.cssText = "display:flex;flex-direction:column;gap:5px;max-height:190px;overflow:auto";
  _overlay.appendChild(_el.roster);

  // apply demo controls
  const ctl = document.createElement("div");
  ctl.style.cssText = "display:flex;flex-direction:column;gap:6px;background:#0a1117;border:1px solid #1d2a36;border-radius:8px;padding:8px";
  const cl = document.createElement("div");
  cl.style.cssText = "font:600 11px ui-sans-serif;color:#e8c074"; cl.textContent = "apply profile → model (governed demo)";
  ctl.appendChild(cl);

  _el.modelSel = document.createElement("select");
  _el.modelSel.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-monospace,monospace";
  ["claude_opus_4_8", "claude_sonnet_4_6", "gpt_5_4", "gpt_5_5", "sovereign_local"].forEach((m) => {
    const o = document.createElement("option"); o.value = m; o.textContent = m; _el.modelSel.appendChild(o);
  });
  _el.modelSel.value = S.selectedModel;
  _el.modelSel.addEventListener("change", () => { S.selectedModel = _el.modelSel.value; });
  ctl.appendChild(_el.modelSel);

  _el.prompt = document.createElement("input");
  _el.prompt.type = "text"; _el.prompt.value = "Demonstrate the applied behavior profile.";
  _el.prompt.style.cssText = "background:#06090d;color:#eef3f6;border:1px solid #1d2a36;border-radius:6px;padding:5px;font:11px ui-sans-serif";
  ctl.appendChild(_el.prompt);

  _el.applyBtn = document.createElement("button");
  _el.applyBtn.textContent = "▶ apply (Λ-gate + sign + forum)";
  _el.applyBtn.style.cssText = "background:#12202b;color:#eef3f6;border:1px solid #39d3c4;border-radius:7px;padding:7px 10px;cursor:pointer;font:600 11px ui-monospace,monospace";
  _el.applyBtn.addEventListener("click", _fireApply);
  ctl.appendChild(_el.applyBtn);

  _el.applyState = document.createElement("div");
  _el.applyState.style.cssText = "font:10.5px ui-monospace,monospace;color:#9fb1bf";
  _el.applyState.textContent = "apply state: idle";
  ctl.appendChild(_el.applyState);
  _overlay.appendChild(ctl);

  // signed receipt panel
  const det = document.createElement("details");
  det.open = true;
  const sum = document.createElement("summary");
  sum.style.cssText = "cursor:pointer;color:#39d3c4;font:11px ui-monospace,monospace";
  sum.textContent = "signed harness receipt (szl.harness_apply.receipt/v1)";
  _el.receipt = document.createElement("div");
  _el.receipt.style.cssText = "white-space:pre-wrap;font:10px ui-monospace,monospace;color:#bfe;background:#06090d;border:1px solid #1d2a36;border-radius:7px;padding:8px;max-height:210px;overflow:auto;margin-top:6px";
  _el.receipt.textContent = "— apply a profile to see the live signed receipt —";
  det.appendChild(sum); det.appendChild(_el.receipt);
  _overlay.appendChild(det);

  // honesty legend
  const lg = ctx.label.legend(); lg.style.opacity = "0.85"; _overlay.appendChild(lg);

  // sources (text only — NOT fetch-shaped, doctrine 0-CDN safe)
  const src = document.createElement("div");
  src.style.cssText = "font-size:9.5px;color:#5b6c78;line-height:1.6;margin-top:2px";
  src.textContent = "Ingested & re-expressed as ours — inspiration: Anthropic 'Prompting Claude Fable 5' (published guidance) · fable-mode (community harness). SZL ships its OWN governed profiles with provenance + not_verbatim_of; behavior transfer is MODELED, not a capability claim; NOT in the locked-8; Λ = Conjecture 1; trust < 100%.";
  _overlay.appendChild(src);

  (ctx.container || document.body).appendChild(_overlay);
}

function _paintOverlay() {
  if (_el.roster) {
    _el.roster.innerHTML = "";
    if (!S.profiles.length) {
      const d = document.createElement("div");
      d.style.cssText = "color:#9fb1bf;font-size:11px";
      d.textContent = S.state === "live" ? "no profiles returned" : ("awaiting live roster (" + S.state + ")");
      _el.roster.appendChild(d);
    }
    S.profiles.forEach((p) => {
      const row = document.createElement("div");
      const on = p.id === S.selectedProfile;
      row.style.cssText = "display:flex;flex-wrap:wrap;gap:5px;align-items:center;cursor:pointer;padding:5px 6px;border-radius:6px;border:1px solid " +
        (on ? "#39d3c4" : "#1d2a36") + ";background:" + (on ? "#12202b" : "#0a1117");
      const avail = p.availability && p.availability.available;
      const nm = document.createElement("b");
      nm.style.cssText = "font:600 11px ui-monospace,monospace;color:" + (avail ? "#39d3c4" : "#e8c074");
      nm.textContent = p.id + " v" + (p.version || "?");
      row.appendChild(nm);
      const mk = (t, color) => { const s = document.createElement("span"); s.textContent = t; s.style.cssText = "font:9.5px ui-monospace,monospace;padding:1px 5px;border-radius:5px;border:1px solid #1d2a36;color:" + color; return s; };
      row.appendChild(mk(p.honesty_label || "MODELED", "#e8c074"));
      const lic = (p.provenance && p.provenance.license) || "—";
      row.appendChild(mk("lic:" + lic, "#9fb1bf"));
      const integ = p.provenance && p.provenance.sha256_integrity;
      if (integ) row.appendChild(mk("sha:" + integ, integ === "match" ? "#2fd07a" : "#ff9b6b"));
      row.appendChild(mk(avail ? "available" : "UNAVAILABLE", avail ? "#2fd07a" : "#ff9b6b"));
      const nv = p.provenance && p.provenance.not_verbatim_of;
      const auth = document.createElement("div");
      auth.style.cssText = "flex:1 1 100%;font:9.5px ui-sans-serif;color:#5b6c78;line-height:1.4";
      auth.textContent = "by " + ((p.provenance && p.provenance.author) || "?") + (nv ? " · not verbatim of: " + nv : "");
      row.appendChild(auth);
      row.addEventListener("click", () => { S.selectedProfile = p.id; _highlightSelected(); _paintOverlay(); });
      _el.roster.appendChild(row);
    });
  }
  if (_el.applyState) _el.applyState.textContent = "apply state: " + S.applyState + (S.selectedProfile ? "  ·  profile: " + S.selectedProfile : "");
}

function _paintReceipt() {
  if (!_el.receipt) return;
  if (!S.lastReceipt) { _el.receipt.textContent = "— apply a profile to see the live signed receipt —"; return; }
  const r = S.lastReceipt;
  const sig = r.signature || {};
  const lines = [
    "schema        : " + (r.schema || "?"),
    "profile       : " + (r.profile && r.profile.id) + " v" + (r.profile && r.profile.version),
    "profile sha256: " + (r.profile && r.profile.sha256),
    "sha integrity : " + (r.profile && r.profile.sha256_integrity),
    "model_id      : " + r.model_id,
    "Λ (lambda)    : " + r.lambda + "  (floor " + r.lambda_floor + ")",
    "tier_selected : " + r.tier_selected,
    "reason        : " + r.reason,
    "honesty_label : " + r.honesty_label,
    "capability    : " + r.capability_claim,
    "api_key_wired : " + r.api_key_wired,
    "provenance    : by " + (r.provenance && r.provenance.author) + " · " + (r.provenance && r.provenance.license),
    "not_verbatim  : " + (r.provenance && r.provenance.not_verbatim_of),
    "signature     : " + sig.alg + " / " + sig.envelope + " · signed=" + sig.signed,
    "  value       : " + (sig.value || "?"),
    "  honesty     : " + (sig.honesty || "?"),
    "conjecture    : " + r.conjecture_note,
    "",
    "response      : " + (S.lastResponse || ""),
  ];
  _el.receipt.textContent = lines.join("\n");
}

// =========================================================================================
// unmount
// =========================================================================================
function unmount() {
  try { if (_poll) _poll.stop(); } catch (_) {}
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
  _poll = null; _overlay = _group = _modelCore = _beam = _billboard = null;
  _profileNodes = []; _badge = null; _el = {};
  S.profiles = []; S.lastReceipt = null; S.lastResponse = null; S.selectedProfile = null;
  _stage = _THREE = _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_PROFILES, EP_APPLY], mount, unmount };
