// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/anatomy_body.js — ANATOMY · Living Body (Dev8, Layer 3).
//
// Renders the sovereign estate as a LIVING, BREATHING body-systems VIEW driven by
// GET /api/a11oy/v1/anatomy/vitals (Layers 1+2 backend, PR #719). Nothing here is
// fabricated: every pixel traces to a field on the live vitals JSON and carries its
// VERBATIM honesty label (MEASURED / MODELED / SAMPLE / UNAVAILABLE / EXPERIMENTAL).
//
// WHAT BREATHES / BEATS:
//   - LUNGS: metal.lungs.breaths[] — each reachable GPU lung expands/contracts at a
//     rate ∝ breathing_rate_watts. The GLM lung is UNAVAILABLE (breathing_rate_watts
//     null) → rendered DARK + still, never faked alive.
//   - HEART / CIRCULATION: metabolism.circulation.flowing + metabolism.beats_last_cycle
//     drive a pulsing heart and a beat travelling the circulation ring. flowing=false
//     → the ring goes still + grey (honest DEGRADED), never a fabricated flow.
//   - SYSTEMS: the 8 systems[] each render as an organ cluster; a health FSM maps the
//     VERBATIM band (healthy/degraded/down/unavailable) → colour + opacity. UNAVAILABLE
//     organs render dim/dark; they are NEVER shown alive.
//
// DOCTRINE: SZL is NEVER claimed to be literally alive — this is a MODELED physiological
// projection over REAL telemetry (top-level `view` disclaimer is rendered verbatim).
// A MODELED next-harvest-window panel is derived from metabolism.intake_rate (grid
// posture); when intake_rate.label is UNAVAILABLE we say so honestly and invent no window.
// Λ = Conjecture 1 (never a theorem). 0 runtime CDN (three.js via ctx.THREE). Palette:
// lattice-blue / violet-blue / proof-teal / greys only (no purple).
//
// CONTRACT: ES module default-exporting { id, title, endpoints[], mount(ctx), unmount() }.

const ID = "anatomy_body";
const TITLE = "Anatomy · Living Body";
const ENDPOINT = "/api/a11oy/v1/anatomy/vitals";

// palette — lattice-blue, violet-blue, proof-teal, greys ONLY (purple banned) --------
const C_BLUE   = 0x5b8dee;   // lattice-blue  — live lungs / intake
const C_VIOLET = 0x8a6bff;   // violet-blue   — "down" band / accents
const C_TEAL   = 0x3af4c8;   // proof-teal    — healthy / heartbeat
const C_GREY   = 0x6b7684;   // honest grey   — degraded neutral
const C_DARK   = 0x27313f;   // dark slate    — UNAVAILABLE (dim, never alive)

// Health FSM — VERBATIM band -> visual. A missing/unknown band degrades to UNAVAILABLE
// (dim), never up to healthy. Colour is ALWAYS paired with the band WORD in a label.
const BAND_FSM = {
  healthy:     { color: C_TEAL,   opacity: 0.92, emissive: 0.85 },
  degraded:    { color: C_BLUE,   opacity: 0.62, emissive: 0.45 },
  down:        { color: C_VIOLET, opacity: 0.5,  emissive: 0.35 },
  unavailable: { color: C_DARK,   opacity: 0.16, emissive: 0.05 },
};
function _bandVis(band) { return BAND_FSM[String(band || "unavailable")] || BAND_FSM.unavailable; }

const BODY_R = 7.0;          // ring radius the 8 systems sit on
const LUNG_Y = 3.2;          // lungs sit high on the torso

let _ctx = null, _stage = null, _THREE = null, _handle = null;
let _root = null, _overlay = null;
let _lungs = [];             // [{ group, mesh, mat, sprite, rateWatts, live }]
let _heart = null, _heartMat = null;
let _ring = null, _ringMat = null, _beatComet = null;
let _systems = [];           // [{ group, key, sprite, organs:[{mesh,mat,band}] }]
let _hud = {};
let _t = 0;
let _pulse = 0;              // heartbeat envelope, re-armed each new beat cycle
let _flowing = false;
let _lastBeatSig = "";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
function _disposeObj(o) {
  if (!o) return;
  o.traverse && o.traverse((c) => {
    if (c.geometry) { try { c.geometry.dispose(); } catch (_) {} }
    if (c.material) {
      const mats = Array.isArray(c.material) ? c.material : [c.material];
      mats.forEach((m) => { try { if (m.map) m.map.dispose(); m.dispose(); } catch (_) {} });
    }
  });
}

