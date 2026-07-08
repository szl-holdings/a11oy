// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/leaders.js — FRONTIER MODELS & AI LEADERS organ for the holographic estate.
//
// A live "frontier landscape observatory": the real, public OpenRouter model catalog
// (every model the aggregator currently serves) rendered as a ring of pillars — one per
// LAB (provider) — around a pulsing frontier core, with the widest-context individual
// models orbiting as satellites. 100% LIVE MEASURED data, pulled same-origin from the
// a11oy deva frontier feed. Nothing here is faked: no invented benchmark, no made-up
// ranking — only the catalog's own published context windows, prices, and lab counts.
//
// Surface export shape (mirrors finance.js / evalarena.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all live, same-origin):
//   /api/a11oy/v1/deva/frontier/models -> openrouter.value.labs[]   {lab, count, maxCtx, free}
//                                         openrouter.value.models[]  {id, name, lab, ctx,
//                                                                      price_prompt, price_completion, modality}
//                                         openrouter.value.total
//
// VISUAL ENCODING (direct read of measured values; the only transform is log-normalization
// for scale, which is a DISPLAY transform — never a model):
//   * each LAB = a pillar on a ring. pillar HEIGHT = log(max context window that lab
//     publishes), normalized; a bead rides up the pillar to the lab's OPEN share
//     (free-priced models / total models); pillar hue lerps lattice-blue (mostly paid)
//     -> proof-teal (mostly open/free).
//   * widest-context MODELS = satellites orbiting the core, size = log(context window),
//     colour proof-teal if the model is free-priced else gold-amber (paid). hover shows
//     the model name, its context window, and live prompt price.
//   * center = proof-teal wireframe "frontier core" that pulses with the total catalog size.
//
// HONESTY: MEASURED (real live observations from the public OpenRouter model catalog).
//   Degrades to NO-LIVE-DATA (grey) on 404 / offline; never fabricates a model or price.
//   Context windows and prices are as PUBLISHED by each provider; informational only.
// COLOURS: proof-teal 0x3af4c8, lattice-blue 0x5b8dee, gold-amber 0xd7b96b (paid), greys.
//   Purple BANNED as UI/background. 0 RUNTIME CDN. Vendored three.js via page importmap.
// CITATIONS: OpenRouter openrouter.ai/api/v1/models — public live model catalog.

import { createShowcase } from "./_showcase.js";

const ID    = "leaders";
const TITLE = "Frontier Models \u00b7 Live AI Leaders (OpenRouter)";

const MODELS_EP = "/api/a11oy/v1/deva/frontier/models?limit=24";

// palette — purple BANNED
const C_PAID   = 0xd7b96b;  // gold-amber   (paid model / mostly-paid lab)
const C_OPEN   = 0x3af4c8;  // proof-teal   (free / open model / mostly-open lab)
const C_LO     = 0x5b8dee;  // lattice-blue (low open-share)
const C_HI     = 0x3af4c8;  // proof-teal   (high open-share)
const C_CORE   = 0x3af4c8;  // proof-teal   (frontier core)
const C_PILLAR = 0x24506a;  // dim pillar body
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;

const RING_R   = 9.5;   // lab ring radius
const MAXL     = 16;    // lab pillar slots
const ORBIT_R  = 4.6;   // model orbit radius
const MAXM     = 8;     // model satellite slots
const PIL_MAXH = 6.5;   // tallest pillar (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _core = null;
let _pillars = [];   // Array<{ grp, body, bead, lab }>
let _sats = [];      // Array<{ mesh, model }>

// live state
const S = {
  label: null, labs: null, models: null, total: null, state: "init",
};

// =============================================================================
// mount(ctx)
// =============================================================================
export function mount(ctx) {
  _ctx = ctx; _stage = ctx.stage; _THREE = ctx.THREE;
  _group = new _THREE.Group();
  _stage.scene.add(_group);
  try { _stage.camera.position.set(0, 10, 27); } catch (_) {}
  try { if (_stage.controls && _stage.controls.target) { _stage.controls.target.set(0, 2.2, 0); _stage.controls.update(); } } catch (_) {}
  try { _stage.setBloom(true); } catch (_) {}

  _buildFloor();
  _buildCore();
  _buildPillars();
  _buildSats();

  if (!_frameReg) { _stage.onFrame(_onFrame); _frameReg = true; }

  _badge = ctx.live.createBadge();
  _polls.push(ctx.live.poll(MODELS_EP, 60000, _onModels, {
    badge: _badge, onState: (m) => { S.state = m.state; _layout(); _layoutSats(); _paint(); },
  }));

  _buildOverlay();
  return { id: ID, started: true };
}

// =============================================================================
// builders
// =============================================================================
function _buildFloor() {
  const THREE = _THREE;
  const grid = new THREE.GridHelper(48, 48, C_GRID, 0x0f2027);
  grid.material.opacity = 0.16; grid.material.transparent = true; grid.position.y = -0.01;
  _group.add(grid);
}

