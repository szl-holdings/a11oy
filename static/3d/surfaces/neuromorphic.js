// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/neuromorphic.js — NEUROMORPHIC / SPIKING-NEURAL-COMPUTE organ for the
// holographic frontier ring.
//
// Renders a small 3D lattice of LIF neuron nodes driven by a live LIF-population
// simulation snapshot from /api/a11oy/v1/neuromorphic/spikes. Nodes pulse/glow when
// they spike (spike_raster_counts drives per-node animation). Honesty label "MODELED"
// is read VERBATIM from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors frontier.js exactly):
//   export default { id, title, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   mean_firing_rate_hz — population-mean LIF firing rate
//   event_sparsity      — fraction of slots that did NOT spike (neuromorphic efficiency)
//   energy_per_spike_pJ — MODELED energy per spike (citing Loihi 2)
//   total_spikes        — raw spike count over the window
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   LIF model: Gerstner & Kistler "Spiking Neuron Models" (2002)
//     https://neuronaldynamics.epfl.ch/online/
//   Intel Loihi 2 / Lava (BSD-3): Davies et al. 2021 JPROC DOI:10.1109/JPROC.2021.3067593
//     https://github.com/lava-nc/lava
//   Surrogate-gradient SNNs: Neftci et al. arXiv:1901.09948
//     https://arxiv.org/abs/1901.09948
//   BrainScaleS: https://brainscales.kip.uni-heidelberg.de/
//
// HONESTY LABELS: MODELED (simulation, not measured silicon). Read verbatim from JSON.
//   endpoint returns label="MODELED"; energy_label="MODELED". Never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (nodes), violet-blue 0x8a6bff (spike flash).
//   Purple BANNED; violet-blue data-viz hue only on spikes, not backgrounds.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.

import { createShowcase } from "./_showcase.js";

const ID    = "neuromorphic";
const TITLE = "Neuromorphic · Spiking Neural Compute (live)";

const EP = "/api/a11oy/v1/neuromorphic/spikes?seed=42&n_neurons=64&dt_ms=0.5&T_ms=100.0";

// data-viz hues — purple BANNED
const C_NODE   = 0x5b8dee;  // lattice-blue (quiescent node)
const C_SPIKE  = 0x8a6bff;  // violet-blue (spike flash — data-viz only)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_ENERGY = 0x6dd47e;  // green accent for energy line
const C_GRID   = 0x1b3a44;  // floor / link colour

// lattice geometry: 4×4×4 = 64 nodes to match n_neurons=64 default
const GRID_DIM  = 4;
const N_NEURONS = GRID_DIM * GRID_DIM * GRID_DIM;  // 64
const SPACING   = 1.15;  // world units between nodes

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _nodes = [];        // Array<THREE.Mesh>  — one per neuron
let _edgeLines = null;  // THREE.LineSegments  — lattice edges
let _hubSphere = null;  // THREE.Mesh          — central hub indicator

// live state
const S = {
  label:             null,
  mean_hz:           null,
  sparsity:          null,
  energy_pj:         null,
  total_spikes:      null,
  spike_counts:      null,  // Array<int> length 64
  membrane_v:        null,  // Array<float> length 64
  energy_label:      null,
  state:             "init",
};

// per-node animation: remaining "spike flash" brightness frames
const _flashTimer = new Float32Array(N_NEURONS);

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 8, 22);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLattice();
  _buildHub();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 4000, _onSpikes, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(40, 40, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildLattice() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.18, 12, 8);

  // Build 64 nodes in a 4×4×4 lattice centred at origin
  _nodes = [];
  const half = (GRID_DIM - 1) * SPACING * 0.5;
  for (let ix = 0; ix < GRID_DIM; ix++) {
    for (let iy = 0; iy < GRID_DIM; iy++) {
      for (let iz = 0; iz < GRID_DIM; iz++) {
        const mat = new THREE.MeshStandardMaterial({
          color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.18,
          metalness: 0.25, roughness: 0.55,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(
          ix * SPACING - half,
          iy * SPACING + 0.5,    // raise the whole lattice above the floor
          iz * SPACING - half,
        );
        _group.add(mesh);
        _nodes.push(mesh);
      }
    }
  }

  // Lattice edges: connect each node to its right/up/forward neighbour
  const edgePts = [];
  const half2 = (GRID_DIM - 1) * SPACING * 0.5;
  function pos(ix, iy, iz) {
    return new THREE.Vector3(ix * SPACING - half2, iy * SPACING + 0.5, iz * SPACING - half2);
  }
  const dirs = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  for (let ix = 0; ix < GRID_DIM; ix++) {
    for (let iy = 0; iy < GRID_DIM; iy++) {
      for (let iz = 0; iz < GRID_DIM; iz++) {
        for (const [dx, dy, dz] of dirs) {
          const nx = ix + dx, ny = iy + dy, nz = iz + dz;
          if (nx < GRID_DIM && ny < GRID_DIM && nz < GRID_DIM) {
            edgePts.push(pos(ix, iy, iz), pos(nx, ny, nz));
          }
        }
      }
    }
  }
  const edgeGeo = new THREE.BufferGeometry().setFromPoints(edgePts);
  _edgeLines = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.25 }));
  _group.add(_edgeLines);
}