function _billboard(parent, label, text, scale, pos) {
  try {
    const s = _ctx.label.billboard(_THREE, label, { text, scale, position: pos });
    parent.add(s);
    return s;
  } catch (_) { return null; }
}

// ---------------------------------------------------------------------------
// scene construction
// ---------------------------------------------------------------------------
function _buildScene() {
  const THREE = _THREE;
  _root = new THREE.Group();
  _stage.scene.add(_root);

  _root.add(new THREE.AmbientLight(0xffffff, 0.5));
  const key = new THREE.PointLight(0xdfe9ff, 1.05, 80);
  key.position.set(7, 11, 9);
  _root.add(key);

  _buildLungs();
  _buildHeartAndRing();
  _buildSystems();

  // faint ground plane below the display plane (holograph feel)
  const grid = new THREE.GridHelper(26, 26, 0x1d2a36, 0x121a22);
  grid.position.y = -6.0;
  grid.material.transparent = true; grid.material.opacity = 0.35;
  _root.add(grid);
}

// LUNGS — one breathing lobe per metal.lungs.breaths[] entry. Built lazily on first
// data so the count + labels match the REAL breaths array (never assume 2 vs 3).
function _ensureLungs(breaths) {
  const THREE = _THREE;
  if (_lungs.length === breaths.length) return;
  // (re)build the lung lobes to match the live breaths[] length
  _lungs.forEach((l) => { _root.remove(l.group); _disposeObj(l.group); });
  _lungs = [];
  const n = breaths.length || 1;
  const spread = 3.0;
  breaths.forEach((b, i) => {
    const group = new THREE.Group();
    const x = (i - (n - 1) / 2) * spread;
    group.position.set(x, LUNG_Y, 0);
    // a lung lobe: a slightly squashed icosphere
    const geo = new THREE.IcosahedronGeometry(1.0, 3);
    geo.scale(0.78, 1.15, 0.72);
    const live = !!b.live && (b.breathing_rate_watts !== null && b.breathing_rate_watts !== undefined);
    const mat = new THREE.MeshStandardMaterial({
      color: live ? C_BLUE : C_DARK,
      emissive: live ? C_BLUE : C_DARK,
      emissiveIntensity: live ? 0.55 : 0.06,
      metalness: 0.25, roughness: 0.5,
      transparent: true, opacity: live ? 0.9 : 0.18,
    });
    const mesh = new THREE.Mesh(geo, mat);
    group.add(mesh);
    const label = String(b.joules_label || (live ? "MEASURED" : "UNAVAILABLE"));
    const shortName = String(b.name || "lung").split("(")[0].trim();
    const sprite = _billboard(group, label, shortName + " · " + label, 0.44, [0, 1.7, 0]);
    _root.add(group);
    _lungs.push({ group, mesh, mat, sprite, rateWatts: null, live, label, name: shortName });
  });
}

// HEART + CIRCULATION RING — the beat lives here (circulation.flowing + beats_last_cycle).
function _buildHeartAndRing() {
  const THREE = _THREE;
  // heart: a pulsing core at torso centre
  const hGeo = new THREE.IcosahedronGeometry(0.85, 2);
  _heartMat = new THREE.MeshStandardMaterial({
    color: C_TEAL, emissive: C_TEAL, emissiveIntensity: 0.7,
    metalness: 0.2, roughness: 0.4, transparent: true, opacity: 0.9,
  });
  _heart = new THREE.Mesh(hGeo, _heartMat);
  _heart.position.set(0, 0.6, 0);
  _root.add(_heart);
  _billboard(_heart, "MEASURED", "HEART · circulation", 0.4, [0, 1.3, 0]);

  // circulation ring the beat travels
  const rGeo = new THREE.TorusGeometry(BODY_R, 0.07, 18, 200);
  rGeo.rotateX(Math.PI / 2);
  _ringMat = new THREE.MeshStandardMaterial({
    color: C_TEAL, emissive: C_TEAL, emissiveIntensity: 0.4,
    metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.55,
  });
  _ring = new THREE.Mesh(rGeo, _ringMat);
  _ring.position.y = 0.6;
  _root.add(_ring);

  const cGeo = new THREE.SphereGeometry(0.22, 16, 16);
  const cMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending,
  });
  _beatComet = new THREE.Mesh(cGeo, cMat);
  _beatComet.position.set(BODY_R, 0.6, 0);
  _root.add(_beatComet);
}

