// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/hybridssm.js — HYBRIDSSM: a MODELED comparison of attention vs
// state-space (SSM) vs hybrid (Jamba / Griffin / Samba / Zamba) architectures on
// the compute / memory frontier. Each architecture is a lane; a polyline traces
// its KV-cache memory (Y, log-scaled) across a sweep of context lengths (X). A
// dense-attention baseline climbs steeply (lattice-blue) as its KV cache grows
// linearly with context; a pure SSM stays flat on the floor (proof-teal — a
// constant recurrent state, no growing KV); the hybrids sit between (violet-blue),
// keeping a MINORITY of attention layers to recover long-context recall at a
// fraction of the memory. Node size = an ILLUSTRATIVE long-context recall proxy
// (NOT a benchmark). Live snapshot:
//   /api/a11oy/v1/frontier/hybridssm
//
// This is a MODELED architecture-frontier picture, honestly labeled:
//   ANALYTIC cost curves — KV-cache memory (2·d·L·bytes per global-attn layer,
//   windowed for sliding attention, constant state for SSM) and per-token decode
//   FLOPs (constant backbone + ~4·d·ctx per attention layer + constant SSM scan)
//   — plus an illustrative recall proxy. NO measured benchmark numbers.
//
// LEADERS CITED (clean-room; NOT claimed as SZL's own):
//   Mamba — Gu & Dao 2023, arXiv:2312.00752
//   Jamba — Lieber et al. 2024, arXiv:2403.19887
//   Griffin — De et al. 2024, arXiv:2402.19427
//   Samba — Ren et al. 2024, arXiv:2406.07522
//   Zamba — Glorioso et al. 2024, arXiv:2405.16712
//
// HONESTY LABELS: MODELED (analytic KV / FLOPs curves computed from documented
//   architecture compositions + stated cost coefficients; read VERBATIM from
//   JSON, never upgraded). The recall proxy is ILLUSTRATIVE, NOT a benchmark. The
//   per-arch compositions and the Λ-advisory pick are CONJECTURE (Λ = Conjecture
//   1, gray, never green; advisory trust capped ≤0.97). Curves are MODELED, NOT
//   MEASURED (no profiler / no hardware).
// COLOURS: lattice-blue 0x5b8dee (dense attention baseline), proof-teal 0x3af4c8
//   (pure SSM / Mamba), violet-blue 0x8a6bff (hybrids), greys (degraded / no data).
//   Purple BANNED.
// 0 RUNTIME CDN. three.js via ctx.THREE (vendored by the page importmap).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8 (adds 0). Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "hybridssm";
const TITLE = "HybridSSM · Attention vs State-Space vs Hybrid Frontier (live)";

// Served SAME-ORIGIN by szl_hybridssm.py — a deterministic MODELED cost model.
const EP = "/api/a11oy/v1/frontier/hybridssm?d_model=4096&n_layers=32";

// data-viz hues — purple BANNED
const C_ATTN  = 0x5b8dee;  // lattice-blue (dense attention baseline)
const C_SSM   = 0x3af4c8;  // proof-teal (pure SSM / Mamba)
const C_HYB   = 0x8a6bff;  // violet-blue (hybrid family)
const C_DIM   = 0x42505d;  // grey (degraded / no live data)
const C_GRID  = 0x1b3a44;  // floor / link colour

// layout geometry
const MAX_ARCH = 8;    // pre-allocated architecture lanes
const MAX_PTS  = 16;   // pre-allocated points per lane (seq-length sweep)
const X_STEP   = 1.7;  // spacing between seq-length nodes along X
const Z_STEP   = 2.3;  // spacing between architecture lanes along Z
const Y_SCALE  = 1.9;  // log10(MB+1) -> world Y

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _badge = null, _f = {};

// geometry handles — pre-allocated lanes; each lane has a polyline + point meshes.
let _floor = null;
let _lanes = [];   // Array<{ line, pts: THREE.Mesh[], endMesh }>

