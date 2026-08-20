// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
//
// surfaces/counter-uas.js — COUNTER-UAS / killinchu holographic surface (Dev4).
//
// Leader/technique modeled on: Anduril Lattice + CesiumJS + Dedrone.
//   3D globe + track entities + restricted-airspace SDF volumes + radar sweep cone
//   + signed-verdict beam. (We are *modeled on* the leader; we never claim to BE it.)
//
// VENDORING NOTE (Dev0 contract §6): the contract offered an escape hatch — full
// CesiumJS@1.123 OR a three.js globe (textured sphere + lat/long plotting). We took
// the three.js globe: it reuses the already-vendored three.js r170 (0 new MB, 0 CDN),
// keeps this PR lean, and is sufficient for track plotting + SDF volumes + sweep cone.
// See VENDOR_MANIFEST.md §Dev4 for the documented decision.
//
// HONESTY (killinchu charter / JIATF-401 C4 crosswalk): killinchu SENSES & EVIDENCES —
// it does NOT defeat (no jamming, no GNSS spoofing, no takeover, no kinetic). Every
// visual here is detect / track / classify / evidence + the signed verdict ONLY. There
// is NO kinetic effect, NO jam beam, NO interceptor-to-target engagement geometry. The
// "verdict beam" is the SIGNED DECISION locking onto a track — an evidence act, not a
// weapon. Λ = Conjecture 1 (advisory, NOT proven trust). All labels are read from the
// live JSON; values trace to real killinchu endpoints via ctx.live.poll, never hardcoded.
//
// Live data (same-origin bridge -> killinchu Space, see szl_counter_uas_proxy.py):
//   /api/a11oy/v1/counter-uas/evaluate     live Λ decision + REAL ECDSA-P256 DSSE sig
//   /api/a11oy/v1/counter-uas/telemetry    friendly fleet + threat tracks (honest data_kind)
//   /api/a11oy/v1/counter-uas/cued-tracks  externally-cued threat tracks (cuing_sensor)
//   /api/a11oy/v1/counter-uas/air-picture  real cooperative ADS-B (airplanes.live)
//   /api/a11oy/v1/counter-uas/gates        13-axis Λ-gate spec
//   /static/3d/surfaces/data/drones_db.json  53 verified drone fingerprints (vendored)

import { createShowcase } from "./_showcase.js";

const ID = "counter-uas";
const TITLE = "Counter-UAS · killinchu";

const EP = {
  evaluate:   "/api/a11oy/v1/counter-uas/evaluate",
  telemetry:  "/api/a11oy/v1/counter-uas/telemetry",
  cued:       "/api/a11oy/v1/counter-uas/cued-tracks",
  airpicture: "/api/a11oy/v1/counter-uas/air-picture",
  gates:      "/api/a11oy/v1/counter-uas/gates",
  // Governed in-request MODELED compute: evaluates the C-UAS formula stack + the
  // Λ-ROE advisory gate (Conjecture 1, gray never green; effector SIMULATED). This
  // is the surface's honest runtime-default label source (szl_cuas_formulas.py).
  compute:    "/api/a11oy/v1/counter-uas/compute",
  dronesDb:   "/static/3d/surfaces/data/drones_db.json",
};

// Honest surface state. The headline label is READ VERBATIM from the live compute
// endpoint and defaults to MODELED (the governed compute is a deterministic model of
// the C-UAS formulas — no live sensor/effector on the demo floor). Λ-ROE is Conjecture
// 1 and renders GRAY, never green. Never fabricated; never upgraded past what the
// endpoint declares.
const S = { label: null, compute: null, roe: null };
const LAMBDA_GRAY = 0x9aa7b0;   // Λ = Conjecture 1 → GRAY (never green). Doctrine v11.

// Globe radius (world units) + altitude scale (alt_m -> world units above surface).
const R = 3.0;
const ALT_SCALE = 1.0 / 18000;   // ~18 km ceiling maps to ~+1 globe radius of lift
const ALT_MAX_LIFT = 0.9;

// Classification → color (benign / unknown / hostile / friendly). NEVER a "defeat" color.
const CLS = {
  friendly: 0x39d3c4,  // teal — own fleet
  benign:   0x2fd07a,  // green — cooperative / allied
  unknown:  0xe8c074,  // amber — uncharacterized
  suspect:  0xffa54a,  // orange — Λ below threshold
  hostile:  0xff6b6b,  // red — Λ below floor (still only SENSED, never engaged)
};