// SYSTEMS — 8 clusters around the body ring; built lazily to match systems[].
function _ensureSystems(systems) {
  const THREE = _THREE;
  if (_systems.length === systems.length) return;
  _systems.forEach((s) => { _root.remove(s.group); _disposeObj(s.group); });
  _systems = [];
  const n = systems.length || 1;
  systems.forEach((sys, si) => {
    const group = new THREE.Group();
    const ang = (si / n) * Math.PI * 2;
    group.position.set(Math.cos(ang) * BODY_R, -0.4, Math.sin(ang) * BODY_R);
    const organs = [];
    const list = Array.isArray(sys.organs) ? sys.organs : [];
    const m = list.length || 1;
    list.forEach((org, oi) => {
      const oGeo = new THREE.IcosahedronGeometry(0.2, 1);
      const oMat = new THREE.MeshStandardMaterial({
        color: C_DARK, emissive: C_DARK, emissiveIntensity: 0.05,
        metalness: 0.3, roughness: 0.5, transparent: true, opacity: 0.16,
      });
      const mesh = new THREE.Mesh(oGeo, oMat);
      // pack organs on a small stacked spiral so big clusters (nervous=23) stay legible
      const t = oi / m;
      const rr = 0.75 + 0.55 * t;
      const aa = oi * 2.399963;              // golden-angle spread
      mesh.position.set(Math.cos(aa) * rr, (t - 0.5) * 1.8, Math.sin(aa) * rr);
      group.add(mesh);
      organs.push({ mesh, mat: oMat, band: String(org.band || "unavailable"),
                    id: org.id, label: String(org.label || "UNAVAILABLE") });
    });
    // system label carries VERBATIM system label + band word
    const sysLabel = String(sys.label || "MODELED");
    const sysKey = String(sys.system || "system");
    const sprite = _billboard(group, sysLabel,
      sysKey + " · " + sysLabel + " · " + String(sys.band || "unavailable"),
      0.4, [0, 1.8, 0]);
    _root.add(group);
    _systems.push({ group, key: sysKey, sprite, organs, band: String(sys.band || "unavailable") });
  });
}

function _buildSystems() { /* built lazily from live systems[] in _onData */ }

// ---------------------------------------------------------------------------
// HUD overlay (DOM)
// ---------------------------------------------------------------------------
function _row(label) {
  const r = document.createElement("div");
  r.style.cssText = "display:flex;justify-content:space-between;gap:14px;align-items:center;" +
    "font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:#cdd8e0;";
  const k = document.createElement("span"); k.textContent = label; k.style.color = "#7d8a96";
  const v = document.createElement("span"); v.style.color = "#eef3f6"; v.style.textAlign = "right";
  r.appendChild(k); r.appendChild(v);
  return { row: r, val: v };
}

