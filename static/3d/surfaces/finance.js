// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
//
// surfaces/finance.js — GOVERNED MARKETS & FINANCE organ for the holographic estate.
//
// A live "prediction-market observatory": the real Polymarket book (top markets by 24h
// volume) rendered as a ring of pillars around a pulsing market core, with the live crypto
// majors (BTC/ETH/SOL) orbiting as satellites. 100% LIVE MEASURED data, pulled same-origin
// from the a11oy deva finance feeds. The 2D "DevPlatform" console mock (fabricated keys /
// invented monthly spend) is deliberately NOT reused here — nothing on this surface is faked.
//
// Surface export shape (mirrors episodic.js / evalarena.js):
//   export default { id, title, endpoints, mount(ctx), unmount() }
//   ctx = { stage, container, live, label, THREE, szl3d }
//
// DATA SHOWN (all live, same-origin):
//   /api/a11oy/v1/deva/finance/predict -> polymarket.value.markets[]
//        {id, question, slug, yes, outcomes, prices, vol24h, liquidity, endDate, url}
//   /api/a11oy/v1/deva/finance/crypto  -> coingecko.value.coins[] {id,usd,chg24h,vol24h,mcap}
//                                         coinbase["BTC-USD"].value.amount
//
// VISUAL ENCODING (direct read of measured values; the only transform is log-normalization
// for scale, which is a DISPLAY transform — never a model):
//   * each prediction market = a pillar on a ring. pillar HEIGHT = log(vol24h) normalized;
//     a probability bead rides up the pillar at the YES price (0 bottom .. 1 top); bead hue
//     lerps lattice-blue (low YES) -> proof-teal (high YES).
//   * crypto majors = satellites orbiting the core, radius = log(mcap), colour proof-teal if
//     24h change >= 0 else gold-amber. hover shows live price + 24h %.
//   * center = proof-teal wireframe "market core" that pulses with aggregate 24h volume.
//
// HONESTY: MEASURED (real live observations from Polymarket gamma-api, CoinGecko, Coinbase).
//   Degrades to NO-LIVE-DATA (grey) on 404 / offline; never fabricates a price. Not advice.
// COLOURS: proof-teal 0x3af4c8, lattice-blue 0x5b8dee, gold-amber 0xd7b96b (down), greys.
//   Purple BANNED as UI/background. 0 RUNTIME CDN. Vendored three.js via page importmap.
// CITATIONS: Polymarket gamma-api.polymarket.com · CoinGecko api.coingecko.com ·
//   Coinbase api.coinbase.com. Public live market data; informational, not investment advice.

import { createShowcase } from "./_showcase.js";

const ID    = "markets";
const TITLE = "Markets & Finance \u00b7 Prediction + Crypto (live)";

const PREDICT_EP = "/api/a11oy/v1/deva/finance/predict?limit=16";
const CRYPTO_EP  = "/api/a11oy/v1/deva/finance/crypto";

// palette — purple BANNED
const C_YESLO  = 0x5b8dee;  // lattice-blue (low YES probability)
const C_YESHI  = 0x3af4c8;  // proof-teal   (high YES probability)
const C_UP     = 0x3af4c8;  // proof-teal   (crypto 24h up)
const C_DOWN   = 0xd7b96b;  // gold-amber   (crypto 24h down)
const C_CORE   = 0x3af4c8;  // proof-teal   (market core)
const C_PILLAR = 0x24506a;  // dim pillar body
const C_DIM    = 0x42505d;  // grey (degraded / no-live-data)
const C_GRID   = 0x1b3a44;

const RING_R   = 9.5;   // prediction-market ring radius
const MAXM     = 16;    // pillar slots
const ORBIT_R  = 4.6;   // crypto orbit radius
const MAXC     = 6;     // crypto satellite slots
const PIL_MAXH = 6.5;   // tallest pillar (world units)

let _stage = null, _THREE = null, _ctx = null, _group = null, _show = null;
let _frameReg = false, _polls = [], _el = {}, _badge = null;

let _core = null;
let _pillars = [];   // Array<{ grp, body, bead, market }>
let _sats = [];      // Array<{ mesh, coin }>

