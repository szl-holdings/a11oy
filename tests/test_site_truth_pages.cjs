// SPDX-License-Identifier: Apache-2.0
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const living = fs.readFileSync(path.join(root, "web", "living-anatomy.html"), "utf8");
const anatomy = fs.readFileSync(path.join(root, "pages", "anatomy-v5.html"), "utf8");

function livingScript() {
  const match = living.match(/<script>([\s\S]*?)<\/script>/i);
  assert.ok(match, "Living Anatomy must retain its inline status script");
  const start = match[1].lastIndexOf("\nload();");
  assert.ok(start > 0, "Remove only the boot call from the test copy");
  return match[1].slice(0, start);
}

async function renderLiving(honestReply) {
  const nodes = new Map(
    ["livelbl", "liveDot", "c_locked", "c_mesh", "c_brain", "m_brain",
      "c_formulas", "m_formulas", "c_ouro", "m_ouro", "scene_meta"]
      .map((id) => [id, {textContent: "", className: "", style: {}}]),
  );
  const context = {
    document: {
      getElementById: (id) => nodes.get(id),
      querySelectorAll: () => [],
    },
    fetch: async (url) => {
      if (url === "/api/a11oy/v1/honest") {
        if (honestReply instanceof Error) throw honestReply;
        return {ok: true, json: async () => honestReply};
      }
      return {ok: false};
    },
  };
  vm.createContext(context);
  vm.runInContext(livingScript(), context);
  await context.load();
  return nodes;
}

function spaceSummary(spaces, state) {
  const start = anatomy.indexOf("    function summarizeSpaceEvidence(");
  const end = anatomy.indexOf("    function paint(){", start);
  assert.ok(start >= 0 && end > start, "Anatomy must keep its evidence summarizer");
  const source = anatomy.slice(start, end).trim();
  const summarize = vm.runInNewContext(`(${source})`);
  return summarize(spaces, state);
}

test("Living Anatomy starts pending and does not claim LIVE when honesty read fails", async () => {
  assert.match(living, /id="livelbl"[^>]*>CONNECTING<\/span>/);
  assert.doesNotMatch(living, /id="livelbl"[^>]*>LIVE/);
  const nodes = await renderLiving(new Error("network unavailable"));
  assert.equal(nodes.get("livelbl").textContent, "UNAVAILABLE");
  assert.equal(nodes.get("liveDot").className, "live-dot unavailable");
});

test("Living Anatomy labels a successful honesty read OBSERVED, without inventing a SHA", async () => {
  const withSha = await renderLiving({locked_formula_count: 8, git_sha: "a".repeat(40)});
  assert.equal(withSha.get("livelbl").textContent, "OBSERVED · aaaaaaaa");
  assert.equal(withSha.get("liveDot").className, "live-dot observed");
  const withoutSha = await renderLiving({locked_formula_count: 8});
  assert.equal(withoutSha.get("livelbl").textContent, "OBSERVED");
});

test("Anatomy uses provider public count, including zero, independently of runtime probes", () => {
  const drift = spaceSummary({
    inventory: {state: "DEGRADED", observed_count: 7, canonical_count: 8},
    configured_runtime: {count: 5},
    spaces: Array(5).fill({}),
  }, "DEGRADED");
  assert.deepEqual(JSON.parse(JSON.stringify(drift)), {
    observed: 7, configured: 5, state: "DEGRADED",
  });
  const zero = spaceSummary({
    inventory: {state: "DEGRADED", observed_count: 0},
    configured_runtime: {count: 5},
  }, "DEGRADED");
  assert.equal(zero.observed, 0);
  assert.match(anatomy, /simple\(spaceEvidence\.observed\),'Public Spaces observed'/);
  assert.match(anatomy, /simple\(counts\.spaces\).*atlas inventory entries/);
});

test("Anatomy leaves public count unavailable when inventory is absent and marks cached evidence", () => {
  const missing = spaceSummary({
    inventory: {state: "UNAVAILABLE", canonical_count: 8},
    configured_runtime: {count: 5},
    spaces: Array(5).fill({}),
  }, "DEGRADED");
  assert.deepEqual(JSON.parse(JSON.stringify(missing)), {
    observed: null, configured: 5, state: "UNAVAILABLE",
  });
  const cached = spaceSummary({
    inventory: {state: "LIVE", observed_count: 8},
    configured_runtime: {count: 5},
  }, "CACHED");
  assert.equal(cached.state, "CACHED");
  assert.equal(cached.observed, 8);
  assert.doesNotMatch(anatomy, /spaceRows\.length\|\|counts\.spaces/);
});
