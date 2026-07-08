// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/research.js — FRONTIER RESEARCH organ for the holographic estate.
//
// A live "research frontier observatory": the real, public arXiv submission stream
// (newest cs.AI / cs.LG / cs.CL / cs.CV / cs.NE papers) rendered as a ring of pillars —
// one per CATEGORY — around a pulsing frontier core, with the most-recent individual
// papers orbiting as satellites. 100% LIVE MEASURED data, pulled same-origin from the
// a11oy deva frontier feed. Nothing here is faked: no invented score, no citation count,
// no ranking — only arXiv's own published titles, authors, categories and timestamps.
//
// Surface export shape (mirrors leaders.js / finance.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all live, same-origin):
//   /api/a11oy/v1/deva/frontier/research -> arxiv.value.cats[]   {cat, count, latest}
//                                           arxiv.value.papers[] {id, title, first_author,
//                                                                  authors_n, published, cat}
//                                           arxiv.value.total
//
// VISUAL ENCODING (direct read of measured values; the only transform is log-normalization
// for scale, which is a DISPLAY transform — never a model):
//   * each CATEGORY = a pillar on a ring. pillar HEIGHT = log(paper count in the live
//     window) normalized; a bead rides up to that category's SHARE of the window; pillar
//     hue lerps lattice-blue (small share) -> proof-teal (large share).
//   * most-recent PAPERS = satellites orbiting the core, size = log(author count) i.e.
//     collaboration breadth. hover shows the paper title, its category, and date.
//   * center = proof-teal wireframe "frontier core" that pulses with the total window size.
//
// HONESTY: MEASURED (real live observations from the public arXiv Atom API).
//   Degrades to NO-LIVE-DATA (grey) on 404 / offline; never fabricates a paper.
//   Titles, authors, categories and dates are as PUBLISHED by arXiv; informational only.
// COLOURS: proof-teal 0x3af4c8, lattice-blue 0x5b8dee, gold-amber 0xd7b96b, greys.
//   Purple BANNED as UI/background. 0 RUNTIME CDN. Vendored three.js via page importmap.
// CITATIONS: arXiv export.arxiv.org/api/query — public live submission feed.

import { createShowcase } from "./_showcase.js";

const ID    = "research";
const TITLE = "Frontier Research \u00b7 Live arXiv AI";

const RESEARCH_EP = "/api/a11oy/v1/deva/frontier/research?limit=24";

// palette — purple BANNED
const C_HOT    = 0xd7b96b;  // gold-amber   (freshest paper)
const C_OPEN   = 0x3af4c8;  // proof-teal   (research / open)
const C_LO     = 0x5b8dee;  // lattice-blue (low share)
const C_HI     = 0x3af4c8;  // proof-teal   (high share)
const C_CORE   = 0x3af4c8;  // proof-teal   (frontier core)
const C_PILLAR = 0x24506a;  // dim pillar body
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;

const RING_R   = 9.5;   // category ring radius
const MAXL     = 16;    // category pillar slots
const ORBIT_R  = 4.6;   // paper orbit radius
const MAXM     = 8;     // paper satellite slots
const PIL_MAXH = 6.5;   // tallest pillar (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _core = null;
let _pillars = [];   // Array<{ grp, body, bead, cat }>
let _sats = [];      // Array<{ mesh, paper }>