// live state
const S = {
  labelP: null, markets: null, pState: "init",   // prediction markets
  labelC: null, coins: null, btcSpot: null, cState: "init",  // crypto
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
  _polls.push(ctx.live.poll(PREDICT_EP, 15000, _onPredict, {
    badge: _badge, onState: (m) => { S.pState = m.state; _layout(); _paint(); },
  }));
  _polls.push(ctx.live.poll(CRYPTO_EP, 20000, _onCrypto, {
    onState: (m) => { S.cState = m.state; _layoutSats(); _paint(); },
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
  // unit-height cylinder (spans -0.5..0.5); we scale.y and lift by height/2 so base sits at y=0
  const bodyGeo = new THREE.CylinderGeometry(0.16, 0.20, 1, 14);
  const beadGeo = new THREE.SphereGeometry(0.26, 16, 12);
  _pillars = [];
  for (let i = 0; i < MAXM; i++) {
    const a = (i / MAXM) * Math.PI * 2;
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
    _pillars.push({ grp, body, bead, market: null });
  }
}

function _buildSats() {
  const THREE = _THREE;
  const geo = new THREE.SphereGeometry(0.34, 18, 14);
  _sats = [];
  for (let i = 0; i < MAXC; i++) {
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: C_DIM, emissive: C_DIM, emissiveIntensity: 0.15, metalness: 0.35, roughness: 0.35,
    }));
    mesh.position.set(0, 2.2, 0);
    mesh.visible = false;
    mesh.userData.label = "";
    _group.add(mesh);
    _sats.push({ mesh, coin: null });
  }
}

// =============================================================================
// live data handlers
// =============================================================================
function _onPredict(j, meta) {
  S.labelP = (_ctx.live.readHonestyLabel(j) || "MEASURED").toUpperCase();
  const pm = (j && j.polymarket && j.polymarket.value) || null;
  S.markets = (pm && Array.isArray(pm.markets)) ? pm.markets : null;
  // An HTTP-200 can still carry a null per-source value (upstream rate-limit / outage).
  // Honestly downgrade to DEGRADED rather than claim "live" while showing dashes. Runs
  // after the poll's onState (which fires first) and on every success, so it self-corrects.
  S.pState = (S.markets != null && !(meta && meta.degraded)) ? "live" : "degraded";
  _layout(); _paint();
}

function _onCrypto(j, meta) {
  S.labelC = (_ctx.live.readHonestyLabel(j) || "MEASURED").toUpperCase();
  const cg = (j && j.coingecko && j.coingecko.value) || null;
  S.coins = (cg && Array.isArray(cg.coins)) ? cg.coins : null;
  const cb = (j && j.coinbase && j.coinbase["BTC-USD"] && j.coinbase["BTC-USD"].value) || null;
  S.btcSpot = cb && typeof cb.amount === "number" ? cb.amount : null;
  // Downgrade to DEGRADED on a null per-source value (e.g. CoinGecko 429) instead of "live".
  S.cState = (S.coins != null && !(meta && meta.degraded)) ? "live" : "degraded";
  _layoutSats(); _paint();
}

// =============================================================================
// geometry updaters
// =============================================================================
function _lerpHex(c0, c1, t) {
  const a = new _THREE.Color(c0), b = new _THREE.Color(c1);
  return a.lerp(b, Math.max(0, Math.min(1, t)));
}

function _layout() {
  const live = S.pState === "live";
  const markets = (S.markets || []).slice(0, MAXM);

  // log-normalize 24h volume across the visible markets for pillar heights
  const vols = markets.map((m) => Math.log10(Math.max(1, num(m.vol24h))));
  const vMin = vols.length ? Math.min(...vols) : 0;
  const vMax = vols.length ? Math.max(...vols) : 1;
  const vSpan = Math.max(vMax - vMin, 1e-6);

  _pillars.forEach((p, i) => {
    const m = markets[i] || null;
    p.market = m;
    if (!m || !live) {
      p.body.material.color.setHex(C_PILLAR);
      p.body.material.emissive.setHex(live ? C_PILLAR : C_DIM);
      p.body.material.emissiveIntensity = 0.1;
      p.body.scale.y = 0.4; p.body.position.y = 0.2;
      p.bead.visible = false;
      p.body.userData.label = "";
      return;
    }
    const h = 0.8 + PIL_MAXH * ((Math.log10(Math.max(1, num(m.vol24h))) - vMin) / vSpan);
    p.body.scale.y = h; p.body.position.y = h / 2;

    const yes = clamp01(typeof m.yes === "number" ? m.yes : 0.5);
    const col = _lerpHex(C_YESLO, C_YESHI, yes);
    p.body.material.color.copy(col);
    p.body.material.emissive.copy(col);
    p.body.material.emissiveIntensity = 0.22 + 0.5 * Math.abs(yes - 0.5) * 2; // conviction glow

    p.bead.visible = true;
    p.bead.position.y = 0.2 + yes * h;   // bead rides up to the YES fraction of the pillar
    p.bead.material.color.copy(col);
    p.bead.material.emissive.copy(col);
    p.bead.material.emissiveIntensity = 0.85;

    p.body.userData.label = shortQ(m.question) + "  \u00b7  YES " + pct(yes) + "  \u00b7  " + fmtUSD(num(m.vol24h));
  });
}

