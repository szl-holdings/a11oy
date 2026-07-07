// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/energy.js — ENERGY · Harvest surface (Dev1, the FLAGSHIP).
//
// Leader / technique modeled: Electricity Maps (live carbon/price choropleth, 15-min
// resolution, flow arcs) + deck.gl GPUGridLayer / ColumnLayer / ArcLayer (GPU hexbin
// column grid + animated flow arcs + extruded negative-price columns).
//
// RENDERING CHOICE (documented in VENDOR_MANIFEST.md): we render the deck.gl *technique*
// in pure three.js r170 inside the shell-owned ctx.stage.scene. deck.gl needs its own GL
// context + canvas and its column/arc/grid layers are WebGL-only in v9 (no WebGPU), so a
// second deck.gl canvas would fight the toolkit's OrbitControls / bloom / WebGPU path /
// clearScene() lifecycle. three.js keeps the surface on the shared WebGPU-or-WebGL2 path
// and inside the one scene graph the shell owns. deck.gl is still vendored 0-CDN per the
// Dev0 contract for Dev9's estate map.
//
// DOCTRINE v11 (binding): WIRE TO LIVE DATA — every value on screen traces to a real
// a11oy endpoint via ctx.live.poll and carries its honesty label read STRAIGHT from the
// JSON (MEASURED/MODELED/SAMPLE/STRUCTURAL-ONLY). We NEVER fabricate or hardcode telemetry.
// If a value is not live we render it grayed with NO-LIVE-DATA. If the endpoint 404s or
// returns degraded we render the honest degraded state, not a crash.
//
// THE FUNNEL (founder's explicit ask — centerpiece): visualize OUR real harvested joules
// as a live-filling reservoir, fed from the MEASURED exporter (joules_evidence.
// joules_measured_total / power_w_sample), with negative-price windows soaking in real
// time. HONEST NOTE: off-box this API emits joules_label="sample" and joules_evidence={}
// (MEASURED requires on-box NVML). So off-box the reservoir shows its structure + the
// honest SAMPLE/NO-LIVE-DATA posture and does NOT invent a fill height; on-box, when a
// real fresh exporter sample arrives, the same geometry fills from the MEASURED joules.
//
// LIVE ENDPOINTS:
//   /api/a11oy/v1/harvest/posture  — posture, rank, wasted_energy_available, soak_hard,
//        measured_any, drivers, readings[] (per-feed reachable/measured + value),
//        joules_label, joules_evidence{joules_measured_total, exporter_node, power_w_sample},
//        and (on-box) flat price_now_eur_mwh / next_min_eur_mwh / next_negative_windows /
//        renewable_share_pct / uk_gco2_per_kwh.
//   /api/a11oy/v1/anatomy/loop     — reservoir.work_credits (the loop's stored credits).
//
// CONTRACT: default-export { id, title, endpoints[], mount(ctx), unmount() }.

import { createShowcase } from "./_showcase.js";

const ID = "energy";
const TITLE = "Energy · Harvest";
const POSTURE_EP = "/api/a11oy/v1/harvest/posture";
const LOOP_EP = "/api/a11oy/v1/anatomy/loop";

// palette
const C = {
  teal: 0x39d3c4, gold: 0xe8c074, green: 0x2fd07a, red: 0xff6b6b,
  blue: 0x6fb1ff, slate: 0x8a97a3, cream: 0xeef3f6, dim: 0x46586a,
};

let _stage = null, _THREE = null, _ctx = null;
let _hPosture = null, _hLoop = null;
let _root = null;          // THREE.Group holding everything we add (one remove on unmount)
let _overlay = null;       // DOM HUD panel
let _show = null;          // shared collapsible showcase chrome
let _frameFn = null;       // our per-frame callback (guards on _root null after unmount)
let _hud = {};             // references to live HUD chip/value elements
let _scene = null;         // built scene-object refs the frame loop + pollers animate
const _anim = {};          // animated-state targets the frame loop eases toward

// ----------------------------------------------------------------------------
// honest field extraction. The real /harvest/posture nests live readings in
// readings[] (per-feed reachable/measured/value) + drivers, and ALSO may carry
// flat fields on-box. We read BOTH shapes, never invent. Each getter returns
// { value:Number|null, live:Bool, label:String|null, src:String } so the viz can
// render NO-LIVE-DATA honestly when a feed is down or the value is absent.
// ----------------------------------------------------------------------------
function _num(x) {
  if (x === null || x === undefined) return null;
  const n = typeof x === "number" ? x : parseFloat(x);
  return Number.isFinite(n) ? n : null;
}

// find a reading whose feed/name matches any of the given substrings (case-insensitive)
function _findReading(json, needles) {
  const rs = (json && Array.isArray(json.readings)) ? json.readings : [];
  for (const r of rs) {
    const key = String((r && (r.feed || r.name || r.id)) || "").toLowerCase();
    if (needles.some((n) => key.indexOf(n) >= 0)) return r;
  }
  return null;
}

