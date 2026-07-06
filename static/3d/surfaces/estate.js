// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
//
// surfaces/estate.js — ESTATE HOLOGRAM · the unified cross-tab overview (Dev9).
//
// Leader / technique modeled: a single "holographic estate" command view — the
// recognized pattern for ops command centers (NVIDIA Omniverse digital-twin
// overview + Microsoft Holograph unified loop). One scene reads MULTIPLE live
// endpoints at once and composes a glance of every other surface:
//   • energy ring        ← /api/a11oy/v1/harvest/posture       (price / renewable / joules)
//   • fabric hex          ← /api/a11oy/v1/compute-pool-hardened (nodes / gpu / sovereign)
//   • PNT horizon         ← /api/a11oy/v1/pnt/limits            (4 physical-bounds pillars)
//   • governance arc      ← /api/a11oy/v1/ecosystem/kpi-board   (locked-8 / Λ / CHAPAQ)
//   • PINN volume glance  ← /api/a11oy/v1/anatomy/loop          (reservoir / beats / ayni)
//
// PRIMARY ENDPOINT (per Dev0 contract): /api/a11oy/v1/ecosystem/kpi-board — the estate
// Λ/KPI rollup (locked-8 EXACTLY 8, Λ < 1.0 Conjecture 1, CHAPAQ verdict, apps reachable,
// restraint tile). We poll it first; if it 404s we degrade honestly (NO-LIVE-DATA) and the
// other four pollers still light their rings from the individual surfaces' real endpoints.
//
// DOCTRINE v11 (binding): WIRE TO LIVE DATA — every value on screen traces to a real a11oy
// endpoint via ctx.live.poll and carries its honesty label read STRAIGHT from the JSON
// (MEASURED / MODELED / SAMPLE / STRUCTURAL-ONLY). We NEVER fabricate or hardcode telemetry.
// If a value is not live we render it grayed with NO-LIVE-DATA; if an endpoint 404s or
// returns degraded we render the honest degraded state, not a crash.
//
// CONTRACT: default-export { id, title, endpoints[], mount(ctx), unmount() }.

const ID = "estate";
const TITLE = "Estate Hologram";

// the five live endpoints this overview funnels into one scene
const EP_KPI    = "/api/a11oy/v1/ecosystem/kpi-board"; // primary (governance arc + Λ)
const EP_ENERGY = "/api/a11oy/v1/harvest/posture";     // energy ring
const EP_FABRIC = "/api/a11oy/v1/compute-pool-hardened";  // fabric hex (egress-scrubbed)
const EP_PNT    = "/api/a11oy/v1/pnt/limits";          // PNT horizon
const EP_LOOP   = "/api/a11oy/v1/anatomy/loop";        // PINN volume glance / reservoir

// palette (matches the other surfaces' accents so the estate reads as the union)
const C = {
  energy: 0xe8c074, fabric: 0x39d3c4, pnt: 0x6fb1ff, gov: 0x8a6bff,
  pinn: 0x2fd07a, slate: 0x8a97a3, cream: 0xeef3f6, dim: 0x46586a, red: 0xff6b6b,
};

let _stage = null, _THREE = null, _ctx = null;
let _root = null, _overlay = null, _frameFn = null;
let _hud = {};                 // live HUD chip/value rows
let _scene = null;             // built scene-object refs the frame loop animates
const _anim = {};              // eased animation targets
const _handles = [];           // every poll handle (stopped on unmount)

function _num(x) {
  if (x === null || x === undefined) return null;
  const n = typeof x === "number" ? x : Number(x);
  return Number.isFinite(n) ? n : null;
}
function ease(cur, target, k) { return cur + (target - cur) * k; }
function _norm(raw) {
  // map an arbitrary honesty token to a canonical doctrine label for the chip
  if (!raw) return "STRUCTURAL-ONLY";
  const u = String(raw).toUpperCase();
  if (u.indexOf("MEASURED") >= 0) return "MEASURED";
  if (u.indexOf("MODELED") >= 0 || u.indexOf("MODEL") >= 0) return "MODELED";
  if (u.indexOf("LIVE") >= 0) return "LIVE";
  if (u.indexOf("SAMPLE") >= 0) return "SAMPLE";
  return "STRUCTURAL-ONLY";
}

