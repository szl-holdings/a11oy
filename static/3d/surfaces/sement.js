// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/sement.js — SEMANTIC-ENTROPY / EFFECTIVE-RANK EPISTEMIC-UNCERTAINTY
// hallucination-detection organ for the holographic frontier ring.
//
// Renders two side-by-side "regime" pylons — a CONFIDENT regime and a CONFABULATING regime —
// driven by a live snapshot from /api/killinchu/v1/sement/estimate. For each regime the organ
// samples K candidate generations for one fixed prompt, clusters them into semantic-equivalence
// classes, and shows three bars: NAIVE (surface-string) entropy, SEMANTIC (meaning-cluster)
// entropy, and spectral EFFECTIVE RANK — plus a threshold-driven answer/abstain verdict. The
// honest signal it visualizes: semantic entropy AND effective rank both RISE on the confabulating
// regime while naive entropy can be misleadingly low. Honesty label "MODELED" is read VERBATIM
// from the JSON and displayed as-is; never upgraded.
//
// IMPORTANT — MODELED, NOT A REAL LLM:
//   This organ simulates the uncertainty-estimation METHOD on synthetic toy data. The
//   semantic-equivalence clustering is a HAND-SPECIFIED lookup table (real semantic entropy
//   uses a bidirectional-entailment model); the "hidden states" behind the effective rank are
//   SYNTHETIC seeded matrices. It demonstrates the ORDERING (uncertain > confident) that the
//   published methods exploit; it does NOT reproduce AUROC or benchmark numbers and makes no
//   claim about real-model calibration. This is stated plainly in the "what this means" copy
//   and echoed in the endpoint's own JSON payload (honest_note).
//
// Surface export shape (mirrors qhall.js / interpretability.js exactly):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all from live endpoint):
//   K                 — candidate generations sampled per regime
//   naive_entropy     — Shannon entropy over SURFACE strings (nats)
//   semantic_entropy  — Shannon entropy over MEANING clusters (nats)
//   effective_rank    — exp(entropy of normalized singular values) of synthetic hidden states
//   decision          — "answer" | "abstain" (threshold on semantic entropy)
//   n_clusters        — semantic-equivalence classes recovered
//   ordering_holds    — semantic entropy & effective rank both rise on confabulating
//
// LEADERS ADOPTED & CITED (clean-room; NOT claimed as SZL's own):
//   Farquhar, Kossen, Kuhn & Gal (2024) "Detecting hallucinations in large language models
//     using semantic entropy". Nature 630, 625-630. DOI 10.1038/s41586-024-07421-0.
//     https://www.nature.com/articles/s41586-024-07421-0
//   Wang, Wei, Yue & Sun (2025) "Revisiting Hallucination Detection with Effective
//     Rank-based Uncertainty". arXiv:2510.08389. https://arxiv.org/abs/2510.08389
//
// HONESTY LABELS: MODELED (simulation of the METHOD on synthetic toy data; hand-specified
//   clustering, synthetic hidden states, NO real LLM). Read verbatim from JSON.
// COLOURS: lattice-blue 0x5b8dee (confident regime / naive-entropy bar), violet-blue 0x8a6bff
//   (confabulating regime / semantic-entropy bar — data-viz only), proof-teal 0x3af4c8
//   (effective-rank accent), greys for dim/idle. Purple BANNED as UI/background.
// 0 RUNTIME CDN. Vendored three.js via page importmap (ctx.THREE).
// DOCTRINE v11: degrades gracefully (grey) on 404/error; honesty label still shown.
// This organ adds NOTHING to SZL's own locked-8 / Λ-Conjecture-1.

import { createShowcase } from "./_showcase.js";

const ID    = "sement";
const TITLE = "Semantic-Entropy · Effective-Rank Epistemic Uncertainty (live)";

// Endpoint is hosted on the dedicated killinchu Space (isolated compute), reached
// cross-origin (killinchu returns access-control-allow-origin for the flagship origin).
const EP = "https://szlholdings-killinchu.hf.space/api/killinchu/v1/sement/estimate?seed=42&K=40&n_clusters=5&threshold=0.6";

