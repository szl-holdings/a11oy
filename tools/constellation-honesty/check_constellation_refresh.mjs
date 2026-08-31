// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// check_constellation_refresh.mjs — keep the a11oy console's auto-refresh loops
// for the 3D constellation + 2D decision-graph block (marker
// `constellation-tab-patch` in pages/console.html) alive and leak-free.
//
// What this guards (and why)
// --------------------------
// check_constellation_honesty.mjs already proves the constellation/graph block
// is wired from real data (no Math.random, finite coords, no dangling edges).
// But the *auto-refresh* added to those tabs has no test: a future edit could
// leave a "LIVE" tab that quietly FREEZES (the interval callback dies after the
// first tick and never re-polls), or LEAKS intervals (the timer keeps firing
// after the tab is left, re-polling forever in the background). Neither would be
// caught by the honesty guard. This check ports the throwaway refresh harness
// into a committed test that asserts, by driving the REAL block in a vm sandbox:
//
//   1. RE-POLL  — the interval callback actually re-invokes the data fetch when
//      fired (the tab keeps polling, it does not silently freeze after tick #1).
//   2. TEARDOWN — once the tab is left (document.body no longer contains the
//      container), the next tick clears its interval and nulls the timer handle
//      (no leaked background polling).
//   3. NO-INTERVAL SAFE — rendering in a sandbox with NO setInterval (the guard
//      `typeof setInterval!=='function'` / `==='function'` short-circuits) must
//      complete WITHOUT throwing or falling into the block's error state.
//
// The block's refresh wiring is closure-private, so the dynamic check executes
// the ACTUAL block with a controllable fake setInterval/clearInterval (callbacks
// captured, never scheduled), a counting fetch stub, and a flippable
// document.body.contains, then fires ticks by hand and reads back the result.
//
// A `--selftest` mode feeds the probes degenerate synthetic blocks (a FROZEN
// timer that never re-polls, a LEAKING timer that never tears down, and a block
// that THROWS when setInterval is missing) and asserts each defect is REJECTED
// before the probes are trusted against the live block — the org guard pattern
// (cf. check_constellation_honesty.mjs --selftest / status-page-guard.yml).
//
// Usage:
//   node check_constellation_refresh.mjs [path/to/console.html]
//   node check_constellation_refresh.mjs --selftest
//
// Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const START_MARK = "/* constellation-tab-patch";
const END_MARK = "/* end constellation-tab-patch */";

function fail(msg) {
  console.error("FAIL: " + msg);
  process.exitCode = 1;
}
function ok(msg) {
  console.log("ok: " + msg);
}

// ── extract the constellation block from console.html ──
function extractBlock(html) {
  const i = html.indexOf(START_MARK);
  if (i < 0) throw new Error("marker `constellation-tab-patch` not found in console.html");
  const j = html.indexOf(END_MARK, i);
  if (j < 0) throw new Error("end marker `end constellation-tab-patch` not found");
  return html.slice(i, j + END_MARK.length);
}

