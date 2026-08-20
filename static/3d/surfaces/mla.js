// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/mla.js — MULTI-HEAD LATENT ATTENTION (MLA) low-rank joint KV-compression
// organ for the holographic frontier ring (DeepSeek-V2/V3-style). Renders the full,
// uncompressed KV cache as a TALL lattice-blue column and the compressed shared
// latent as a SHORT proof-teal column beside it — the height ratio between the two
// columns visualizes `compression_ratio` directly. A faint grey ghost column shows
// the up-projected RECONSTRUCTION overlaid on the full-KV column (its height/opacity
// wobble encodes `reconstruction_error`). A HUD shows compression_ratio +
// reconstruction_error read live from /api/killinchu/v1/mla/latent-compress. Honesty
// label "MODELED" is read VERBATIM from the JSON and displayed as-is; it is never
// upgraded.
//
// Surface export shape (mirrors ringattn.js / specdecode.js / testtime.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   seq_len, n_heads, d_head, d_latent, mha_cache_size, mla_cache_size,
//   compression_ratio, reconstruction_error
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   DeepSeek-V2 (introduces Multi-Head Latent Attention / low-rank KV joint
//   compression):
//     DeepSeek-AI et al. 2024, arXiv:2405.04434
//     https://arxiv.org/abs/2405.04434
//   DeepSeek-V3 (adopts and validates MLA at larger scale):
//     DeepSeek-AI et al. 2024, arXiv:2412.19437
//     https://arxiv.org/abs/2412.19437
//
// HONESTY LABELS: MODELED (deterministic low-rank down/up-projection simulation of
//   the MLA KV-compression idea; NOT trained weights; NEVER-CLAIMED-AS DeepSeek-V2
//   or DeepSeek-V3). Read verbatim from JSON; never upgraded here.
// COLOURS: lattice-blue 0x5b8dee (full/uncompressed KV column), proof-teal 0x3af4c8
//   (compressed latent column / HUD accent), greys (reconstruction ghost / degraded
//   state). Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "mla";
const TITLE = "Multi-Head Latent Attention · KV-Compression Simulator (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted twin (same-origin, szl_latent_attention.py):
// a real low-rank down/up-projection of a seeded KV matrix (DeepSeek MLA idea) with an exact
// L2 reconstruction residual (label MODELED, read verbatim). The isolated killinchu Space stays
// a guarded cross-origin FALLBACK so a fault in either path never darkens the other.
const EP = "/api/a11oy/v1/mla/latent-compress?seed=42&seq_len=128&n_heads=8&d_head=64&d_latent=128";
const EP_FALLBACK = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/mla/latent-compress?seed=42&seq_len=128&n_heads=8&d_head=64&d_latent=128";

// data-viz hues — purple BANNED
const C_FULL   = 0x5b8dee;  // lattice-blue (full/uncompressed KV column)
const C_LATENT = 0x3af4c8;  // proof-teal (compressed latent column / HUD accent)
const C_GHOST  = 0x8a9099;  // grey (reconstruction ghost overlay)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// column layout geometry
const COL_HALF_W   = 0.55;  // column half-width/depth (box footprint)
const COL_GAP      = 2.4;   // world-units between the full-KV and latent columns
const MAX_FULL_H   = 8.0;   // world-units — height of the full-KV column at scale=1
const MIN_LATENT_H = 0.15;  // world-units — floor height so the latent column never vanishes

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _floor       = null;
let _fullCol     = null;    // THREE.Mesh — full/uncompressed KV column (lattice-blue)
let _latentCol   = null;    // THREE.Mesh — compressed latent column (proof-teal)
let _ghostCol    = null;    // THREE.Mesh — reconstruction ghost, overlaid on the full column
let _linkLine    = null;    // THREE.Line — connecting line between the two columns
let _fullTargetH   = 0.4;
let _latentTargetH = 0.4;
let _ghostTargetH  = 0.4;

// live state
const S = {
  label:        null,
  seqLen:       null,   // seq_len
  nHeads:       null,   // n_heads
  dHead:        null,   // d_head
  dLatent:      null,   // d_latent
  mhaCache:     null,   // mha_cache_size
  mlaCache:     null,   // mla_cache_size
  ratio:        null,   // compression_ratio
  reconErr:     null,   // reconstruction_error
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(6, 6, 14);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(1, 2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildColumns();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onMla, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

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
  _floor = grid;
}

// Two box columns side-by-side: full/uncompressed KV (tall, lattice-blue) and
// compressed latent (short, proof-teal), plus a faint grey ghost box overlaid
// on the full-KV column showing the up-projected reconstruction. We scale
// each column's Y-scale in-place (no per-poll geometry churn) with its base
// centered at y=0 via geometry translation, so scaling grows it upward.
function _buildColumns() {
  const THREE = _THREE;

  const boxGeo = new THREE.BoxGeometry(COL_HALF_W * 2, 1, COL_HALF_W * 2);
  boxGeo.translate(0, 0.5, 0); // base sits at y=0; scaling Y grows upward

  _fullCol = new THREE.Mesh(
    boxGeo,
    new THREE.MeshStandardMaterial({ color: C_FULL, emissive: C_FULL, emissiveIntensity: 0.28, transparent: true, opacity: 0.85 }),
  );
  _fullCol.position.set(-COL_GAP / 2, 0, 0);
  _fullCol.scale.set(1, MIN_LATENT_H, 1);
  _group.add(_fullCol);

  // ghost reconstruction: same footprint as the full column, slightly larger
  // to read as an "aura", faint grey wireframe-ish translucency.
  const ghostGeo = new THREE.BoxGeometry(COL_HALF_W * 2.22, 1, COL_HALF_W * 2.22);
  ghostGeo.translate(0, 0.5, 0);
  _ghostCol = new THREE.Mesh(
    ghostGeo,
    new THREE.MeshStandardMaterial({ color: C_GHOST, emissive: C_GHOST, emissiveIntensity: 0.12, transparent: true, opacity: 0.22, wireframe: true }),
  );
  _ghostCol.position.set(-COL_GAP / 2, 0, 0);
  _ghostCol.scale.set(1, MIN_LATENT_H, 1);
  _group.add(_ghostCol);

  _latentCol = new THREE.Mesh(
    boxGeo,
    new THREE.MeshStandardMaterial({ color: C_LATENT, emissive: C_LATENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.92 }),
  );
  _latentCol.position.set(COL_GAP / 2, 0, 0);
  _latentCol.scale.set(1, MIN_LATENT_H, 1);
  _group.add(_latentCol);

  // connecting line from the top of the full column down to the top of the
  // latent column — a visual "compression funnel" cue.
  const linkGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(-COL_GAP / 2, MIN_LATENT_H, 0),
    new THREE.Vector3(COL_GAP / 2, MIN_LATENT_H, 0),
  ]);
  const linkMat = new THREE.LineBasicMaterial({ color: C_GRID, transparent: true, opacity: 0.35 });
  _linkLine = new THREE.Line(linkGeo, linkMat);
  _group.add(_linkLine);
}