// data-viz hues — purple BANNED
const C_CONF   = 0x5b8dee;  // lattice-blue (confident regime / naive-entropy bar)
const C_CONFAB = 0x8a6bff;  // violet-blue (confabulating regime / semantic-entropy bar — data-viz only)
const C_ACCENT = 0x3af4c8;  // proof-teal accent (effective-rank bar + verdict ring)
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data / idle)
const C_GRID   = 0x1b3a44;  // floor / link colour

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;
let _plain = false;

// geometry handles — two regime clusters, each with three metric bars
let _bars = [];         // Array<THREE.Mesh> — 2 regimes x 3 metrics
let _rings = [];        // Array<THREE.Mesh> — one verdict ring per regime
const _MAX_BARS = 6;
const _pulse = new Float32Array(_MAX_BARS);
let _built = false;

// live state
const S = {
  label:      null,
  K:          null,   // K samples per regime
  threshold:  null,   // abstain/answer threshold (nats)
  ordering:   null,   // ordering_holds
  // per-regime metrics: index 0 = confident, 1 = confabulating
  reg: [
    { name: "confident",     naive: null, sem: null, effr: null, decision: null, nclus: null },
    { name: "confabulating", naive: null, sem: null, effr: null, decision: null, nclus: null },
  ],
  state:      "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _stage.camera.position.set(0, 7, 20);
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.0, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildBars();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(EP, 5000, _onEstimate, { badge: _badge, onState: (m) => { S.state = m.state; _paintOverlay(); _updateBars(); } }));

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

// Two regime clusters, each with three metric bars (naive / semantic / effective-rank),
// plus a verdict ring above each cluster. Heights are set from live data in _updateBars().
function _buildBars() {
  const THREE = _THREE;
  if (_built) return;
  _built = true;

  const barGeo = new THREE.BoxGeometry(0.9, 1.0, 0.9);
  const cols = [C_CONF, C_CONFAB, C_ACCENT]; // naive, semantic, effective-rank
  // regime cluster centres (confident left, confabulating right)
  const centres = [-5.0, 5.0];
  const spread = 1.4;

  _bars = [];
  for (let r = 0; r < 2; r++) {
    for (let m = 0; m < 3; m++) {
      const mat = new THREE.MeshStandardMaterial({
        color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.25, roughness: 0.55,
      });
      const mesh = new THREE.Mesh(barGeo, mat);
      const x = centres[r] + (m - 1) * spread;
      mesh.position.set(x, 0.5, 0);
      mesh.userData.baseCol = cols[m];
      mesh.userData.x = x;
      _group.add(mesh);
      _bars.push(mesh);
    }
  }

  // verdict rings, one above each regime cluster
  _rings = [];
  for (let r = 0; r < 2; r++) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(1.6, 0.05, 10, 48),
      new THREE.MeshStandardMaterial({ color: C_ACCENT, emissive: C_ACCENT, emissiveIntensity: 0.4, transparent: true, opacity: 0.5 }),
    );
    ring.position.set(centres[r], 6.4, 0);
    ring.rotation.x = Math.PI / 2;
    _group.add(ring);
    _rings.push(ring);
  }
}

// =============================================================================
// live data handler — reads label VERBATIM (top-level 'label' OR nested 'payload.label')
// =============================================================================
function _onEstimate(j) {
  const p = (j && typeof j.payload === "object" && j.payload) ? j.payload : j;
  const rawLabel = (p && p.label != null) ? p.label : (j && j.label != null ? j.label : "MODELED");
  S.label = String(rawLabel).toUpperCase();

  S.K         = typeof p.K              === "number"  ? p.K              : null;
  S.threshold = typeof p.threshold      === "number"  ? p.threshold      : null;
  S.ordering  = typeof p.ordering_holds === "boolean" ? p.ordering_holds : null;

  if (Array.isArray(p.regimes)) {
    p.regimes.forEach((rr) => {
      const idx = rr && rr.regime === "confabulating" ? 1 : (rr && rr.regime === "confident" ? 0 : -1);
      if (idx < 0) return;
      const slot = S.reg[idx];
      slot.naive    = typeof rr.naive_entropy    === "number" ? rr.naive_entropy    : null;
      slot.sem      = typeof rr.semantic_entropy === "number" ? rr.semantic_entropy : null;
      slot.effr     = typeof rr.effective_rank   === "number" ? rr.effective_rank   : null;
      slot.decision = typeof rr.decision         === "string" ? rr.decision         : null;
      slot.nclus    = typeof rr.n_clusters       === "number" ? rr.n_clusters       : null;
    });
  }

  _updateBars();
  _paintOverlay();
}