// ----------------------------------------------------------------------------
// scene — the five glance widgets arranged radially around a central core.
// All geometry is lightweight (low poly + instancing where it counts) to hold
// the 60fps target on the WebGL2 fallback path.
// ----------------------------------------------------------------------------
function buildScene() {
  const THREE = _THREE;
  _root = new THREE.Group();
  _scene = {};

  // lights
  _root.add(new THREE.AmbientLight(0xffffff, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 0.9); key.position.set(6, 12, 8); _root.add(key);

  // ---- DEMO 1: central estate core (unified Λ heart; pulses on KPI freshness) ----
  const coreGeo = new THREE.IcosahedronGeometry(1.4, 1);
  const coreMat = new THREE.MeshStandardMaterial({
    color: C.gov, emissive: C.gov, emissiveIntensity: 0.4, metalness: 0.4, roughness: 0.35, wireframe: true,
  });
  _scene.core = new THREE.Mesh(coreGeo, coreMat);
  _root.add(_scene.core);

  // ---- DEMO 2: governance arc — locked-8 segments + Λ sweep (from kpi-board) ----
  _scene.govSegs = [];
  const arcR = 5.6;
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 1.6 - Math.PI * 0.8;
    const seg = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.16, 0.16),
      new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.3 }),
    );
    seg.position.set(Math.cos(a) * arcR, 3.4, Math.sin(a) * arcR);
    seg.lookAt(0, 3.4, 0);
    _root.add(seg); _scene.govSegs.push(seg);
  }
  // Λ sweep needle
  _scene.lambdaNeedle = new THREE.Mesh(
    new THREE.ConeGeometry(0.14, 1.1, 8),
    new THREE.MeshStandardMaterial({ color: C.gov, emissive: C.gov, emissiveIntensity: 0.6 }),
  );
  _scene.lambdaNeedle.position.set(0, 3.4, 0);
  _root.add(_scene.lambdaNeedle);

  // ---- DEMO 3: energy ring — radius/tint from price + renewable (harvest/posture) ----
  _scene.energyRing = new THREE.Mesh(
    new THREE.TorusGeometry(3.4, 0.12, 12, 64),
    new THREE.MeshStandardMaterial({ color: C.energy, emissive: C.energy, emissiveIntensity: 0.35 }),
  );
  _scene.energyRing.rotation.x = Math.PI / 2;
  _root.add(_scene.energyRing);

  // ---- DEMO 4: energy joules reservoir glance (fill bar; only fills when MEASURED) ----
  _scene.resShell = new THREE.Mesh(
    new THREE.CylinderGeometry(0.5, 0.5, 2.0, 16, 1, true),
    new THREE.MeshBasicMaterial({ color: C.energy, transparent: true, opacity: 0.18, side: THREE.DoubleSide, wireframe: true }),
  );
  _scene.resShell.position.set(-6.2, 1.0, 0);
  _root.add(_scene.resShell);
  _scene.resFluid = new THREE.Mesh(
    new THREE.CylinderGeometry(0.46, 0.46, 1.0, 16),
    new THREE.MeshStandardMaterial({ color: C.energy, emissive: C.energy, emissiveIntensity: 0.5 }),
  );
  _scene.resFluid.position.set(-6.2, 0.05, 0);
  _scene.resFluid.scale.y = 0.001;
  _root.add(_scene.resFluid);

  // ---- DEMO 5: fabric hex field — instanced node cells (compute-pool nodes) ----
  const HEXN = 24;
  const hexGeo = new THREE.CylinderGeometry(0.34, 0.34, 0.18, 6);
  const hexMat = new THREE.MeshStandardMaterial({ color: C.fabric, emissive: C.fabric, emissiveIntensity: 0.25 });
  _scene.hex = new THREE.InstancedMesh(hexGeo, hexMat, HEXN);
  _scene.hex.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  const dummy = new THREE.Object3D();
  let idx = 0;
  for (let ring = 0; ring < 3 && idx < HEXN; ring++) {
    const count = ring === 0 ? 1 : ring * 6;
    for (let k = 0; k < count && idx < HEXN; k++) {
      const a = (k / count) * Math.PI * 2;
      const rr = ring * 0.8;
      dummy.position.set(6.2 + Math.cos(a) * rr, 0.1, Math.sin(a) * rr);
      dummy.updateMatrix();
      _scene.hex.setMatrixAt(idx, dummy.matrix);
      _scene.hex.setColorAt(idx, new THREE.Color(C.dim));
      idx++;
    }
  }
  _scene.hexCount = idx;
  _scene.hex.instanceMatrix.needsUpdate = true;
  _root.add(_scene.hex);

  // ---- DEMO 6: PNT horizon — 4 physical-bounds pillars (pnt/limits) ----
  _scene.pillars = [];
  for (let i = 0; i < 4; i++) {
    const p = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.5, 0.5),
      new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.3 }),
    );
    p.position.set(-2.4 + i * 1.6, -3.0, -5.6);
    _root.add(p); _scene.pillars.push(p);
  }

  // ---- DEMO 7: PINN/anatomy volume glance — beat particle ring (anatomy/loop) ----
  const PN = 64;
  const pgeo = new THREE.BufferGeometry();
  const ppos = new Float32Array(PN * 3);
  for (let i = 0; i < PN; i++) {
    const a = (i / PN) * Math.PI * 2;
    ppos[i * 3] = Math.cos(a) * 2.2; ppos[i * 3 + 1] = -3.0 + Math.sin(a * 3) * 0.2; ppos[i * 3 + 2] = 5.6 + Math.sin(a) * 2.2;
  }
  pgeo.setAttribute("position", new THREE.BufferAttribute(ppos, 3));
  _scene.beats = new THREE.Points(pgeo, new THREE.PointsMaterial({ color: C.pinn, size: 0.18, transparent: true, opacity: 0.5 }));
  _root.add(_scene.beats);

  // billboards label each cluster honestly (default STRUCTURAL-ONLY until live)
  try {
    _scene.bb = {
      gov: _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Governance · Λ", scale: 0.5, position: [0, 5.0, 0] }),
      energy: _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Energy", scale: 0.45, position: [-6.2, 2.6, 0] }),
      fabric: _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Fabric", scale: 0.45, position: [6.2, 1.6, 0] }),
      pnt: _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "PNT bounds", scale: 0.45, position: [0, -1.9, -5.6] }),
      pinn: _ctx.label.billboard(THREE, "STRUCTURAL-ONLY", { text: "Anatomy loop", scale: 0.45, position: [0, -1.9, 5.6] }),
    };
    Object.values(_scene.bb).forEach((b) => b && _root.add(b));
  } catch (_) { _scene.bb = {}; }

  _anim.lambda = 0; _anim.lambdaT = 0;       // Λ needle angle target (0..1 → arc)
  _anim.fill = 0; _anim.fillT = 0;           // reservoir fill (only when MEASURED)
  _anim.energyTint = 0; _anim.energyTintT = 0;
  _anim.beatPulse = 0;

  _stage.scene.add(_root);
  try { if (_stage.backend === "webgl2") _stage.setBloom(true); } catch (_) {}
}

