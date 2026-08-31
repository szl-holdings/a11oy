// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/retrievalattn.js — RETRIEVAL-MODULATED LONG-CONTEXT ATTENTION organ for
// the holographic frontier ring. Renders a long token stream as a row of nodes: the
// last W tokens are the LOCAL window (kept for free), and planted "needle" facts glow
// by whether each read policy recalls them. A plain sparse window is structurally
// blind to any needle beyond the window; the MATCH retrieval step re-injects the
// long-range needles it drops — chosen by CONTENT similarity to the query — so they
// re-light proof-teal. An exponentially-decaying-memory baseline only rescues the
// recent tail. A HUD shows long-range recall per policy, the recovery the retrieval
// step adds over a plain sparse window, and the sub-dense attend fraction it pays,
// from /api/a11oy/v1/retrievalattn/recall. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; it is never upgraded.
//
// Surface export shape (mirrors gateddelta.js / kvcache.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from the live endpoint):
//   seq_len, window, n_needles, retrieval_k, dim, decay,
//   full_long_range_recall, sparse_long_range_recall, edm_long_range_recall,
//   retrieval_long_range_recall, long_range_recall_recovery, retrieval_vs_edm_gain,
//   attend_frac_sparse/retrieval/full, n_long_range_needles, n_window_needles,
//   per_needle[] {pos,in_window,sim,retrieved,edm_weight,recalled_*}
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own; arXiv ids VERIFIED):
//   MATCH: Modulating Attention via In-Context Retrieval — Ma et al. 2026, arXiv:2606.29844
//   Augmenting Attention with Exponentially Decaying Memory — Wei & Gulcehre 2026, arXiv:2605.28640
//
// HONESTY LABELS: MODELED (deterministic simulation of full / sparse-window /
//   decaying-memory / retrieval-augmented read policies over a synthetic needle task;
//   NOT a real trained model, corpus, or GPU). Read verbatim from JSON; never upgraded.
// COLOURS: proof-teal 0x3af4c8 (retrieval-recovered / HUD accent), lattice-blue
//   0x5b8dee (local window), amber 0xf5b23a (decaying-memory tail), greys (dropped /
//   degraded). Purple BANNED.
// 0 RUNTIME CDN. Vendored three.js r170 via page importmap.
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// Nothing here is in the locked-8. Λ stays Conjecture 1. Trust never 100%.

import { createShowcase } from "./_showcase.js";

const ID    = "retrievalattn";
const TITLE = "Retrieval-Modulated Long-Context Attention · needle recall (live)";

// PRIMARY endpoint is the a11oy-NATIVE self-hosted twin (same-origin, szl_retrieval_attn.py):
// real full / sparse / decaying-memory / retrieval read policies over a seeded needle
// task (label MODELED, read verbatim). No cross-origin dependency.
const EP = "/api/a11oy/v1/retrievalattn/recall?seed=42&seq_len=512&window=64&n_needles=12&retrieval_k=16&dim=16&decay=0.08";

// data-viz hues — purple BANNED
const C_RETR   = 0x3af4c8;  // proof-teal (retrieval-recovered needle / HUD accent)
const C_WIN    = 0x5b8dee;  // lattice-blue (local window)
const C_EDM    = 0xf5b23a;  // amber (decaying-memory tail)
const C_DROP   = 0x5a6570;  // grey (dropped long-range needle)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;  // floor / link colour

// token-stream layout geometry
const STREAM_LEN = 15.0;    // world-units the whole sequence spans along X
const MAX_NEEDLES = 24;     // cap on needle nodes rendered (backend clamps n_needles)
const BASE_Y     = 0.4;     // resting height of a needle node

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

// geometry handles
let _spine     = null;                // THREE.Line — the token-stream spine
let _winMesh   = null;                // THREE.Mesh — the local-window slab (last W tokens)
let _query     = null;                // THREE.Mesh — the query marker at the stream head
let _needle    = [];                  // Array<THREE.Mesh> — one node per planted needle