// =============================================================================
// geometry updater — bar heights from metrics, colours by regime/metric, verdict rings
// =============================================================================
function _updateBars() {
  const live = S.state === "live";
  // normalization so bars stay on-screen: entropies in nats (~0..2), eff-rank (~1..8)
  const entScale = 1.6;   // world units per nat
  const rankScale = 0.5;  // world units per rank unit
  for (let r = 0; r < 2; r++) {
    const slot = S.reg[r];
    const vals = [slot.naive, slot.sem, slot.effr];
    for (let m = 0; m < 3; m++) {
      const mesh = _bars[r * 3 + m];
      if (!mesh) continue;
      let v = vals[m];
      let h = 0.4;
      if (live && typeof v === "number") {
        h = (m === 2 ? v * rankScale : v * entScale);
        h = Math.max(0.4, Math.min(h, 9.0));
      }
      mesh.scale.y = h;
      mesh.position.y = h / 2;
      const col = live ? mesh.userData.baseCol : C_DIM;
      mesh.material.color.setHex(col);
      mesh.material.emissive.setHex(col);
      mesh.material.emissiveIntensity = live ? 0.35 : 0.12;
      if (live) _pulse[r * 3 + m] = 60;
    }
    // verdict ring: abstain burns violet-blue + bright; answer stays calm teal
    const ring = _rings[r];
    if (ring) {
      const abstain = slot.decision === "abstain";
      const rcol = live ? (abstain ? C_CONFAB : C_ACCENT) : C_DIM;
      ring.material.color.setHex(rcol);
      ring.material.emissive.setHex(rcol);
      ring.material.emissiveIntensity = live ? (abstain ? 0.85 : 0.3) : 0.12;
      ring.material.opacity = live ? 0.6 : 0.2;
      ring.scale.setScalar(live ? (abstain ? 1.15 : 0.85) : 0.8);
    }
  }
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.0001) * 0.12;
  _rings.forEach((ring) => { if (ring) ring.rotation.z += 0.004; });

  const live = S.state === "live";
  _bars.forEach((mesh, i) => {
    if (_pulse[i] > 0) {
      _pulse[i] -= 1;
      const f = _pulse[i] / 60;
      mesh.material.emissiveIntensity = Math.max(mesh.material.emissiveIntensity, 0.2 + 0.7 * f);
    }
    if (live) mesh.position.x = mesh.userData.x + Math.sin(t * 0.0011 + i) * 0.02;
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", badge: _badge,
    chips: [{ label: "MODELED", text: "semantic entropy", name: "lbl" }],
    legend: ["MODELED"],
  });
  const host = _show.body;

  const sub = document.createElement("div");
  sub.style.cssText = "color:#9fb1bf;font-size:11px;line-height:1.55";
  sub.innerHTML =
    'For one prompt we sample <b>K</b> candidate answers, group answers that <b>mean the same ' +
    'thing</b> into semantic clusters, and score the <b>entropy</b> over those clusters ' +
    '(<b>semantic entropy</b>). We compare a <b>confident</b> regime against a ' +
    '<b>confabulating</b> one, and add the 2025 <b>spectral effective rank</b> of the ' +
    'hidden states. Semantic entropy and effective rank both <b>rise</b> when the model ' +
    'confabulates \\u2014 even when naive surface entropy stays misleadingly low \\u2014 so we ' +
    '<b>abstain</b>. Honesty label <b>MODELED</b> \\u2014 a simulation of the method on ' +
    'synthetic toy data, <b>not</b> a real LLM. 0 runtime CDN.';
  host.appendChild(sub);

  const card = document.createElement("div");
  card.style.cssText = "background:#0a1117;border:1px solid #1d2a36;border-radius:9px;padding:9px 10px;display:flex;flex-direction:column;gap:6px";

  const chead = document.createElement("div");
  chead.style.cssText = "display:flex;align-items:center;gap:8px;flex-wrap:wrap";
  const dot = document.createElement("span");
  dot.style.cssText = "width:9px;height:9px;border-radius:50%;background:#5b8dee;box-shadow:0 0 7px #5b8dee";
  const nm = document.createElement("b");
  nm.style.cssText = "font-size:12px;color:#5b8dee;letter-spacing:.3px";
  nm.textContent = "sement \\u00b7 epistemic uncertainty";
  chead.appendChild(dot); chead.appendChild(nm);
  card.appendChild(chead);

  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:1fr;gap:4px";

  function kpiRow(id, label) {
    const r = document.createElement("div");
    r.style.cssText = "display:flex;justify-content:space-between;gap:10px;font-size:11px";
    const l = document.createElement("span"); l.style.cssText = "color:#9fb1bf"; l.textContent = label;
    const v = document.createElement("b");
    v.id = id;
    v.style.cssText = "font-variant-numeric:tabular-nums;color:#eef3f6;text-align:right;max-width:60%";
    v.textContent = "\\u2014";
    _el[id] = v;
    r.appendChild(l); r.appendChild(v); return r;
  }

  grid.appendChild(kpiRow("se-K",       "candidate generations K"));
  grid.appendChild(kpiRow("se-thr",     "abstain threshold (nats)"));
  grid.appendChild(kpiRow("se-cn",      "confident \\u00b7 naive / semantic H"));
  grid.appendChild(kpiRow("se-cr",      "confident \\u00b7 effective rank"));
  grid.appendChild(kpiRow("se-cd",      "confident \\u00b7 decision"));
  grid.appendChild(kpiRow("se-bn",      "confabulating \\u00b7 naive / semantic H"));
  grid.appendChild(kpiRow("se-br",      "confabulating \\u00b7 effective rank"));
  grid.appendChild(kpiRow("se-bd",      "confabulating \\u00b7 decision"));
  grid.appendChild(kpiRow("se-ord",     "ordering holds (uncertain > confident)"));
  card.appendChild(grid);

  const fn = document.createElement("div");
  fn.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5";
  fn.textContent = "Farquhar, Kossen, Kuhn & Gal, Nature 2024 (DOI 10.1038/s41586-024-07421-0) \\u00b7 " +
    "Wang, Wei, Yue & Sun arXiv:2510.08389 (2025) \\u00b7 MODELED \\u00b7 hand-specified clustering, " +
    "synthetic hidden states, no real LLM \\u00b7 not claimed-as.";
  card.appendChild(fn);
  host.appendChild(card);

  const pl = document.createElement("button");
  pl.textContent = "\\u25d1 what this means";
  pl.title = "Toggle plain-language explanation for investors & consumers.";
  pl.style.cssText = "font:11px ui-monospace,monospace;padding:5px 11px;border-radius:7px;border:1px solid #3af4c8;background:#08140f;color:#3af4c8;cursor:pointer;width:fit-content";
  pl.addEventListener("click", () => {
    _plain = !_plain;
    pl.style.background = _plain ? "#0f2a20" : "#08140f";
    _applyPlain();
  });
  host.appendChild(pl);

  const pd = document.createElement("div");
  pd.id = "sement-plain";
  pd.style.cssText = "font-size:10.5px;color:#c9d6df;line-height:1.55;border:1px dashed #26333f;border-radius:7px;padding:7px 9px;display:none";
  _el["plain"] = pd;
  host.appendChild(pd);

  _paintOverlay();
}

