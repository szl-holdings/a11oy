// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/anatomy.js — ANATOMY · Unified Loop (Dev8).
//
// Leader/technique modeled (NOT claimed to BE): Microsoft Holograph (spatiotemporal
// data above/below the display plane) + TSL-era particle attractors. We render the ONE
// closed circulation loop as a 3D organ-flow: a beat particle travels a torus ring,
// three YARQA organs (WAQAYCHAQ guard/store · KAMAY act/animate · RIKUY observe) pulse
// when flowing, a work-credit reservoir fills, the last receipt id tickers, and an Ayni
// reciprocity scale balances intake == output == stored (reciprocal, NEVER net-positive).
//
// EVERY value on screen is read live from /api/a11oy/v1/anatomy/loop (doctrine v11:
// WIRE TO LIVE DATA, never fabricate). HONESTY, baked in:
//   - organs are EXPERIMENTAL tier — they carry the BEAT (work + receipts), NOT electrons;
//     never claimed proven.
//   - joules off-box are SAMPLE (no power meter wired). Label read straight from the JSON.
//   - Ayni is reciprocal, never net-positive (no free energy / over-unity).
//   - Λ = Conjecture 1, never a theorem.
//   - when the loop is degraded:true / gpu sleeping, we render the honest DEGRADED state.
// The honesty token for the loop is SAMPLE (joules_label) — surfaced via the live badge
// and 3D billboards. The STRUCTURAL-ONLY chip remains in the legend so all 4 doctrine
// states are visible.
//
// CONTRACT: ES module default-exporting { id, title, endpoints[], mount(ctx), unmount() }.
// ctx supplies stage / container / live / label / THREE / szl3d (see Dev0 toolkit).

const ID = "anatomy";
const TITLE = "Anatomy · Unified Loop";
const ENDPOINT = "/api/a11oy/v1/anatomy/loop";

// loop geometry / palette ----------------------------------------------------
const RING_R = 5.2;             // major radius of the circulation torus
const RING_TUBE = 0.16;         // tube radius of the ring
const ORGAN_R = 0.62;           // organ node radius
const BEAT_PARTICLES = 1400;    // beat / blood particle stream around the ring
const C_FLOW = 0xff8fcf;        // circulation pink (HEART+BLOOD)
const C_FLOW_DIM = 0x4a2740;
const C_DEGRADED = 0x8a97a3;    // gray — honest degraded
const C_AYNI = 0x39d3c4;        // teal — reciprocity balanced
const C_AYNI_OFF = 0xe8c074;    // amber — out of balance
const C_RESERVOIR = 0x6fb1ff;   // blue — SAMPLE work-credit tank

// The three YARQA dispersal organs, in canonical loop order around the ring.
const ORGAN_ANGLES = { WAQAYCHAQ: Math.PI * 0.5, KAMAY: Math.PI * 1.1666, RIKUY: Math.PI * 1.8333 };

let _ctx = null, _stage = null, _THREE = null, _handle = null;
let _root = null, _overlay = null;
let _ring = null, _ringMat = null, _beats = null, _beatMat = null;
let _beatPhase = null;          // per-particle phase along the ring
let _organs = {};               // name -> { group, core, halo, sprite }
let _reservoir = null, _reservoirFill = null, _reservoirMat = null;
let _ayniGroup = null, _ayniBeam = null, _ayniL = null, _ayniR = null;
let _beatComet = null;          // the single traveling beat
let _hud = {};                  // DOM HUD field refs
let _last = null;               // last live JSON
let _meta = { state: "init", label: null };
let _t = 0;
let _pulse = 0;                 // 0..1 envelope re-armed on each new beat
let _lastReceipt = "";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
function _ringPos(THREE, angle, lift = 0) {
  // point on the circulation torus centerline (XZ plane, slight Y lift for organs)
  return new THREE.Vector3(Math.cos(angle) * RING_R, lift, Math.sin(angle) * RING_R);
}

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

function _fmtReceipt(id) {
  if (!id) return "—";
  const s = String(id);
  return s.length > 18 ? s.slice(0, 10) + "…" + s.slice(-6) : s;
}