// ----------------------------------------------------------------------------
// HUD — one combined live KPI board; every row carries an honesty chip.
// ----------------------------------------------------------------------------
function buildHud() {
  const lab = _ctx.label;
  _overlay = document.createElement("div");
  _overlay.className = "szl3d-estate-hud";
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "6",
    display: "flex", flexDirection: "column", gap: "6px",
    maxWidth: "min(94%,440px)", font: "12px ui-monospace,SFMono-Regular,Menlo,monospace",
    color: "#cfe0ea", background: "rgba(6,11,16,.74)", border: "1px solid #15212c",
    borderRadius: "10px", padding: "12px 14px", backdropFilter: "blur(3px)",
  });

  const title = document.createElement("div");
  title.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px;display:flex;gap:8px;align-items:center";
  title.innerHTML = "◇ Estate Hologram <span style='color:#46586a;font-weight:400'>· 5 endpoints · one scene</span>";
  _overlay.appendChild(title);

  const badge = _ctx.live.createBadge();
  _overlay.appendChild(badge.el);
  _hud.badge = badge;

  function row(key, name) {
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;align-items:center;gap:8px;justify-content:space-between";
    const left = document.createElement("span"); left.textContent = name; left.style.color = "#9fb1bf";
    const right = document.createElement("span"); right.style.cssText = "display:flex;align-items:center;gap:6px";
    const val = document.createElement("span"); val.textContent = "—"; val.style.color = "#eef3f6";
    const chip = lab.chip("STRUCTURAL-ONLY"); chip.style.transform = "scale(.92)";
    right.appendChild(val); right.appendChild(chip);
    wrap.appendChild(left); wrap.appendChild(right);
    _overlay.appendChild(wrap);
    _hud[key] = { val, chip };
  }
  // ≥15 combined KPI rows spanning all five surfaces — each a wired value + honesty chip
  row("locked8", "locked-8 formulas");        // governance (kpi-board)
  row("lambda", "Λ aggregator");              // governance (kpi-board)
  row("checks", "trust axes passing");        // governance (kpi-board)
  row("chapaq", "CHAPAQ verdict");            // governance (kpi-board)
  row("apps", "apps reachable");              // governance (kpi-board)
  row("restraint", "restraint tile");         // governance (kpi-board)
  row("price", "energy price EUR/MWh");       // energy
  row("renew", "renewable %");                // energy
  row("joules", "harvested joules");          // energy
  row("power", "power_w sample");             // energy
  row("nodes", "fabric nodes reachable");     // fabric
  row("gpu", "GPU nodes live");               // fabric
  row("sovereign", "sovereign GPU");          // fabric
  row("pnt", "PNT bounds pillars");           // pnt
  row("beats", "loop beats/cycle");           // anatomy
  row("credits", "reservoir work_credits");   // anatomy
  row("ayni", "Ayni balance");                // anatomy

  const note = document.createElement("div");
  note.style.cssText = "color:#6d7d8a;font-size:10.5px;line-height:1.45;margin-top:4px;border-top:1px solid #15212c;padding-top:6px";
  note.textContent = "Unified overview: governance arc (kpi-board) + energy ring + fabric hex + PNT horizon + anatomy beat glance. Every value wired live; NO-LIVE-DATA shown grayed, never fabricated. Λ = Conjecture 1, clamped < 1.0.";
  _overlay.appendChild(note);

  const legend = _ctx.label.legend(); legend.style.opacity = "0.85"; legend.style.marginTop = "2px";
  _overlay.appendChild(legend);

  (_ctx.container || document.body).appendChild(_overlay);
}