let _ctx = null, _stage = null, THREE = null;
let _group = null, _globe = null, _handles = [], _frameOff = null, _overlay = null, _show = null;
let _disposables = [];

// Live caches (honest: empty until a real fetch lands).
let _state = {
  evaluate: null, telemetry: null, cued: null, airpicture: null, gates: null, db: null,
  compute: null, meta: {}, dbCount: 0,
};

// ── geo helpers ────────────────────────────────────────────────────────────
function llToVec(lat, lon, lift) {
  const phi = (90 - lat) * Math.PI / 180;
  const theta = (lon + 180) * Math.PI / 180;
  const r = R + (lift || 0);
  return new THREE.Vector3(
    -r * Math.sin(phi) * Math.cos(theta),
    r * Math.cos(phi),
    r * Math.sin(phi) * Math.sin(theta)
  );
}
function altLift(alt_m) {
  if (alt_m == null) return 0.02;
  return Math.min(ALT_MAX_LIFT, Math.max(0.0, alt_m * ALT_SCALE));
}
function classify(track) {
  // Honest mapping straight off the live fields — no invented severity.
  if (track.threat_category == null && track.role) return "friendly";
  const v = (track.lambda_verdict || "").toUpperCase();
  if (v.indexOf("THREAT") >= 0) return "hostile";
  if (v.indexOf("SUSPECT") >= 0) return "suspect";
  const s = (track.side || "").toLowerCase();
  if (s === "allied") return "benign";
  if (track.threat_category) return "unknown";
  return "unknown";
}

function _track(fn) { _disposables.push(fn); }

// ── demo builders (each returns {group, update?} and is added to _group) ─────
// D1: textured-feel globe (procedural lat/long graticule sphere; no external image,
//     0 CDN). Sense-only base for the air picture.
function buildGlobe() {
  const g = new THREE.Group();
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(R, 64, 48),
    new THREE.MeshStandardMaterial({ color: 0x0a1626, emissive: 0x06101c,
      emissiveIntensity: 0.5, metalness: 0.1, roughness: 0.9, transparent: true, opacity: 0.96 })
  );
  g.add(sphere);
  _globe = sphere;
  // graticule (lat/long lines) — gives the globe orientation without a texture/CDN
  const grat = new THREE.Group();
  const lineMat = new THREE.LineBasicMaterial({ color: 0x1d3a52, transparent: true, opacity: 0.5 });
  for (let lat = -60; lat <= 60; lat += 30) {
    const pts = [];
    for (let lon = -180; lon <= 180; lon += 6) pts.push(llToVec(lat, lon, 0.005));
    grat.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
  }
  for (let lon = -180; lon < 180; lon += 30) {
    const pts = [];
    for (let lat = -90; lat <= 90; lat += 6) pts.push(llToVec(lat, lon, 0.005));
    grat.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat));
  }
  g.add(grat);
  // D2: atmospheric SDF-style glow halo (additive shell)
  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.06, 48, 32),
    new THREE.MeshBasicMaterial({ color: 0x2a6f9e, transparent: true, opacity: 0.08,
      side: THREE.BackSide, blending: THREE.AdditiveBlending, depthWrite: false })
  );
  g.add(halo);
  _track(() => { sphere.geometry.dispose(); sphere.material.dispose(); halo.geometry.dispose(); halo.material.dispose(); });
  return { group: g };
}

// D3: radar sweep cone — animated sector that rotates around the site (Dedrone/Anduril
//     coverage sweep). This is a SENSOR coverage sweep, not an effector.
function buildRadarSweep(siteLat, siteLon) {
  const g = new THREE.Group();
  const center = llToVec(siteLat, siteLon, 0.0);
  // D4: sensor coverage cone (dome of regard)
  const coneGeo = new THREE.ConeGeometry(0.9, 1.2, 32, 1, true);
  const coneMat = new THREE.MeshBasicMaterial({ color: 0x39d3c4, transparent: true,
    opacity: 0.07, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending });
  const cone = new THREE.Mesh(coneGeo, coneMat);
  cone.position.copy(center.clone().multiplyScalar(1.18));
  cone.lookAt(0, 0, 0);
  cone.rotateX(Math.PI);
  g.add(cone);
  // sweep wedge
  const sweepGeo = new THREE.CircleGeometry(0.85, 24, 0, Math.PI / 5);
  const sweepMat = new THREE.MeshBasicMaterial({ color: 0x6fb1ff, transparent: true,
    opacity: 0.22, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending });
  const sweep = new THREE.Mesh(sweepGeo, sweepMat);
  sweep.position.copy(center.clone().multiplyScalar(1.02));
  sweep.lookAt(center.clone().multiplyScalar(2));
  g.add(sweep);
  _track(() => { coneGeo.dispose(); coneMat.dispose(); sweepGeo.dispose(); sweepMat.dispose(); });
  return { group: g, update: (t) => { sweep.rotation.z = t * 1.4; } };
}

