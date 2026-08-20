// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// check_constellation_honesty.mjs — keep the a11oy console's 3D constellation +
// 2D decision-graph block (marker `constellation-tab-patch` in pages/console.html)
// honest per Doctrine v11: it must be wired ONLY from real data.
//
// What this guards (and why)
// --------------------------
// The constellation/graph block was verified during its build with a throwaway
// headless harness that lived only in /tmp — so a future edit could quietly
// reintroduce fabricated data (Math.random coordinates, NaN/Infinity positions,
// or edges pointing at nodes that don't exist) with nothing to catch it. This
// committed check ports those assertions:
//
//   1. STATIC — the constellation block contains no `Math.random` in code
//      (comments are stripped first; the header literally says "NO Math.random").
//      Coordinates must come from the deterministic Fibonacci-sphere layout.
//   2. DYNAMIC — loading the real block against seeded fixtures yields a graph
//      whose every node has finite x/y/z (zero non-finite coordinates) and whose
//      every edge endpoint maps to a real node (zero dangling edges).
//
// The block's pure builders (cn_build / cn_layout) are closure-private, so the
// dynamic check executes the ACTUAL block in a minimal DOM/fetch sandbox, drives
// the real render path with seeded payloads, and reads back window.__cn_graph.
//
// A `--selftest` mode feeds the validators degenerate inputs (injected
// Math.random, a planted NaN coordinate, a planted dangling edge) and asserts
// each is REJECTED before the guard trusts them against the live block — the org
// guard pattern (cf. eval-arena-negative-control.yml / status-page-guard.yml).
//
// Usage:
//   node check_constellation_honesty.mjs [path/to/console.html]
//   node check_constellation_honesty.mjs --selftest
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

// ── strip /* block */ comments so the comment header ("NO Math.random") does
//    not produce a false positive. Line comments are NOT stripped because the
//    block contains URLs (https://…) whose `//` would be mangled; instead the
//    Math.random scan below tolerates that by only matching real call syntax. ──
function stripBlockComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ");
}

// ── ASSERTION 1: no Math.random in the (comment-stripped) code ──
function assertNoMathRandom(blockSrc) {
  const code = stripBlockComments(blockSrc);
  const re = /Math\s*\.\s*random/g;
  const hits = code.match(re) || [];
  return { ok: hits.length === 0, count: hits.length };
}

// ── ASSERTION 2: every node coordinate is finite ──
function assertGraphFinite(graph) {
  const bad = [];
  for (const n of graph.nodes) {
    if (!Number.isFinite(n.x) || !Number.isFinite(n.y) || !Number.isFinite(n.z)) {
      bad.push({ id: n.id, x: n.x, y: n.y, z: n.z });
    }
  }
  return { ok: bad.length === 0, bad };
}

// ── ASSERTION 3: every edge endpoint maps to a real node (no dangling edges) ──
function assertNoDanglingEdges(graph) {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const dangling = [];
  for (const e of graph.edges) {
    if (!ids.has(e.a) || !ids.has(e.b)) dangling.push(e);
  }
  return { ok: dangling.length === 0, dangling };
}

// ── seeded fixtures shaped exactly like cn_loadAll's 8 fetch payloads ──
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

// ── build a minimal DOM/fetch sandbox and run the REAL block, returning
//    window.__cn_graph after the seeded render path completes ──
async function buildGraphFromBlock(blockSrc, fixtures) {
  const fixtureFor = (url) => {
    // most-specific first so '/readiness/tab-matrix' wins over '/readiness'
    const keys = Object.keys(fixtures).sort((a, b) => b.length - a.length);
    for (const k of keys) if (String(url).indexOf(k) >= 0) return fixtures[k];
    return null;
  };
  const fetchStub = (url) => {
    const body = fixtureFor(url);
    if (body == null) {
      return Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve("not found") });
    }
    return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(body)) });
  };

  const noop = () => {};
  // container whose querySelector returns null → cn_initCanvas early-returns,
  // so no canvas stubbing is needed; window.__cn_graph is set before that point.
  const container = { innerHTML: "", querySelector: () => null };
  const documentStub = {
    readyState: "loading", // keeps injectNav from running (no retry loop)
    addEventListener: noop,
    createElement: () => ({ style: {}, setAttribute: noop, appendChild: noop, innerHTML: "" }),
    getElementById: () => null,
    querySelector: () => null,
    body: { appendChild: noop, contains: () => false },
  };
  const windowStub = {
    VIEWS: {},
    performance: globalThis.performance,
    devicePixelRatio: 1,
    addEventListener: noop,
    requestAnimationFrame: noop,
    esc: (s) => String(s == null ? "" : s),
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
    Date,
    Math,
    JSON,
    Promise,
    Number,
    String,
    Array,
    Object,
    isNaN,
    parseInt,
    parseFloat,
    location: { pathname: "/console" },
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(blockSrc, sandbox, { filename: "constellation-block.js" });

  if (typeof windowStub.cn_renderConstellation !== "function") {
    throw new Error("block did not expose window.cn_renderConstellation");
  }
  windowStub.cn_renderConstellation(container);

  // wait for the (real) async render path to populate __cn_graph
  for (let i = 0; i < 200 && !windowStub.__cn_graph; i++) {
    await new Promise((r) => setTimeout(r, 5));
  }
  if (!windowStub.__cn_graph) throw new Error("render path never populated window.__cn_graph");
  return windowStub.__cn_graph;
}