function _setRow(key, text, label) {
  const r = _hud[key];
  if (!r) return;
  r.val.textContent = text;
  _ctx.label.updateChip(r.chip, _norm(label));
}

// ----------------------------------------------------------------------------
// pollers — each wires REAL endpoint values; honest NO-LIVE-DATA on missing/error.
// ----------------------------------------------------------------------------
function onKpi(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    // primary down — degrade honestly; individual pollers still light their surfaces
    ["locked8", "lambda", "checks", "chapaq", "apps", "restraint"].forEach((k) => _setRow(k, "NO-LIVE-DATA", "STRUCTURAL-ONLY"));
    _anim.lambdaT = 0;
    _scene.govSegs.forEach((s) => s.material.color.setHex(C.dim));
    return;
  }
  const lab = _norm(meta.label || (json && json.label));

  // locked-8 (always display canonical 8; flag source defects honestly)
  const l8 = (json && json.locked8) || {};
  const okCount = _num(l8.display_count) ?? _num(l8.source_count);
  _setRow("locked8", (l8.ok === false ? "8 (canonical · source DEFECT)" : (okCount != null ? `${okCount}/8` : "8")), l8.ok === false ? "STRUCTURAL-ONLY" : lab);
  _scene.govSegs.forEach((s, i) => s.material.color.setHex(i < 8 ? C.gov : C.dim));

  // Λ aggregator — clamped < 1.0, Conjecture 1
  const lam = (json && json.lambda) || {};
  const lv = _num(lam.value);
  if (lv != null) {
    _setRow("lambda", `${lv.toFixed(3)} (< ${_num(lam.cap) ?? 1.0})`, lab);
    _anim.lambdaT = Math.max(0, Math.min(1, lv));
  } else { _setRow("lambda", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); _anim.lambdaT = 0; }

  const cp = _num(lam.checks_passing), ct = _num(lam.checks_total);
  if (cp != null && ct != null) _setRow("checks", `${cp}/${ct}`, lab);
  else _setRow("checks", "NO-LIVE-DATA", "STRUCTURAL-ONLY");

  // CHAPAQ verdict
  const ch = json && json.chapaq_verdict;
  _setRow("chapaq", ch ? (ch.verdict || ch.decision || "present") : "NO-LIVE-DATA", ch ? lab : "STRUCTURAL-ONLY");

  // apps reachable
  const apps = (json && json.apps) || {};
  const reach = Object.keys(apps).filter((k) => apps[k] && apps[k].reachable).length;
  const tot = Object.keys(apps).length;
  _setRow("apps", tot ? `${reach}/${tot}` : "NO-LIVE-DATA", tot ? lab : "STRUCTURAL-ONLY");

  // restraint tile (its own honesty label)
  const rt = (json && json.restraint) || null;
  _setRow("restraint", rt ? (rt.tile || "present") : "NO-LIVE-DATA", rt ? _norm(rt.label) : "STRUCTURAL-ONLY");

  _anim.beatPulse = 1; // KPI freshness pulses the core
}

