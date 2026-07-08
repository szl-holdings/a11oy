// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/brainwatch.js — BRAIN WATCH. A governed honesty-posture DRIFT monitor
// for the knowledge graph. It reads the CURRENT posture snapshot from the backend
// (GET /brain/watch) — label distribution, orphan share, community fragmentation,
// salience concentration — and renders it as a lattice of posture bars. Snapshot
// numbers are MEASURED from this live read; a drift verdict is MODELED and only
// exists once a PRIOR snapshot is compared (POST /brain/watch/compare).
//
// HONESTY (Doctrine v11 — labels read VERBATIM, never upgraded):
//   * every snapshot metric is MEASURED from the live graph; shown verbatim.
//   * with no prior the verdict is honestly BASELINE-ONLY — NO trend is fabricated.
//   * a drift comparison is MODELED; a DEGRADED posture is never shown as STABLE.
//   * Λ = Conjecture 1 → GREY, never green. locked-proven = exactly 8.
//   * palette: lattice-blue 0x5b8dee · violet-blue 0x8a6bff · proof-teal 0x3af4c8
//     · greys. PURPLE BANNED. 0 runtime CDN (three.js via ctx.THREE).
//
// Surface export shape: export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }

import { createShowcase } from "./_showcase.js";

const ID    = "brainwatch";
const TITLE = "Brain Watch — honesty-posture drift";

// same-origin a11oy endpoints (canonical a-11-oy.com in prod; relative here)
const EP_WATCH   = "/api/a11oy/v1/brain/watch";
const EP_COMPARE = "/api/a11oy/v1/brain/watch/compare";

// palette (doctrine v11) — NO purple
const C_OK     = 0x3af4c8;  // proof-teal — healthy posture bar
const C_MID    = 0x5b8dee;  // lattice-blue — neutral posture bar
const C_WARN   = 0x8a6bff;  // violet-blue — elevated (attention) bar
const C_CONJ   = 0x5a6570;  // GREY — conjecture / degraded floor — never green
const C_BASE   = 0x1b3a44;  // dim base grid

const MAX_BARS = 24;

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _badge = null, _frameReg = false, _t0 = 0, _inFlight = null;

// scene objects
let _boxGeo = null;
let _meshes = [];   // posture-metric bar meshes

const S = {
  label: "MEASURED", state: "idle",
  verdict: "BASELINE-ONLY", verdictReason: null,
  snapshot: null,            // the last MEASURED snapshot (also the next prior)
  metrics: null,             // convenience alias to snapshot.metrics
  bars: [],                  // [{key, value, color}] rendered bars
  drift: null,               // MODELED drift block (null until a compare)
  priorProvided: false,
  note: null,
};

// -------------------------------------------------------------------------- //
// mount
// -------------------------------------------------------------------------- //
function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  _boxGeo = new _THREE.BoxGeometry(1, 1, 1);

  _buildOverlay(ctx);
  if (ctx.live && ctx.live.createBadge) {
    _badge = ctx.live.createBadge();
    if (_show) _show.setBadge(_badge);
  }

  if (_show) {
    _show.attachSceneLabels({
      objects: () => _meshes,
      text: (o) => (o.userData && o.userData.bar && o.userData.bar.key) || "",
      weight: (o) => (o.userData && o.userData.bar && o.userData.bar.value) || 0,
      topN: 8, hover: true, fadeNear: 9, fadeFar: 70,
    });
  }

  _fetchWatch();

  if (!_frameReg && _stage.onFrame) { _stage.onFrame(_animate); _frameReg = true; }
}

function _readLabel(j, fallback) {
  const lbl = (j && j.label != null) ? j.label : (fallback || "MEASURED");
  return String(lbl).toUpperCase();
}

function _setBadge(state) {
  S.state = state;
  if (_badge && _badge.set) { try { _badge.set(state); } catch (_) {} }
}

// -------------------------------------------------------------------------- //
// data — GET current snapshot (BASELINE-ONLY); mints nothing.
// -------------------------------------------------------------------------- //
function _fetchWatch() {
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const ctrl = ("AbortController" in window) ? new AbortController() : null;
  if (_inFlight && _inFlight.abort) { try { _inFlight.abort(); } catch (_) {} }
  _inFlight = ctrl;

  fetch(EP_WATCH, { headers: { accept: "application/json" },
                    signal: ctrl ? ctrl.signal : undefined })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => { _inFlight = null; _onWatch(j); })
    .catch((e) => {
      if (e && e.name === "AbortError") return;
      _inFlight = null;
      S.state = "error"; _setBadge("error"); _paintOverlay();
    });
}