function _buildCore() {
  const THREE = _THREE;
  _core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.7, 1),
    new THREE.MeshStandardMaterial({ color: C_CORE, emissive: C_CORE, emissiveIntensity: 0.35, wireframe: true, transparent: true, opacity: 0.55 }),
  );
  _core.position.set(0, 2.2, 0);
  _group.add(_core);
}

function _buildPillars() {
  const THREE = _THREE;
  const bodyGeo = new THREE.CylinderGeometry(0.16, 0.20, 1, 14);
  const beadGeo = new THREE.SphereGeometry(0.26, 16, 12);
  _pillars = [];
  for (let i = 0; i < MAXL; i++) {
    const a = (i / MAXL) * Math.PI * 2;
    const x = Math.cos(a) * RING_R, z = Math.sin(a) * RING_R;
    const grp = new THREE.Group();
    grp.position.set(x, 0, z);

    const body = new THREE.Mesh(bodyGeo, new THREE.MeshStandardMaterial({
      color: C_PILLAR, emissive: C_PILLAR, emissiveIntensity: 0.12, metalness: 0.3, roughness: 0.5,
    }));
    body.scale.y = 0.4; body.position.y = 0.2;
    body.userData.label = "";
    grp.add(body);

    const bead = new THREE.Mesh(beadGeo, new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.2, roughness: 0.4,
    }));
    bead.position.y = 0.4; bead.visible = false;
    grp.add(bead);

    _group.add(grp);
    _pillars.push({ grp, body, bead, lab: null });
  }
}