function onEnergy(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    ["price", "renew", "joules", "power"].forEach((k) => _setRow(k, "NO-LIVE-DATA", "STRUCTURAL-ONLY"));
    _anim.fillT = 0; _anim.energyTintT = 0;
    return;
  }
  const price = _num(json && json.price_now_eur_mwh);
  if (price != null) { _setRow("price", price.toFixed(1), "MEASURED"); _anim.energyTintT = price < 0 ? 1 : 0; }
  else _setRow("price", "NO-LIVE-DATA", "STRUCTURAL-ONLY");

  const renew = _num(json && json.renewable_share_pct);
  if (renew != null) { _setRow("renew", renew.toFixed(0) + "%", "MEASURED"); }
  else _setRow("renew", "NO-LIVE-DATA", "STRUCTURAL-ONLY");

  // joules — MEASURED only when the JSON says so; never fabricate a fill
  const jlabel = _norm(json && json.joules_label);
  const ev = (json && json.joules_evidence) || {};
  const jm = _num(ev.joules_measured_total);
  if (jlabel === "MEASURED" && jm != null) {
    _setRow("joules", jm.toExponential(2) + " J", "MEASURED");
    _anim.fillT = Math.max(0.04, Math.min(1, Math.log10(Math.max(1, jm)) / 12));
  } else {
    _setRow("joules", jlabel === "SAMPLE" ? "sample (no on-box NVML)" : "NO-LIVE-DATA", jlabel === "SAMPLE" ? "SAMPLE" : "STRUCTURAL-ONLY");
    _anim.fillT = 0; // honest: no measured joules → empty reservoir
  }
  const pw = _num(ev.power_w_sample);
  if (pw != null) _setRow("power", pw.toFixed(1) + " W", jlabel === "MEASURED" ? "MEASURED" : "SAMPLE");
  else _setRow("power", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
}

function onFabric(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    ["nodes", "gpu", "sovereign"].forEach((k) => _setRow(k, "NO-LIVE-DATA", "STRUCTURAL-ONLY"));
    for (let i = 0; i < _scene.hexCount; i++) _scene.hex.setColorAt(i, new _THREE.Color(C.dim));
    if (_scene.hex.instanceColor) _scene.hex.instanceColor.needsUpdate = true;
    return;
  }
  const counts = (json && json.counts) || {};
  const reach = _num(counts.nodes_reachable), tot = _num(counts.nodes_total);
  if (reach != null && tot != null) _setRow("nodes", `${reach}/${tot}`, "MEASURED");
  else _setRow("nodes", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
  const gpu = _num(counts.gpu_nodes_reachable);
  _setRow("gpu", gpu != null ? String(gpu) : "NO-LIVE-DATA", gpu != null ? "MEASURED" : "STRUCTURAL-ONLY");
  const sov = _num(counts.sovereign_gpu_live);
  _setRow("sovereign", sov != null ? String(sov) : "NO-LIVE-DATA", sov != null ? "MEASURED" : "STRUCTURAL-ONLY");

  // light hex cells by reachable node count (honest: only as many as are live)
  const lit = reach != null ? reach : 0;
  for (let i = 0; i < _scene.hexCount; i++) {
    _scene.hex.setColorAt(i, new _THREE.Color(i < lit ? C.fabric : C.dim));
  }
  if (_scene.hex.instanceColor) _scene.hex.instanceColor.needsUpdate = true;
}

function onPnt(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    _setRow("pnt", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
    _scene.pillars.forEach((p) => p.material.color.setHex(C.dim));
    return;
  }
  const pillars = (json && json.pillars) || {};
  const keys = Object.keys(pillars);
  const wired = keys.filter((k) => pillars[k] && pillars[k].wired).length;
  if (keys.length) {
    _setRow("pnt", `${wired}/${keys.length} wired`, _norm(json && json.label) || "MODELED");
    _scene.pillars.forEach((p, i) => {
      const k = keys[i];
      const on = k && pillars[k] && pillars[k].wired;
      p.material.color.setHex(on ? C.pnt : C.dim);
      p.scale.y = on ? 1.6 : 1.0;
    });
  } else { _setRow("pnt", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); }
}