// ── seeded fixtures shaped exactly like cn_loadAll's 8 fetch payloads (kept in
//    sync with check_constellation_honesty.mjs) ──
function seededFixtures() {
  const now = new Date().toISOString();
  return {
    "/api/a11oy/v1/readiness/tab-matrix": {
      matrix: {
        endpoints: {
          "/api/a11oy/v1/readiness": { method: "GET", schema: "obj", citationsRequired: true },
          "/api/killinchu/timeline": { method: "GET", schema: "list" },
        },
        tabs: [
          { key: "overview", title: "Overview", group: "core", endpoints: ["/api/a11oy/v1/readiness"] },
          { key: "intel", title: "Intel", group: "intel", endpoints: ["/api/killinchu/timeline"] },
        ],
      },
      verdict: {
        results: [
          { path: "/api/a11oy/v1/readiness", status: 200, p50: 12, p95: 30, freshOk: true, ageSec: 4, schemaOk: true, citationOk: true },
          { path: "/api/killinchu/timeline", status: 200, p50: 40, p95: 90, freshOk: true, ageSec: 9 },
        ],
        summary: { endpoints: 2, ok: 2, throttled: 0, lies: 0, unreachable: 0 },
        checkedAt: now,
      },
    },
    "/api/a11oy/v1/readiness": {
      sections: [
        { id: "endpoints", title: "Endpoints", kind: "endpoints", total: 2, reachable: 2, fetched_at: now },
        { id: "parity", title: "Parity", kind: "parity", build: { status: "current", behind_by: 0 } },
      ],
      citations: [{ kind: "doc", url: "https://example.org/doc", title: "doc" }],
    },
    "/api/a11oy/v1/mcp/tools": { tools: [{ name: "list_formulas" }, { name: "run_formula" }] },
    "/api/a11oy/provenance": { kernel_commit: "abc123", organ: "a11oy" },
    "/api/killinchu/watchlists": { watchlists: [{ id: 1, name: "WL-Alpha", source: "adsb" }] },
    "/api/killinchu/timeline": {
      events: [
        { id: 1, title: "ev-1", severity: "high", source: "adsb", source_url: "https://k/evt/1", ts: now, kind: "crawl" },
        { id: 2, title: "ev-2", severity: "info", source: "adsb", source_url: "https://k/evt/2", ts: now, kind: "scan" },
      ],
    },
    "/api/killinchu/alerts/recent": {
      alerts: [{ id: 1, title: "al-1", severity: "high", source_url: "https://k/evt/1", ts: now }],
    },
    "/api/killinchu/db/health": { db: { backend: "sqlite", durable: true, ping_ok: true, ping_ms: 2 } },
  };
}

// ── small async helpers (real microtask/timer draining; no fake clocks) ──
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
async function drain(n = 25) { for (let i = 0; i < n; i++) await sleep(2); }
async function pollUntil(fn, tries = 200, ms = 3) {
  for (let i = 0; i < tries; i++) { if (fn()) return true; await sleep(ms); }
  return false;
}

// ── build a controllable DOM/fetch/timer sandbox and run the block in it.
//    `withSetInterval:false` omits setInterval/clearInterval entirely so the
//    block's `typeof setInterval` guards must short-circuit. ──
function makeSandbox({ withSetInterval = true } = {}) {
  const state = { bodyContains: true, fetchCount: 0, intervals: new Map(), nextId: 1 };

  const fixtures = seededFixtures();
  const fixtureFor = (url) => {
    const keys = Object.keys(fixtures).sort((a, b) => b.length - a.length);
    for (const k of keys) if (String(url).indexOf(k) >= 0) return fixtures[k];
    return null;
  };
  const fetchStub = (url) => {
    state.fetchCount++;
    const body = fixtureFor(url);
    if (body == null) {
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve("not found") });
    }
    return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(body)) });
  };

  const noop = () => {};
  // container whose querySelector returns null → cn_initCanvas early-returns and
  // cn_softRefreshConstellation takes its "no canvas → full re-render" path; both
  // still re-poll cn_loadAll, which is all we measure here.
  const container = { innerHTML: "", querySelector: () => null, querySelectorAll: () => [] };
  const documentStub = {
    readyState: "loading", // keeps injectNav from running (no retry loop)
    addEventListener: noop,
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, innerHTML: "", querySelector: () => null }),
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    body: { appendChild: noop, contains: () => state.bodyContains },
  };
  const windowStub = {
    VIEWS: {},
    performance: globalThis.performance,
    devicePixelRatio: 1,
    addEventListener: noop,
    requestAnimationFrame: noop,
    esc: (s) => String(s == null ? "" : s),
  };

  const fakeSetInterval = (fn) => {
    const id = state.nextId++;
    state.intervals.set(id, { fn, cleared: false });
    return id;
  };
  const fakeClearInterval = (id) => {
    const it = state.intervals.get(id);
    if (it) it.cleared = true;
  };

  const sandbox = {
    window: windowStub,
    document: documentStub,
    fetch: fetchStub,
    requestAnimationFrame: noop,
    setTimeout,
    clearTimeout,
    performance: globalThis.performance,
    console: { log: noop, warn: noop, error: noop },
    Date, Math, JSON, Promise, Number, String, Array, Object,
    isNaN, parseInt, parseFloat,
    location: { pathname: "/console" },
  };
  if (withSetInterval) {
    sandbox.setInterval = fakeSetInterval;
    sandbox.clearInterval = fakeClearInterval;
  }
  sandbox.globalThis = sandbox;
  return { sandbox, state, windowStub, documentStub, container };
}