function _buildSats() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.34, 18, 14);
  _sats = [];
  for (let i = 0; i < MAXM; i++) {
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.35, roughness: 0.35,
    }));
    mesh.position.set(0, 2.2, 0);
    mesh.visible = false;
    mesh.userData.label = "";
    _group.add(mesh);
    _sats.push({ mesh, model: null });
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onModels(j, meta) {
  S.label = (_ctx.live.readHonestyLabel(j) || "MEASURED").toUpperCase();
  const or = (j && j.openrouter && j.openrouter.value) || null;
  S.labs   = (or && Array.isArray(or.labs))   ? or.labs   : null;
  S.models = (or && Array.isArray(or.models)) ? or.models : null;
  S.total  = (or && typeof or.total === "number") ? or.total : null;
  // An HTTP-200 can still carry a null per-source value (upstream outage). Honestly
  // downgrade to DEGRADED rather than claim "live" while showing dashes.
  S.state = (S.labs != null && !(meta && meta.degraded)) ? "live" : "degraded";
  _layout(); _layoutSats(); _paint();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _lerpHex(c0, c1, t) {
  const a = new _THREE.Color(c0), b = new _THREE.Color(c1);
  return a.lerp(b, Math.max(0, Math.min(1, t)));
}

function _layout() {
  const live = S.state === "live";
  const labs = (S.labs || []).slice(0, MAXL);

  // log-normalize max context window across the visible labs for pillar heights
  const cx = labs.map((l) => Math.log10(Math.max(1, num(l.maxCtx))));
  const cMin = cx.length ? Math.min(...cx) : 0;
  const cMax = cx.length ? Math.max(...cx) : 1;
  const cSpan = Math.max(cMax - cMin, 1e-6);

  _pillars.forEach((p, i) => {
    const l = labs[i] || null;
    p.lab = l;
    if (!l || !live) {
      p.body.material.color.setHex(C_PILLAR);
      p.body.material.emissive.setHex(live ? C_PILLAR : C_DIM);
      p.body.material.emissiveIntensity = 0.1;
      p.body.scale.y = 0.4; p.body.position.y = 0.2;
      p.bead.visible = false;
      p.body.userData.label = "";
      return;
    }
    const h = 0.8 + PIL_MAXH * ((Math.log10(Math.max(1, num(l.maxCtx))) - cMin) / cSpan);
    p.body.scale.y = h; p.body.position.y = h / 2;

    const open = openShare(l);
    const col = _lerpHex(C_LO, C_HI, open);
    p.body.material.color.copy(col);
    p.body.material.emissive.copy(col);
    p.body.material.emissiveIntensity = 0.22 + 0.5 * open;

    p.bead.visible = true;
    p.bead.position.y = 0.2 + open * h;   // bead rides up to the open (free) share
    p.bead.material.color.copy(col);
    p.bead.material.emissive.copy(col);
    p.bead.material.emissiveIntensity = 0.85;

    p.body.userData.label = labShort(l.lab) + "  \u00b7  " + num(l.count) + " models  \u00b7  " + fmtCtx(num(l.maxCtx)) + " ctx";
  });
}

function _layoutSats() {
  const live = S.state === "live";
  const models = topModels().slice(0, MAXM);
  const ctxs = models.map((m) => Math.log10(Math.max(1, num(m.ctx))));
  const mMin = ctxs.length ? Math.min(...ctxs) : 0;
  const mMax = ctxs.length ? Math.max(...ctxs) : 1;
  const mSpan = Math.max(mMax - mMin, 1e-6);

  _sats.forEach((s, i) => {
    const m = models[i] || null;
    s.model = m;
    if (!m || !live) { s.mesh.visible = false; s.mesh.userData.label = ""; return; }
    s.mesh.visible = true;
    const scale = 0.55 + 1.0 * ((Math.log10(Math.max(1, num(m.ctx))) - mMin) / mSpan);
    s.mesh.scale.setScalar(scale);
    const free = isFree(m);
    const col = free ? C_OPEN : C_PAID;
    s.mesh.material.color.setHex(col);
    s.mesh.material.emissive.setHex(col);
    s.mesh.material.emissiveIntensity = 0.4;
    s.mesh.userData.label = modShort(m) + "  " + fmtCtx(num(m.ctx)) + "  " + priceTxt(m);
  });
}

// =============================================================================
// per-frame animation
// =============================================================================
function _onFrame() {
  const t = performance.now();
  if (_group) _group.rotation.y = Math.sin(t * 0.00008) * 0.18;
  if (_core) {
    _core.rotation.y += 0.003; _core.rotation.x += 0.0012;
    const pulse = 1 + 0.06 * Math.sin(t * 0.002);
    _core.scale.setScalar(pulse);
  }
  const live = S.state === "live";
  _sats.forEach((s, i) => {
    if (!s.mesh.visible) return;
    const a = t * 0.00022 * (live ? 1 : 0) + (i / MAXM) * Math.PI * 2;
    s.mesh.position.set(Math.cos(a) * ORBIT_R, 2.2 + Math.sin(a * 1.3) * 0.6, Math.sin(a) * ORBIT_R);
  });
  if (live) _pillars.forEach((p, i) => {
    if (p.bead.visible) p.bead.rotation.y += 0.02 + 0.004 * i;
  });
}

// =============================================================================
// overlay
// =============================================================================
function _buildOverlay() {
  const ctx = _ctx;
  _show = createShowcase(ctx, {
    id: ID, title: TITLE, accent: "#3af4c8",
    badge: _badge,
    chips: [{ label: "MEASURED", text: "live catalog", name: "src" }],
    legend: ["MEASURED", "MODELED"],
    description:
      'The live, public <b>OpenRouter</b> model catalog as a ring of <b>pillars</b> \u2014 one ' +
      'per <b>lab</b> \u2014 around a pulsing frontier core: pillar <b>height</b> = the widest ' +
      'context window that lab publishes (log-scaled), a bead rides up each pillar to the lab\u2019s ' +
      '<b>open share</b> (free-priced / total models), hue lattice-blue \u2192 proof-teal as more of ' +
      'the lab\u2019s models are open. The <b>widest-context models</b> orbit as satellites sized by ' +
      'context window, teal = free / amber = paid. All values are <b>live &amp; MEASURED</b> from the ' +
      'catalog\u2019s own published context windows and prices \u2014 no invented benchmark, no ranking. ' +
      'Log-scaling is a display transform, not a model. 0 runtime CDN.',
    citations:
      "OpenRouter openrouter.ai/api/v1/models \u2014 public live model catalog. Context windows and " +
      "prices are as PUBLISHED by each provider; informational only. MEASURED \u2014 real live observations.",
    plain: { html: _plainHtml },
  });

  _el["l-n"]     = _show.addField("labs on the frontier (live)");
  _el["l-top"]   = _show.addField("top lab (models \u00b7 max ctx)");
  _el["l-wide"]  = _show.addField("widest-context model");
  _el["l-open"]  = _show.addField("free / open \u00b7 paid");
  _el["l-total"] = _show.addField("total models cataloged");
  _el["l-label"] = _show.addField("honesty label");

  _show.attachSceneLabels({
    objects: () => {
      const out = [];
      _pillars.forEach((p) => { if (p.body && p.body.userData.label) out.push(p.body); });
      _sats.forEach((s) => { if (s.mesh && s.mesh.visible && s.mesh.userData.label) out.push(s.mesh); });
      return out;
    },
    text: (o) => (o && o.userData && o.userData.label) || "",
    weight: (o) => (o && o.scale ? o.scale.y : 0),
    topN: 4, hover: true, fadeNear: 11, fadeFar: 72,
  });

  _paint();
}

function _plainHtml() {
  const n = S.labs ? String(S.labs.length) : "loading\u2026";
  const top = _topLab();
  const topTxt = top ? (esc(labShort(top.lab)) + " \u2014 " + num(top.count) + " models") : "loading\u2026";
  return (
    "<b>What this means:</b> A <b>frontier model</b> is one of the large AI systems the world\u2019s " +
    "labs are racing to build. <b>OpenRouter</b> is a live marketplace that lists most of them side " +
    "by side. This surface plots every <b>lab</b> serving models there right now as a pillar: the " +
    "taller the pillar, the bigger the <b>context window</b> that lab\u2019s best model can read at " +
    "once; the bead\u2019s height is how much of that lab\u2019s line-up is <b>free / open</b> (teal) " +
    "versus paid. The busiest lab at this moment is <b>" + topTxt + "</b>, out of <b>" + n + "</b> " +
    "competing. Orbiting the center are the individual models with the <b>widest context windows</b> " +
    "available today. Everything here is <b>real, live catalog data</b> \u2014 nothing is ranked, " +
    "scored, or made up \u2014 shown for orientation.");
}

// =============================================================================
// helpers + paint
// =============================================================================
function num(v) { return typeof v === "number" && isFinite(v) ? v : (parseFloat(v) || 0); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function isFree(m) { return m && num(m.price_prompt) === 0 && num(m.price_completion) === 0; }
function openShare(l) {
  const c = num(l && l.count); if (!c) return 0;
  return Math.max(0, Math.min(1, num(l.free) / c));
}
function fmtCtx(v) {
  v = num(v);
  if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M";
  if (v >= 1e3) return Math.round(v / 1e3) + "K";
  return String(Math.round(v));
}
function priceTxt(m) {
  if (isFree(m)) return "free";
  const p = num(m && m.price_prompt) * 1e6;   // $ per 1M prompt tokens
  if (p <= 0) return "\u2014";
  if (p < 1) return "$" + p.toFixed(2) + "/M";
  return "$" + p.toFixed(p < 10 ? 1 : 0) + "/M";
}
function labShort(s) {
  s = String(s || "").trim();
  const M = { "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta-llama": "Meta",
    "mistralai": "Mistral", "deepseek": "DeepSeek", "qwen": "Qwen", "x-ai": "xAI",
    "cohere": "Cohere", "microsoft": "Microsoft", "nvidia": "NVIDIA", "amazon": "Amazon",
    "perplexity": "Perplexity", "ai21": "AI21", "moonshotai": "Moonshot" };
  return M[s.toLowerCase()] || (s ? s.charAt(0).toUpperCase() + s.slice(1) : "other");
}
function modShort(m) {
  const name = String((m && m.name) || (m && m.id) || "").trim();
  const short = name.replace(/^[^:]+:\s*/, "");   // drop "Lab: " prefix if present
  const n = 26;
  return short.length > n ? short.slice(0, n - 1) + "\u2026" : short;
}
function topModels() {
  const ms = (S.models || []).slice();
  return ms.sort((a, b) => num(b.ctx) - num(a.ctx));
}
function _topLab() {
  const ls = S.labs || [];
  if (!ls.length) return null;
  return ls.reduce((a, b) => (num(b.count) > num(a.count) ? b : a), ls[0]);
}
function _widest() {
  const ms = topModels();
  return ms.length ? ms[0] : null;
}
function _freePaid() {
  const ms = S.models || [];
  let f = 0, p = 0;
  ms.forEach((m) => (isFree(m) ? f++ : p++));
  return { f, p };
}

function _tok(state) {
  if (state === "live") return null;
  if (state === "missing") return "NO-LIVE-DATA";
  if (state === "degraded") return "DEGRADED";
  if (state === "error") return "OFFLINE";
  return "\u2026";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paint() {
  const t = _tok(S.state);
  _set("l-n", t || (S.labs != null ? String(S.labs.length) : "\u2014"));
  const top = _topLab();
  _set("l-top", t || (top ? (labShort(top.lab) + "  " + num(top.count) + " \u00b7 " + fmtCtx(num(top.maxCtx))) : "\u2014"));
  const w = _widest();
  _set("l-wide", t || (w ? (modShort(w) + "  " + fmtCtx(num(w.ctx))) : "\u2014"));
  if (S.models) { const fp = _freePaid(); _set("l-open", t || (fp.f + " free \u00b7 " + fp.p + " paid")); }
  else _set("l-open", t || "\u2014");
  _set("l-total", t || (S.total != null ? String(S.total) : "\u2014"));

  // honesty label verbatim — never upgraded
  _set("l-label", S.label || "MEASURED");
  if (_show) { _show.setChip("src", S.label || "MEASURED", { text: "live catalog" }); _show.refreshPlain(); }
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
  _group = _show = _core = null;
  _pillars = []; _sats = [];
  _el = {}; _badge = null; _frameReg = false;
  _stage = _THREE = _ctx = null;
  S.label = S.labs = S.models = S.total = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [MODELS_EP], mount, unmount };