async function runGuard(htmlPath) {
  const html = fs.readFileSync(htmlPath, "utf8");
  const block = extractBlock(html);
  let failed = false;

  const mr = assertNoMathRandom(block);
  if (!mr.ok) { fail(`constellation block contains Math.random (${mr.count} occurrence(s)) — coordinates must be deterministic`); failed = true; }
  else ok("no Math.random in constellation code");

  const graph = await buildGraphFromBlock(block, seededFixtures());

  if (!(graph.nodes.length > 0)) { fail("seeded fixtures produced zero nodes — fixtures no longer exercise the layout"); failed = true; }
  else ok(`graph built: ${graph.nodes.length} nodes`);
  if (!(graph.edges.length > 0)) { fail("seeded fixtures produced zero edges — fixtures no longer exercise the edge model"); failed = true; }
  else ok(`graph built: ${graph.edges.length} edges`);

  const fin = assertGraphFinite(graph);
  if (!fin.ok) { fail(`${fin.bad.length} node(s) have non-finite coordinates: ${JSON.stringify(fin.bad.slice(0, 5))}`); failed = true; }
  else ok("all node coordinates are finite");

  const dang = assertNoDanglingEdges(graph);
  if (!dang.ok) { fail(`${dang.dangling.length} dangling edge(s): ${JSON.stringify(dang.dangling.slice(0, 5))}`); failed = true; }
  else ok("no dangling edges (every endpoint maps to a real node)");

  if (failed) { console.error("\nconstellation honesty guard FAILED"); process.exit(1); }
  console.log("\nconstellation honesty guard PASSED");
}

async function selftest() {
  let bad = false;
  const expect = (cond, msg) => { if (cond) ok("selftest: " + msg); else { fail("selftest: " + msg); bad = true; } };

  // load the real block as a positive control
  const here = path.dirname(new URL(import.meta.url).pathname);
  // resolve console.html relative to repo root (two levels up: tools/constellation-honesty/)
  const candidates = [
    path.resolve(here, "../../pages/console.html"),
    path.resolve(process.cwd(), "pages/console.html"),
    path.resolve(here, "console.html"),
  ];
  const htmlPath = candidates.find((p) => fs.existsSync(p));
  if (!htmlPath) throw new Error("selftest: could not locate pages/console.html");
  const block = extractBlock(fs.readFileSync(htmlPath, "utf8"));

  // 1. positive: real block has no Math.random
  expect(assertNoMathRandom(block).ok, "real block has no Math.random");
  // 2. negative: injected Math.random is detected (in code, not a comment)
  const tampered = block.replace("function fib(", "var _evil=Math.random();\n  function fib(");
  expect(!assertNoMathRandom(tampered).ok, "injected Math.random is REJECTED");
  // 3. negative: a comment mentioning Math.random must NOT trip the check
  const commented = "/* a note about Math.random in prose */\n" + block;
  expect(assertNoMathRandom(commented).ok, "Math.random inside a comment is tolerated");

  // build a real graph for the structural validators
  const graph = await buildGraphFromBlock(block, seededFixtures());
  // 4. positive controls
  expect(assertGraphFinite(graph).ok, "real graph has finite coordinates");
  expect(assertNoDanglingEdges(graph).ok, "real graph has no dangling edges");
  // 5. negative: planted NaN coordinate is detected
  const g1 = { nodes: graph.nodes.map((n) => ({ ...n })), edges: graph.edges };
  g1.nodes[0] = { ...g1.nodes[0], x: NaN };
  expect(!assertGraphFinite(g1).ok, "planted NaN coordinate is REJECTED");
  const g2 = { nodes: graph.nodes.map((n) => ({ ...n })), edges: graph.edges };
  g2.nodes[1] = { ...g2.nodes[1], z: Infinity };
  expect(!assertGraphFinite(g2).ok, "planted Infinity coordinate is REJECTED");
  // 6. negative: planted dangling edge is detected
  const g3 = { nodes: graph.nodes, edges: graph.edges.concat([{ a: "ghost:nonexistent", b: graph.nodes[0].id, kind: "fake" }]) };
  expect(!assertNoDanglingEdges(g3).ok, "planted dangling edge is REJECTED");

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
