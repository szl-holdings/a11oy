// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test, { after, mock } from "node:test";
import { PaymentRequiredV2Schema } from "@x402/core/schemas";
import { declareDiscoveryExtension, validateDiscoveryExtension, validateDiscoveryExtensionSpec, extractDiscoveryInfo } from "@x402/extensions/bazaar";

const config = JSON.parse(await readFile(new URL("../discovery-config.json", import.meta.url), "utf8"));
const provenance = JSON.parse(await readFile(new URL("./provenance.json", import.meta.url), "utf8"));
const source = await readFile(new URL("../worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const endpoint = "https://inference.a-11-oy.com/v1/chat/completions";
let gatewayCalls = 0;
const network = mock.method(globalThis, "fetch", async () => { throw new Error("network forbidden in discovery contract tests"); });
const response = await worker.fetch(new Request(endpoint, { method: "POST" }), {
  PAYMENT_GATEWAY: { async fetch() { gatewayCalls++; throw new Error("anonymous discovery must not invoke gateway"); } },
});
const body = await response.json();
const extension = body.extensions.bazaar;
const generated = declareDiscoveryExtension(config);
const clone = (value) => structuredClone(value);

after(() => {
  assert.equal(network.mock.calls.length, 0, "all validation must stay offline");
  assert.equal(gatewayCalls, 0, "discovery must not invoke payment or inference");
  mock.restoreAll();
});

test("complete 402 challenge passes the pinned x402 V2 schema", () => {
  assert.equal(response.status, 402);
  const parsed = PaymentRequiredV2Schema.safeParse(body);
  assert.equal(parsed.success, true, JSON.stringify(parsed.error?.issues));
});

test("advertised discovery passes protocol-level validation", () => {
  const result = validateDiscoveryExtensionSpec(extension);
  assert.equal(result.valid, true, JSON.stringify(result.errors));
});

test("advertised examples satisfy the declared JSON Schema", () => {
  const result = validateDiscoveryExtension(extension);
  assert.equal(result.valid, true, JSON.stringify(result.errors));
});

test("advertised metadata exactly equals pinned SDK generation", () => {
  assert.deepEqual(body.extensions, generated);
  assert.deepEqual(Object.keys(body.extensions), ["bazaar"]);
});

test("discovery declares POST JSON input and JSON output explicitly", () => {
  assert.equal(extension.info.input.type, "http");
  assert.equal(extension.info.input.method, "POST");
  assert.equal(extension.info.input.bodyType, "json");
  assert.equal(extension.info.output.type, "json");
  assert.equal(extension.info.input.body.stream, false);
});

test("example model is present in the timestamped registry witness", () => {
  const witness = provenance.model_registry_observation;
  assert.equal(witness.status, 200);
  assert.ok(witness.model_ids.includes(extension.info.input.body.model));
  assert.notEqual(extension.info.input.body.model, "bonsai2-27b");
  assert.equal(provenance.examples_are_fixtures, true);
  assert.equal(provenance.settlement_verified, false);
  assert.equal(provenance.catalog_indexing_verified, false);
});

test("payment header carries exactly the same metadata as the body", () => {
  const header = response.headers.get("payment-required");
  assert.ok(header);
  assert.deepEqual(JSON.parse(Buffer.from(header, "base64").toString("utf8")), body);
  assert.ok(Buffer.byteLength(header) < 16384, "project header-size budget exceeded");
});

test("resource description is at the protocol resource boundary", () => {
  assert.equal(body.resource.url, endpoint);
  assert.equal(body.resource.mimeType, "application/json");
  assert.ok(body.resource.description.length > 0);
  assert.equal(extension.description, undefined);
});

test("SDK extracts an echoed discovery declaration without a payment operation", () => {
  const fixture = { x402Version: 2, resource: body.resource, accepted: body.accepts[0], payload: {}, extensions: body.extensions };
  const discovered = extractDiscoveryInfo(fixture, body.accepts[0], true);
  assert.ok(discovered);
  assert.equal(discovered.resourceUrl, endpoint);
  assert.equal(discovered.method, "POST");
  assert.deepEqual(discovered.discoveryInfo, extension.info);
});

test("former custom envelope is rejected by the upstream validator", () => {
  const legacy = { method: "POST", input: { schema: config.inputSchema, example: config.input }, output: config.output };
  assert.equal(validateDiscoveryExtensionSpec(legacy).valid, false);
  assert.equal(validateDiscoveryExtension(legacy).valid, false);
});

const invalidBodies = [
  ["missing model", (b) => { delete b.model; }],
  ["empty model", (b) => { b.model = ""; }],
  ["missing messages", (b) => { delete b.messages; }],
  ["empty messages", (b) => { b.messages = []; }],
  ["non-array messages", (b) => { b.messages = "invalid"; }],
  ["missing message content", (b) => { delete b.messages[0].content; }],
  ["invalid role", (b) => { b.messages[0].role = "unsupported-role"; }],
  ["non-text content", (b) => { b.messages[0].content = 7; }],
  ["nonpositive token cap", (b) => { b.max_tokens = 0; }],
  ["fractional token cap", (b) => { b.max_tokens = 1.5; }],
  ["streaming outside advertised JSON contract", (b) => { b.stream = true; }],
];
for (const [label, mutate] of invalidBodies) {
  test(`SDK rejects request example with ${label}`, () => {
    const invalid = clone(extension);
    mutate(invalid.info.input.body);
    assert.equal(validateDiscoveryExtension(invalid).valid, false);
  });
}

for (const [label, mutate] of [
  ["missing input type", (e) => { delete e.info.input.type; }],
  ["wrong transport", (e) => { e.info.input.type = "rpc"; }],
  ["body method mismatch", (e) => { e.info.input.method = "GET"; }],
  ["unknown body type", (e) => { e.info.input.bodyType = "unknown"; }],
]) {
  test(`SDK rejects ${label}`, () => {
    const invalid = clone(extension);
    mutate(invalid);
    assert.equal(validateDiscoveryExtensionSpec(invalid).valid, false);
  });
}

test("SDK rejects an output example missing its format label", () => {
  const invalid = clone(extension);
  delete invalid.info.output.type;
  assert.equal(validateDiscoveryExtension(invalid).valid, false);
});

test("SDK rejects invalid completion output examples", () => {
  const invalid = clone(extension);
  invalid.info.output.example.choices = [];
  assert.equal(validateDiscoveryExtension(invalid).valid, false);
});

test("SDK refuses external schema references without a network fetch", () => {
  for (const ref of ["https://example.invalid/schema.json", "file:///not-a-real-secret", "relative-schema.json"]) {
    const invalid = clone(extension);
    invalid.schema = { $ref: ref };
    const result = validateDiscoveryExtension(invalid);
    assert.equal(result.valid, false);
    assert.match(result.errors.join(" "), /external/);
  }
});


test("published source files retain LF-only bytes under repository attributes", async () => {
  const paths = [
    "../worker.js", "../worker.test.mjs", "../README.md", "../discovery-config.json",
    "./.gitignore", "./package.json", "./package-lock.json", "./provenance.json",
    "./generate-discovery.mjs", "./discovery.test.mjs",
    "../../../.github/workflows/x402-bazaar-worker.yml",
  ];
  for (const path of paths) {
    const bytes = await readFile(new URL(path, import.meta.url));
    assert.equal(bytes.includes(13), false, `${path} contains CR bytes and cannot round-trip through LF-only checkout`);
  }
});