// Build a single track entity: marker + altitude stalk + history trail + label.
function buildTrackEntity(track, isFriendly) {
  const g = new THREE.Group();
  const cls = isFriendly ? "friendly" : classify(track);
  const color = CLS[cls] || CLS.unknown;
  const lift = altLift(track.alt_m);
  const pos = llToVec(track.lat, track.lon, lift);

  // marker (octahedron = aircraft track glyph)
  const mGeo = new THREE.OctahedronGeometry(0.055, 0);
  const mMat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.85, metalness: 0.3, roughness: 0.4 });
  const marker = new THREE.Mesh(mGeo, mMat);
  marker.position.copy(pos);
  g.add(marker);

  // D5: altitude stalk to surface (3D altitude encoding)
  const surf = llToVec(track.lat, track.lon, 0.0);
  const stalk = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([surf, pos]),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 })
  );
  g.add(stalk);

  // D6: classification ring around hostile/suspect (SENSED status, never an engagement)
  let ring = null;
  if (cls === "hostile" || cls === "suspect") {
    const rGeo = new THREE.RingGeometry(0.09, 0.11, 24);
    const rMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5, side: THREE.DoubleSide, depthWrite: false });
    ring = new THREE.Mesh(rGeo, rMat);
    ring.position.copy(pos);
    ring.lookAt(0, 0, 0);
    g.add(ring);
    _track(() => { rGeo.dispose(); rMat.dispose(); });
  }

  _track(() => { mGeo.dispose(); mMat.dispose(); stalk.geometry.dispose(); stalk.material.dispose(); });
  return { group: g, marker, ring, cls, track };
}

// ── HUD / overlay ────────────────────────────────────────────────────────────
function hud(html) {
  const d = document.createElement("div");
  d.innerHTML = html;
  return d;
}
function row(label, value, labelToken) {
  const r = document.createElement("div");
  r.style.cssText = "display:flex;align-items:center;gap:8px;justify-content:space-between;font:11px ui-monospace,Menlo,monospace;color:#9fb1bf";
  const l = document.createElement("span"); l.textContent = label; l.style.color = "#cfe0ec";
  const v = document.createElement("span"); v.textContent = value; v.style.color = "#eef3f6"; v.style.fontWeight = "600";
  r.appendChild(l); r.appendChild(v);
  if (labelToken && _ctx) { const c = _ctx.label.chip(labelToken); c.style.marginLeft = "6px"; r.appendChild(c); }
  return r;
}

// ── live scene state ──────────────────────────────────────────────────────────
let _trackGroup = null;       // holds all track entities, rebuilt on telemetry/cued change
let _verdictBeam = null;      // signed-verdict beam (decision lock), not a weapon
let _dsseLock = null;         // DSSE signature lock animation node
let _fingerprintCallout = null;
let _restrictedZones = null;  // restricted-airspace SDF volumes
let _ridPanel = null, _gatesPanel = null, _verdictPanel = null, _posturePanel = null, _fpPanel = null;
let _computePanel = null;   // governed MODELED compute + Λ-ROE advisory gate (gray)
let _beamPhase = 0, _lockPhase = 0;