// POST the last snapshot back as the PRIOR → MODELED drift verdict.
function _compareAgainstLast() {
  if (!S.snapshot) return;
  _setBadge("loading");
  S.state = "loading";
  _paintOverlay();

  const body = JSON.stringify({ prior: S.snapshot });
  fetch(EP_COMPARE, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body,
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("http " + r.status))))
    .then((j) => _onCompare(j))
    .catch(() => { S.state = "error"; _setBadge("error"); _paintOverlay(); });
}

function _onWatch(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  const snap = j.snapshot || j;
  S.label = _readLabel(snap, "MEASURED");
  S.snapshot = snap;
  S.metrics = snap.metrics || null;
  S.verdict = String(j.verdict || "BASELINE-ONLY").toUpperCase();
  S.verdictReason = j.verdict_reason || null;
  S.drift = null;
  S.priorProvided = false;
  S.note = (snap && snap.measurement) || null;
  S.bars = _barsFromMetrics(S.metrics);
  S.state = "live"; _setBadge("live");
  _rebuild(); _paintOverlay();
}

function _onCompare(j) {
  if (!j) { S.state = "error"; _setBadge("error"); _paintOverlay(); return; }
  // the compare response carries the fresh CURRENT snapshot + a MODELED drift.
  const cur = j.current || S.snapshot;
  S.label = _readLabel(cur, "MEASURED");
  S.snapshot = cur;
  S.metrics = (cur && cur.metrics) || S.metrics;
  S.verdict = String(j.verdict || "BASELINE-ONLY").toUpperCase();
  S.verdictReason = j.verdict_reason || null;
  S.drift = j.drift || null;   // MODELED; null when BASELINE-ONLY
  S.priorProvided = !!j.prior_provided;
  S.note = (j.drift && j.drift.note) || (cur && cur.measurement) || null;
  S.bars = _barsFromMetrics(S.metrics);
  S.state = "live"; _setBadge("live");
  _rebuild(); _paintOverlay();
}

// Pick the posture metrics that live in [0,1] and render them as bars.
function _barsFromMetrics(m) {
  if (!m) return [];
  const keys = [
    "unavailable_share", "orphan_share", "community_fragmentation",
    "largest_community_share", "singleton_community_share",
    "salience_gini", "salience_top1_share", "salience_top5_share",
  ];
  const bars = [];
  keys.forEach((k) => {
    const v = m[k];
    if (typeof v === "number" && isFinite(v)) {
      bars.push({ key: k, value: Math.max(0, Math.min(1, v)), color: _barColor(k, v) });
    }
  });
  return bars.slice(0, MAX_BARS);
}

// Higher UNAVAILABLE/orphan share is a worse honesty posture → GREY warning floor.
function _barColor(key, v) {
  if (key === "unavailable_share") return v > 0.02 ? C_CONJ : C_OK;
  if (key === "orphan_share") return v > 0.5 ? C_WARN : C_MID;
  if (key === "salience_gini" || key === "salience_top1_share") {
    return v > 0.8 ? C_WARN : C_MID;   // extreme concentration = attention
  }
  return C_MID;
}

// -------------------------------------------------------------------------- //
// build
// -------------------------------------------------------------------------- //
function _rebuild() {
  if (!_group) return;
  _clearScene();
  const bars = S.bars || [];
  if (!bars.length) return;
  const n = bars.length;
  const spread = 12.0;
  bars.forEach((bar, i) => {
    const h = 0.4 + 8.5 * bar.value;             // bar height ∝ metric value
    const mat = new _THREE.MeshStandardMaterial({
      color: bar.color, emissive: bar.color, emissiveIntensity: 0.22,
      metalness: 0.12, roughness: 0.5, transparent: true, opacity: 0.95,
    });
    const mesh = new _THREE.Mesh(_boxGeo, mat);
    mesh.scale.set(0.7, h, 0.7);
    const x = (n === 1) ? 0 : (-spread / 2 + spread * (i / (n - 1)));
    mesh.position.set(x, h / 2 - 3.0, 0);
    mesh.userData = { bar, baseGlow: 0.22 };
    _meshes.push(mesh);
    _group.add(mesh);
  });
}

