// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/open.js — OPEN FRONTIER (Hugging Face Hub) organ for the holographic estate.
//
// A live "open-model observatory": the real, public Hugging Face Hub trending stream
// (the open models the Hub is surfacing right now) rendered as a ring of pillars — one
// per ORG / author — around a pulsing frontier core, with the most-liked individual
// models orbiting as satellites. 100% LIVE MEASURED data, pulled same-origin from the
// a11oy deva frontier feed. Nothing here is faked: no invented benchmark, no made-up
// ranking — only the Hub's own published like counts, downloads, authors and task tags.
//
// Surface export shape (mirrors leaders.js / finance.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all live, same-origin):
//   /api/a11oy/v1/deva/frontier/open -> huggingface.value.orgs[]   {org, count, likes, downloads}
//                                       huggingface.value.models[]  {id, org, likes, downloads,
//                                                                     task, library}
//                                       huggingface.value.total
//
// VISUAL ENCODING (direct read of measured values; the only transform is log-normalization
// for scale, which is a DISPLAY transform — never a model):
//   * each ORG = a pillar on a ring. pillar HEIGHT = log(summed likes across that org's
//     trending models), normalized; a bead rides up the pillar to that org's download
//     reach (log-normalized total downloads); pillar hue lerps lattice-blue (low reach)
//     -> proof-teal (high reach).
//   * most-liked MODELS = satellites orbiting the core, size = log(likes), colour by task
//     family (teal = text/generation, amber = vision/image, blue = audio/speech, grey =
//     other). hover shows the model id, its like count and downloads.
//   * center = proof-teal wireframe "frontier core" that pulses with the total window size.
//
// HONESTY: MEASURED (real live observations from the public Hugging Face Hub API).
//   Degrades to NO-LIVE-DATA (grey) on 404 / offline; never fabricates a model or a count.
//   Like and download counts are as PUBLISHED by the Hub; informational only.
// COLOURS: proof-teal 0x3af4c8, lattice-blue 0x5b8dee, gold-amber 0xd7b96b, greys.
//   Purple BANNED as UI/background. 0 RUNTIME CDN. Vendored three.js via page importmap.
// CITATIONS: Hugging Face huggingface.co/api/models — public live model hub.

import { createShowcase } from "./_showcase.js";

const ID    = "open";
const TITLE = "Open Frontier \u00b7 Live Hugging Face";

const OPEN_EP = "/api/a11oy/v1/deva/frontier/open?limit=24";

// palette — purple BANNED
const C_GEN    = 0x3af4c8;  // proof-teal   (text / generation)
const C_VIS    = 0xd7b96b;  // gold-amber   (vision / image / video)
const C_AUD    = 0x5b8dee;  // lattice-blue (audio / speech)
const C_OTH    = 0x7fa8b0;  // muted        (other task)
const C_LO     = 0x5b8dee;  // lattice-blue (low reach)
const C_HI     = 0x3af4c8;  // proof-teal   (high reach)
const C_CORE   = 0x3af4c8;  // proof-teal   (frontier core)
const C_PILLAR = 0x24506a;  // dim pillar body
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;

const RING_R   = 9.5;   // org ring radius
const MAXO     = 16;    // org pillar slots
const ORBIT_R  = 4.6;   // model orbit radius
const MAXM     = 8;     // model satellite slots
const PIL_MAXH = 6.5;   // tallest pillar (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _core = null;
let _pillars = [];   // Array<{ grp, body, bead, org }>
let _sats = [];      // Array<{ mesh, model }>