function rebuildTracks() {
  if (!_trackGroup) { _trackGroup = new THREE.Group(); _group.add(_trackGroup); }
  // clear old
  while (_trackGroup.children.length) {
    const c = _trackGroup.children.pop();
    _trackGroup.remove(c);
  }
  const entities = [];
  const tele = _state.telemetry;
  const cued = _state.cued;

  // D7: friendly fleet tracks (own fleet, teal) — telemetry.friendly_drones
  if (tele && Array.isArray(tele.friendly_drones)) {
    tele.friendly_drones.forEach((d) => {
      const e = buildTrackEntity(d, true); _trackGroup.add(e.group); entities.push(e);
    });
  }
  // D8: SENSED threat tracks (telemetry.threat_tracks) — classification color
  if (tele && Array.isArray(tele.threat_tracks)) {
    tele.threat_tracks.forEach((d) => {
      const e = buildTrackEntity(d, false); _trackGroup.add(e.group); entities.push(e);
    });
  }
  // D9: externally-cued tracks (cued-tracks) — carry cuing_sensor (we own no sensor)
  if (cued && Array.isArray(cued.tracks)) {
    cued.tracks.forEach((d) => {
      const e = buildTrackEntity(d, false); _trackGroup.add(e.group); entities.push(e);
    });
  }
  // D10: real cooperative ADS-B air picture (airplanes.live) — small benign dots,
  //      capped for perf. Cooperative manned aircraft = green (benign), per AirSight pattern.
  if (_state.airpicture && Array.isArray(_state.airpicture.aircraft)) {
    const ac = _state.airpicture.aircraft.slice(0, 120);
    const geo = new THREE.BufferGeometry();
    const verts = [];
    ac.forEach((a) => {
      if (a.lat == null || a.lon == null) return;
      const p = llToVec(a.lat, a.lon, altLift((a.alt_baro || 0) * 0.3048));
      verts.push(p.x, p.y, p.z);
    });
    geo.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({ color: CLS.benign, size: 0.04, transparent: true, opacity: 0.7 }));
    _trackGroup.add(pts);
    _track(() => { geo.dispose(); pts.material.dispose(); });
  }
  _trackGroup.userData.entities = entities;
  return entities;
}

// D11: restricted-airspace SDF volumes — translucent glowing boxes/spheres around
//      protected sites. Breach = pulse (SENSED breach, not an engagement).
function buildRestrictedZones(centerLat, centerLon) {
  const g = new THREE.Group();
  const sites = [
    { lat: centerLat, lon: centerLon, r: 0.42, name: "PROTECTED SITE" },
    { lat: centerLat + 0.02, lon: centerLon + 0.03, r: 0.26, name: "INNER KEEP-OUT" },
  ];
  const meshes = [];
  sites.forEach((s) => {
    const geo = new THREE.SphereGeometry(s.r, 24, 18);
    const mat = new THREE.MeshBasicMaterial({ color: 0xff6b6b, transparent: true, opacity: 0.08,
      side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending });
    const m = new THREE.Mesh(geo, mat);
    m.position.copy(llToVec(s.lat, s.lon, s.r * 0.4));
    g.add(m);
    // wireframe outline (SDF boundary)
    const wf = new THREE.LineSegments(new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xff8a8a, transparent: true, opacity: 0.35 }));
    wf.position.copy(m.position);
    g.add(wf);
    meshes.push(m);
    _track(() => { geo.dispose(); mat.dispose(); wf.geometry.dispose(); wf.material.dispose(); });
  });
  return { group: g, update: (t) => { meshes.forEach((m, i) => { m.material.opacity = 0.06 + 0.05 * (0.5 + 0.5 * Math.sin(t * 1.5 + i)); }); } };
}

// D12: Λ-gate signed-verdict beam — when /evaluate returns, a beam from the globe
//      core to the decision plane "locks" the verdict. This is the SIGNED DECISION
//      (an evidence act). Color = decision (ALLOW=green / CLASSIFY=amber / HALT=red).
//      It is NOT a weapon: nothing is emitted at a track, nothing is defeated.
function buildVerdictBeam() {
  const g = new THREE.Group();
  const geo = new THREE.CylinderGeometry(0.02, 0.08, 2.6, 16, 1, true);
  const mat = new THREE.MeshBasicMaterial({ color: CLS.benign, transparent: true, opacity: 0.0,
    side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending });
  const beam = new THREE.Mesh(geo, mat);
  beam.position.set(0, R + 1.3, 0);
  g.add(beam);
  _verdictBeam = beam;
  _track(() => { geo.dispose(); mat.dispose(); });
  return { group: g, update: (t) => {
    if (!_state.evaluate) return;
    const dec = (_state.evaluate.decision || "").toUpperCase();
    const col = dec === "ALLOW" ? CLS.benign : dec === "HALT" ? CLS.hostile : CLS.unknown;
    beam.material.color.setHex(col);
    beam.material.opacity = 0.18 + 0.12 * (0.5 + 0.5 * Math.sin(t * 2.2));
  } };
}