function _buildHub() {
  const THREE = _THREE;
  // Central floating hub — icosahedron that brightens with mean firing rate
  _hubSphere = new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.45, 1),
    new THREE.MeshStandardMaterial({ color: C_NODE, emissive: C_NODE, emissiveIntensity: 0.3, wireframe: true, transparent: true, opacity: 0.55 }),
  );
  _hubSphere.position.set(0, (GRID_DIM - 1) * SPACING * 0.5 + 0.5 + 1.6, 0);
  _group.add(_hubSphere);
}

// =============================================================================
// live data handler
// =============================================================================
function _onSpikes(j) {
  // read honesty label VERBATIM — never upgrade
  S.label        = (j.label        || "MODELED").toUpperCase();
  S.mean_hz      = typeof j.mean_firing_rate_hz === "number" ? j.mean_firing_rate_hz  : null;
  S.sparsity     = typeof j.event_sparsity      === "number" ? j.event_sparsity       : null;
  S.energy_pj    = typeof j.energy_per_spike_pJ === "number" ? j.energy_per_spike_pJ  : null;
  S.total_spikes = typeof j.total_spikes        === "number" ? j.total_spikes         : null;
  S.spike_counts = Array.isArray(j.spike_raster_counts) ? j.spike_raster_counts : null;
  S.membrane_v   = Array.isArray(j.membrane_potentials) ? j.membrane_potentials  : null;
  S.energy_label = (j.energy_label || j.label || "MODELED").toUpperCase();

  _updateLattice();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives node colour/brightness from spike counts
// =============================================================================
function _updateLattice() {
  const live   = S.state === "live";
  const counts = S.spike_counts;
  const maxC   = counts ? Math.max(...counts, 1) : 1;

  _nodes.forEach((mesh, i) => {
    const raw = counts ? (counts[i] || 0) : 0;
    const norm = raw / maxC;          // 0..1 relative spike activity
    const col  = live ? (norm > 0.65 ? C_SPIKE : C_NODE) : C_DIM;
    const ei   = live ? (0.12 + 0.88 * norm) : 0.1;
    mesh.material.color.setHex(col);
    mesh.material.emissive.setHex(col);
    mesh.material.emissiveIntensity = ei;

    // arm the flash timer proportional to spike count (capped at 90 frames)
    if (live && raw > 0) {
      _flashTimer[i] = Math.min(30 + norm * 60, 90);
    }
  });

  if (_hubSphere) {
    const hz   = S.mean_hz || 0;
    const hcol = live ? C_NODE : C_DIM;
    _hubSphere.material.color.setHex(hcol);
    _hubSphere.material.emissive.setHex(hcol);
    _hubSphere.material.emissiveIntensity = live ? Math.min(0.25 + hz * 0.012, 1.2) : 0.15;
    _hubSphere.material.opacity = live ? 0.7 : 0.35;
  }

  if (_edgeLines) {
    _edgeLines.material.opacity = live ? 0.32 : 0.15;
    _edgeLines.material.color.setHex(live ? C_GRID : C_DIM);
  }
}

// =============================================================================
// per-frame animation — flash timer drives pulse decay
// =============================================================================
function _onFrame() {
  const t = performance.now();

  // Rotate the whole lattice very slowly
  if (_group) _group.rotation.y = Math.sin(t * 0.00012) * 0.18;

  // Hub slow rotation
  if (_hubSphere) {
    _hubSphere.rotation.y += 0.006;
    _hubSphere.rotation.x += 0.003;
  }

  // Pulse decay on spiking nodes
  const live = S.state === "live";
  _nodes.forEach((mesh, i) => {
    if (_flashTimer[i] > 0) {
      _flashTimer[i] -= 1;
      const f = _flashTimer[i] / 90;
      const col = live ? C_SPIKE : C_DIM;
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = 0.12 + 1.0 * f;
      mesh.scale.setScalar(1.0 + 0.35 * f);
    } else {
      mesh.scale.setScalar(1.0);
    }
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "MODELED", text: "LIF spikes", name: "spk" },
      { label: "MODELED", text: "energy est.", name: "energy" },
    ],
    legend: ["MODELED", "SAMPLE"],
    description:
      '<b>LIF (Leaky Integrate-and-Fire)</b> neuron population \u2014 64 nodes on a 3D lattice, ' +
      'each pulsing from a live deterministic simulation. Honesty label <b>MODELED</b> ' +
      '(simulation, not measured silicon). Energy estimate cites Intel Loihi\u00a02 ' +
      '(Davies\u00a0et\u00a0al.\u00a02021\u00a0JPROC). 0\u00a0runtime\u00a0CDN.',
    citations:
      "Gerstner & Kistler \"Spiking Neuron Models\" (2002) \u00b7 Intel Loihi\u00a02 Davies\u00a0et\u00a0al.\u00a02021 DOI:10.1109/JPROC.2021.3067593 \u00b7 Lava\u00a0OSS github.com/lava-nc/lava (BSD-3) \u00b7 Neftci\u00a0et\u00a0al.\u00a0arXiv:1901.09948 \u00b7 BrainScaleS. MODELED \u00b7 not\u00a0claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["nm-hz"]     = _show.addField("mean firing rate (Hz)");
  _el["nm-sparse"] = _show.addField("event sparsity");
  _el["nm-energy"] = _show.addField("energy / spike (pJ) \u2014 MODELED");
  _el["nm-spikes"] = _show.addField("total spikes");
  _el["nm-label"]  = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const hz = S.mean_hz != null ? S.mean_hz.toFixed(2) + " Hz" : "loading\u2026";
  const sp = S.sparsity != null ? (S.sparsity * 100).toFixed(1) + "% idle slots" : "loading\u2026";
  const ep = S.energy_pj != null ? S.energy_pj + " pJ/spike (MODELED, citing Loihi\u00a02)" : "loading\u2026";
  return (
    "<b>What this means:</b> A simulated population of 64 spiking neurons is firing " +
    "at roughly <b>" + hz + "</b> on average. " +
    "Neuromorphic chips fire only on events \u2014 <b>" + sp + "</b> means most circuits " +
    "are idle most of the time (that is the efficiency claim). " +
    "Energy per spike is <b>" + ep + "</b> \u2014 this is a <b>MODELED</b> estimate from " +
    "Intel\u2019s published Loihi\u00a02 specs, not a measured chip reading. " +
    "Plain: spiking neural chips could be far more energy-efficient than dense matrix " +
    "multiplication, but this number comes from a simulation, not a running chip.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("nm-hz",     t || fx(S.mean_hz, 3));
  _set("nm-sparse", t || fx(S.sparsity, 5));
  _set("nm-energy", t || (S.energy_pj != null ? S.energy_pj + " pJ" : "\u2014"));
  _set("nm-spikes", t || (S.total_spikes != null ? String(S.total_spikes) : "\u2014"));
  // honesty label verbatim — never upgraded
  _set("nm-label",  t || (S.label || "MODELED"));
  if (_show) {
    _show.setChip("spk", S.label || "MODELED", { text: "LIF spikes" });
    _show.setChip("energy", S.energy_label || "MODELED", { text: "energy est." });
    _show.refreshPlain();
  }
}

// =============================================================================
// unmount — clean up everything; must not affect other organs
// =============================================================================
export function unmount() {
  _polls.forEach((p) => { try { p.stop(); } catch (_) {} }); _polls = [];
  try { if (_show) _show.destroy(); } catch (_) {}
  try {
    if (_group && _stage) {
      _group.traverse((o) => {
        if (o.geometry && o.geometry.dispose) o.geometry.dispose();
        if (o.material) {
          const ms = Array.isArray(o.material) ? o.material : [o.material];
          ms.forEach((m) => { if (m.dispose) m.dispose(); });
        }
      });
      _stage.scene.remove(_group);
    }
  } catch (_) {}
  _group = _show = null;
  _nodes = []; _edgeLines = null; _hubSphere = null;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.mean_hz = S.sparsity = S.energy_pj = S.total_spikes = null;
  S.spike_counts = S.membrane_v = S.energy_label = null;
  S.state = "init";
  _flashTimer.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