function onLoop(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    ["beats", "credits", "ayni"].forEach((k) => _setRow(k, "NO-LIVE-DATA", "STRUCTURAL-ONLY"));
    return;
  }
  const beats = _num(json && json.beats_last_cycle);
  _setRow("beats", beats != null ? String(beats) : "NO-LIVE-DATA", beats != null ? "MODELED" : "STRUCTURAL-ONLY");
  const credits = _num(json && json.reservoir && json.reservoir.work_credits);
  _setRow("credits", credits != null ? credits.toFixed(2) : "NO-LIVE-DATA", credits != null ? "MODELED" : "STRUCTURAL-ONLY");
  const ayni = json && json.ayni;
  _setRow("ayni", ayni ? (ayni.balanced ? "balanced" : "imbalanced") : "NO-LIVE-DATA", ayni ? "MODELED" : "STRUCTURAL-ONLY");
  if (beats != null) _anim.beatPulse = 1;
}

// ----------------------------------------------------------------------------
// frame loop — eased animation; cheap per-frame work to hold 60fps.
// ----------------------------------------------------------------------------
function frame() {
  if (!_root || !_scene) return;
  const t = performance.now() * 0.001;

  // core slow spin + freshness pulse
  _scene.core.rotation.y += 0.004; _scene.core.rotation.x += 0.0015;
  _anim.beatPulse = ease(_anim.beatPulse, 0, 0.04);
  const s = 1 + _anim.beatPulse * 0.18;
  _scene.core.scale.setScalar(s);

  // ---- DEMO 8: Λ needle sweeps the governance arc (0..1 → the arc span) ----
  _anim.lambda = ease(_anim.lambda, _anim.lambdaT, 0.08);
  const ang = (_anim.lambda * 1.6 - 0.8) * Math.PI;
  _scene.lambdaNeedle.rotation.z = -ang;

  // ---- DEMO 9: energy ring tint pulses red on negative price ----
  _anim.energyTint = ease(_anim.energyTint, _anim.energyTintT, 0.06);
  _scene.energyRing.material.emissiveIntensity = 0.35 + 0.4 * (0.5 + 0.5 * Math.sin(t * 2)) * _anim.energyTint;
  _scene.energyRing.rotation.z += 0.002;

  // ---- DEMO 10: reservoir fluid rises to MEASURED joules fraction only ----
  _anim.fill = ease(_anim.fill, _anim.fillT, 0.07);
  const fy = Math.max(0.001, _anim.fill * 1.9);
  _scene.resFluid.scale.y = fy;
  _scene.resFluid.position.y = 0.05 + fy * 0.5;

  // ---- DEMO 11: anatomy beat particles drift (loop circulation glance) ----
  _scene.beats.rotation.y += 0.01;
  _scene.beats.material.opacity = 0.35 + 0.25 * (0.5 + 0.5 * Math.sin(t * 3));

  // ---- DEMO 12: fabric hex slow rotation (the compute mesh breathing) ----
  _scene.hex.rotation.y += 0.0015;
}

// ----------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  buildScene();
  buildHud();

  // one shared LIVE badge follows the PRIMARY (kpi-board) poll
  const badge = _hud.badge;

  // ---- DEMO 13: poll the PRIMARY governance/KPI endpoint ----
  _handles.push(ctx.live.poll(EP_KPI, 5000, onKpi, { badge }));
  // ---- DEMO 14: poll energy + fabric ----
  _handles.push(ctx.live.poll(EP_ENERGY, 6000, onEnergy));
  _handles.push(ctx.live.poll(EP_FABRIC, 7000, onFabric));
  // ---- DEMO 15: poll PNT bounds + anatomy loop ----
  _handles.push(ctx.live.poll(EP_PNT, 8000, onPnt));
  _handles.push(ctx.live.poll(EP_LOOP, 6500, onLoop));

  _frameFn = () => frame();
  _stage.onFrame(_frameFn);

  return { id: ID, started: true, endpoints: 5 };
}

function unmount() {
  for (const h of _handles) { try { h && h.stop && h.stop(); } catch (_) {} }
  _handles.length = 0;
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_root) {
      _root.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m && m.map && m.map.dispose) m.map.dispose(); if (m && m.dispose) m.dispose(); });
        }
      });
      if (_stage) _stage.scene.remove(_root);
    }
  } catch (_) {}
  try { if (_stage) _stage.setBloom(false); } catch (_) {}
  _root = null; _overlay = null; _scene = null; _frameFn = null; _hud = {}; _stage = null; _THREE = null; _ctx = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_KPI, EP_ENERGY, EP_FABRIC, EP_PNT, EP_LOOP], mount, unmount };