function _clearScene() {
  _meshes.forEach((m) => {
    if (m.material && m.material.dispose) m.material.dispose();
    _group.remove(m);
  });
  _meshes = [];
}

// -------------------------------------------------------------------------- //
// animation: gentle rotation + soft breathing glow
// -------------------------------------------------------------------------- //
function _animate() {
  if (!_group) return;
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const t = (now - _t0) / 1000;
  _group.rotation.y = Math.sin(t * 0.08) * 0.4;
  const pulse = 0.5 + 0.5 * Math.sin(t * 1.5);
  _meshes.forEach((m) => {
    if (!m.material) return;
    const base = m.userData.baseGlow || 0.22;
    m.material.emissiveIntensity = base * (0.8 + 0.3 * pulse);
  });
}

// -------------------------------------------------------------------------- //
// overlay (shared showcase helper)
// -------------------------------------------------------------------------- //
const _el = {};

function _buildOverlay(ctx) {
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#5b8dee", startExpanded: true,
    chips: [{ label: "MEASURED", text: "snapshot", name: "src" }],
    legend: ["MEASURED", "MODELED", "DEGRADED", "UNAVAILABLE"],
    description:
      "<b>Watch the knowledge graph's honesty posture.</b> The server takes a " +
      "deterministic snapshot of the live brain graph — the distribution of honesty " +
      "<b>labels</b> its nodes carry (read verbatim), the share of <b>orphan</b> nodes " +
      "(degree ≤ 1), how <b>fragmented</b> the communities are, and how <b>concentrated</b> " +
      "the PageRank salience is. Each of those is <b>MEASURED</b> from this read and shown " +
      "as a bar. Press <b>compare</b> to POST the current snapshot back as a prior and get a " +
      "<b>MODELED</b> drift verdict: STABLE / DRIFTING / DEGRADED. With no prior it is honestly " +
      "<b>BASELINE-ONLY</b> — no trend is fabricated.",
    citations:
      "Snapshot is LIVE from /api/a11oy/v1/brain/watch (pure read — no signing on GET) over the " +
      "same honest graph as /brain/graph. Drift is MODELED via POST /brain/watch/compare, which " +
      "mints an unsigned SHA-256 content digest (receipt-on-write). Λ = Conjecture 1 (grey, never " +
      "proven green); nothing here touches the locked-8.",
    plain: { html: _plainHtml },
  });

  // compare button (POST last snapshot as prior)
  const wrap = document.createElement("div");
  wrap.style.cssText = "display:flex;gap:6px;align-items:center";
  const cmpBtn = document.createElement("button");
  cmpBtn.type = "button";
  cmpBtn.textContent = "compare vs current";
  cmpBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #3af4c8;background:#08201a;color:#3af4c8";
  cmpBtn.addEventListener("click", () => _compareAgainstLast());
  const refBtn = document.createElement("button");
  refBtn.type = "button";
  refBtn.textContent = "refresh snapshot";
  refBtn.style.cssText =
    "font:600 12px ui-monospace,Menlo,monospace;padding:7px 13px;border-radius:8px;" +
    "cursor:pointer;border:1px solid #1c2836;background:#0a1117;color:#c9d6df";
  refBtn.addEventListener("click", () => _fetchWatch());
  wrap.appendChild(cmpBtn); wrap.appendChild(refBtn);
  _show.appendBody(wrap);

  // KPI rows
  _el.verdict   = _show.addField("Drift verdict");
  _el.nodes     = _show.addField("Nodes / links");
  _el.unavail   = _show.addField("Unavailable share");
  _el.orphan    = _show.addField("Orphan share (deg≤1)");
  _el.comm      = _show.addField("Communities");
  _el.frag      = _show.addField("Fragmentation");
  _el.gini      = _show.addField("Salience Gini");
  _el.top5      = _show.addField("Top-5 salience share");

  // label distribution list
  _el.labels = document.createElement("div");
  _el.labels.style.cssText =
    "display:flex;flex-direction:column;gap:3px;font-size:10.5px;color:#9fb1bf";
  _show.appendBody(_el.labels);

  // honest note (verbatim from the endpoint)
  _el.note = document.createElement("div");
  _el.note.style.cssText = "font-size:9.5px;color:#6b7a86;line-height:1.5;margin-top:2px";
  _show.appendBody(_el.note);
}

