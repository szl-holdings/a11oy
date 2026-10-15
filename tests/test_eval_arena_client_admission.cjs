// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"use strict";
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { runInNewContext } = require("node:vm");
const test = require("node:test");

const ROOT = join(__dirname, "..");
const TOKEN = "eval-client-test-only-credential";

function isolatedClient() {
  const fields = new Map();
  const requests = [];
  const field = (id) => {
    if (!fields.has(id)) fields.set(id, { value: "", textContent: "", innerHTML: "", disabled: false });
    return fields.get(id);
  };
  const context = {
    window: {}, V: {}, API: "", GOLD: "", LAMBDA_NOTE: "",
    E: field,
    H: (id, value) => { field(id).innerHTML = value; },
    esc: (value) => String(value),
    chip: () => "",
    AbortController, setTimeout, clearTimeout,
    fetch: async (url, options) => {
      requests.push({ url, options });
      // A synthetic refusal keeps response presentation outside this request
      // contract. No provider, signer, forum, or network function is connected.
      return { ok: false, status: 401, text: async () => '{"status":"BLOCKED"}' };
    },
  };
  return { field, requests, context };
}

function assertExplicitRequest(request) {
  assert.equal(request.url, "/api/a11oy/v1/eval/run");
  assert.equal(request.options.method, "POST");
  assert.equal(request.options.redirect, "error");
  assert.equal(request.options.credentials, "same-origin");
  assert.equal(request.options.cache, "no-store");
  assert.equal(request.options.headers.authorization, "Bearer " + TOKEN);
  assert.deepEqual(JSON.parse(request.options.body), {
    suite: "core_honest_v1", model_id: "test-model", execution_mode: "live",
  });
}

test("console one-shot sends explicit live admission and clears its credential", async () => {
  const fixture = isolatedClient();
  const source = readFileSync(join(ROOT, "pages/console.html"), "utf8");
  const start = source.indexOf("var FLYEVAL_RUN_PATH=");
  const end = source.indexOf("/* ============================ RAG", start);
  assert.ok(start >= 0 && end > start, "evaluation client block must remain discoverable");
  runInNewContext(source.slice(start, end), fixture.context, { timeout: 1000 });
  fixture.field("fe-token").value = TOKEN;
  fixture.field("fe-suite").value = "core_honest_v1";
  fixture.field("fe-model").value = "test-model";
  assert.equal(fixture.requests.length, 0, "loading definitions must not evaluate");
  await fixture.context.window.flyeval_run();
  assert.equal(fixture.requests.length, 1);
  assertExplicitRequest(fixture.requests[0]);
  assert.equal(fixture.field("fe-token").value, "");
});

test("3D one-shot sends explicit live admission and clears its credential", async () => {
  const fixture = isolatedClient();
  const source = readFileSync(join(ROOT, "static/3d/surfaces/evalarena.js"), "utf8");
  const script = source.replace(/^import .*;\s*$/m, "")
    .replace(/^export default /m, "globalThis.surface = ");
  runInNewContext(script + `
    globalThis.invoke = async (fields) => {
      _overlay = { querySelector: (selector) => fields(selector.slice(1)) };
      await _runEvalOnce();
    };`, fixture.context, { timeout: 1000 });
  fixture.field("ea-token").value = TOKEN;
  fixture.field("ea-suite-input").value = "core_honest_v1";
  fixture.field("ea-model-input").value = "test-model";
  assert.equal(fixture.requests.length, 0, "loading definitions must not evaluate");
  await fixture.context.invoke(fixture.field);
  assert.equal(fixture.requests.length, 1);
  assertExplicitRequest(fixture.requests[0]);
  assert.equal(fixture.field("ea-token").value, "");
});