// live state
const S = {
  label: null, orgs: null, models: null, total: null, state: "init",
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
  _polls.push(ctx.live.poll(OPEN_EP, 60000, _onData, {
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
  for (let i = 0; i < MAXO; i++) {
    const a = (i / MAXO) * Math.PI * 2;
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
    _pillars.push({ grp, body, bead, org: null });
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
function _onData(j, meta) {
  S.label = (_ctx.live.readHonestyLabel(j) || "MEASURED").toUpperCase();
  const hf = (j && j.huggingface && j.huggingface.value) || null;
  S.orgs   = (hf && Array.isArray(hf.orgs))   ? hf.orgs   : null;
  S.models = (hf && Array.isArray(hf.models)) ? hf.models : null;
  S.total  = (hf && typeof hf.total === "number") ? hf.total : null;
  // An HTTP-200 can still carry a null per-source value (upstream outage). Honestly
  // downgrade to DEGRADED rather than claim "live" while showing dashes.
  S.state = (S.orgs != null && !(meta && meta.degraded)) ? "live" : "degraded";
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
  const orgs = (S.orgs || []).slice(0, MAXO);

  // log-normalize summed likes across visible orgs for pillar heights
  const lk = orgs.map((o) => Math.log10(Math.max(1, num(o.likes))));
  const lMin = lk.length ? Math.min(...lk) : 0;
  const lMax = lk.length ? Math.max(...lk) : 1;
  const lSpan = Math.max(lMax - lMin, 1e-6);
  // log-normalize downloads across visible orgs for the reach bead + hue
  const dl = orgs.map((o) => Math.log10(Math.max(1, num(o.downloads))));
  const dMin = dl.length ? Math.min(...dl) : 0;
  const dMax = dl.length ? Math.max(...dl) : 1;
  const dSpan = Math.max(dMax - dMin, 1e-6);

  _pillars.forEach((p, i) => {
    const o = orgs[i] || null;
    p.org = o;
    if (!o || !live) {
      p.body.material.color.setHex(C_PILLAR);
      p.body.material.emissive.setHex(live ? C_PILLAR : C_DIM);
      p.body.material.emissiveIntensity = 0.1;
      p.body.scale.y = 0.4; p.body.position.y = 0.2;
      p.bead.visible = false;
      p.body.userData.label = "";
      return;
    }
    const h = 0.8 + PIL_MAXH * ((Math.log10(Math.max(1, num(o.likes))) - lMin) / lSpan);
    p.body.scale.y = h; p.body.position.y = h / 2;

    const reach = Math.max(0, Math.min(1, (Math.log10(Math.max(1, num(o.downloads))) - dMin) / dSpan));
    const col = _lerpHex(C_LO, C_HI, reach);
    p.body.material.color.copy(col);
    p.body.material.emissive.copy(col);
    p.body.material.emissiveIntensity = 0.22 + 0.5 * reach;

    p.bead.visible = true;
    p.bead.position.y = 0.2 + reach * h;   // bead rides up to the org's download reach
    p.bead.material.color.copy(col);
    p.bead.material.emissive.copy(col);
    p.bead.material.emissiveIntensity = 0.85;

    p.body.userData.label = orgShort(o.org) + "  \u00b7  " + num(o.count) + " models  \u00b7  " + fmtNum(num(o.likes)) + " likes";
  });
}

function _layoutSats() {
  const live = S.state === "live";
  const models = topModels().slice(0, MAXM);
  const lks = models.map((m) => Math.log10(Math.max(1, num(m.likes))));
  const mMin = lks.length ? Math.min(...lks) : 0;
  const mMax = lks.length ? Math.max(...lks) : 1;
  const mSpan = Math.max(mMax - mMin, 1e-6);

  _sats.forEach((s, i) => {
    const m = models[i] || null;
    s.model = m;
    if (!m || !live) { s.mesh.visible = false; s.mesh.userData.label = ""; return; }
    s.mesh.visible = true;
    const scale = 0.55 + 1.0 * ((Math.log10(Math.max(1, num(m.likes))) - mMin) / mSpan);
    s.mesh.scale.setScalar(scale);
    const col = taskColor(m.task);
    s.mesh.material.color.setHex(col);
    s.mesh.material.emissive.setHex(col);
    s.mesh.material.emissiveIntensity = 0.4;
    s.mesh.userData.label = modShort(m) + "  " + fmtNum(num(m.likes)) + " likes \u00b7 " + fmtNum(num(m.downloads)) + " dl";
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
    chips: [{ label: "MEASURED", text: "live hub", name: "src" }],
    legend: ["MEASURED", "MODELED"],
    description:
      'The live, public <b>Hugging Face</b> hub trending stream as a ring of <b>pillars</b> \u2014 one ' +
      'per <b>org</b> (author) \u2014 around a pulsing frontier core: pillar <b>height</b> = the summed ' +
      '<b>likes</b> of that org\u2019s trending models (log-scaled), a bead rides up each pillar to the ' +
      'org\u2019s <b>download reach</b>, hue lattice-blue \u2192 proof-teal as reach grows. The <b>most-liked ' +
      'models</b> orbit as satellites sized by likes, coloured by task family (teal = text, amber = ' +
      'vision, blue = audio). All values are <b>live &amp; MEASURED</b> from the hub\u2019s own published ' +
      'like and download counts \u2014 no invented benchmark, no ranking. Log-scaling is a display ' +
      'transform, not a model. 0 runtime CDN.',
    citations:
      "Hugging Face huggingface.co/api/models \u2014 public live model hub. Like and download counts " +
      "are as PUBLISHED by the hub; informational only. MEASURED \u2014 real live observations.",
    plain: { html: _plainHtml },
  });

  _el["o-n"]     = _show.addField("orgs on the frontier (live)");
  _el["o-top"]   = _show.addField("top org (models \u00b7 likes)");
  _el["o-liked"] = _show.addField("most-liked model");
  _el["o-dl"]    = _show.addField("most-downloaded model");
  _el["o-total"] = _show.addField("models in the window");
  _el["o-label"] = _show.addField("honesty label");

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
  const n = S.orgs ? String(S.orgs.length) : "loading\u2026";
  const top = _topOrg();
  const topTxt = top ? (esc(orgShort(top.org)) + " \u2014 " + num(top.count) + " models") : "loading\u2026";
  return (
    "<b>What this means:</b> The <b>open frontier</b> is the world of AI models anyone can " +
    "download and run for free. <b>Hugging Face</b> is the public hub where those models live, " +
    "and it tracks which ones people are favouriting and downloading right now. This surface " +
    "plots each <b>org</b> (the team that published the models) as a pillar: the taller the " +
    "pillar, the more <b>likes</b> that team\u2019s trending models have gathered; a bead rides up " +
    "to show how widely those models are <b>downloaded</b>. The busiest team at this moment is <b>" +
    topTxt + "</b>, out of <b>" + n + "</b> in view. Orbiting the center are the single <b>most-" +
    "liked open models</b> right now, coloured by what they do \u2014 text, vision, or audio. " +
    "Everything here is <b>real, live hub data</b> \u2014 nothing is ranked, scored, or made up.");
}

// =============================================================================
// helpers + paint
// =============================================================================
function num(v) { return typeof v === "number" && isFinite(v) ? v : (parseFloat(v) || 0); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function fmtNum(v) {
  v = num(v);
  if (v >= 1e9) return (v / 1e9).toFixed(v >= 1e10 ? 0 : 1) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(v >= 1e4 ? 0 : 1) + "K";
  return String(Math.round(v));
}
function taskColor(task) {
  const t = String(task || "").toLowerCase();
  if (!t) return C_OTH;
  if (t.includes("image") || t.includes("vision") || t.includes("video") || t.includes("depth") || t.includes("object") || t.includes("mask")) return C_VIS;
  if (t.includes("audio") || t.includes("speech") || t.includes("voice") || t.includes("music")) return C_AUD;
  if (t.includes("text") || t.includes("generation") || t.includes("translation") || t.includes("summar") || t.includes("question") || t.includes("classification") || t.includes("token") || t.includes("sentence") || t.includes("fill") || t.includes("conversational")) return C_GEN;
  return C_OTH;
}
function orgShort(s) {
  s = String(s || "").trim();
  const M = { "meta-llama": "Meta", "mistralai": "Mistral", "google": "Google",
    "microsoft": "Microsoft", "nvidia": "NVIDIA", "deepseek-ai": "DeepSeek",
    "qwen": "Qwen", "openai": "OpenAI", "stabilityai": "Stability",
    "black-forest-labs": "Black Forest", "tencent": "Tencent", "baidu": "Baidu",
    "zai-org": "Z.ai", "bigcode": "BigCode", "facebook": "Meta AI", "apple": "Apple" };
  const key = s.toLowerCase();
  if (M[key]) return M[key];
  const n = 16;
  return s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
}
function modShort(m) {
  const id = String((m && m.id) || "").trim();
  const short = id.includes("/") ? id.slice(id.indexOf("/") + 1) : id;
  const n = 26;
  return short.length > n ? short.slice(0, n - 1) + "\u2026" : short;
}
function topModels() {
  const ms = (S.models || []).slice();
  return ms.sort((a, b) => num(b.likes) - num(a.likes));
}
function _topOrg() {
  const os = S.orgs || [];
  if (!os.length) return null;
  return os.reduce((a, b) => (num(b.likes) > num(a.likes) ? b : a), os[0]);
}
function _mostLiked() { const ms = topModels(); return ms.length ? ms[0] : null; }
function _mostDownloaded() {
  const ms = S.models || [];
  if (!ms.length) return null;
  return ms.reduce((a, b) => (num(b.downloads) > num(a.downloads) ? b : a), ms[0]);
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
  _set("o-n", t || (S.orgs != null ? String(S.orgs.length) : "\u2014"));
  const top = _topOrg();
  _set("o-top", t || (top ? (orgShort(top.org) + "  " + num(top.count) + " \u00b7 " + fmtNum(num(top.likes))) : "\u2014"));
  const liked = _mostLiked();
  _set("o-liked", t || (liked ? (modShort(liked) + "  " + fmtNum(num(liked.likes)) + " likes") : "\u2014"));
  const dld = _mostDownloaded();
  _set("o-dl", t || (dld ? (modShort(dld) + "  " + fmtNum(num(dld.downloads)) + " dl") : "\u2014"));
  _set("o-total", t || (S.total != null ? String(S.total) : "\u2014"));

  // honesty label verbatim — never upgraded
  _set("o-label", S.label || "MEASURED");
  if (_show) { _show.setChip("src", S.label || "MEASURED", { text: "live hub" }); _show.refreshPlain(); }
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
  S.label = S.orgs = S.models = S.total = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [OPEN_EP], mount, unmount };