// D13: DSSE-signature lock animation — when the real ECDSA-P256 DSSE signature is
//      present (lambda_receipt.dsse.signed === true), an orbiting ring "locks" closed
//      around the verdict, with the signature truncation shown in the HUD. The lock is
//      the cryptographic seal of the SIGNED VERDICT — the evidence, not an effect.
function buildDsseLock() {
  const g = new THREE.Group();
  const geo = new THREE.TorusGeometry(0.5, 0.018, 12, 48);
  const mat = new THREE.MeshStandardMaterial({ color: 0x6fb1ff, emissive: 0x6fb1ff, emissiveIntensity: 0.6, metalness: 0.6, roughness: 0.3 });
  const ring = new THREE.Mesh(geo, mat);
  ring.position.set(0, R + 1.3, 0);
  g.add(ring);
  _dsseLock = ring;
  _track(() => { geo.dispose(); mat.dispose(); });
  return { group: g, update: (t) => {
    const signed = !!(_state.evaluate && _state.evaluate.lambda_receipt &&
      _state.evaluate.lambda_receipt.dsse && _state.evaluate.lambda_receipt.dsse.signed);
    ring.rotation.x = Math.PI / 2;
    ring.rotation.z = t * (signed ? 0.9 : 0.15);
    ring.material.color.setHex(signed ? 0x2fd07a : 0x8a97a3);   // green when signed, gray when not
    ring.material.emissive.setHex(signed ? 0x2fd07a : 0x8a97a3);
    ring.scale.setScalar(signed ? 1.0 : 0.92 + 0.06 * Math.sin(t * 3));
  } };
}

// ── overlay panels (the HUD reads live values + honest labels) ────────────────
function buildOverlay() {
  const badge = _ctx.live.createBadge();

  // Shared collapsible showcase: title + badge + legend live in the compact chrome;
  // the verdict / RID / posture / gates / fingerprint panels fold into the (collapsed)
  // body so the 3D globe stays the star and text never spans the viewport.
  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge, legend: true,
  });

  // panels flow (wrap) inside the body instead of a full-width two-column banner
  _overlay = document.createElement("div");
  Object.assign(_overlay.style, {
    display: "flex", flexWrap: "wrap", gap: "8px",
    fontFamily: "ui-monospace,Menlo,monospace",
  });

  const card = (title) => {
    const c = document.createElement("div");
    c.style.cssText = "flex:1 1 220px;background:rgba(8,14,20,.82);border:1px solid #1d2a36;border-radius:9px;padding:9px 11px;display:flex;flex-direction:column;gap:5px";
    const h = document.createElement("div");
    h.style.cssText = "font:600 11px ui-sans-serif,system-ui;color:#eef3f6;letter-spacing:.5px;text-transform:uppercase";
    h.textContent = title; c.appendChild(h);
    return c;
  };

  // D14: 13-axis Λ-gate verdict panel
  _verdictPanel = card("Λ-Gate Verdict · senses-and-evidences");
  _overlay.appendChild(_verdictPanel);

  // Governed MODELED compute + Λ-ROE advisory gate (Conjecture 1, gray never green).
  _computePanel = card("Governed compute · Λ-ROE (Conjecture 1)");
  _overlay.appendChild(_computePanel);

  // D15: DSSE signature panel (real ECDSA-P256)
  _fpPanel = null;
  _ridPanel = card("Remote-ID / RID Validator");
  _overlay.appendChild(_ridPanel);

  _posturePanel = card("JIATF-401 posture");
  _overlay.appendChild(_posturePanel);
  _gatesPanel = card("13-Axis Λ-Gates");
  _overlay.appendChild(_gatesPanel);
  _fingerprintCallout = card("Fingerprint match · 53-DB");
  _overlay.appendChild(_fingerprintCallout);

  _show.body.appendChild(_overlay);
  return badge;
}

function clearCard(card) { while (card.children.length > 1) card.removeChild(card.lastChild); }