function _buildHUD() {
  _overlay = document.createElement("div");
  _overlay.className = "szl3d-surface-overlay";
  Object.assign(_overlay.style, {
    position: "absolute", left: "14px", top: "14px", zIndex: "5",
    display: "flex", flexDirection: "column", gap: "9px",
    maxWidth: "min(94%,460px)", padding: "12px 14px",
    background: "rgba(8,14,20,.74)", border: "1px solid #1d2a36", borderRadius: "10px",
    backdropFilter: "blur(3px)",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px;";
  h.textContent = "◇ " + TITLE;
  _overlay.appendChild(h);

  const badge = _ctx.live.createBadge();
  _hud.badge = badge;
  _overlay.appendChild(badge.el);

  // top-level `view` disclaimer — rendered VERBATIM from the JSON when it arrives.
  _hud.view = document.createElement("div");
  _hud.view.style.cssText = "font:10.5px ui-monospace,Menlo,monospace;color:#9fb1bf;line-height:1.5;" +
    "border-left:3px solid #5b8dee;padding-left:8px;";
  _hud.view.textContent = "MODELED physiological projection over REAL telemetry — a body-systems " +
    "VIEW; SZL is never claimed to be literally alive.";
  _overlay.appendChild(_hud.view);

  // live field readout
  const fields = document.createElement("div");
  fields.style.cssText = "display:flex;flex-direction:column;gap:5px;margin-top:2px;";
  const mk = (key, lbl) => { const f = _row(lbl); _hud[key] = f.val; fields.appendChild(f.row); };
  mk("lungs", "lungs · total_watts");
  mk("breathing", "lungs · breathing (∝ watts)");
  mk("circulation", "circulation · flowing");
  mk("beats", "beats_last_cycle");
  mk("reservoir", "reservoir · energy_joules");
  mk("systemsLive", "systems · healthy / total");
  mk("organsLive", "organs_live / organs_total");
  _overlay.appendChild(fields);

  // MODELED next-harvest-window panel (derived from metabolism.intake_rate). Never
  // MEASURED; if intake_rate.label is UNAVAILABLE we say so and invent NO window.
  _hud.harvest = document.createElement("div");
  _hud.harvest.style.cssText = "font:10.5px ui-monospace,Menlo,monospace;color:#cdd8e0;line-height:1.5;" +
    "border-left:3px solid #8a6bff;padding-left:8px;margin-top:2px;";
  _hud.harvest.textContent = "MODELED next-harvest-window · awaiting intake_rate…";
  _overlay.appendChild(_hud.harvest);

  // honesty chips
  const chips = document.createElement("div");
  chips.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;align-items:center;";
  _hud.lungsChip = _ctx.label.chip("MEASURED", { text: "lungs" });
  _hud.joulesChip = _ctx.label.chip("SAMPLE", { text: "joules" });
  _hud.organChip = _ctx.label.chip("UNAVAILABLE", { text: "organs" });
  chips.appendChild(_hud.lungsChip);
  chips.appendChild(_hud.joulesChip);
  chips.appendChild(_hud.organChip);
  _overlay.appendChild(chips);

  const legend = _ctx.label.legend();
  legend.style.opacity = "0.85"; legend.style.marginTop = "4px";
  _overlay.appendChild(legend);

  // honesty footer — Ayni + Λ, always visible
  const foot = document.createElement("div");
  foot.style.cssText = "font:10px ui-monospace,Menlo,monospace;color:#7d8a96;line-height:1.5;margin-top:2px;";
  foot.textContent = "Ayni reciprocal, never net-positive (no free energy / over-unity) · " +
    "Λ = Conjecture 1, not a theorem · joules MEASURED only from a reachable NVML exporter, else UNAVAILABLE.";
  _overlay.appendChild(foot);

  (_ctx.container || document.body).appendChild(_overlay);
}

// ---------------------------------------------------------------------------
// LIVE update — map the real /anatomy/vitals JSON onto the scene. NEVER fabricate.
// ---------------------------------------------------------------------------
function _dash(v) { return (v === null || v === undefined || v === "") ? "NO-LIVE-DATA" : String(v); }

function _onData(json, meta) {
  if (!json || typeof json !== "object") return;
  const THREE = _THREE;

  // verbatim top-level disclaimer
  if (_hud.view && typeof json.view === "string") _hud.view.textContent = json.view;

  // ---- LUNGS -------------------------------------------------------------
  const lungs = (json.metal && json.metal.lungs) || {};
  const breaths = Array.isArray(lungs.breaths) ? lungs.breaths : [];
  _ensureLungs(breaths);
  breaths.forEach((b, i) => {
    const l = _lungs[i];
    if (!l) return;
    const w = b.breathing_rate_watts;
    const live = !!b.live && (w !== null && w !== undefined);
    l.live = live;
    l.rateWatts = live ? Number(w) : null;
    l.label = String(b.joules_label || (live ? "MEASURED" : "UNAVAILABLE"));
    l.mat.color.setHex(live ? C_BLUE : C_DARK);
    l.mat.emissive.setHex(live ? C_BLUE : C_DARK);
    l.mat.emissiveIntensity = live ? 0.55 : 0.06;
    l.mat.opacity = live ? 0.9 : 0.18;
  });
  if (_hud.lungs) {
    const tw = lungs.total_watts;
    _hud.lungs.textContent = (tw === null || tw === undefined ? "NO-LIVE-DATA" : tw + " W") +
      "  (" + String(lungs.label || "UNAVAILABLE") + ")";
  }
  if (_hud.breathing) {
    const liveN = breaths.filter((b) => b.live && b.breathing_rate_watts != null).length;
    const parts = breaths.map((b) => (b.breathing_rate_watts != null)
      ? Number(b.breathing_rate_watts).toFixed(1) + "W" : "UNAVAILABLE");
    _hud.breathing.textContent = liveN + "/" + breaths.length + " breathing · " + parts.join(" · ");
  }
  if (_hud.lungsChip) _ctx.label.updateChip(_hud.lungsChip, String(lungs.label || "UNAVAILABLE"), { text: "lungs" });

  // ---- CIRCULATION / HEART ----------------------------------------------
  const metab = json.metabolism || {};
  const circ = metab.circulation || {};
  _flowing = !!circ.flowing;
  const beats = (typeof metab.beats_last_cycle === "number") ? metab.beats_last_cycle : 0;
  const beatSig = String(beats) + "|" + String(circ.ledger_jobs || "") + "|" + String(json.computed_at || "");
  if (beatSig !== _lastBeatSig) { _pulse = 1.0; _lastBeatSig = beatSig; }

  const heartColor = _flowing ? C_TEAL : C_GREY;
  if (_heartMat) {
    _heartMat.color.setHex(heartColor);
    _heartMat.emissive.setHex(heartColor);
    _heartMat.emissiveIntensity = _flowing ? 0.7 : 0.2;
  }
  if (_ringMat) {
    _ringMat.color.setHex(heartColor);
    _ringMat.emissive.setHex(heartColor);
    _ringMat.emissiveIntensity = _flowing ? 0.4 : 0.12;
    _ringMat.opacity = _flowing ? 0.55 : 0.3;
  }
  if (_hud.circulation) {
    _hud.circulation.textContent = (_flowing ? "true" : "false") + "  (" + String(circ.label || "UNAVAILABLE") + ")";
    _hud.circulation.style.color = _flowing ? "#3af4c8" : "#e8c074";
  }
  if (_hud.beats) _hud.beats.textContent = String(beats);

  // ---- RESERVOIR (SAMPLE joules) ----------------------------------------
  const reservoir = metab.reservoir || {};
  if (_hud.reservoir) {
    const ej = reservoir.energy_joules;
    _hud.reservoir.textContent = (ej === null || ej === undefined ? "NO-LIVE-DATA" : ej) +
      "  (" + String(reservoir.energy_label || "UNAVAILABLE") + ")";
  }
  if (_hud.joulesChip) _ctx.label.updateChip(_hud.joulesChip, String(reservoir.energy_label || "SAMPLE"), { text: "joules" });

  // ---- SYSTEMS / ORGANS band FSM ----------------------------------------
  const systems = Array.isArray(json.systems) ? json.systems : [];
  _ensureSystems(systems);
  systems.forEach((sys, si) => {
    const s = _systems[si];
    if (!s) return;
    s.band = String(sys.band || "unavailable");
    if (s.sprite) { /* label baked at build; band shown in chip/summary */ }
    const list = Array.isArray(sys.organs) ? sys.organs : [];
    list.forEach((org, oi) => {
      const on = s.organs[oi];
      if (!on) return;
      const band = String(org.band || "unavailable");
      on.band = band;
      const vis = _bandVis(band);
      on.mat.color.setHex(vis.color);
      on.mat.emissive.setHex(vis.color);
      on.mat.emissiveIntensity = vis.emissive;
      on.mat.opacity = vis.opacity;
    });
  });

  // ---- summary readouts --------------------------------------------------
  const summary = json.summary || {};
  const bandCounts = summary.system_band_counts || {};
  if (_hud.systemsLive) {
    _hud.systemsLive.textContent = String(bandCounts.healthy || 0) + " / " + String(summary.systems || systems.length);
  }
  if (_hud.organsLive) {
    _hud.organsLive.textContent = String(summary.organs_live != null ? summary.organs_live : "?") +
      " / " + String(summary.organs_total != null ? summary.organs_total : "?");
  }
  if (_hud.organChip) {
    _ctx.label.updateChip(_hud.organChip, "UNAVAILABLE",
      { text: "organs " + String(summary.organs_live || 0) + "/" + String(summary.organs_total || 0) + " live" });
  }

  // ---- MODELED next-harvest-window (honest UNAVAILABLE, never invented) ---
  _updateHarvest(metab.intake_rate || {});
}

// Derive a MODELED harvest-window hint from grid posture. Doctrine: MODELED, never
// MEASURED; if the intake_rate label is UNAVAILABLE we say so and invent NO window.
function _updateHarvest(ir) {
  if (!_hud.harvest) return;
  const label = String(ir.label || "UNAVAILABLE");
  if (label === "UNAVAILABLE" || label.toUpperCase() === "UNAVAILABLE") {
    _hud.harvest.textContent = "MODELED next-harvest-window · NO-LIVE-DATA " +
      "(intake_rate UNAVAILABLE — window not invented)";
    return;
  }
  const price = ir.grid_price_eur_mwh;
  const posture = String(ir.posture || "sample");
  const neg = !!ir.negative_price;
  let hint;
  if (neg || posture === "harvest") {
    hint = "OPEN now (negative/cheap grid) — MODELED from posture";
  } else if (price === null || price === undefined) {
    hint = "NO-LIVE-DATA (no grid price) — window not invented";
  } else {
    hint = "posture=" + posture + " · grid " + price + " €/MWh — MODELED projection";
  }
  _hud.harvest.textContent = "MODELED next-harvest-window (" + label + ") · " + hint;
}

// ---------------------------------------------------------------------------
// per-frame animation
// ---------------------------------------------------------------------------
function _frame() {
  _t += 0.016;
  _pulse *= 0.955; // heartbeat envelope decay; re-armed on each new beat cycle

  // lungs breathe at a rate ∝ live watts (UNAVAILABLE lungs stay still) ------
  _lungs.forEach((l, i) => {
    if (!l.mesh) return;
    if (l.live && l.rateWatts) {
      // map watts -> breaths/sec (gentle): ~0.25..0.9 Hz for typical GPU idle-load watts
      const hz = 0.25 + Math.min(0.65, l.rateWatts / 25);
      const breath = 0.5 + 0.5 * Math.sin(_t * hz * Math.PI * 2 + i * 0.7);
      l.mesh.scale.setScalar(0.9 + 0.16 * breath);
      l.mat.emissiveIntensity = 0.4 + 0.35 * breath;
    } else {
      l.mesh.scale.setScalar(0.9); // UNAVAILABLE — still, dim; never faked alive
    }
  });

  // heart beat + travelling comet driven by flowing --------------------------
  if (_heart) {
    const beat = _flowing ? (0.7 + 0.9 * _pulse) : 0.4;
    _heart.scale.setScalar(0.85 + 0.3 * beat);
  }
  if (_beatComet) {
    const ph = _t * (_flowing ? 0.8 : 0.08);
    _beatComet.position.set(Math.cos(ph) * BODY_R, 0.6, Math.sin(ph) * BODY_R);
    _beatComet.scale.setScalar(0.6 + 0.8 * _pulse);
    _beatComet.material.opacity = _flowing ? (0.5 + 0.5 * _pulse) : 0.2;
  }

  // healthy organs gently pulse; unavailable stay inert ----------------------
  _systems.forEach((s) => {
    s.organs.forEach((on, oi) => {
      if (!on.mesh) return;
      if (on.band === "healthy") {
        const p = 1 + 0.12 * (0.5 + 0.5 * Math.sin(_t * 3 + oi));
        on.mesh.scale.setScalar(p);
      } else {
        on.mesh.scale.setScalar(1);
      }
    });
  });

  if (_root) _root.rotation.y += _flowing ? 0.0016 : 0.0006;
}

// ---------------------------------------------------------------------------
// mount / unmount
// ---------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _t = 0; _pulse = 0; _flowing = false; _lastBeatSig = "";
  _lungs = []; _systems = []; _hud = {};

  _buildScene();
  _buildHUD();

  try { _stage.setBloom && _stage.setBloom(true); } catch (_) {}
  _stage.onFrame(_frame);

  // WIRE TO LIVE DATA: poll the real vitals endpoint (~5s), badge auto-synced.
  _handle = ctx.live.poll(ENDPOINT, 5000, _onData, { badge: _hud.badge });

  return { id: ID, started: true };
}

function unmount() {
  try { if (_handle) _handle.stop(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try { if (_root && _stage) { _stage.scene.remove(_root); _disposeObj(_root); } } catch (_) {}
  try { _stage && _stage.setBloom && _stage.setBloom(false); } catch (_) {}
  _ctx = null; _stage = null; _THREE = null; _handle = null;
  _root = null; _overlay = null;
  _lungs = []; _heart = null; _heartMat = null;
  _ring = null; _ringMat = null; _beatComet = null;
  _systems = []; _hud = {};
  _t = 0; _pulse = 0; _flowing = false; _lastBeatSig = "";
}

export default { id: ID, title: TITLE, endpoints: [ENDPOINT], mount, unmount };