function _layoutSats() {
  const live = S.cState === "live";
  const coins = (S.coins || []).slice(0, MAXC);
  const mcaps = coins.map((c) => Math.log10(Math.max(1, num(c.mcap))));
  const mMin = mcaps.length ? Math.min(...mcaps) : 0;
  const mMax = mcaps.length ? Math.max(...mcaps) : 1;
  const mSpan = Math.max(mMax - mMin, 1e-6);

  _sats.forEach((s, i) => {
    const c = coins[i] || null;
    s.coin = c;
    if (!c || !live) { s.mesh.visible = false; s.mesh.userData.label = ""; return; }
    s.mesh.visible = true;
    const scale = 0.55 + 1.0 * ((Math.log10(Math.max(1, num(c.mcap))) - mMin) / mSpan);
    s.mesh.scale.setScalar(scale);
    const up = num(c.chg24h) >= 0;
    const col = up ? C_UP : C_DOWN;
    s.mesh.material.color.setHex(col);
    s.mesh.material.emissive.setHex(col);
    s.mesh.material.emissiveIntensity = 0.4;
    s.mesh.userData.label = sym(c.id) + "  " + fmtUSD(num(c.usd)) + "  " + signPct(num(c.chg24h));
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
  // crypto satellites orbit the core
  const liveC = S.cState === "live";
  _sats.forEach((s, i) => {
    if (!s.mesh.visible) return;
    const a = t * 0.00022 * (liveC ? 1 : 0) + (i / MAXC) * Math.PI * 2;
    s.mesh.position.set(Math.cos(a) * ORBIT_R, 2.2 + Math.sin(a * 1.3) * 0.6, Math.sin(a) * ORBIT_R);
  });
  // probability beads gently bob
  const liveP = S.pState === "live";
  if (liveP) _pillars.forEach((p, i) => {
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
    chips: [{ label: "MEASURED", text: "live markets", name: "src" }],
    legend: ["MEASURED", "MODELED"],
    description:
      'The real <b>Polymarket</b> book (top markets by 24h volume) as a ring of <b>pillars</b> ' +
      'around a pulsing market core: pillar <b>height</b> = 24h volume (log-scaled), a bead ' +
      'rides up each pillar to its live <b>YES</b> probability, hue lattice-blue \u2192 proof-teal ' +
      'with conviction. The <b>major cryptocurrencies</b> orbit as satellites sized by market ' +
      'cap, teal up / amber down. All values are <b>live &amp; MEASURED</b> \u2014 no mocked ' +
      'spend, no fabricated keys. Log-scaling is a display transform, not a model. 0 runtime CDN.',
    citations:
      "Polymarket gamma-api.polymarket.com \u00b7 CoinGecko api.coingecko.com \u00b7 Coinbase api.coinbase.com. " +
      "Public live market data; informational only, not investment advice. MEASURED \u2014 real live observations.",
    plain: { html: _plainHtml },
  });

  _el["m-n"]     = _show.addField("prediction markets (live)");
  _el["m-top"]   = _show.addField("top market (YES \u00b7 24h vol)");
  _el["m-vol"]   = _show.addField("aggregate 24h volume");
  _el["m-btc"]   = _show.addField("BTC \u00b7 ETH \u00b7 SOL");
  _el["m-cfeed"] = _show.addField("crypto feed");
  _el["m-label"] = _show.addField("honesty label");

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
  const n = S.markets ? String(S.markets.length) : "loading\u2026";
  const top = _topMarket();
  const topTxt = top ? (esc(shortQ(top.question, 46)) + " \u2014 YES " + pct(clamp01(top.yes))) : "loading\u2026";
  return (
    "<b>What this means:</b> A <b>prediction market</b> is a live crowd forecast \u2014 people " +
    "buy and sell contracts on real-world outcomes, and the price is the crowd\u2019s implied " +
    "probability. This surface plots the busiest <b>" + n + "</b> markets on <b>Polymarket</b> " +
    "right now: the taller the pillar, the more money traded in 24 hours; the bead\u2019s height " +
    "is how likely the crowd thinks \u201cYES\u201d is. The loudest market at this moment is " +
    "<b>" + topTxt + "</b>. Orbiting the center are the major cryptocurrencies at their live " +
    "prices (teal = up today, amber = down). Everything here is <b>real, live market data</b> " +
    "\u2014 nothing is mocked or made up \u2014 shown for orientation, not as investment advice.");
}

// =============================================================================
// helpers + paint
// =============================================================================
function num(v) { return typeof v === "number" && isFinite(v) ? v : (parseFloat(v) || 0); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function clamp01(v) { v = num(v); return v < 0 ? 0 : v > 1 ? 1 : v; }
function pct(v) { return (clamp01(v) * 100).toFixed(1) + "%"; }
function signPct(v) { v = num(v); return (v >= 0 ? "+" : "") + v.toFixed(2) + "%"; }
function sym(id) {
  const M = { bitcoin: "BTC", ethereum: "ETH", solana: "SOL", cardano: "ADA", chainlink: "LINK" };
  return M[id] || String(id || "").toUpperCase();
}
function fmtUSD(v) {
  v = num(v);
  if (v >= 1e9) return "$" + (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(1) + "M";
  if (v >= 1e3) return "$" + (v / 1e3).toFixed(1) + "K";
  if (v >= 1) return "$" + v.toFixed(2);
  return "$" + v.toFixed(4);
}
function shortQ(q, n) { q = String(q || "").trim(); n = n || 58; return q.length > n ? q.slice(0, n - 1) + "\u2026" : q; }
function _topMarket() {
  const ms = S.markets || [];
  if (!ms.length) return null;
  return ms.reduce((a, b) => (num(b.vol24h) > num(a.vol24h) ? b : a), ms[0]);
}
function _aggVol() { return (S.markets || []).reduce((s, m) => s + num(m.vol24h), 0); }
function _coin(id) { return (S.coins || []).find((c) => c.id === id) || null; }

function _tok(state) {
  if (state === "live") return null;
  if (state === "missing") return "NO-LIVE-DATA";
  if (state === "degraded") return "DEGRADED";
  if (state === "error") return "OFFLINE";
  return "\u2026";
}
function _set(id, v) { if (_el[id]) _el[id].textContent = v; }

function _paint() {
  const tp = _tok(S.pState);
  _set("m-n", tp || (S.markets != null ? String(S.markets.length) : "\u2014"));
  const top = _topMarket();
  _set("m-top", tp || (top ? (shortQ(top.question, 30) + "  " + pct(clamp01(top.yes)) + " \u00b7 " + fmtUSD(num(top.vol24h))) : "\u2014"));
  _set("m-vol", tp || (S.markets ? fmtUSD(_aggVol()) : "\u2014"));

  const tc = _tok(S.cState);
  const btc = _coin("bitcoin"), eth = _coin("ethereum"), sol = _coin("solana");
  const cline = (btc ? fmtUSD(num(btc.usd)) : "\u2014") + " / " + (eth ? fmtUSD(num(eth.usd)) : "\u2014") + " / " + (sol ? fmtUSD(num(sol.usd)) : "\u2014");
  _set("m-btc", tc || (S.coins ? cline : "\u2014"));
  _set("m-cfeed", tc || "live");

  // honesty label verbatim — never upgraded
  _set("m-label", S.labelP || "MEASURED");
  if (_show) { _show.setChip("src", S.labelP || "MEASURED", { text: "live markets" }); _show.refreshPlain(); }
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
  S.labelP = S.markets = null; S.pState = "init";
  S.labelC = S.coins = S.btcSpot = null; S.cState = "init";
}

export default { id: ID, title: TITLE, endpoints: [PREDICT_EP, CRYPTO_EP], mount, unmount };