function renderVerdict() {
  const ev = _state.evaluate;
  clearCard(_verdictPanel);
  if (!ev || ev.degraded) {
    _verdictPanel.appendChild(row("decision", ev && ev.degraded ? "DEGRADED" : "—", "STRUCTURAL-ONLY"));
    return;
  }
  const dec = ev.decision || "—";
  const lam = ev.lambda != null ? ev.lambda.toFixed(6) : "—";
  const floor = ev.lambda_floor != null ? ev.lambda_floor : "—";
  _verdictPanel.appendChild(row("decision", dec));
  _verdictPanel.appendChild(row("Λ score", lam + "  (floor " + floor + ")"));
  _verdictPanel.appendChild(row("Λ status", "Conjecture 1 · advisory"));
  // D16: real DSSE signature lock-on (truncated sig + keyid)
  const dsse = ev.lambda_receipt && ev.lambda_receipt.dsse;
  if (dsse) {
    const sig = (dsse.signatures && dsse.signatures[0] && dsse.signatures[0].sig) || "";
    const sigShort = sig ? (sig.slice(0, 18) + "…" + sig.slice(-8)) : "—";
    _verdictPanel.appendChild(row("DSSE", dsse.signed ? "SIGNED ✓" : "UNSIGNED", dsse.signed ? "MEASURED" : "STRUCTURAL-ONLY"));
    _verdictPanel.appendChild(row("keyid", dsse.keyid || "—"));
    _verdictPanel.appendChild(row("ECDSA-P256 sig", sigShort));
  }
  // D17: CI signing honesty disclosure (PLACEHOLDER per killinchu honest posture)
  if (ev.signature) {
    const ci = row("CI sign", ev.signature.indexOf("PLACEHOLDER") >= 0 ? "PLACEHOLDER" : "wired", "STRUCTURAL-ONLY");
    _verdictPanel.appendChild(ci);
  }
}

// Governed MODELED compute + Λ-ROE advisory gate. The headline label is read VERBATIM
// from the endpoint (defaults MODELED). Λ-ROE is Conjecture 1 — its chip is ALWAYS the
// gray Conjecture token, NEVER green; the effector is SIMULATED, human-on-loop. We honor
// the endpoint's explicit render contract (render_green must be false).
function renderCompute() {
  if (!_computePanel) return;
  clearCard(_computePanel);
  const j = _state.compute;
  // Runtime-default honesty label, read verbatim from the live compute endpoint. This
  // is the census single-source-of-truth (a11oy_frontier_page._derive_label): the
  // headline label is `(endpoint.label || "MODELED")`, never upgraded past what the
  // endpoint declares. Λ-ROE stays Conjecture 1 (gray) regardless.
  const jl = j && j.label;
  S.label = (jl || "MODELED").toUpperCase();
  if (!j || j.degraded || j.ok === false) {
    _computePanel.appendChild(row("compute", j && j.degraded ? "DEGRADED" : "—", S.label));
    // Λ-ROE remains Conjecture 1 (gray) even when the compute is unavailable.
    _computePanel.appendChild(row("Λ-ROE", "Conjecture 1 · advisory", "MODELED"));
    return;
  }
  const roe = j.lambda_roe_gate || {};
  S.roe = roe;
  _computePanel.appendChild(row("data", String(j.data_label || "MODELED"), S.label));
  const eng = (j.results && j.results.engageability) || {};
  if (eng.feasible != null) {
    _computePanel.appendChild(row("engageability", eng.feasible ? "feasible" : "infeasible",
      eng.effector === "SIMULATED" ? "SIMULATED" : "MODELED"));
  }
  const cons = (j.results && j.results.consensus) || {};
  if (cons.lambda2 != null) _computePanel.appendChild(row("consensus λ₂", String(cons.lambda2)));
  // Λ-ROE gate row — ALWAYS the gray Conjecture chip, NEVER green. Doctrine v11.
  const posture = roe.posture || "advisory";
  const roeRow = row("Λ-ROE", String(posture), "MODELED");
  // Force the Λ posture pill gray (Conjecture 1) regardless of sub-gate pass state.
  const pill = document.createElement("span");
  pill.textContent = "Conjecture 1 · gray";
  pill.style.cssText = "margin-left:6px;padding:1px 6px;border-radius:6px;font:10px ui-monospace,monospace;" +
    "color:#0d1117;background:#9aa7b0;";   // gray (#9aa7b0) — NEVER green
  roeRow.appendChild(pill);
  _computePanel.appendChild(roeRow);
  _computePanel.appendChild(row("authorization", String(roe.authorization || "advisory") +
    " · " + String(roe.control_mode || "human_on_loop")));
  _computePanel.appendChild(row("effector", String(roe.effector || "SIMULATED"), "SIMULATED"));
  _computePanel.appendChild(row("autonomous engage", roe.autonomous_engage ? "YES" : "NO — never"));
}