function loadBlock(env, blockSrc) {
  vm.createContext(env.sandbox);
  vm.runInContext(blockSrc, env.sandbox, { filename: "constellation-refresh-block.js" });
}

// ── probe one tab's refresh loop: does it re-poll on tick, and tear down on
//    leave? Returns { registered, repolls, tearsDown }. ──
async function probeRefresh(blockSrc, { renderFn, timerGlobal }) {
  const env = makeSandbox({ withSetInterval: true });
  loadBlock(env, blockSrc);
  const w = env.windowStub;
  if (typeof w[renderFn] !== "function") {
    throw new Error("block did not expose window." + renderFn);
  }

  // initial render registers the auto-refresh interval (inside an async .then)
  w[renderFn](env.container);
  const registered = await pollUntil(() => w[timerGlobal] != null);
  const result = { registered, repolls: false, tearsDown: false };
  if (!registered) return result;

  // RE-POLL: fire the interval callback with the tab still mounted; the data
  // fetch must run again (the loop is alive, it did not freeze after tick #1).
  await drain(5);
  const before = env.state.fetchCount;
  const it1 = env.state.intervals.get(w[timerGlobal]);
  if (it1 && !it1.cleared) it1.fn();
  await drain(25);
  result.repolls = env.state.fetchCount > before;

  // TEARDOWN: leave the tab; the next tick must clear the interval + null the
  // handle so nothing keeps polling in the background.
  env.state.bodyContains = false;
  const id2 = w[timerGlobal]; // may have been re-registered by the re-render
  const it2 = env.state.intervals.get(id2);
  if (it2 && !it2.cleared) it2.fn();
  await drain(5);
  result.tearsDown = !!(it2 && it2.cleared) && w[timerGlobal] === null;
  return result;
}

// ── probe that rendering one tab in a NO-setInterval sandbox neither throws
//    synchronously nor lands in the block's error state. ──
async function probeNoIntervalSafe(blockSrc, renderFn) {
  const env = makeSandbox({ withSetInterval: false });
  const out = { threw: false, errorState: false, rendered: false };
  try {
    loadBlock(env, blockSrc);
    const w = env.windowStub;
    if (typeof w[renderFn] === "function") w[renderFn](env.container);
    await drain(25);
    out.rendered = w.__cn_graph != null;
    out.errorState = /unavailable/i.test(String(env.container.innerHTML || ""));
  } catch (e) {
    out.threw = true;
    out.error = String((e && e.message) || e);
  }
  return out;
}

const TABS = [
  { name: "constellation (3D)", renderFn: "cn_renderConstellation", timerGlobal: "__cn_con_timer" },
  { name: "decision graphs (2D)", renderFn: "cn_renderGraphs", timerGlobal: "__cn_gr_timer" },
];

async function runGuard(htmlPath) {
  const html = fs.readFileSync(htmlPath, "utf8");
  const block = extractBlock(html);
  let failed = false;

  for (const tab of TABS) {
    const r = await probeRefresh(block, tab);
    if (!r.registered) { fail(`${tab.name}: render did not register an auto-refresh interval (${tab.timerGlobal} never set)`); failed = true; }
    else ok(`${tab.name}: auto-refresh interval registered`);
    if (!r.repolls) { fail(`${tab.name}: interval tick did NOT re-invoke the data fetch — the tab would silently freeze`); failed = true; }
    else ok(`${tab.name}: interval tick re-polls the real data fetch`);
    if (!r.tearsDown) { fail(`${tab.name}: leaving the tab did NOT clear the interval — leaked background polling`); failed = true; }
    else ok(`${tab.name}: leaving the tab clears the interval and nulls ${tab.timerGlobal}`);

    const s = await probeNoIntervalSafe(block, tab.renderFn);
    if (s.threw) { fail(`${tab.name}: rendering in a no-setInterval sandbox threw: ${s.error}`); failed = true; }
    else if (s.errorState) { fail(`${tab.name}: rendering in a no-setInterval sandbox fell into the block's error state`); failed = true; }
    else if (!s.rendered) { fail(`${tab.name}: rendering in a no-setInterval sandbox never populated the graph`); failed = true; }
    else ok(`${tab.name}: renders cleanly in a no-setInterval sandbox`);
  }

  if (failed) { console.error("\nconstellation refresh guard FAILED"); process.exit(1); }
  console.log("\nconstellation refresh guard PASSED");
}

