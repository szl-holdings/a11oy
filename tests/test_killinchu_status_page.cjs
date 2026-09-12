// SPDX-License-Identifier: Apache-2.0
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const html = fs.readFileSync(
  path.join(__dirname, "..", "pages", "killinchu.html"),
  "utf8",
);
const match = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(match, "Killinchu page must contain one executable inline script");
const source = match[1].replace(/\nboot\(\);\s*$/, "\n");

function livePayload() {
  return {
    state: "LIVE",
    fetchedAt: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    spaces: [{
      name: "killinchu",
      slug: "killinchu",
      url: "https://szlholdings-killinchu.hf.space",
      state: "LIVE",
      stage: "RUNNING",
      app_reachable: true,
      app_status: 200,
      contract_state: "LIVE",
      contracts: [
        {id: "api_health", state: "LIVE"},
        {id: "healthz", state: "LIVE"},
      ],
    }],
  };
}

async function render(payload, responseOk = true) {
  const nodes = {
    st: {textContent: "TWIN UNAVAILABLE"},
    detail: {textContent: "Awaiting inventory"},
  };
  let request;
  const context = {
    Array,
    Date,
    Error,
    Number,
    Set,
    document: {getElementById: (id) => nodes[id]},
    fetch: async (url, options) => {
      request = {url, options};
      return {ok: responseOk, json: async () => payload};
    },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  await context.boot();
  return {nodes, request};
}

test("fresh exact Space and both health contracts are required for LIVE", async () => {
  const result = await render(livePayload());
  assert.equal(result.nodes.st.textContent, "TWIN LIVE");
  assert.match(result.nodes.detail.textContent, /contracts observed/);
  assert.match(result.nodes.detail.textContent, /observed \d{4}-\d{2}-\d{2}T/);
  assert.equal(result.request.url, "/api/a11oy/v1/spaces/health");
  assert.deepEqual(
    JSON.parse(JSON.stringify(result.request.options)),
    {headers: {accept: "application/json"}, cache: "no-store", credentials: "omit"},
  );
});

test("cached observation never renders LIVE", async () => {
  const payload = livePayload();
  payload.state = "CACHED";
  payload.cached_state = "LIVE";
  const result = await render(payload);
  assert.equal(result.nodes.st.textContent, "TWIN CACHED");
  assert.match(result.nodes.detail.textContent, /snapshot CACHED \(prior LIVE\)/);
});

test("missing or failed Killinchu health contract stays degraded", async () => {
  for (const contracts of [
    [{id: "api_health", state: "LIVE"}],
    [{id: "api_health", state: "LIVE"}, {id: "healthz", state: "UNAVAILABLE"}],
    [{id: "api_health", state: "LIVE"}, {id: "unexpected", state: "LIVE"}],
  ]) {
    const payload = livePayload();
    payload.spaces[0].contracts = contracts;
    const result = await render(payload);
    assert.equal(result.nodes.st.textContent, "TWIN DEGRADED");
    assert.match(result.nodes.detail.textContent, /contracts unavailable/);
  }
});

test("fresh aggregate drift does not hide an exact live Killinchu row", async () => {
  const payload = livePayload();
  payload.state = "DEGRADED";
  const result = await render(payload);
  assert.equal(result.nodes.st.textContent, "TWIN LIVE");
  assert.match(result.nodes.detail.textContent, /snapshot DEGRADED/);
});

test("malformed, missing, or transport-unavailable evidence fails closed", async () => {
  const stale = livePayload();
  stale.fetchedAt = "2026-01-01T00:00:00Z";
  for (const [payload, ok] of [
    [{state: "LIVE", spaces: []}, true],
    [{state: "LIVE", fetchedAt: "not-a-time", spaces: []}, true],
    [stale, true],
    [livePayload(), false],
  ]) {
    const result = await render(payload, ok);
    assert.equal(result.nodes.st.textContent, "TWIN UNAVAILABLE");
    assert.equal(
      result.nodes.detail.textContent,
      "Space inventory unavailable; no runtime claim made.",
    );
  }
});