// live state
const S = {
  label: null, cats: null, papers: null, total: null, state: "init",
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
  _polls.push(ctx.live.poll(RESEARCH_EP, 60000, _onResearch, {
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
    _pillars.push({ grp, body, bead, cat: null });
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
    _sats.push({ mesh, paper: null });
  }
}

// =============================================================================
// live data handler
// =============================================================================
function _onResearch(j, meta) {
  S.label = (_ctx.live.readHonestyLabel(j) || "MEASURED").toUpperCase();
  const ax = (j && j.arxiv && j.arxiv.value) || null;
  S.cats   = (ax && Array.isArray(ax.cats))   ? ax.cats   : null;
  S.papers = (ax && Array.isArray(ax.papers)) ? ax.papers : null;
  S.total  = (ax && typeof ax.total === "number") ? ax.total : null;
  // An HTTP-200 can still carry a null per-source value (upstream outage). Honestly
  // downgrade to DEGRADED rather than claim "live" while showing dashes.
  S.state = (S.cats != null && !(meta && meta.degraded)) ? "live" : "degraded";
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
  const cats = (S.cats || []).slice(0, MAXL);
  const totalWin = cats.reduce((s, c) => s + num(c.count), 0) || 1;

  // log-normalize paper count across the visible categories for pillar heights
  const cx = cats.map((c) => Math.log10(Math.max(1, num(c.count))));
  const cMin = cx.length ? Math.min(...cx) : 0;
  const cMax = cx.length ? Math.max(...cx) : 1;
  const cSpan = Math.max(cMax - cMin, 1e-6);

  _pillars.forEach((p, i) => {
    const c = cats[i] || null;
    p.cat = c;
    if (!c || !live) {
      p.body.material.color.setHex(C_PILLAR);
      p.body.material.emissive.setHex(live ? C_PILLAR : C_DIM);
      p.body.material.emissiveIntensity = 0.1;
      p.body.scale.y = 0.4; p.body.position.y = 0.2;
      p.bead.visible = false;
      p.body.userData.label = "";
      return;
    }
    const h = 0.8 + PIL_MAXH * ((Math.log10(Math.max(1, num(c.count))) - cMin) / cSpan);
    p.body.scale.y = h; p.body.position.y = h / 2;

    const share = Math.max(0, Math.min(1, num(c.count) / totalWin));
    const col = _lerpHex(C_LO, C_HI, share);
    p.body.material.color.copy(col);
    p.body.material.emissive.copy(col);
    p.body.material.emissiveIntensity = 0.22 + 0.5 * share;

    p.bead.visible = true;
    p.bead.position.y = 0.2 + share * h;   // bead rides up to the category's share of the window
    p.bead.material.color.copy(col);
    p.bead.material.emissive.copy(col);
    p.bead.material.emissiveIntensity = 0.85;

    p.body.userData.label = catShort(c.cat) + "  \u00b7  " + num(c.count) + " papers  \u00b7  " + Math.round(share * 100) + "%";
  });
}

function _layoutSats() {
  const live = S.state === "live";
  const papers = topPapers().slice(0, MAXM);
  const az = papers.map((p) => Math.log10(Math.max(1, num(p.authors_n))));
  const mMin = az.length ? Math.min(...az) : 0;
  const mMax = az.length ? Math.max(...az) : 1;
  const mSpan = Math.max(mMax - mMin, 1e-6);

  _sats.forEach((s, i) => {
    const p = papers[i] || null;
    s.paper = p;
    if (!p || !live) { s.mesh.visible = false; s.mesh.userData.label = ""; return; }
    s.mesh.visible = true;
    const scale = 0.55 + 1.0 * ((Math.log10(Math.max(1, num(p.authors_n))) - mMin) / mSpan);
    s.mesh.scale.setScalar(scale);
    const col = i === 0 ? C_HOT : C_OPEN;   // freshest paper glows amber
    s.mesh.material.color.setHex(col);
    s.mesh.material.emissive.setHex(col);
    s.mesh.material.emissiveIntensity = 0.4;
    s.mesh.userData.label = paperShort(p) + "  \u00b7  " + catShort(p.cat) + "  \u00b7  " + fmtDate(p.published);
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
    chips: [{ label: "MEASURED", text: "live feed", name: "src" }],
    legend: ["MEASURED", "MODELED"],
    description:
      'The live, public <b>arXiv</b> submission stream (newest cs.AI / cs.LG / cs.CL / cs.CV / cs.NE ' +
      'papers) as a ring of <b>pillars</b> \u2014 one per <b>category</b> \u2014 around a pulsing ' +
      'frontier core: pillar <b>height</b> = the number of papers that category has in the live ' +
      'window (log-scaled), a bead rides up each pillar to that category\u2019s <b>share</b> of the ' +
      'window, hue lattice-blue \u2192 proof-teal as its share grows. The <b>most-recent papers</b> ' +
      'orbit as satellites sized by <b>author count</b> (collaboration breadth); the freshest glows ' +
      'amber. All values are <b>live &amp; MEASURED</b> from arXiv\u2019s own published titles, ' +
      'authors, categories and timestamps \u2014 no citation count, no score, no ranking. ' +
      'Log-scaling is a display transform, not a model. 0 runtime CDN.',
    citations:
      "arXiv export.arxiv.org/api/query \u2014 public live submission feed. Titles, authors, " +
      "categories and dates are as PUBLISHED by arXiv; informational only. MEASURED \u2014 real live observations.",
    plain: { html: _plainHtml },
  });

  _el["r-n"]     = _show.addField("categories in the window (live)");
  _el["r-top"]   = _show.addField("most active category (papers \u00b7 share)");
  _el["r-new"]   = _show.addField("newest paper");
  _el["r-date"]  = _show.addField("newest submission");
  _el["r-total"] = _show.addField("papers in live window");
  _el["r-label"] = _show.addField("honesty label");

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
  const n = S.cats ? String(S.cats.length) : "loading\u2026";
  const top = _topCat();
  const topTxt = top ? (esc(catShort(top.cat)) + " \u2014 " + num(top.count) + " papers") : "loading\u2026";
  return (
    "<b>What this means:</b> <b>arXiv</b> is where the world\u2019s AI researchers post new work, " +
    "often the day it\u2019s written \u2014 the true frontier, months ahead of any product. This " +
    "surface reads the newest submissions right now and plots each research <b>category</b> as a " +
    "pillar: the taller the pillar, the more fresh papers that area has in this window; the bead\u2019s " +
    "height is that area\u2019s <b>share</b> of everything posted. The busiest area at this moment is " +
    "<b>" + topTxt + "</b>, across <b>" + n + "</b> categories. Orbiting the center are the <b>most " +
    "recent individual papers</b>, sized by how many authors collaborated. Everything here is " +
    "<b>real, live feed data</b> \u2014 nothing is scored, ranked, or made up \u2014 shown for orientation.");
}

// =============================================================================
// helpers + paint
// =============================================================================
function num(v) { return typeof v === "number" && isFinite(v) ? v : (parseFloat(v) || 0); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function catShort(s) {
  s = String(s || "").trim();
  const M = { "cs.AI": "AI", "cs.LG": "Machine Learning", "cs.CL": "NLP / Language",
    "cs.CV": "Vision", "cs.NE": "Neural / Evolutionary", "cs.RO": "Robotics",
    "cs.MA": "Multi-Agent", "cs.IR": "Info Retrieval", "cs.CR": "Security",
    "stat.ML": "Stats ML", "cs.HC": "Human-Computer", "cs.SE": "Software Eng",
    "cs.DC": "Distributed", "cs.CY": "Computers & Society", "eess.AS": "Audio/Speech" };
  return M[s] || (s || "other");
}
function paperShort(p) {
  const title = String((p && p.title) || "").trim();
  const n = 30;
  return title.length > n ? title.slice(0, n - 1) + "\u2026" : title;
}
function fmtDate(s) {
  s = String(s || "");
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return "\u2014";
  const MON = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return MON[parseInt(m[2], 10)] + " " + parseInt(m[3], 10);
}
function topPapers() {
  const ps = (S.papers || []).slice();
  return ps.sort((a, b) => String(b.published || "").localeCompare(String(a.published || "")));
}
function _topCat() {
  const cs = S.cats || [];
  if (!cs.length) return null;
  return cs.reduce((a, b) => (num(b.count) > num(a.count) ? b : a), cs[0]);
}
function _newest() {
  const ps = topPapers();
  return ps.length ? ps[0] : null;
}
function _winShare(c) {
  const cs = S.cats || [];
  const tot = cs.reduce((s, x) => s + num(x.count), 0) || 1;
  return c ? Math.round((num(c.count) / tot) * 100) : 0;
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
  _set("r-n", t || (S.cats != null ? String(S.cats.length) : "\u2014"));
  const top = _topCat();
  _set("r-top", t || (top ? (catShort(top.cat) + "  " + num(top.count) + " \u00b7 " + _winShare(top) + "%") : "\u2014"));
  const w = _newest();
  _set("r-new", t || (w ? paperShort(w) : "\u2014"));
  _set("r-date", t || (w ? fmtDate(w.published) : "\u2014"));
  _set("r-total", t || (S.total != null ? String(S.total) : "\u2014"));

  // honesty label verbatim — never upgraded
  _set("r-label", S.label || "MEASURED");
  if (_show) { _show.setChip("src", S.label || "MEASURED", { text: "live feed" }); _show.refreshPlain(); }
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
  S.label = S.cats = S.papers = S.total = null; S.state = "init";
}

export default { id: ID, title: TITLE, endpoints: [RESEARCH_EP], mount, unmount };