const S = {
  label: null,
  dModel: null, nLayers: null, bytesPerElem: null, stateDim: null,
  seqLengths: null,
  archs: null,          // architectures[]
  frontier: null,
  advisory: null,
  state: "init",
};

function _colorFor(name) {
  if (name === "attention") return C_ATTN;
  if (name === "mamba") return C_SSM;
  return C_HYB;  // jamba / griffin / samba / zamba (hybrid family)
}

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(2, 11, 24);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 3.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildLanes();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _buildShowcase(ctx);

  // top-N lane labels (billboarded) + hover tooltip via the shared helper.
  // Label the endpoint node of each lane; weight by KV memory so the steep
  // attention lane ranks first.
  _show.attachSceneLabels({
    objects: () => _lanes.map((l) => l.endMesh).filter((m) => m && m.visible),
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.userData ? o.userData.weight : 0),
    topN: MAX_ARCH,
    hover: true,
  });

  _polls.push(ctx.live.poll(EP, 8000, _onData, {
    badge: _badge, onState: (m) => { S.state = m.state; _paint(); },
  }));
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(44, 44, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
  _floor = grid;
}

// Pre-allocate MAX_ARCH lanes, each with a polyline (KV-memory curve) and
// MAX_PTS point meshes. Everything hidden until live data arrives.
function _buildLanes() {
  const THREE = _THREE;
  const ptGeo = new THREE.SphereGeometry(0.16, 10, 10);
  for (let a = 0; a < MAX_ARCH; a++) {
    const pts = [];
    for (let i = 0; i < MAX_PTS; i++) {
      const mesh = new THREE.Mesh(
        ptGeo,
        new THREE.MeshStandardMaterial({ color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
      );
      mesh.visible = false;
      mesh.userData = { label: "", weight: 0 };
      _group.add(mesh);
      pts.push(mesh);
    }
    const lgeo = new THREE.BufferGeometry();
    lgeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(MAX_PTS * 3), 3));
    lgeo.setDrawRange(0, 0);
    const lmat = new THREE.LineBasicMaterial({ color: C_DIM, transparent: true, opacity: 0.0 });
    const line = new THREE.Line(lgeo, lmat);
    line.visible = false;
    _group.add(line);
    _lanes.push({ line, pts, endMesh: pts[0] });
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onData(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (j && j.label) || (p && p.label) || "MODELED";
  S.label = String(rawLabel).toUpperCase();

  S.dModel       = typeof p.d_model === "number" ? p.d_model : null;
  S.nLayers      = typeof p.n_layers === "number" ? p.n_layers : null;
  S.bytesPerElem = typeof p.bytes_per_elem === "number" ? p.bytes_per_elem : null;
  S.stateDim     = typeof p.state_dim === "number" ? p.state_dim : null;
  S.seqLengths   = Array.isArray(p.seq_lengths) ? p.seq_lengths : null;
  S.archs        = Array.isArray(p.architectures) ? p.architectures : null;
  S.frontier     = (p && typeof p.frontier === "object") ? p.frontier : null;
  S.advisory     = (p && typeof p.advisory === "object") ? p.advisory : null;

  _updateScene();
  _paint();
}

// =============================================================================
// geometry updater
// =============================================================================
function _updateScene() {
  const live = S.state === "live";
  const archs = live && S.archs ? S.archs.slice(0, MAX_ARCH) : [];
  const nSeq = S.seqLengths ? Math.min(S.seqLengths.length, MAX_PTS) : 0;
  const xMid = (nSeq - 1) / 2;
  const zMid = (Math.max(1, archs.length) - 1) / 2;

  for (let a = 0; a < MAX_ARCH; a++) {
    const lane = _lanes[a];
    const arch = a < archs.length ? archs[a] : null;
    if (!arch || !arch.curve || nSeq === 0) {
      lane.line.visible = false;
      lane.pts.forEach((m) => { m.visible = false; });
      continue;
    }
    const col = live ? _colorFor(arch.name) : C_DIM;
    const z = (a - zMid) * Z_STEP;
    const curve = arch.curve;
    const posAttr = lane.line.geometry.getAttribute("position");
    let drawn = 0;
    let endIdx = 0;

    for (let i = 0; i < MAX_PTS; i++) {
      const mesh = lane.pts[i];
      const pt = i < nSeq && i < curve.length ? curve[i] : null;
      if (!pt) { mesh.visible = false; continue; }
      const mb = typeof pt.kv_cache_mb === "number" ? pt.kv_cache_mb : 0;
      const recall = typeof pt.recall_proxy === "number" ? pt.recall_proxy : 0.5;
      const x = (i - xMid) * X_STEP;
      const y = Math.log10(mb + 1) * Y_SCALE;
      mesh.position.set(x, y, z);
      mesh.visible = true;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = live ? 0.5 : 0.12;
      mesh.material.opacity = live ? 0.95 : 0.3;
      // node size encodes the illustrative recall proxy (bigger = better recall).
      mesh.scale.setScalar(0.55 + recall * 1.4);
      mesh.userData.label = "";
      mesh.userData.weight = 0;
      posAttr.array[drawn * 3] = x;
      posAttr.array[drawn * 3 + 1] = y;
      posAttr.array[drawn * 3 + 2] = z;
      drawn++;
      endIdx = i;
    }

    posAttr.needsUpdate = true;
    lane.line.geometry.setDrawRange(0, drawn);
    lane.line.geometry.computeBoundingSphere();
    lane.line.visible = drawn > 1;
    lane.line.material.color.setHex(col);
    lane.line.material.opacity = live ? 0.55 : 0.12;

    // endpoint node carries the lane label (arch name + KV at seq_max).
    const endMesh = lane.pts[endIdx];
    lane.endMesh = endMesh;
    const summ = arch.summary || {};
    const kvEnd = typeof summ.kv_cache_mb === "number" ? summ.kv_cache_mb : null;
    endMesh.userData.label = arch.name + (kvEnd != null ? " · " + _mb(kvEnd) : "");
    endMesh.userData.weight = kvEnd != null ? kvEnd : 0;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = (typeof performance !== "undefined" ? performance.now() : Date.now());
  if (_group) _group.rotation.y = Math.sin(t * 0.00006) * 0.10;
}

// =============================================================================
// showcase overlay (shared helper) — compact chrome + collapsible KPIs
// =============================================================================
function _buildShowcase(ctx) {
  _show = createShowcase(ctx, {
    id: ID,
    title: TITLE,
    accent: "#5b8dee",
    badge: _badge,
    chips: [
      { label: "MODELED", text: "cost curves", name: "cost" },
      { label: "STRUCTURAL-ONLY", text: "Λ=Conjecture 1 · recall proxy illustrative", name: "syn" },
    ],
    legend: ["MODELED", "STRUCTURAL-ONLY"],
    description:
      "<b>HybridSSM.</b> Each lane is an architecture; its polyline traces the " +
      "<b>KV-cache memory</b> (log Y) across a sweep of context lengths (X). " +
      "Dense <b>attention</b> (lattice-blue) climbs steeply — its KV cache grows " +
      "linearly with context. A pure <b>SSM</b> (Mamba, proof-teal) stays on the " +
      "floor: a constant recurrent state, no growing KV. The <b>hybrids</b> " +
      "(Jamba / Griffin / Samba / Zamba, violet-blue) keep a minority of " +
      "attention layers to recover long-context recall at a fraction of the " +
      "memory. Node size = an <b>illustrative long-context recall proxy</b> — a " +
      "coverage model, <b>NOT a benchmark</b>. The KV-memory and per-token " +
      "decode-FLOPs curves are <b>MODELED (analytic), not MEASURED</b> — no " +
      "profiler or hardware is involved.",
    citations:
      "Mamba arXiv:2312.00752 · Jamba arXiv:2403.19887 · Griffin arXiv:2402.19427 · " +
      "Samba arXiv:2406.07522 · Zamba arXiv:2405.16712. " +
      "MODELED/CONJECTURE · not claimed-as. Nothing here is in the locked-8.",
    plain: {
      html: () =>
        "Big language models remember their context in a <b>KV cache</b> that grows " +
        "with the length of the text — so very long prompts cost a lot of memory. " +
        "<b>State-space models</b> (like Mamba) instead keep a small fixed summary, " +
        "so they stay cheap, but a fixed summary can forget exact details far back. " +
        "<b>Hybrids</b> mix a few attention layers into a state-space backbone to " +
        "get the best of both: near-attention recall at a fraction of the memory. " +
        "This view models that trade-off — the curves are calculated from each " +
        "design, <b>not measured</b>, and the recall dots are illustrative, not a " +
        "benchmark score.",
    },
  });

  _f.ref      = _show.addField("reference model (MODELED)", "ref");
  _f.attnKv   = _show.addField("attention KV @ seq_max", "attnKv");
  _f.ssmKv    = _show.addField("SSM (Mamba) KV @ seq_max", "ssmKv");
  _f.hybKv    = _show.addField("best hybrid KV @ seq_max", "hybKv");
  _f.kvRed    = _show.addField("KV reduction vs attention", "kvRed");
  _f.flRed    = _show.addField("decode-FLOPs reduction", "flRed");
  _f.advise   = _show.addField("Λ-advisory pick (gray)", "advise");
  _f.trust    = _show.addField("advisory trust (≤0.97)", "trust");
  _f.recall   = _show.addField("recall proxy (illustrative)", "recall");
  _f.label    = _show.addField("honesty label", "label");
  _paint();
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function _mb(v) {
  if (typeof v !== "number") return "—";
  if (v >= 1024) return (v / 1024).toFixed(2) + " GB";
  if (v >= 1) return v.toFixed(1) + " MB";
  return v.toFixed(3) + " MB";
}
function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "—"; }
function _archByName(n) { return (S.archs || []).find((a) => a.name === n) || null; }

function _paint() {
  if (!_show) return;
  const t = _tok(S.state);
  if (_show.setChip) _show.setChip("cost", S.label || "MODELED", { text: "cost curves" });

  _set("ref", t || (S.dModel != null
        ? "d=" + S.dModel + " · L=" + (S.nLayers != null ? S.nLayers : "—") + " layers · bf" + (S.bytesPerElem != null ? S.bytesPerElem * 8 : "?")
        : "—"));

  const attn = _archByName("attention");
  const ssm  = _archByName("mamba");
  const fr = S.frontier || {};

  _set("attnKv", t || (attn && attn.summary ? _mb(attn.summary.kv_cache_mb) : "—"));
  _set("ssmKv",  t || (ssm && ssm.summary ? _mb(ssm.summary.kv_cache_mb) : "—"));
  _set("hybKv",  t || (fr.min_hybrid
        ? _mb(fr.min_hybrid_kv_mb) + " (" + fr.min_hybrid + ")" : "—"));
  _set("kvRed",  t || (fr.best_kv_reduction_x != null ? fr.best_kv_reduction_x + "×" : "—"));
  _set("flRed",  t || (fr.best_flops_reduction_x != null ? fr.best_flops_reduction_x + "×" : "—"));

  const adv = S.advisory || {};
  _set("advise", t || (adv.recommended
        ? adv.recommended + (adv.at_seq_len ? " @ " + _ctxLen(adv.at_seq_len) : "") : "—"));
  _set("trust",  t || (adv.trust != null
        ? fx(adv.trust, 3) + (adv.trust_cap != null ? " (≤" + adv.trust_cap + ")" : "") : "—"));
  _set("recall", t || (adv.recommended_recall_proxy != null
        ? fx(adv.recommended_recall_proxy, 3) + " (illustrative)" : "—"));
  _set("label",  t || (S.label || "MODELED"));
}

function _ctxLen(n) {
  if (typeof n !== "number") return "—";
  if (n >= 1024) return (n / 1024) + "k";
  return String(n);
}
function _set(k, v) { if (_f[k]) _f[k].textContent = v; }

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
  _floor = null; _lanes = [];
  _f = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.dModel = S.nLayers = S.bytesPerElem = S.stateDim = null;
  S.seqLengths = S.archs = S.frontier = S.advisory = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