// pull a numeric value out of a FeedReading dict, honestly tracking reachable/measured
function _readingValue(r, fields) {
  if (!r) return { value: null, live: false, label: null, src: "absent" };
  const reachable = r.reachable !== false; // default true unless explicitly false
  let v = null;
  for (const f of fields) { v = _num(r[f]); if (v !== null) break; }
  const measured = r.measured === true;
  const label = measured ? "MEASURED" : (reachable && v !== null ? "SAMPLE" : null);
  return { value: v, live: reachable && v !== null, label, src: String((r.feed || r.name) || "feed") };
}

// price (EUR/MWh): prefer flat on-box field, else aWATTar DE/AT reading
function _getPrice(json) {
  const flat = _num(json && json.price_now_eur_mwh);
  if (flat !== null) return { value: flat, live: true, label: "SAMPLE", src: "price_now_eur_mwh" };
  const r = _findReading(json, ["awattar", "price", "lmp", "marketprice", "caiso"]);
  return _readingValue(r, ["price_eur_mwh", "marketprice", "value", "price", "lmp"]);
}
function _getNextMin(json) {
  const flat = _num(json && json.next_min_eur_mwh);
  if (flat !== null) return { value: flat, live: true, label: "SAMPLE", src: "next_min_eur_mwh" };
  return { value: null, live: false, label: null, src: "absent" };
}
function _getRenewable(json) {
  const flat = _num(json && json.renewable_share_pct);
  if (flat !== null) return { value: flat, live: true, label: "SAMPLE", src: "renewable_share_pct" };
  const r = _findReading(json, ["ren_share", "renewable", "energy_charts_ren"]);
  return _readingValue(r, ["renewable_share_pct", "share", "value", "ren_share"]);
}
function _getCarbon(json) {
  const flat = _num(json && json.uk_gco2_per_kwh);
  if (flat !== null) return { value: flat, live: true, label: "SAMPLE", src: "uk_gco2_per_kwh" };
  const r = _findReading(json, ["carbon", "gco2", "intensity"]);
  return _readingValue(r, ["uk_gco2_per_kwh", "gco2_per_kwh", "intensity", "value", "gco2"]);
}
function _getFrequency(json) {
  const r = _findReading(json, ["frequency", "freq"]);
  return _readingValue(r, ["hz", "frequency", "value", "freq"]);
}
function _getForecast(json) {
  const r = _findReading(json, ["forecast", "open_meteo", "meteo"]);
  return _readingValue(r, ["score", "value", "surplus_score"]);
}
// negative-price windows: array of {start,end,...} or a count
function _getNegWindows(json) {
  const w = json && json.next_negative_windows;
  if (Array.isArray(w)) return { list: w, count: w.length, live: true };
  const n = _num(w);
  if (n !== null) return { list: null, count: n, live: true };
  return { list: null, count: null, live: false };
}
// joules evidence — MEASURED only on-box; off-box {} (we render the honest empty posture)
function _getJoules(json) {
  const ev = (json && json.joules_evidence) || {};
  const total = _num(ev.joules_measured_total);
  const powerW = _num(ev.power_w_sample);
  const node = ev.exporter_node || null;
  // joules_label is the doctrine truth token straight off the JSON ("measured"/"sample")
  const label = (json && (json.joules_label || (json.joules_evidence && json.joules_evidence.label))) || null;
  return {
    total, powerW, node,
    label: label ? String(label).toUpperCase() : null,
    measured: total !== null && String(label || "").toLowerCase().indexOf("measured") >= 0,
  };
}