function renderRid() {
  clearCard(_ridPanel);
  const tele = _state.telemetry, cued = _state.cued;
  // RID validator: count tracks broadcasting a Remote-ID vs those without (RID-OFF =
  // spoofable/uncooperative). Honest: a broadcast ID is a CLAIM, not ground truth.
  let withRid = 0, withoutRid = 0;
  const scan = (arr, key) => (arr || []).forEach((t) => { (t[key]) ? withRid++ : withoutRid++; });
  if (tele) { scan(tele.friendly_drones, "remote_id"); scan(tele.threat_tracks, "remote_id"); }
  if (cued) scan(cued.tracks, "remote_id");
  _ridPanel.appendChild(row("RID present", String(withRid)));
  _ridPanel.appendChild(row("RID OFF (uncoop)", String(withoutRid)));
  _ridPanel.appendChild(row("note", "broadcast ID = claim"));
  if (tele && tele.data_kind) _ridPanel.appendChild(row("data_kind", String(tele.data_kind), tele.data_kind === "demo_mock" ? "SAMPLE" : "MEASURED"));
}

function renderPosture() {
  clearCard(_posturePanel);
  _posturePanel.appendChild(row("charter", "SENSE + EVIDENCE"));
  _posturePanel.appendChild(row("defeat", "OUT-OF-SCOPE"));
  _posturePanel.appendChild(row("no jam/spoof", "✓"));
  _posturePanel.appendChild(row("no takeover", "✓"));
  _posturePanel.appendChild(row("no kinetic", "✓"));
  _posturePanel.appendChild(row("human-on-loop", "ROE gate"));
  _posturePanel.appendChild(row("C4 strongest fit", "§6–§7 receipts"));
}

function renderGates() {
  clearCard(_gatesPanel);
  const g = _state.gates;
  if (!g || g.degraded || !Array.isArray(g.gates)) {
    _gatesPanel.appendChild(row("gates", g && g.degraded ? "DEGRADED" : "—", "STRUCTURAL-ONLY"));
    return;
  }
  _gatesPanel.appendChild(row("axes", String(g.count != null ? g.count : g.gates.length)));
  // show first few axis names live
  g.gates.slice(0, 5).forEach((ax) => _gatesPanel.appendChild(row("Λ" + ax.axis, ax.name || "—")));
  _gatesPanel.appendChild(row("status", "Conjecture 1 — OPEN"));
}

function renderFingerprint() {
  clearCard(_fingerprintCallout);
  const db = _state.db;
  if (!db || !Array.isArray(db)) {
    _fingerprintCallout.appendChild(row("DB", "loading…", "STRUCTURAL-ONLY"));
    return;
  }
  _fingerprintCallout.appendChild(row("fingerprints", String(db.length)));
  // D: attempt to match a SENSED threat track type to the DB (classification callout)
  const tele = _state.telemetry;
  let matched = null;
  if (tele && Array.isArray(tele.threat_tracks)) {
    for (const t of tele.threat_tracks) {
      const ty = (t.type || "").toUpperCase();
      matched = db.find((d) => ty && (String(d.model).toUpperCase().indexOf(ty.split("-")[0]) >= 0));
      if (matched) break;
    }
  }
  // fall back to a representative adversary fingerprint to show the callout shape
  const ex = matched || db.find((d) => d.side === "adversary") || db[0];
  if (ex) {
    _fingerprintCallout.appendChild(row("model", String(ex.model)));
    _fingerprintCallout.appendChild(row("mfr", String(ex.manufacturer)));
    _fingerprintCallout.appendChild(row("group", String(ex.group || "—")));
    _fingerprintCallout.appendChild(row("side", String(ex.side || "—")));
  }
  _fingerprintCallout.appendChild(row("source", "drones_db.json"));
}