function _applyPlain() {
  const pd = _el["plain"];
  if (!pd) return;
  pd.style.display = _plain ? "block" : "none";
  if (!_plain) return;
  const K   = S.K != null ? String(S.K) : "loading\\u2026";
  const conf = S.reg[0], bad = S.reg[1];
  const cSem = conf.sem != null ? conf.sem.toFixed(3) : "loading\\u2026";
  const bSem = bad.sem  != null ? bad.sem.toFixed(3)  : "loading\\u2026";
  const bNaive = bad.naive != null ? bad.naive.toFixed(3) : "loading\\u2026";
  const bRank = bad.effr != null ? bad.effr.toFixed(2) : "loading\\u2026";
  const bDec  = bad.decision || "loading\\u2026";
  pd.innerHTML =
    "<b>What this means:</b> We ask the model the same question <b>" + K + "</b> times and collect " +
    "its candidate answers. We group answers that <b>mean the same thing</b> together, then measure " +
    "how scattered the meanings are (<b>semantic entropy</b>). When the model is <b>confident</b>, " +
    "almost every answer means the same thing, so semantic entropy is low (here <b>" + cSem + "</b>) " +
    "and we <b>answer</b>. When the model is <b>confabulating</b>, its answers scatter across many " +
    "contradictory meanings, so semantic entropy jumps to <b>" + bSem + "</b> and a second, spectral " +
    "signal \\u2014 the <b>effective rank</b> of its hidden states (\\u2248 <b>" + bRank + "</b>) \\u2014 " +
    "rises too, so we <b>" + bDec + "</b>. Crucially, plain surface-word entropy on the confabulating " +
    "case can look misleadingly modest (\\u2248 <b>" + bNaive + "</b>), which is exactly why " +
    "meaning-level and spectral uncertainty beat surface uncertainty." +
    "<br><br><b>Important honesty note:</b> this is a <b>MODELED</b> toy simulation of the " +
    "<b>uncertainty estimator</b>, <b>not a real language model</b>. The step that decides which " +
    "answers \\u201cmean the same thing\\u201d is a <b>hand-specified lookup table</b> (real semantic " +
    "entropy uses a trained entailment model), and the <b>hidden states are synthetic seeded " +
    "matrices</b>. It faithfully demonstrates the <b>ordering</b> (uncertain &gt; confident) that the " +
    "published methods exploit, but it does <b>not</b> reproduce the Nature paper\\u2019s AUROC or the " +
    "effective-rank paper\\u2019s benchmark numbers, and makes no claim about real-model calibration " +
    "(Farquhar et al., Nature 2024; Wang et al., arXiv:2510.08389, 2025).";
}