// ----------------------------------------------------------------------------
// scene builders. Each returns objects added to _root; the frame loop animates
// them from the live values written into _anim by the pollers.
// ----------------------------------------------------------------------------
function _makeText(text, color, scale) {
  // tiny canvas-sprite label (system font), used for axis ticks / value callouts
  const cnv = document.createElement("canvas");
  const ctx = cnv.getContext("2d");
  const fs = 44; ctx.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  const w = Math.ceil(ctx.measureText(text).width) + 12, h = fs + 12;
  cnv.width = w; cnv.height = h;
  ctx.font = "600 " + fs + "px ui-monospace,Menlo,monospace";
  ctx.fillStyle = "#" + color.toString(16).padStart(6, "0");
  ctx.textBaseline = "middle"; ctx.fillText(text, 6, h / 2);
  const tex = new _THREE.CanvasTexture(cnv);
  if ("colorSpace" in tex && _THREE.SRGBColorSpace) tex.colorSpace = _THREE.SRGBColorSpace;
  const spr = new _THREE.Sprite(new _THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  const s = scale || 0.5; spr.scale.set(s * (w / h), s, 1);
  spr.userData.szlText = true; spr.userData.tex = tex;
  return spr;
}

function build() {
  const THREE = _THREE;
  _root = new THREE.Group();
  _stage.scene.add(_root);

  // ---- DEMO 1: GPU-style hexbin/column grid floor (deck.gl GPUGridLayer technique) ----
  // A hex-packed field of instanced columns; height/color animate to renewable share +
  // carbon tint when live. This is the "grid surface" the rest of the scene sits on.
  const GRID = { cols: 0, mesh: null, dummy: new THREE.Object3D(), base: [], rings: 5 };
  const cells = [];
  const hexR = 0.62, gap = 0.06;
  for (let q = -GRID.rings; q <= GRID.rings; q++) {
    for (let r = -GRID.rings; r <= GRID.rings; r++) {
      const x = (hexR * 1.5) * q;
      const z = (hexR * Math.sqrt(3)) * (r + q / 2);
      if (Math.hypot(x, z) > (GRID.rings + 0.4) * hexR * 1.5) continue;
      cells.push([x, z]);
    }
  }
  GRID.cols = cells.length;
  const colGeo = new THREE.CylinderGeometry(hexR - gap, hexR - gap, 1, 6);
  colGeo.translate(0, 0.5, 0); // grow upward from y=0
  const colMat = new THREE.MeshStandardMaterial({
    color: C.teal, emissive: C.teal, emissiveIntensity: 0.25, metalness: 0.3, roughness: 0.55,
  });
  GRID.mesh = new THREE.InstancedMesh(colGeo, colMat, GRID.cols);
  GRID.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(GRID.cols * 3), 3);
  for (let i = 0; i < GRID.cols; i++) {
    GRID.base.push({ x: cells[i][0], z: cells[i][1], h: 0.05, hT: 0.05, phase: Math.random() * Math.PI * 2 });
  }
  GRID.mesh.position.y = -2.2;
  _root.add(GRID.mesh);

  // ---- DEMO 2: negative-price extruded column field (deck.gl ColumnLayer technique) ----
  // Up to 12 columns around a ring; when negative-price windows are live, columns extrude
  // (height = abs(price)) and turn red (sign(price) < 0). Otherwise they sit flat/dim.
  const NEG = { group: new THREE.Group(), cols: [], n: 12 };
  for (let i = 0; i < NEG.n; i++) {
    const a = (i / NEG.n) * Math.PI * 2;
    const g = new THREE.BoxGeometry(0.34, 1, 0.34); g.translate(0, 0.5, 0);
    const m = new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.2, transparent: true, opacity: 0.85 });
    const mesh = new THREE.Mesh(g, m);
    mesh.position.set(Math.cos(a) * 6.4, -2.2, Math.sin(a) * 6.4);
    mesh.scale.y = 0.05;
    NEG.cols.push({ mesh, a, soak: 0, soakT: 0 });
    NEG.group.add(mesh);
  }
  _root.add(NEG.group);

  // ---- DEMO 3: THE FUNNEL — live-filling joules reservoir (founder centerpiece) ----
  // A transparent glass funnel/reservoir. Fill height animates to OUR harvested joules
  // (joules_evidence.joules_measured_total) ONLY when label==MEASURED on-box. Off-box
  // (label=sample, evidence={}) the fluid stays at 0 with the honest SAMPLE/NO-LIVE-DATA
  // chip floating on it — we never fabricate a fill. A MEASURED honesty billboard rides
  // on the reservoir per the founder's explicit ask.
  const RES = { group: new THREE.Group() };
  const shellGeo = new THREE.CylinderGeometry(1.7, 0.9, 4.0, 40, 1, true);
  const shellMat = new THREE.MeshPhysicalMaterial({
    color: C.cream, metalness: 0, roughness: 0.08, transmission: 0.92, transparent: true,
    opacity: 0.22, thickness: 0.4, side: THREE.DoubleSide, emissive: C.teal, emissiveIntensity: 0.04,
  });
  RES.shell = new THREE.Mesh(shellGeo, shellMat);
  RES.group.add(RES.shell);
  // rim + base rings
  const rim = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.04, 12, 40), new THREE.MeshStandardMaterial({ color: C.teal, emissive: C.teal, emissiveIntensity: 0.6 }));
  rim.rotation.x = Math.PI / 2; rim.position.y = 2.0; RES.group.add(rim);
  // the FLUID — its scale.y is the live fill fraction; starts EMPTY (honest)
  const fluidGeo = new THREE.CylinderGeometry(1.55, 0.78, 3.8, 40);
  fluidGeo.translate(0, 1.9, 0); // bottom at reservoir base, grows up
  RES.fluidMat = new THREE.MeshStandardMaterial({ color: C.green, emissive: C.green, emissiveIntensity: 0.5, transparent: true, opacity: 0.78, metalness: 0.2, roughness: 0.3 });
  RES.fluid = new THREE.Mesh(fluidGeo, RES.fluidMat);
  RES.fluid.position.y = -2.0; RES.fluid.scale.y = 0.0001;
  RES.group.add(RES.fluid);
  RES.group.position.set(0, 0.2, 0);
  _root.add(RES.group);
  _anim.fill = 0; _anim.fillT = 0;       // reservoir fill fraction (0..1), eased
  _anim.fluidPulse = 0;

  // MEASURED honesty billboard riding on the reservoir (founder's explicit ask)
  try {
    RES.chip = _ctx.label.billboard(THREE, "SAMPLE", { text: "joules", scale: 0.55, position: [0, 2.55, 0], depthTest: false });
    RES.group.add(RES.chip);
  } catch (_) {}

  // ---- DEMO 4: animated flow arcs (deck.gl ArcLayer technique) ----
  // Arcs from the grid floor up into the reservoir, representing energy flowing INTO the
  // funnel. Dash offset animates; brightness rises when wasted_energy_available is live.
  const ARC = { group: new THREE.Group(), arcs: [], n: 7 };
  for (let i = 0; i < ARC.n; i++) {
    const a = (i / ARC.n) * Math.PI * 2;
    const src = new THREE.Vector3(Math.cos(a) * 5.5, -2.0, Math.sin(a) * 5.5);
    const mid = new THREE.Vector3(Math.cos(a) * 2.6, 3.2, Math.sin(a) * 2.6);
    const dst = new THREE.Vector3(0, 1.0, 0);
    const curve = new THREE.QuadraticBezierCurve3(src, mid, dst);
    const geo = new THREE.TubeGeometry(curve, 40, 0.035, 6, false);
    const mat = new THREE.MeshStandardMaterial({ color: C.teal, emissive: C.teal, emissiveIntensity: 0.5, transparent: true, opacity: 0.0 });
    const mesh = new THREE.Mesh(geo, mat);
    ARC.arcs.push({ mesh, phase: i / ARC.n });
    ARC.group.add(mesh);
  }
  _root.add(ARC.group);
  _anim.flow = 0; _anim.flowT = 0;       // 0..1 flow intensity

  // ---- DEMO 5: renewable >100% halo ring ----
  // A glowing ring whose radius/opacity grows with renewable share; if share crosses
  // 100% (genuine oversupply) it flares gold — the "free wind" signal.
  const HALO = {};
  HALO.ring = new THREE.Mesh(new THREE.TorusGeometry(3.0, 0.06, 16, 80), new THREE.MeshBasicMaterial({ color: C.green, transparent: true, opacity: 0.0 }));
  HALO.ring.rotation.x = Math.PI / 2; HALO.ring.position.y = 2.6;
  _root.add(HALO.ring);
  _anim.renew = 0; _anim.renewT = 0;     // renewable share fraction (0..1.2)

  // ---- DEMO 6: power_w live gauge (radial arc) ----
  const GAUGE = {};
  const gaugeBg = new THREE.Mesh(new THREE.RingGeometry(0.9, 1.05, 48, 1, 0, Math.PI), new THREE.MeshBasicMaterial({ color: C.dim, transparent: true, opacity: 0.5, side: THREE.DoubleSide }));
  GAUGE.fill = new THREE.Mesh(new THREE.RingGeometry(0.9, 1.05, 48, 1, 0, 0.001), new THREE.MeshBasicMaterial({ color: C.gold, side: THREE.DoubleSide }));
  GAUGE.group = new THREE.Group();
  GAUGE.group.add(gaugeBg, GAUGE.fill);
  GAUGE.group.position.set(-6.5, 1.6, 0); GAUGE.group.rotation.y = Math.PI / 2;
  _root.add(GAUGE.group);
  _anim.powerW = 0; _anim.powerWT = 0;   // 0..1 fraction of an assumed 1kW scale

  // ---- DEMO 7: carbon-intensity tint dome (Electricity Maps choropleth tint) ----
  const DOME = {};
  DOME.mesh = new THREE.Mesh(new THREE.SphereGeometry(9.5, 32, 24, 0, Math.PI * 2, 0, Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: C.green, transparent: true, opacity: 0.04, side: THREE.BackSide }));
  _root.add(DOME.mesh);
  _anim.carbon = 0; _anim.carbonT = 0;   // 0(clean)..1(dirty)

  // ---- DEMO 8: next_negative_windows countdown ribbon ----
  const RIBBON = { group: new THREE.Group(), ticks: [] };
  for (let i = 0; i < 16; i++) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.18, 0.04), new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.3 }));
    m.position.set(-2.4 + i * 0.32, 4.6, 0);
    RIBBON.ticks.push(m); RIBBON.group.add(m);
  }
  _root.add(RIBBON.group);
  _anim.negCount = 0; _anim.negCountT = 0;

  // ---- DEMO 9: grid-feed health constellation (3/3 ... n/n) ----
  // One small node per live feed reading; green=reachable+measured, blue=reachable,
  // red=unreachable. Honest 3/3 health badge in the HUD.
  const HEALTH = { group: new THREE.Group(), nodes: [] };
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 12), new THREE.MeshStandardMaterial({ color: C.dim, emissive: C.dim, emissiveIntensity: 0.4 }));
    m.position.set(6.6 + Math.cos(a) * 0.9, 1.6 + Math.sin(a) * 0.9, 0);
    HEALTH.nodes.push(m); HEALTH.group.add(m);
  }
  _root.add(HEALTH.group);

  // ---- DEMO 10: soak-decision beacon ----
  // A pillar in the reservoir core that turns green and pulses when soak_hard / wasted
  // energy is live (the loop SHOULD soak now), amber when marginal, gray when idle.
  const SOAK = {};
  SOAK.mesh = new THREE.Mesh(new THREE.OctahedronGeometry(0.45, 0), new THREE.MeshStandardMaterial({ color: C.slate, emissive: C.slate, emissiveIntensity: 0.5 }));
  SOAK.mesh.position.set(0, 4.0, 0);
  _root.add(SOAK.mesh);
  _anim.soak = 0; _anim.soakT = 0;       // 0 idle .. 1 soak-now

  // ---- DEMO 11: work_credits reservoir-credits ring (from /anatomy/loop) ----
  const CREDITS = {};
  CREDITS.ring = new THREE.Mesh(new THREE.TorusGeometry(2.2, 0.05, 12, 64, 0.001), new THREE.MeshStandardMaterial({ color: C.blue, emissive: C.blue, emissiveIntensity: 0.6 }));
  CREDITS.ring.rotation.x = Math.PI / 2; CREDITS.ring.position.y = -1.9;
  _root.add(CREDITS.ring);
  _anim.credits = 0; _anim.creditsT = 0;

  // ---- DEMO 12: ambient particle field (wasted-energy motes drifting to the funnel) ----
  const MOTES = {};
  const mN = 280;
  const mGeo = new THREE.BufferGeometry();
  const mPos = new Float32Array(mN * 3);
  MOTES.seed = [];
  for (let i = 0; i < mN; i++) {
    const a = Math.random() * Math.PI * 2, rad = 3 + Math.random() * 6, y = -2 + Math.random() * 6;
    mPos[i * 3] = Math.cos(a) * rad; mPos[i * 3 + 1] = y; mPos[i * 3 + 2] = Math.sin(a) * rad;
    MOTES.seed.push({ a, rad, y, spd: 0.2 + Math.random() * 0.6 });
  }
  mGeo.setAttribute("position", new THREE.BufferAttribute(mPos, 3));
  MOTES.points = new THREE.Points(mGeo, new THREE.PointsMaterial({ color: C.teal, size: 0.06, transparent: true, opacity: 0.5, depthWrite: false }));
  MOTES.pos = mPos; MOTES.geo = mGeo;
  _root.add(MOTES.points);

  // stash builders for the frame loop + pollers
  _scene = { GRID, NEG, RES, ARC, HALO, GAUGE, DOME, RIBBON, HEALTH, SOAK, CREDITS, MOTES };

  // enable bloom for the holographic glow (safe no-op on WebGPU per toolkit)
  try { _stage.setBloom(true); } catch (_) {}

  // ---- per-frame animation (eases _anim.*  toward live targets) ----
  _frameFn = () => {
    if (!_root) return; // unmounted — guard (shell keeps frame cbs registered)
    const t = (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000;
    const ease = (cur, target, k) => cur + (target - cur) * k;

    // grid columns: idle wave + renewable-driven height + carbon tint
    _anim.renew = ease(_anim.renew, _anim.renewT, 0.06);
    _anim.carbon = ease(_anim.carbon, _anim.carbonT, 0.06);
    const gridColor = new THREE.Color().lerpColors(new THREE.Color(C.green), new THREE.Color(C.red), Math.min(1, _anim.carbon));
    for (let i = 0; i < GRID.cols; i++) {
      const b = GRID.base[i];
      const wave = 0.18 + 0.12 * Math.sin(t * 1.2 + b.phase);
      b.hT = 0.08 + wave + _anim.renew * 0.9 * (0.6 + 0.4 * Math.sin(t * 0.7 + b.phase));
      b.h = ease(b.h, b.hT, 0.08);
      GRID.dummy.position.set(b.x, 0, b.z);
      GRID.dummy.scale.set(1, b.h, 1);
      GRID.dummy.updateMatrix();
      GRID.mesh.setMatrixAt(i, GRID.dummy.matrix);
      GRID.mesh.setColorAt(i, gridColor);
    }
    GRID.mesh.instanceMatrix.needsUpdate = true;
    if (GRID.mesh.instanceColor) GRID.mesh.instanceColor.needsUpdate = true;

    // negative-price columns soak animation
    for (let i = 0; i < NEG.cols.length; i++) {
      const c = NEG.cols[i];
      c.soak = ease(c.soak, c.soakT, 0.07);
      c.mesh.scale.y = Math.max(0.05, c.soak * 5.0);
      const lit = c.soakT > 0.05;
      c.mesh.material.color.setHex(lit ? C.red : C.dim);
      c.mesh.material.emissive.setHex(lit ? C.red : C.dim);
      c.mesh.material.emissiveIntensity = lit ? 0.5 + 0.3 * Math.sin(t * 3 + i) : 0.2;
    }

    // THE FUNNEL fill
    _anim.fill = ease(_anim.fill, _anim.fillT, 0.05);
    RES.fluid.scale.y = Math.max(0.0001, _anim.fill);
    _anim.fluidPulse = 0.5 + 0.5 * Math.sin(t * 2);
    RES.fluidMat.emissiveIntensity = 0.35 + 0.25 * _anim.fluidPulse;

    // flow arcs
    _anim.flow = ease(_anim.flow, _anim.flowT, 0.06);
    for (let i = 0; i < ARC.arcs.length; i++) {
      const arc = ARC.arcs[i];
      const pulse = (Math.sin(t * 1.5 + arc.phase * Math.PI * 2) + 1) / 2;
      arc.mesh.material.opacity = _anim.flow * (0.2 + 0.6 * pulse);
      arc.mesh.material.emissiveIntensity = 0.3 + 0.7 * pulse * _anim.flow;
    }

    // renewable halo
    HALO.ring.material.opacity = Math.min(0.9, _anim.renew * 0.7);
    HALO.ring.scale.setScalar(0.8 + _anim.renew * 0.5);
    const over = _anim.renew > 1.0;
    HALO.ring.material.color.setHex(over ? C.gold : C.green);

    // power gauge
    _anim.powerW = ease(_anim.powerW, _anim.powerWT, 0.07);
    const ang = Math.max(0.001, Math.min(Math.PI, _anim.powerW * Math.PI));
    GAUGE.fill.geometry.dispose();
    GAUGE.fill.geometry = new THREE.RingGeometry(0.9, 1.05, 48, 1, 0, ang);

    // carbon dome tint
    DOME.mesh.material.color.copy(gridColor);
    DOME.mesh.material.opacity = 0.03 + _anim.carbon * 0.06;

    // countdown ribbon
    _anim.negCount = ease(_anim.negCount, _anim.negCountT, 0.1);
    for (let i = 0; i < RIBBON.ticks.length; i++) {
      const lit = i < Math.round(_anim.negCount * RIBBON.ticks.length / Math.max(1, _scene._negMax || 4));
      const m = RIBBON.ticks[i];
      const flash = lit ? 0.5 + 0.4 * Math.sin(t * 4 + i) : 0.25;
      m.material.color.setHex(lit ? C.gold : C.dim);
      m.material.emissive.setHex(lit ? C.gold : C.dim);
      m.material.emissiveIntensity = flash;
    }

    // soak beacon
    _anim.soak = ease(_anim.soak, _anim.soakT, 0.08);
    const sCol = _anim.soak > 0.6 ? C.green : (_anim.soak > 0.2 ? C.gold : C.slate);
    SOAK.mesh.material.color.setHex(sCol);
    SOAK.mesh.material.emissive.setHex(sCol);
    SOAK.mesh.material.emissiveIntensity = 0.4 + 0.5 * _anim.soak * (0.5 + 0.5 * Math.sin(t * 4));
    SOAK.mesh.rotation.y += 0.01 + 0.04 * _anim.soak;
    SOAK.mesh.scale.setScalar(0.9 + 0.2 * _anim.soak * Math.sin(t * 5));

    // work_credits ring sweep (from /anatomy/loop)
    _anim.credits = ease(_anim.credits, _anim.creditsT, 0.06);
    CREDITS.ring.geometry.dispose();
    CREDITS.ring.geometry = new THREE.TorusGeometry(2.2, 0.05, 12, 64, Math.max(0.001, _anim.credits * Math.PI * 2));

    // motes drift inward + up (energy flowing to the funnel)
    for (let i = 0; i < MOTES.seed.length; i++) {
      const s = MOTES.seed[i];
      s.a += 0.003 * s.spd;
      const pull = 0.2 + _anim.flow * 0.8;
      s.rad -= 0.01 * pull * s.spd;
      s.y += 0.012 * pull;
      if (s.rad < 1.2 || s.y > 4.5) { s.rad = 3 + Math.random() * 6; s.y = -2 + Math.random() * 1.5; }
      MOTES.pos[i * 3] = Math.cos(s.a) * s.rad;
      MOTES.pos[i * 3 + 1] = s.y;
      MOTES.pos[i * 3 + 2] = Math.sin(s.a) * s.rad;
    }
    MOTES.geo.attributes.position.needsUpdate = true;
    MOTES.points.material.opacity = 0.25 + _anim.flow * 0.4;

    _root.rotation.y += 0.0012; // gentle estate drift
  };
  _stage.onFrame(_frameFn);
}