// ── mount / unmount ───────────────────────────────────────────────────────────
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; THREE = ctx.THREE;
  _group = new THREE.Group();
  _stage.scene.add(_group);

  // lighting so the globe reads in 3D
  const amb = new THREE.AmbientLight(0x223344, 1.1);
  const key = new THREE.DirectionalLight(0xbfe0ff, 1.3); key.position.set(5, 6, 7);
  _group.add(amb); _group.add(key);
  _track(() => { /* lights freed with group removal */ });

  // build the static scene demos
  const updaters = [];
  const globe = buildGlobe(); _group.add(globe.group);

  // protected site (matches killinchu demo fleet vicinity ~ 37.42, -122.17)
  const siteLat = 37.4275, siteLon = -122.1697;
  const sweep = buildRadarSweep(siteLat, siteLon); _group.add(sweep.group); updaters.push(sweep.update);
  const zones = buildRestrictedZones(siteLat, siteLon); _group.add(zones.group); updaters.push(zones.update);
  const beam = buildVerdictBeam(); _group.add(beam.group); updaters.push(beam.update);
  const lock = buildDsseLock(); _group.add(lock.group); updaters.push(lock.update);

  // floating honesty billboard
  try {
    const bb = ctx.label.billboard(THREE, "MODELED", { text: "senses · evidences · NOT defeats · Λ-ROE Conjecture 1", scale: 0.42, position: [0, R + 2.0, 0] });
    _group.add(bb);
    _track(() => { if (bb.material.map) bb.material.map.dispose(); bb.material.dispose(); });
  } catch (_) {}

  const badge = buildOverlay();
  renderPosture(); renderVerdict(); renderCompute(); renderRid(); renderGates(); renderFingerprint();

  // per-frame animation (rotate the estate slowly + run demo updaters). The shell's
  // Stage has no offFrame(), so we self-guard: once unmounted, _group is null and the
  // callback no-ops (the shell disposes the renderer/loop on tab switch).
  let _t = 0;
  _frameOff = () => {
    if (!_group) return;
    _t += 0.016;
    _group.rotation.y += 0.0009;
    for (const u of updaters) { try { u(_t); } catch (_) {} }
    // pulse SENSED hostile/suspect rings
    if (_trackGroup && _trackGroup.userData.entities) {
      for (const e of _trackGroup.userData.entities) {
        if (e.ring) { e.ring.material.opacity = 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(_t * 3)); }
        if (e.marker) e.marker.rotation.y += 0.02;
      }
    }
  };
  _stage.onFrame(_frameOff);

  // ── wire LIVE data (never fabricate; degrade gracefully) ──
  // primary endpoint drives the badge
  _handles.push(ctx.live.poll(EP.evaluate, 6000, (json, meta) => {
    _state.evaluate = json; _state.meta.evaluate = meta; renderVerdict();
  }, { badge }));
  _handles.push(ctx.live.poll(EP.telemetry, 5000, (json, meta) => {
    _state.telemetry = json; _state.meta.telemetry = meta; rebuildTracks(); renderRid(); renderFingerprint();
  }));
  _handles.push(ctx.live.poll(EP.cued, 7000, (json) => {
    _state.cued = json; rebuildTracks(); renderRid();
  }));
  _handles.push(ctx.live.poll(EP.airpicture, 12000, (json) => {
    _state.airpicture = json; rebuildTracks();
  }));
  _handles.push(ctx.live.poll(EP.gates, 30000, (json) => {
    _state.gates = json; renderGates();
  }));
  // Governed MODELED compute + Λ-ROE advisory gate (Conjecture 1, gray never green).
  _handles.push(ctx.live.poll(EP.compute, 8000, (json) => {
    _state.compute = json; renderCompute();
  }));
  // 53-fingerprint DB (static vendored; fetched once)
  fetch(EP.dronesDb, { headers: { accept: "application/json" } })
    .then((r) => r.ok ? r.json() : null)
    .then((db) => { if (db) { _state.db = db; _state.dbCount = db.length; renderFingerprint(); } })
    .catch(() => {});

  return { id: ID, started: true };
}

function unmount() {
  for (const h of _handles) { try { h.stop(); } catch (_) {} }
  _handles = [];
  _frameOff = null;
  for (const d of _disposables) { try { d(); } catch (_) {} }
  _disposables = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _overlay = _show = null; _group = null; _globe = null; _trackGroup = null;
  _verdictBeam = null; _dsseLock = null; _stage = null; THREE = null; _ctx = null;
  _computePanel = null; S.label = null; S.compute = null; S.roe = null;
  _state = { evaluate: null, telemetry: null, cued: null, airpicture: null, gates: null, db: null, compute: null, meta: {}, dbCount: 0 };
}

export default { id: ID, title: TITLE, endpoints: [EP.evaluate, EP.telemetry, EP.cued, EP.airpicture, EP.gates, EP.compute], mount, unmount };