// ── synthetic negative-control blocks: each exposes the constellation contract
//    but with a single planted defect the probes must reject. ──
const FROZEN_BLOCK = `(function(){
  window.cn_renderConstellation=function(c){
    fetch('/api/a11oy/v1/readiness');               // initial poll
    window.__cn_con_timer=setInterval(function(){   // FROZEN: callback never re-polls
      if(!document.body.contains(c)){ clearInterval(window.__cn_con_timer); window.__cn_con_timer=null; return; }
      /* dies here — no fetch */
    }, 30000);
  };
})();`;

const LEAK_BLOCK = `(function(){
  window.cn_renderConstellation=function(c){
    fetch('/api/a11oy/v1/readiness');               // initial poll
    window.__cn_con_timer=setInterval(function(){   // LEAK: never checks body, never clears
      fetch('/api/a11oy/v1/readiness');
    }, 30000);
  };
})();`;

const THROWS_BLOCK = `(function(){
  window.cn_renderConstellation=function(c){
    setInterval(function(){}, 30000);               // no typeof guard → throws when setInterval is absent
  };
})();`;

async function selftest() {
  let bad = false;
  const expect = (cond, msg) => { if (cond) ok("selftest: " + msg); else { fail("selftest: " + msg); bad = true; } };

  // locate the real console.html as a positive control
  const here = path.dirname(new URL(import.meta.url).pathname);
  const candidates = [
    path.resolve(here, "../../pages/console.html"),
    path.resolve(process.cwd(), "pages/console.html"),
    path.resolve(here, "console.html"),
  ];
  const htmlPath = candidates.find((p) => fs.existsSync(p));
  if (!htmlPath) throw new Error("selftest: could not locate pages/console.html");
  const block = extractBlock(fs.readFileSync(htmlPath, "utf8"));

  const con = { renderFn: "cn_renderConstellation", timerGlobal: "__cn_con_timer" };

  // 1. positive controls: the real block re-polls, tears down, and is no-interval safe
  for (const tab of TABS) {
    const r = await probeRefresh(block, tab);
    expect(r.registered, `real ${tab.name} registers an interval`);
    expect(r.repolls, `real ${tab.name} re-polls on tick`);
    expect(r.tearsDown, `real ${tab.name} tears down on leave`);
    const s = await probeNoIntervalSafe(block, tab.renderFn);
    expect(!s.threw && !s.errorState && s.rendered, `real ${tab.name} renders in a no-setInterval sandbox`);
  }

  // 2. negative: a FROZEN timer (never re-polls) is REJECTED
  const frozen = await probeRefresh(FROZEN_BLOCK, con);
  expect(frozen.registered && !frozen.repolls, "a frozen interval (no re-poll) is REJECTED");

  // 3. negative: a LEAKING timer (never tears down) is REJECTED
  const leak = await probeRefresh(LEAK_BLOCK, con);
  expect(leak.registered && leak.repolls && !leak.tearsDown, "a leaking interval (no teardown) is REJECTED");

  // 4. negative: a block that THROWS without a setInterval guard is REJECTED
  const thrown = await probeNoIntervalSafe(THROWS_BLOCK, "cn_renderConstellation");
  expect(thrown.threw, "an unguarded setInterval (throws when absent) is REJECTED");

  if (bad) { console.error("\nselftest FAILED"); process.exit(1); }
  console.log("\nselftest PASSED");
}

const arg = process.argv[2];
if (arg === "--selftest") {
  selftest().catch((e) => { fail(String((e && e.stack) || e)); process.exit(1); });
} else {
  const htmlPath = arg || path.resolve(process.cwd(), "pages/console.html");
  runGuard(htmlPath).catch((e) => { fail(String((e && e.stack) || e)); process.exit(1); });
}