// live state
const S = {
  label:        null,
  seqLen:       null,
  window:       null,
  nNeedles:     null,
  retrievalK:   null,
  dim:          null,
  decay:        null,
  nLongRange:   null,
  nWindow:      null,
  fullLR:       null,   // full_long_range_recall
  sparseLR:     null,   // sparse_long_range_recall
  edmLR:        null,   // edm_long_range_recall
  retrLR:       null,   // retrieval_long_range_recall
  recovery:     null,   // long_range_recall_recovery
  vsEdm:        null,   // retrieval_vs_edm_gain
  attendSparse: null,
  attendRetr:   null,
  perNeedle:    null,   // per_needle[]
  state:        "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 6, 18);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 1, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildStream();
  _buildNeedles();
  _buildQuery();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onRecall, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); } }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(36, 36, C_GRID, 0x0f2027);
  grid.material.opacity = 0.18; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildStream() {
  const THREE = _THREE;
  const half = STREAM_LEN / 2;
  // token-stream spine along X (index 0 at -half, last token at +half == query head)
  {
    const pts = [new THREE.Vector3(-half, 0, 0), new THREE.Vector3(half, 0, 0)];
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: C_WIN, transparent: true, opacity: 0.4 });
    _spine = new THREE.Line(geo, mat);
    _group.add(_spine);
  }
  // local-window slab — a translucent box hugging the last W tokens near the head.
  // width is set from live data in _updateStream; starts hidden.
  _winMesh = new THREE.Mesh(
    new THREE.BoxGeometry(1.0, 1.2, 2.4),
    new THREE.MeshStandardMaterial({ color: C_WIN, emissive: C_WIN, emissiveIntensity: 0.22, transparent: true, opacity: 0.0 }),
  );
  _winMesh.position.set(half, 0.6, 0);
  _winMesh.visible = false;
  _group.add(_winMesh);
}

// Pre-allocate a fixed pool of needle nodes; toggled in-place as live data arrives
// (no per-poll geometry churn).
function _buildNeedles() {
  const THREE = _THREE;
  const geo = new THREE.IcosahedronGeometry(0.24, 0);
  for (let n = 0; n < MAX_NEEDLES; n++) {
    const node = new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({ color: C_DROP, emissive: C_DROP, emissiveIntensity: 0.2, transparent: true, opacity: 0.0 }),
    );
    node.position.set(0, BASE_Y, 0);
    node.visible = false;
    _group.add(node);
    _needle.push(node);
  }
}

function _buildQuery() {
  const THREE = _THREE;
  _query = new THREE.Mesh(
    new THREE.ConeGeometry(0.34, 0.9, 4),
    new THREE.MeshStandardMaterial({ color: C_RETR, emissive: C_RETR, emissiveIntensity: 0.5, wireframe: true, transparent: true, opacity: 0.85 }),
  );
  _query.position.set(STREAM_LEN / 2, 1.4, 0);
  _query.rotation.z = Math.PI;   // point down at the stream head
  _group.add(_query);
}

// =============================================================================
// live data handler
// =============================================================================
function _onRecall(j) {
  // read honesty label VERBATIM — never upgrade
  S.label        = (j.label || "MODELED").toUpperCase();
  S.seqLen       = typeof j.seq_len                      === "number" ? j.seq_len                      : null;
  S.window       = typeof j.window                       === "number" ? j.window                       : null;
  S.nNeedles     = typeof j.n_needles                    === "number" ? j.n_needles                    : null;
  S.retrievalK   = typeof j.retrieval_k                  === "number" ? j.retrieval_k                  : null;
  S.dim          = typeof j.dim                          === "number" ? j.dim                          : null;
  S.decay        = typeof j.decay                        === "number" ? j.decay                        : null;
  S.nLongRange   = typeof j.n_long_range_needles         === "number" ? j.n_long_range_needles         : null;
  S.nWindow      = typeof j.n_window_needles             === "number" ? j.n_window_needles             : null;
  S.fullLR       = typeof j.full_long_range_recall       === "number" ? j.full_long_range_recall       : null;
  S.sparseLR     = typeof j.sparse_long_range_recall     === "number" ? j.sparse_long_range_recall     : null;
  S.edmLR        = typeof j.edm_long_range_recall        === "number" ? j.edm_long_range_recall        : null;
  S.retrLR       = typeof j.retrieval_long_range_recall  === "number" ? j.retrieval_long_range_recall  : null;
  S.recovery     = typeof j.long_range_recall_recovery   === "number" ? j.long_range_recall_recovery   : null;
  S.vsEdm        = typeof j.retrieval_vs_edm_gain        === "number" ? j.retrieval_vs_edm_gain        : null;
  S.attendSparse = typeof j.attend_frac_sparse           === "number" ? j.attend_frac_sparse           : null;
  S.attendRetr   = typeof j.attend_frac_retrieval        === "number" ? j.attend_frac_retrieval        : null;
  S.perNeedle    = Array.isArray(j.per_needle) ? j.per_needle : null;

  _updateStream();
  _paintOverlay();
}