// ----------------------------------------------------------------------------
// HUD — a DOM panel of live values, EACH carrying its honesty chip. Reads live;
// never fabricates. Built once; updated in place by the pollers.
// ----------------------------------------------------------------------------
function buildHUD() {
  const lab = _ctx.label;
  const badge = _ctx.live.createBadge();
  _hud.badge = badge;

  _show = createShowcase(_ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge, legend: true,
  });

  // rows fold into the (collapsed) showcase body; the 3D funnel stays the star.
  _overlay = document.createElement("div");
  _overlay.className = "szl3d-energy-hud";
  Object.assign(_overlay.style, {
    display: "flex", flexDirection: "column", gap: "7px",
    font: "12px ui-monospace,SFMono-Regular,Menlo,monospace", color: "#cfe0ea",
  });

  // a small row factory: label text + value + honesty chip
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
  row("posture", "posture");
  row("price", "price EUR/MWh");
  row("renew", "renewable %");
  row("carbon", "carbon gCO₂/kWh");
  row("neg", "neg-price windows");
  row("joules", "harvested joules");
  row("power", "power_w sample");
  row("credits", "loop work_credits");
  row("health", "grid feeds");

  // doctrine note (the off-box joules honesty reality)
  const note = document.createElement("div");
  note.style.cssText = "color:#6d7d8a;font-size:10.5px;line-height:1.45;margin-top:4px;border-top:1px solid #15212c;padding-top:6px";
  note.textContent = "joules MEASURED only on-box (NVML exporter). Off-box label=sample, evidence empty — the funnel shows its structure, never a fabricated fill. Modeled on Electricity Maps + deck.gl; rendered in three.js (see manifest).";
  _overlay.appendChild(note);

  _show.body.appendChild(_overlay);
}