// =============================================================================
// live data handler
// =============================================================================
function _onMla(j) {
  // read honesty label VERBATIM — never upgrade
  S.label    = (j.label || "MODELED").toUpperCase();
  S.seqLen   = typeof j.seq_len              === "number" ? j.seq_len              : null;
  S.nHeads   = typeof j.n_heads              === "number" ? j.n_heads              : null;
  S.dHead    = typeof j.d_head               === "number" ? j.d_head               : null;
  S.dLatent  = typeof j.d_latent             === "number" ? j.d_latent             : null;
  S.mhaCache = typeof j.mha_cache_size       === "number" ? j.mha_cache_size       : null;
  S.mlaCache = typeof j.mla_cache_size       === "number" ? j.mla_cache_size       : null;
  S.ratio    = typeof j.compression_ratio    === "number" ? j.compression_ratio    : null;
  S.reconErr = typeof j.reconstruction_error === "number" ? j.reconstruction_error : null;

  _updateColumns();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the two columns + ghost from live data
// =============================================================================
function _updateColumns() {
  const live = S.state === "live";

  // Full-KV column height is fixed at MAX_FULL_H when live (it's the
  // reference/baseline). Latent column height is MAX_FULL_H / compression_ratio
  // — directly visualizing how much smaller the compressed cache is.
  _fullTargetH = live ? MAX_FULL_H : MIN_LATENT_H;
  _latentTargetH = live && S.ratio ? Math.max(MIN_LATENT_H, MAX_FULL_H / S.ratio) : MIN_LATENT_H;
  // Ghost height wobbles around the full column's height, offset by a
  // normalized reconstruction-error term so a larger error reads as a more
  // visibly mismatched (taller/shorter) ghost silhouette.
  const errNorm = live && S.reconErr != null ? Math.min(1.0, S.reconErr / 40.0) : 0;
  _ghostTargetH = live ? MAX_FULL_H * (1.0 + 0.18 * errNorm) : MIN_LATENT_H;

  const fullColor = live ? C_FULL : C_DIM;
  _fullCol.material.color.setHex(fullColor);
  _fullCol.material.emissive.setHex(fullColor);
  _fullCol.material.opacity = live ? 0.85 : 0.2;

  const latentColor = live ? C_LATENT : C_DIM;
  _latentCol.material.color.setHex(latentColor);
  _latentCol.material.emissive.setHex(latentColor);
  _latentCol.material.opacity = live ? 0.92 : 0.2;

  _ghostCol.material.opacity = live ? Math.min(0.4, 0.15 + 0.5 * errNorm) : 0.06;

  if (_linkLine) {
    _linkLine.material.color.setHex(live ? C_GRID : C_DIM);
    _linkLine.material.opacity = live ? 0.35 : 0.1;
  }
}

// =============================================================================
// per-frame animation — smooth column height easing + gentle rotation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00007) * 0.10;

  const ease = 0.08;
  if (_fullCol) {
    _fullCol.scale.y += (_fullTargetH - _fullCol.scale.y) * ease;
  }
  if (_latentCol) {
    _latentCol.scale.y += (_latentTargetH - _latentCol.scale.y) * ease;
    // gentle pulse on the compressed column to draw the eye to the "win"
    const pulse = 1.0 + 0.03 * Math.sin(t * 0.005);
    _latentCol.scale.x = pulse; _latentCol.scale.z = pulse;
  }
  if (_ghostCol) {
    _ghostCol.scale.y += (_ghostTargetH - _ghostCol.scale.y) * ease;
  }
  if (_linkLine && _fullCol && _latentCol) {
    const pts = [
      new _THREE.Vector3(-COL_GAP / 2, _fullCol.scale.y, 0),
      new _THREE.Vector3(COL_GAP / 2, _latentCol.scale.y, 0),
    ];
    _linkLine.geometry.setFromPoints(pts);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee",
    badge: _badge,
    chips: [{ label: "MODELED", text: "KV compression", name: "mla" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'Per-token Key/Value vectors across all heads are jointly <b>down-projected</b> to a ' +
      'shared low-rank <b>latent</b> vector (only this gets cached), then <b>up-projected</b> ' +
      'back on demand. The tall <b>lattice-blue</b> column is the full/uncompressed KV cache; ' +
      'the short <b>proof-teal</b> column is the compressed latent cache; the faint grey ghost ' +
      'shows the reconstruction. Honesty label <b>MODELED</b> (deterministic low-rank ' +
      'down/up-projection simulation; NOT trained DeepSeek weights). 0 runtime CDN.',
    citations:
      "DeepSeek-V2 arXiv:2405.04434 (introduces MLA) \u00b7 DeepSeek-V3 arXiv:2412.19437 (adopts MLA). MODELED \u00b7 not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["mla-seqlen"]   = _show.addField("seq_len (positions)");
  _el["mla-heads"]    = _show.addField("n_heads \u00d7 d_head");
  _el["mla-dlatent"]  = _show.addField("d_latent (compressed width)");
  _el["mla-mhacache"] = _show.addField("mha_cache_size (elements)");
  _el["mla-mlacache"] = _show.addField("mla_cache_size (elements)");
  _el["mla-ratio"]    = _show.addField("compression_ratio \u2014 MODELED");
  _el["mla-err"]      = _show.addField("reconstruction_error (mean L2)");
  _el["mla-label"]    = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const ratio = S.ratio    != null ? S.ratio.toFixed(2) + "\u00d7" : "loading\u2026";
  const err   = S.reconErr != null ? S.reconErr.toFixed(3) : "loading\u2026";
  const dl    = S.dLatent  != null ? String(S.dLatent) : "loading\u2026";
  return (
    "<b>What this means:</b> Normally, a model must remember a separate \u201ckey\u201d and " +
    "\u201cvalue\u201d vector for every attention head, for every word it has generated so far " +
    "\u2014 this memory (the KV cache) grows huge for long conversations. <b>Multi-Head Latent " +
    "Attention</b> instead squeezes all of a word's keys/values into ONE small shared " +
    "summary vector (width <b>" + dl + "</b>) before caching it, then unpacks that summary " +
    "back out when needed. Here, that squeeze-then-unpack trick shrinks the cache by " +
    "<b>" + ratio + "</b> \u2014 at the cost of a small, measurable reconstruction mismatch " +
    "(<b>" + err + "</b> average error) since a random squeeze loses some detail. In real " +
    "DeepSeek-V2/V3 models, that squeeze is <i>trained</i> to keep the mismatch tiny; this " +
    "view uses an untrained, deterministic squeeze to demonstrate the compression math " +
    "honestly \u2014 it is a <b>MODELED</b> simulation, not a run of DeepSeek's actual model.");
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
  _set("mla-seqlen",   t || (S.seqLen != null ? S.seqLen.toLocaleString() : "\u2014"));
  _set("mla-heads",    t || (S.nHeads != null && S.dHead != null ? (S.nHeads + " \u00d7 " + S.dHead) : "\u2014"));
  _set("mla-dlatent",  t || (S.dLatent != null ? String(S.dLatent) : "\u2014"));
  _set("mla-mhacache", t || (S.mhaCache != null ? S.mhaCache.toLocaleString() : "\u2014"));
  _set("mla-mlacache", t || (S.mlaCache != null ? S.mlaCache.toLocaleString() : "\u2014"));
  _set("mla-ratio",    t || (S.ratio != null ? S.ratio.toFixed(3) + "\u00d7" : "\u2014"));
  _set("mla-err",      t || fx(S.reconErr, 4));
  // honesty label verbatim — never upgraded
  _set("mla-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("mla", S.label || "MODELED", { text: "KV compression" }); _show.refreshPlain(); }
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
  _floor = null; _fullCol = null; _latentCol = null; _ghostCol = null; _linkLine = null;
  _fullTargetH = 0.4; _latentTargetH = 0.4; _ghostTargetH = 0.4;
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.nHeads = S.dHead = S.dLatent = null;
  S.mhaCache = S.mlaCache = S.ratio = S.reconErr = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP, EP_FALLBACK], mount, unmount };