// =============================================================================
// geometry updater — drives the token stream from live data
// =============================================================================
function _updateStream() {
  const live = S.state === "live";
  const half = STREAM_LEN / 2;
  const needles = live && S.perNeedle && S.perNeedle.length ? S.perNeedle.slice(0, MAX_NEEDLES) : [];
  const seq = S.seqLen || 1;

  // local-window slab: cover [seq-W, seq) mapped onto the stream near the head.
  if (_winMesh) {
    if (live && S.window != null && seq > 0) {
      const wFrac = Math.max(0.02, Math.min(1.0, S.window / seq));
      const w = wFrac * STREAM_LEN;
      _winMesh.scale.x = Math.max(0.02, w);
      _winMesh.position.x = half - w / 2;
      _winMesh.material.color.setHex(C_WIN);
      _winMesh.material.emissive.setHex(C_WIN);
      _winMesh.material.opacity = 0.16;
      _winMesh.visible = true;
    } else {
      _winMesh.visible = false;
    }
  }

  for (let n = 0; n < MAX_NEEDLES; n++) {
    const node = _needle[n];
    if (!live || n >= needles.length) { node.visible = false; continue; }
    node.visible = true;
    const rec = needles[n];
    const pos = typeof rec.pos === "number" ? rec.pos : 0;
    const x = -half + (pos / Math.max(1, seq - 1)) * STREAM_LEN;

    // classify colour by which policy recalls this needle:
    //   in-window       -> lattice-blue (kept for free)
    //   retrieval-only  -> proof-teal   (MATCH recovered it)
    //   edm-only tail   -> amber        (decay rescued the recent tail)
    //   dropped         -> grey         (no policy short of dense reaches it)
    let col = C_DROP, glow = 0.15, y = BASE_Y;
    const sim = typeof rec.sim === "number" ? rec.sim : 0;
    if (rec.in_window) {
      col = C_WIN; glow = 0.4; y = BASE_Y + 0.5;
    } else if (rec.recalled_retrieval) {
      col = C_RETR; glow = 0.35 + 0.5 * Math.max(0, Math.min(1, sim)); y = BASE_Y + 0.4 + 0.8 * Math.max(0, sim);
    } else if (rec.recalled_edm) {
      col = C_EDM; glow = 0.3; y = BASE_Y + 0.3;
    } else {
      col = C_DROP; glow = 0.12; y = BASE_Y;
    }
    node.position.set(x, y, 0);
    node.material.color.setHex(col);
    node.material.emissive.setHex(col);
    node.material.emissiveIntensity = glow;
    node.material.opacity = rec.in_window ? 0.95 : (rec.recalled_retrieval ? 0.95 : 0.6);
    // retrieved long-range needles read a touch larger (re-injected into the read set)
    node.scale.setScalar(rec.retrieved && !rec.in_window ? 1.25 : 1.0);
  }

  // spine + query degrade to grey when not live
  if (_spine) {
    _spine.material.color.setHex(live ? C_WIN : C_DIM);
    _spine.material.opacity = live ? 0.4 : 0.15;
  }
  if (_query) {
    const c = live ? C_RETR : C_DIM;
    _query.material.color.setHex(c);
    _query.material.emissive.setHex(c);
    _query.material.opacity = live ? 0.85 : 0.3;
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00009) * 0.10;
  if (_query) {
    _query.rotation.y += 0.03;
    const pulse = 1.0 + 0.12 * Math.sin(t * 0.004);
    _query.scale.setScalar(pulse);
  }
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MODELED", text: "long-range recall", name: "ra" }],
    legend: ["MODELED", "SAMPLE"],
    description:
      'A cheap <b>sparse / local attention window</b> only reads the last W tokens, so any ' +
      'fact planted further back — a long-context <b>needle</b> — is structurally dropped and ' +
      'no recency weighting brings it back. <b>MATCH</b> modulates that window with an ' +
      'in-context <b>retrieval</b> step: it scores the dropped tokens by CONTENT similarity to ' +
      'the query and re-injects the Top-k, recovering the long-range needles the window missed. ' +
      'For contrast an <b>exponentially-decaying-memory</b> baseline only rescues the recent ' +
      'tail (position, not content). The HUD reports long-range recall for each policy, the ' +
      'recovery retrieval adds over a plain sparse window, and the still-sub-dense attend ' +
      'fraction it pays. Honesty label <b>MODELED</b> (deterministic simulation on a synthetic ' +
      'needle task; NOT a real trained model, corpus, or GPU). 0 runtime CDN.',
    citations:
      "MATCH — Ma et al. arXiv:2606.29844 (ACL 2026) · Exponentially-Decaying-Memory attention " +
      "— Wei & Gulcehre arXiv:2605.28640. MODELED · not claimed-as.",
    plain: { html: _plainHtml },
  });

  _el["ra-seqwin"]  = _show.addField("seq_len · window W");
  _el["ra-needles"] = _show.addField("needles (long-range / in-window)");
  _el["ra-fullLR"]  = _show.addField("full-dense long-range recall (oracle)");
  _el["ra-sparse"]  = _show.addField("sparse-window long-range recall");
  _el["ra-edm"]     = _show.addField("decaying-memory long-range recall");
  _el["ra-retr"]    = _show.addField("retrieval long-range recall — MODELED");
  _el["ra-recov"]   = _show.addField("recovery vs plain sparse window");
  _el["ra-vsedm"]   = _show.addField("retrieval vs decaying-memory gain");
  _el["ra-attend"]  = _show.addField("attend fraction (sparse / retrieval)");
  _el["ra-k"]       = _show.addField("retrieval Top-k re-injected");
  _el["ra-label"]   = _show.addField("honesty label");

  _paintOverlay();
}