function _setRow(key, text, label) {
  const r = _hud[key];
  if (!r) return;
  r.val.textContent = text;
  _ctx.label.updateChip(r.chip, label || "STRUCTURAL-ONLY");
}

// ----------------------------------------------------------------------------
// pollers — wire EVERY value to the real endpoints; render honest degraded/missing.
// ----------------------------------------------------------------------------
function onPosture(json, meta) {
  if (!_scene) return;

  // degraded / missing posture → honest HUD, don't fabricate
  if (meta.state === "missing" || meta.state === "error") {
    ["posture", "price", "renew", "carbon", "neg", "joules", "power", "health"].forEach((k) => _setRow(k, "NO-LIVE-DATA", "STRUCTURAL-ONLY"));
    _anim.flowT = 0; _anim.soakT = 0; _anim.fillT = 0;
    return;
  }
  const degraded = meta.state === "degraded" || json.ok === false;

  // posture / soak decision
  const posture = (json && json.posture) || "unknown";
  const wasted = json && (json.wasted_energy_available === true || _num(json.wasted_energy_available) > 0);
  const soakHard = json && json.soak_hard === true;
  _setRow("posture", String(posture) + (degraded ? " (degraded)" : ""), degraded ? "STRUCTURAL-ONLY" : "SAMPLE");
  _anim.soakT = soakHard ? 1.0 : (wasted ? 0.55 : 0.1);
  _anim.flowT = wasted ? 1.0 : (posture && String(posture).toLowerCase().indexOf("soak") >= 0 ? 0.7 : 0.15);

  // price → negative-price columns
  const price = _getPrice(json);
  if (price.live) {
    _setRow("price", price.value.toFixed(1), price.label);
    const neg = price.value < 0;
    const mag = Math.min(1, Math.abs(price.value) / 80);
    _scene.NEG.cols.forEach((c, i) => { c.soakT = neg ? (0.2 + mag) : 0.0; });
  } else {
    _setRow("price", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
    _scene.NEG.cols.forEach((c) => { c.soakT = 0; });
  }

  // renewable share → halo + grid height
  const renew = _getRenewable(json);
  if (renew.live) {
    _setRow("renew", renew.value.toFixed(1) + "%", renew.label);
    _anim.renewT = renew.value / 100;
  } else { _setRow("renew", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); _anim.renewT = 0; }

  // carbon → dome + grid tint
  const carb = _getCarbon(json);
  if (carb.live) {
    _setRow("carbon", Math.round(carb.value) + "", carb.label);
    _anim.carbonT = Math.min(1, carb.value / 500); // ~500 gCO2/kWh = "dirty"
  } else { _setRow("carbon", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); _anim.carbonT = 0; }

  // next negative windows → countdown ribbon
  const nw = _getNegWindows(json);
  if (nw.live && nw.count !== null) {
    _setRow("neg", nw.count + (nw.count === 1 ? " window" : " windows"), "SAMPLE");
    _scene._negMax = Math.max(_scene._negMax || 4, nw.count || 0, 4);
    _anim.negCountT = nw.count;
  } else { _setRow("neg", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); _anim.negCountT = 0; }

  // THE FUNNEL — joules. MEASURED only on-box; off-box honest sample posture, no fill.
  const j = _getJoules(json);
  const jlabel = j.label || (json.joules_label ? String(json.joules_label).toUpperCase() : "STRUCTURAL-ONLY");
  if (_scene.RES.chip) {
    try {
      _scene.RES.group.remove(_scene.RES.chip);
      _scene.RES.chip = _ctx.label.billboard(_THREE, jlabel, {
        text: j.measured && j.total !== null ? (j.total.toFixed(0) + " J") : "joules",
        scale: 0.55, position: [0, 2.55, 0], depthTest: false,
      });
      _scene.RES.group.add(_scene.RES.chip);
    } catch (_) {}
  }
  if (j.measured && j.total !== null) {
    // on-box: fill the reservoir from REAL measured joules (log-scaled to a sane visual range)
    const frac = Math.max(0.02, Math.min(1, Math.log10(1 + j.total) / 6)); // 1e6 J ~= full
    _anim.fillT = frac;
    _setRow("joules", j.total.toFixed(0) + " J (" + (j.node || "exporter") + ")", "MEASURED");
    _scene.RES.fluidMat.color.setHex(C.green); _scene.RES.fluidMat.emissive.setHex(C.green);
  } else {
    // off-box / no fresh sample: honest — reservoir stays empty, label sample/structural
    _anim.fillT = 0;
    _setRow("joules", jlabel === "SAMPLE" ? "sample (no on-box NVML)" : "NO-LIVE-DATA", jlabel === "SAMPLE" ? "SAMPLE" : "STRUCTURAL-ONLY");
    _scene.RES.fluidMat.color.setHex(C.blue); _scene.RES.fluidMat.emissive.setHex(C.blue);
  }

  // power_w gauge
  if (j.powerW !== null) {
    _setRow("power", j.powerW.toFixed(1) + " W", j.measured ? "MEASURED" : "SAMPLE");
    _anim.powerWT = Math.min(1, j.powerW / 1000);
  } else { _setRow("power", "NO-LIVE-DATA", "STRUCTURAL-ONLY"); _anim.powerWT = 0; }

  // grid-feed health constellation + badge (n reachable / total)
  const rs = Array.isArray(json.readings) ? json.readings : [];
  let reachable = 0, measured = 0;
  for (let i = 0; i < _scene.HEALTH.nodes.length; i++) {
    const node = _scene.HEALTH.nodes[i];
    const r = rs[i];
    if (!r) { node.material.color.setHex(C.dim); node.material.emissive.setHex(C.dim); node.material.emissiveIntensity = 0.15; node.visible = i < Math.max(3, rs.length); continue; }
    node.visible = true;
    const ok = r.reachable !== false;
    const meas = r.measured === true;
    if (ok) reachable++;
    if (meas) measured++;
    const col = meas ? C.green : (ok ? C.blue : C.red);
    node.material.color.setHex(col); node.material.emissive.setHex(col); node.material.emissiveIntensity = 0.6;
  }
  if (rs.length) _setRow("health", reachable + "/" + rs.length + " reachable" + (measured ? " · " + measured + " measured" : ""), measured ? "MEASURED" : (reachable ? "SAMPLE" : "STRUCTURAL-ONLY"));
  else _setRow("health", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
}

function onLoop(json, meta) {
  if (!_scene) return;
  if (meta.state === "missing" || meta.state === "error") {
    _setRow("credits", "NO-LIVE-DATA", "STRUCTURAL-ONLY");
    _anim.creditsT = 0;
    return;
  }
  const res = (json && json.reservoir) || {};
  const credits = _num(res.work_credits);
  if (credits !== null) {
    const lbl = (json && json.intake && json.intake.joules_label) ? String(json.intake.joules_label).toUpperCase() : "STRUCTURAL-ONLY";
    _setRow("credits", credits.toFixed(2), lbl === "MEASURED" ? "MEASURED" : (lbl === "SAMPLE" ? "SAMPLE" : "STRUCTURAL-ONLY"));
    _anim.creditsT = Math.max(0.02, Math.min(1, credits / 100));
  } else {
    _setRow("credits", meta.state === "degraded" ? "degraded" : "NO-LIVE-DATA", "STRUCTURAL-ONLY");
    _anim.creditsT = 0;
  }
}

// ----------------------------------------------------------------------------
// contract: mount / unmount
// ----------------------------------------------------------------------------
function mount(ctx) {
  _ctx = ctx;
  _stage = ctx.stage;
  _THREE = ctx.THREE;

  build();
  buildHUD();

  // wire BOTH live endpoints. The HUD badge tracks the primary (posture) endpoint.
  _hPosture = ctx.live.poll(POSTURE_EP, 5000, onPosture, { badge: _hud.badge });
  _hLoop = ctx.live.poll(LOOP_EP, 7000, onLoop);

  return { id: ID, started: true };
}

function unmount() {
  try { if (_hPosture) _hPosture.stop(); } catch (_) {}
  try { if (_hLoop) _hLoop.stop(); } catch (_) {}
  try { if (_show) _show.destroy(); } catch (_) {}
  try { if (_overlay && _overlay.parentNode) _overlay.parentNode.removeChild(_overlay); } catch (_) {}
  try { if (_root && _stage) _stage.scene.remove(_root); } catch (_) {}
  // dispose geometries/materials we created under _root
  try {
    if (_root) _root.traverse((o) => {
      if (o.geometry && o.geometry.dispose) o.geometry.dispose();
      if (o.material) { const m = o.material; (Array.isArray(m) ? m : [m]).forEach((x) => { if (x.map && x.map.dispose) x.map.dispose(); if (x.dispose) x.dispose(); }); }
    });
  } catch (_) {}
  try { if (_stage) _stage.setBloom(false); } catch (_) {}
  _hPosture = null; _hLoop = null; _overlay = null; _show = null; _root = null;
  _scene = null; _frameFn = null; _hud = {}; _ctx = null; _stage = null; _THREE = null;
}

export default { id: ID, title: TITLE, endpoints: [POSTURE_EP, LOOP_EP], mount, unmount };
