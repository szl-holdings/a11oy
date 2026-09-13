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
function inlineScriptSource(documentHtml) {
  const match = documentHtml.match(/<script>([\s\S]*?)<\/script>/i);
  assert.ok(match, "Killinchu page must contain one executable inline script");
  return match[1].replace(/\nboot\(\);\s*$/, "\n");
}

const source = inlineScriptSource(html);

test("inline script extraction is case-insensitive for HTML tags", () => {
  assert.equal(
    inlineScriptSource("<SCRIPT>const marker = 1;\nboot();</SCRIPT>"),
    "const marker = 1;\n",
  );
});

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

// Navigation is separate from runtime readiness: a failed observation must not
// strand visitors on the status page or require JavaScript to discover the app.
function assertShowcaseLinks(documentHtml) {
  const staticHtml = documentHtml.split(/<script\b/i, 1)[0];
  const nav = staticHtml.match(/<nav\b[^>]*aria-label="Killinchu showcase"[^>]*>([\s\S]*?)<\/nav>/i);
  assert.ok(nav, "Showcase navigation must exist before JavaScript executes");
  const anchors = [...nav[1].matchAll(/<a\b([^>]*)>([^<]+)<\/a>/gi)];
  assert.equal(anchors.length, 2, "Keep exactly the runtime and its existing Space");
  assert.deepEqual(anchors.map((match) => {
    assert.doesNotMatch(match[1], /\b(?:hidden|inert|onclick|style)\s*(?:=|$)/i);
    assert.match(match[1], /rel="external noopener noreferrer"/);
    const href = match[1].match(/\bhref="([^"]+)"/);
    assert.ok(href, "Each launch control must be a real anchor");
    return [href[1], match[2].trim()];
  }), [
    ["https://szlholdings-killinchu.hf.space/elite", "Open interactive Killinchu demo"],
    ["https://huggingface.co/spaces/SZLHOLDINGS/killinchu", "View Hugging Face Space"],
  ]);
}

test("showcase launch controls are fixed-origin anchors without JavaScript", () => {
  assertShowcaseLinks(html);
});

test("showcase contract rejects a removed or replaced runtime destination", () => {
  assert.throws(() => assertShowcaseLinks(html.replace(
    "https://szlholdings-killinchu.hf.space/elite", "https://example.invalid/elite",
  )));
  assert.throws(() => assertShowcaseLinks(html.replace(
    /<nav\b[^>]*aria-label="Killinchu showcase"[^>]*>[\s\S]*?<\/nav>/i, "",
  )));
});

test("showcase links preserve product canonical and do not redirect automatically", () => {
  assert.match(html, /<link rel="canonical" href="https:\/\/a-11-oy\.com\/killinchu"\/>/);
  assert.doesNotMatch(html, /http-equiv=["']refresh["']/i);
  assert.doesNotMatch(source, /\blocation\.(?:assign|replace|href)\b/);
  assert.match(html, /min-height:44px/);
  assert.match(html, /\.showcase-actions a:focus-visible/);
});

test("failed runtime observation leaves the showcase controls available", async () => {
  const result = await render(livePayload(), false);
  assert.equal(result.nodes.st.textContent, "TWIN UNAVAILABLE");
  assertShowcaseLinks(html);
  assert.doesNotMatch(source, /showcase-actions|querySelector|innerHTML/);
});