// ---------------------------------------------------------------------------
// scene construction (demos #1–#15 are these objects + their live behaviors)
// ---------------------------------------------------------------------------
function _buildScene() {
  const THREE = _THREE;
  _root = new THREE.Group();
  _stage.scene.add(_root);

  // ambient + a soft key so MeshStandard organs read without a heavy rig
  const amb = new THREE.AmbientLight(0xffffff, 0.55);
  const key = new THREE.PointLight(0xffd9ec, 1.1, 60);
  key.position.set(6, 9, 8);
  _root.add(amb); _root.add(key);

  // DEMO #1 — the circulation loop ring (the ONE loop) ----------------------
  const ringGeo = new THREE.TorusGeometry(RING_R, RING_TUBE, 24, 220);
  ringGeo.rotateX(Math.PI / 2); // lay flat in XZ
  _ringMat = new THREE.MeshStandardMaterial({
    color: C_FLOW, emissive: C_FLOW, emissiveIntensity: 0.5,
    metalness: 0.3, roughness: 0.4, transparent: true, opacity: 0.92,
  });
  _ring = new THREE.Mesh(ringGeo, _ringMat);
  _root.add(_ring);

  // DEMO #2 — beat particle STREAM (blood) circulating the ring -------------
  const positions = new Float32Array(BEAT_PARTICLES * 3);
  _beatPhase = new Float32Array(BEAT_PARTICLES);
  for (let i = 0; i < BEAT_PARTICLES; i++) {
    const ph = (i / BEAT_PARTICLES) * Math.PI * 2;
    _beatPhase[i] = ph;
    const p = _ringPos(THREE, ph);
    positions[i * 3] = p.x; positions[i * 3 + 1] = p.y; positions[i * 3 + 2] = p.z;
  }
  const beatGeo = new THREE.BufferGeometry();
  beatGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  _beatMat = new THREE.PointsMaterial({
    color: C_FLOW, size: 0.12, transparent: true, opacity: 0.9,
    sizeAttenuation: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  _beats = new THREE.Points(beatGeo, _beatMat);
  _root.add(_beats);

  // DEMO #3 — the single traveling BEAT comet (one beat per cycle) ----------
  const cometGeo = new THREE.SphereGeometry(0.28, 18, 18);
  const cometMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending,
  });
  _beatComet = new THREE.Mesh(cometGeo, cometMat);
  _root.add(_beatComet);

  // DEMO #4–#6 — the 3 YARQA organ nodes (pulse on flowing=true) ------------
  Object.keys(ORGAN_ANGLES).forEach((name) => {
    const angle = ORGAN_ANGLES[name];
    const group = new THREE.Group();
    const pos = _ringPos(THREE, angle, 0.0);
    group.position.copy(pos);

    const coreGeo = new THREE.IcosahedronGeometry(ORGAN_R, 1);
    const coreMat = new THREE.MeshStandardMaterial({
      color: C_FLOW_DIM, emissive: C_FLOW_DIM, emissiveIntensity: 0.4,
      metalness: 0.5, roughness: 0.35,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    group.add(core);

    // DEMO #9 — organ halo ring — SDF-glow-style proxy, pulses with the beat when flowing
    const haloGeo = new THREE.RingGeometry(ORGAN_R * 1.4, ORGAN_R * 1.7, 48);
    const haloMat = new THREE.MeshBasicMaterial({
      color: C_FLOW, transparent: true, opacity: 0.0, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const halo = new THREE.Mesh(haloGeo, haloMat);
    halo.lookAt(0, 1, 0);
    group.add(halo);

    // DEMO #10 — EXPERIMENTAL-tier billboard label on each organ (honest tier) ----
    let sprite = null;
    try {
      sprite = _ctx.label.billboard(THREE, "STRUCTURAL-ONLY",
        { text: name + " · EXPERIMENTAL", scale: 0.5, position: [0, ORGAN_R + 0.9, 0] });
      group.add(sprite);
    } catch (_) {}

    _root.add(group);
    _organs[name] = { group, core, coreMat, halo, haloMat, sprite, angle };
  });

  // DEMO #7 — reservoir work-credit tank (fills with stored work_credits) ----
  _reservoir = new THREE.Group();
  _reservoir.position.set(0, 0, 0);
  const tankH = 3.0, tankR = 0.9;
  const shellGeo = new THREE.CylinderGeometry(tankR, tankR, tankH, 36, 1, true);
  const shellMat = new THREE.MeshStandardMaterial({
    color: 0x16202b, emissive: 0x0a141d, transparent: true, opacity: 0.35,
    side: THREE.DoubleSide, metalness: 0.2, roughness: 0.8,
  });
  _reservoir.add(new THREE.Mesh(shellGeo, shellMat));
  const fillGeo = new THREE.CylinderGeometry(tankR * 0.92, tankR * 0.92, 1, 36);
  _reservoirMat = new THREE.MeshStandardMaterial({
    color: C_RESERVOIR, emissive: C_RESERVOIR, emissiveIntensity: 0.5,
    transparent: true, opacity: 0.7, metalness: 0.1, roughness: 0.5,
  });
  _reservoirFill = new THREE.Mesh(fillGeo, _reservoirMat);
  _reservoirFill.scale.y = 0.001;
  _reservoirFill.position.y = -tankH / 2;
  _reservoir.userData.tankH = tankH;
  _reservoir.add(_reservoirFill);
  try {
    const rb = _ctx.label.billboard(THREE, "SAMPLE",
      { text: "RESERVOIR · work_credits", scale: 0.42, position: [0, tankH / 2 + 0.7, 0] });
    _reservoir.add(rb);
  } catch (_) {}
  _root.add(_reservoir);

  // DEMO #8 — Ayni reciprocity balance scale (intake=output=stored) ---------
  _ayniGroup = new THREE.Group();
  _ayniGroup.position.set(0, -3.6, 0);
  const beamGeo = new THREE.BoxGeometry(4.0, 0.08, 0.08);
  _ayniBeam = new THREE.Mesh(beamGeo, new THREE.MeshStandardMaterial({
    color: C_AYNI, emissive: C_AYNI, emissiveIntensity: 0.4, metalness: 0.4, roughness: 0.4,
  }));
  _ayniGroup.add(_ayniBeam);
  const fulcrum = new THREE.Mesh(
    new THREE.ConeGeometry(0.35, 0.7, 4),
    new THREE.MeshStandardMaterial({ color: 0x223040, metalness: 0.3, roughness: 0.7 }));
  fulcrum.position.y = -0.45;
  _ayniGroup.add(fulcrum);
  const panGeo = new THREE.SphereGeometry(0.34, 20, 20);
  _ayniL = new THREE.Mesh(panGeo, new THREE.MeshStandardMaterial({
    color: C_RESERVOIR, emissive: C_RESERVOIR, emissiveIntensity: 0.35 }));
  _ayniR = new THREE.Mesh(panGeo.clone(), new THREE.MeshStandardMaterial({
    color: C_FLOW, emissive: C_FLOW, emissiveIntensity: 0.35 }));
  _ayniL.position.set(-2.0, -0.4, 0);
  _ayniR.position.set(2.0, -0.4, 0);
  _ayniGroup.add(_ayniL); _ayniGroup.add(_ayniR);
  try {
    const ab = _ctx.label.billboard(THREE, "SAMPLE",
      { text: "AYNI · reciprocal, never net-positive", scale: 0.4, position: [0, 0.9, 0] });
    _ayniGroup.add(ab);
  } catch (_) {}
  _root.add(_ayniGroup);

  // DEMO #11 — a faint Holograph-style ground plane below the display plane ----
  const grid = new THREE.GridHelper(22, 22, 0x1d2a36, 0x121a22);
  grid.position.y = -5.2;
  grid.material.transparent = true; grid.material.opacity = 0.4;
  _root.add(grid);
}

// ---------------------------------------------------------------------------
// HUD overlay (DOM) — the textual demos (#16+) read straight off the JSON
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
    maxWidth: "min(94%,430px)", padding: "12px 14px",
    background: "rgba(8,14,20,.72)", border: "1px solid #1d2a36", borderRadius: "10px",
    backdropFilter: "blur(3px)",
  });

  const h = document.createElement("div");
  h.style.cssText = "font:600 13px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.4px;" +
    "display:flex;align-items:center;gap:9px;";
  h.innerHTML = "<span>◇ " + TITLE + "</span>";
  _overlay.appendChild(h);

  const badge = _ctx.live.createBadge();
  _hud.badge = badge;
  _overlay.appendChild(badge.el);

  // honesty banner — the doctrine truth, always visible
  const honesty = document.createElement("div");
  honesty.style.cssText = "font:10.5px ui-monospace,Menlo,monospace;color:#9fb1bf;line-height:1.5;" +
    "border-left:3px solid " + "#ff8fcf" + ";padding-left:8px;";
  honesty.textContent = "organs carry the BEAT (work + receipts), NOT electrons · EXPERIMENTAL tier, " +
    "never proven · joules SAMPLE off-box · Ayni reciprocal, never net-positive · Λ = Conjecture 1";
  _overlay.appendChild(honesty);

  // live field readout — each is a demo wired to a real JSON field
  const fields = document.createElement("div");
  fields.style.cssText = "display:flex;flexDirection:column;gap:5px;margin-top:2px;";
  fields.style.display = "flex"; fields.style.flexDirection = "column"; fields.style.gap = "5px";
  const mk = (key, lbl) => { const f = _row(lbl); _hud[key] = f.val; fields.appendChild(f.row); };
  mk("intakePosture", "intake · posture");          // DEMO #16
  mk("gridPrice", "intake · grid_price (€/MWh)");    // DEMO #17
  mk("gpuState", "intake · gpu_state");              // DEMO #18
  mk("beats", "beats_last_cycle");                   // DEMO #19
  mk("credits", "reservoir · work_credits");         // DEMO #20
  mk("receipt", "last_receipt_id");                  // DEMO #21
  mk("ayni", "ayni · intake=output=stored");         // DEMO #22
  _overlay.appendChild(fields);

  // honesty chips row: joules_label (live) + organ EXPERIMENTAL tier --------
  const chips = document.createElement("div");
  chips.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;align-items:center;";
  _hud.joulesChip = _ctx.label.chip("SAMPLE", { text: "joules" });
  _hud.organChip = _ctx.label.chip("STRUCTURAL-ONLY", { text: "organs EXPERIMENTAL" });
  chips.appendChild(_hud.joulesChip);
  chips.appendChild(_hud.organChip);
  _overlay.appendChild(chips);

  // full doctrine legend (keeps all 4 honesty states + STRUCTURAL-ONLY token)
  const legend = _ctx.label.legend();
  legend.style.opacity = "0.85"; legend.style.marginTop = "4px";
  _overlay.appendChild(legend);

  (_ctx.container || document.body).appendChild(_overlay);
}

// ---------------------------------------------------------------------------
// LIVE update — map the real /anatomy/loop JSON onto the scene. NEVER fabricate;
// when the loop is degraded:true / gpu sleeping, render the honest degraded state.
// ---------------------------------------------------------------------------
function _onData(json, meta) {
  _last = json; _meta = meta;
  const THREE = _THREE;
  const degraded = !!(json && (json.degraded || (json.intake && json.intake.degraded))) ||
    meta.state === "degraded";

  const intake = (json && json.intake) || {};
  const ayni = (json && json.ayni) || {};
  const reservoir = (json && json.reservoir) || {};
  const organs = (json && Array.isArray(json.organs)) ? json.organs : [];
  const beats = (json && typeof json.beats_last_cycle === "number") ? json.beats_last_cycle : 0;
  const credits = Number(reservoir.work_credits || 0);
  const receipt = (json && json.last_receipt_id) || "";
  const joulesLabel = (json && json.joules_label) || (reservoir.joules_label) || "SAMPLE";

  // DEMO #12 — beat-pulse envelope re-armed on each fresh receipt (a new cycle beat)
  if (receipt && receipt !== _lastReceipt) { _pulse = 1.0; _lastReceipt = receipt; }

  // DEMO #13 — ring + stream recolor: flowing pink vs honest DEGRADED gray ----
  const flowColor = degraded ? C_DEGRADED : C_FLOW;
  if (_ringMat) {
    _ringMat.color.setHex(flowColor);
    _ringMat.emissive.setHex(flowColor);
    _ringMat.emissiveIntensity = degraded ? 0.15 : 0.5;
    _ringMat.opacity = degraded ? 0.5 : 0.92;
  }
  if (_beatMat) {
    _beatMat.color.setHex(flowColor);
    _beatMat.opacity = degraded ? 0.35 : 0.9;
  }

  // ---- organs: pulse on flowing=true; gray + idle when not flowing --------
  organs.forEach((o) => {
    const name = (o && o.name || "").toUpperCase();
    const node = _organs[name];
    if (!node) return;
    const flowing = !!(o && o.flowing) && !degraded;
    node.flowing = flowing;
    node.coreMat.color.setHex(flowing ? C_FLOW : C_FLOW_DIM);
    node.coreMat.emissive.setHex(flowing ? C_FLOW : (degraded ? C_DEGRADED : C_FLOW_DIM));
    node.coreMat.emissiveIntensity = flowing ? 0.85 : 0.25;
    if (o && o.note) node.group.userData.note = o.note; // EXPERIMENTAL note carried live
  });

  // DEMO #14 — reservoir fill: scale to log-mapped work_credits (SAMPLE units) ----
  if (_reservoirFill && _reservoir) {
    const tankH = _reservoir.userData.tankH;
    // log map so a 0..big credit range reads on a fixed tank; honest: 0 -> empty.
    const frac = credits > 0 ? Math.min(1, Math.log10(1 + credits) / 4) : 0;
    const h = Math.max(0.001, frac * tankH);
    _reservoirFill.scale.y = h;
    _reservoirFill.position.y = -tankH / 2 + h / 2;
    _reservoirMat.color.setHex(degraded ? C_DEGRADED : C_RESERVOIR);
    _reservoirMat.emissive.setHex(degraded ? C_DEGRADED : C_RESERVOIR);
  }

  // DEMO #15 — Ayni scale: balance the beam to LEVEL when reciprocal & balanced ----
  // intake == output == stored is the doctrine invariant; never net-positive.
  if (_ayniBeam) {
    const i = Number(ayni.intake || 0), out = Number(ayni.output || 0), st = Number(ayni.stored || 0);
    const balanced = !!ayni.balanced && (i === out) && (out === st);
    // tilt proportional to the largest pairwise gap (level when balanced) ----
    const span = Math.max(Math.abs(i - out), Math.abs(out - st), Math.abs(i - st));
    const denom = Math.max(1, Math.abs(i) + Math.abs(out) + Math.abs(st));
    let tilt = balanced ? 0 : Math.min(0.35, span / denom);
    if (degraded) tilt = 0; // degraded empty cycle balances trivially (0==0==0)
    _ayniBeam.userData.targetTilt = (out > st ? -tilt : tilt);
    const c = balanced ? C_AYNI : C_AYNI_OFF;
    _ayniBeam.material.color.setHex(c);
    _ayniBeam.material.emissive.setHex(c);
    if (_ayniL) { _ayniL.material.color.setHex(degraded ? C_DEGRADED : C_RESERVOIR); }
    if (_ayniR) { _ayniR.material.color.setHex(degraded ? C_DEGRADED : C_FLOW); }
  }

  // ---- HUD textual readouts (honest "—"/NO-LIVE-DATA when absent) ----------
  const dash = (v) => (v === null || v === undefined || v === "") ? "—" : String(v);
  if (_hud.intakePosture) _hud.intakePosture.textContent = dash(intake.posture) + (degraded ? "  (DEGRADED)" : "");
  if (_hud.gridPrice) {
    const gp = intake.grid_price_eur_mwh;
    _hud.gridPrice.textContent = (gp === null || gp === undefined) ? "NO-LIVE-DATA" : String(gp);
  }
  if (_hud.gpuState) {
    const gs = dash(intake.gpu_state);
    _hud.gpuState.textContent = gs;
    _hud.gpuState.style.color = (gs === "sleeping" || gs === "unreachable") ? "#e8c074" : "#eef3f6";
  }
  if (_hud.beats) _hud.beats.textContent = String(beats);
  if (_hud.credits) _hud.credits.textContent = credits.toLocaleString() + "  (SAMPLE)";
  if (_hud.receipt) { _hud.receipt.textContent = _fmtReceipt(receipt); _hud.receipt.title = receipt || ""; }
  if (_hud.ayni) {
    const i = Number(ayni.intake || 0), out = Number(ayni.output || 0), st = Number(ayni.stored || 0);
    const ok = !!ayni.balanced;
    _hud.ayni.textContent = `${i}=${out}=${st}  ${ok ? "✓ balanced" : "✗ unbalanced"}`;
    _hud.ayni.style.color = ok ? "#39d3c4" : "#e8c074";
  }

  // ---- live honesty chips ------------------------------------------------
  if (_hud.joulesChip) _ctx.label.updateChip(_hud.joulesChip, joulesLabel, { text: "joules" });
  if (_hud.organChip) {
    // organs stay EXPERIMENTAL-tier; show flowing count honestly
    const flowingN = organs.filter((o) => o && o.flowing).length;
    _ctx.label.updateChip(_hud.organChip, "STRUCTURAL-ONLY",
      { text: `organs EXPERIMENTAL (${flowingN}/${organs.length} flowing)` });
  }
}

// ---------------------------------------------------------------------------
// per-frame animation: circulate the stream, pulse organs, tick the scale.
// ---------------------------------------------------------------------------
function _frame() {
  const THREE = _THREE;
  _t += 0.016;
  _pulse *= 0.96; // beat envelope decays each frame; re-armed on new receipt

  const degraded = _meta && _meta.state === "degraded";
  const flowSpeed = degraded ? 0.06 : 0.5;

  // beat stream circulation (demo #2 motion) --------------------------------
  if (_beats) {
    const pos = _beats.geometry.attributes.position;
    for (let i = 0; i < BEAT_PARTICLES; i++) {
      _beatPhase[i] += flowSpeed * 0.016 * (0.6 + 0.8 * ((i % 7) / 7));
      const ph = _beatPhase[i];
      const jitter = 0.05 * Math.sin(ph * 9 + i);
      const p = _ringPos(THREE, ph, jitter);
      pos.array[i * 3] = p.x; pos.array[i * 3 + 1] = p.y; pos.array[i * 3 + 2] = p.z;
    }
    pos.needsUpdate = true;
  }

  // the single beat comet riding the ring (demo #3) -------------------------
  if (_beatComet) {
    const ph = _t * (degraded ? 0.12 : 0.9);
    const p = _ringPos(THREE, ph, 0);
    _beatComet.position.copy(p);
    const s = 0.7 + 0.9 * _pulse;
    _beatComet.scale.setScalar(s);
    _beatComet.material.opacity = degraded ? 0.25 : (0.5 + 0.5 * _pulse);
  }

  // organ pulse on flowing (demo #4-6) -------------------------------------
  Object.keys(_organs).forEach((name) => {
    const n = _organs[name];
    if (!n) return;
    const beat = n.flowing ? (0.5 + 0.5 * Math.sin(_t * 4 + n.angle)) * (0.5 + _pulse) : 0;
    const s = 1 + 0.18 * beat;
    n.core.scale.setScalar(s);
    if (n.haloMat) n.haloMat.opacity = n.flowing ? 0.25 + 0.5 * beat : 0.0;
    if (n.halo) n.halo.scale.setScalar(1 + 0.25 * beat);
  });

  // Ayni beam easing toward target tilt (demo #8) ---------------------------
  if (_ayniBeam) {
    const target = _ayniBeam.userData.targetTilt || 0;
    _ayniBeam.rotation.z += (target - _ayniBeam.rotation.z) * 0.08;
    if (_ayniL && _ayniR) {
      const t = _ayniBeam.rotation.z;
      _ayniL.position.y = -0.4 + Math.sin(t) * 2.0;
      _ayniR.position.y = -0.4 - Math.sin(t) * 2.0;
    }
  }

  // gentle whole-loop rotation for the Holograph "above/below plane" feel
  if (_root) _root.rotation.y += degraded ? 0.0008 : 0.0022;
}

// ---------------------------------------------------------------------------
// mount / unmount
// ---------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _t = 0; _pulse = 0; _lastReceipt = ""; _organs = {}; _hud = {};

  _buildScene();
  _buildHUD();

  // enable the holographic bloom look when the backend supports it (no-op safe)
  try { _stage.setBloom && _stage.setBloom(true); } catch (_) {}

  _stage.onFrame(_frame);

  // WIRE TO LIVE DATA: poll the real loop endpoint, badge auto-synced.
  _handle = ctx.live.poll(ENDPOINT, 5000, _onData, { badge: _hud.badge });

  return { id: ID, started: true };
}

function unmount() {
  try { if (_handle) _handle.stop(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try {
    if (_root && _stage) { _stage.scene.remove(_root); _disposeObj(_root); }
  } catch (_) {}
  try { _stage && _stage.setBloom && _stage.setBloom(false); } catch (_) {}
  _ctx = null; _stage = null; _THREE = null; _handle = null;
  _root = null; _overlay = null; _ring = null; _ringMat = null;
  _beats = null; _beatMat = null; _beatPhase = null; _beatComet = null;
  _organs = {}; _reservoir = null; _reservoirFill = null; _reservoirMat = null;
  _ayniGroup = null; _ayniBeam = null; _ayniL = null; _ayniR = null;
  _hud = {}; _last = null; _meta = { state: "init", label: null }; _lastReceipt = "";
}

export default { id: ID, title: TITLE, endpoints: [ENDPOINT], mount, unmount };