function _fmt(n) { return (n == null) ? "—" : Number(n).toLocaleString("en-US"); }
function _pct(v) { return (typeof v === "number") ? (100 * v).toFixed(1) + "%" : "—"; }

function _paintOverlay() {
  if (!_show) return;
  _show.setChip("src", S.label || "MEASURED", { text: "snapshot" });

  const set = (k, v) => { if (_el[k]) _el[k].textContent = v; };
  const m = S.metrics || {};
  const loading = S.state === "loading";

  set("verdict", loading ? "loading…"
      : (S.verdict + (S.drift ? " · MODELED" : (S.priorProvided ? "" : " · no prior"))));
  set("nodes", loading ? "loading…"
      : (S.snapshot ? (_fmt(S.snapshot.node_count) + " / " + _fmt(S.snapshot.link_count)) : "—"));
  set("unavail", loading ? "…" : _pct(m.unavailable_share));
  set("orphan", loading ? "…" : _pct(m.orphan_share));
  set("comm", loading ? "…"
      : (m.community_count != null ? (_fmt(m.community_count) + " · " + (m.community_algo || "?")) : "—"));
  set("frag", loading ? "…" : _pct(m.community_fragmentation));
  set("gini", loading ? "…" : (typeof m.salience_gini === "number" ? m.salience_gini.toFixed(3) : "—"));
  set("top5", loading ? "…" : _pct(m.salience_top5_share));

  // label distribution (verbatim honesty labels + counts)
  if (_el.labels) {
    _el.labels.textContent = "";
    const dist = (m && m.label_distribution) || {};
    Object.keys(dist).forEach((lbl) => {
      const line = document.createElement("div");
      line.style.cssText = "white-space:nowrap;overflow:hidden;text-overflow:ellipsis";
      line.textContent = "· " + lbl + " — " + _fmt(dist[lbl]);
      _el.labels.appendChild(line);
    });
  }

  if (_el.note) {
    let note = S.note || "";
    if (S.state === "error") note = "watch error — the brain-watch API did not respond.";
    else if (S.verdictReason) note = S.verdictReason + (note ? "  " + note : "");
    _el.note.textContent = note;
  }

  if (_show.refreshPlain) _show.refreshPlain();
}

function _plainHtml() {
  return (
    "This is a health check for our estate's <b>brain</b>. It takes a snapshot of the knowledge " +
    "graph and measures things like: how much of it is marked <b>UNAVAILABLE</b>, how many " +
    "nodes are <b>orphans</b> (barely connected to anything), how broken-up the clusters are, and " +
    "whether a few nodes hog all the importance. Those numbers are <b>MEASURED</b> — read straight " +
    "off the live graph. If you give it an earlier snapshot to compare against, it tells you " +
    "whether the posture is <b>STABLE</b>, <b>DRIFTING</b>, or <b>DEGRADED</b> — but that trend is " +
    "a <b>MODELED</b> comparison, and with no earlier snapshot it honestly says " +
    "<b>BASELINE-ONLY</b> instead of inventing a trend. Label <b>" + (S.label || "MEASURED") + "</b>."
  );
}

// -------------------------------------------------------------------------- //
// unmount
// -------------------------------------------------------------------------- //
function unmount() {
  try { if (_inFlight && _inFlight.abort) _inFlight.abort(); } catch (_) {}
  _inFlight = null;
  try { if (_show) _show.destroy(); } catch (_) {}
  try { _clearScene(); } catch (_) {}
  try { if (_boxGeo) _boxGeo.dispose(); } catch (_) {}
  try { if (_group && _stage) _stage.scene.remove(_group); } catch (_) {}
  _boxGeo = null;
  _group = _show = _badge = null;
  Object.keys(_el).forEach((k) => delete _el[k]);
  _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = "MEASURED"; S.state = "idle";
  S.verdict = "BASELINE-ONLY"; S.verdictReason = null;
  S.snapshot = null; S.metrics = null; S.bars = []; S.drift = null;
  S.priorProvided = false; S.note = null;
}

export default { id: ID, title: TITLE, endpoints: [EP_WATCH, EP_COMPARE], mount, unmount };