function _tok(s) {
  if (s === "live") return null;
  if (s === "missing") return "NO-LIVE-DATA";
  if (s === "degraded") return "DEGRADED";
  if (s === "error") return "OFFLINE";
  return "\\u2026";
}

function fx(v, d) { return typeof v === "number" ? v.toFixed(d) : "\\u2014"; }
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paintOverlay() {
  const t = _tok(S.state);
  const conf = S.reg[0], bad = S.reg[1];
  _set("se-K",   t || (S.K != null ? String(S.K) : "\\u2014"));
  _set("se-thr", t || fx(S.threshold, 2));
  _set("se-cn",  t || (conf.naive != null && conf.sem != null ? fx(conf.naive, 3) + " / " + fx(conf.sem, 3) : "\\u2014"));
  _set("se-cr",  t || fx(conf.effr, 3));
  _set("se-cd",  t || (conf.decision ? conf.decision.toUpperCase() : "\\u2014"));
  _set("se-bn",  t || (bad.naive != null && bad.sem != null ? fx(bad.naive, 3) + " / " + fx(bad.sem, 3) : "\\u2014"));
  _set("se-br",  t || fx(bad.effr, 3));
  _set("se-bd",  t || (bad.decision ? bad.decision.toUpperCase() : "\\u2014"));
  _set("se-ord", t || (S.ordering == null ? "\\u2014" : (S.ordering ? "YES \\u2014 semantic H & eff-rank both rise" : "no")));
  // honesty label verbatim — never upgraded
  if (_show) _show.setChip("lbl", S.label || "MODELED", { text: "semantic entropy" });
  if (_plain) _applyPlain();
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
  _bars = []; _rings = [];
  _built = false;
  _el = {}; _badge = null; _plain = false; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.K = S.threshold = S.ordering = null;
  S.reg[0] = { name: "confident",     naive: null, sem: null, effr: null, decision: null, nclus: null };
  S.reg[1] = { name: "confabulating", naive: null, sem: null, effr: null, decision: null, nclus: null };
  S.state = "init";
  _pulse.fill(0);
}

export default { id: ID, title: TITLE, endpoints: [EP], mount, unmount };