function _plainHtml() {
  const sp = S.sparseLR != null ? (S.sparseLR * 100).toFixed(0) + "%" : "loading…";
  const rt = S.retrLR   != null ? (S.retrLR   * 100).toFixed(0) + "%" : "loading…";
  const rc = S.recovery != null ? (S.recovery * 100).toFixed(0) + " points" : "loading…";
  return (
    "<b>What this means:</b> Picture reading a very long book but only being allowed to look at " +
    "the last few pages. If an important fact was mentioned early on, you simply cannot see it — " +
    "that is a sparse window, and here it recalls <b>" + sp + "</b> of the far-back facts. The " +
    "<b>retrieval</b> trick lets the model glance back and PULL IN the few early sentences that " +
    "best match the question, no matter how far back they are — so it now recalls <b>" + rt + "</b> " +
    "of those far facts, a recovery of about <b>" + rc + "</b>. It does this while still reading far " +
    "fewer tokens than looking at the whole book. This view is a <b>MODELED</b> deterministic " +
    "simulation of those read rules on a synthetic needle task, not a run of a real trained model.");
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "…";
}

function pct(v) { return typeof v === "number" ? (v * 100).toFixed(1) + "%" : "—"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  _set("ra-seqwin",  t || ((S.seqLen != null && S.window != null) ? (S.seqLen + " · " + S.window) : "—"));
  _set("ra-needles", t || ((S.nLongRange != null && S.nWindow != null) ? (S.nLongRange + " / " + S.nWindow) : "—"));
  _set("ra-fullLR",  t || pct(S.fullLR));
  _set("ra-sparse",  t || pct(S.sparseLR));
  _set("ra-edm",     t || pct(S.edmLR));
  _set("ra-retr",    t || pct(S.retrLR));
  _set("ra-recov",   t || (S.recovery != null ? "+" + pct(S.recovery) : "—"));
  _set("ra-vsedm",   t || (S.vsEdm != null ? "+" + pct(S.vsEdm) : "—"));
  _set("ra-attend",  t || ((S.attendSparse != null && S.attendRetr != null) ? (pct(S.attendSparse) + " / " + pct(S.attendRetr)) : "—"));
  _set("ra-k",       t || (S.retrievalK != null ? String(S.retrievalK) : "—"));
  // honesty label verbatim — never upgraded
  _set("ra-label", t || (S.label || "MODELED"));
  if (_show) { _show.setChip("ra", S.label || "MODELED", { text: "long-range recall" }); _show.refreshPlain(); }
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
  _spine = null; _winMesh = null; _query = null; _needle = [];
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.seqLen = S.window = S.nNeedles = S.retrievalK = S.dim = S.decay = null;
  S.nLongRange = S.nWindow = null;
  S.fullLR = S.sparseLR = S.edmLR = S.retrLR = S.recovery = S.vsEdm = null;
  S.attendSparse = S.attendRetr = S.perNeedle = null;
  S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
