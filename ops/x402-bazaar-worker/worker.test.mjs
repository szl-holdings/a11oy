// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const URL_BASE = "https://inference.a-11-oy.com/v1/chat/completions";
const payload = JSON.stringify({ model: "fixture-model", messages: [{ role: "user", content: "fixture" }] });
const settlement = Buffer.from(JSON.stringify({ success: true, network: "eip155:8453", transaction: "fixture-transaction-not-a-real-payment" })).toString("base64");
function request(headers = {}, method = "POST", url = URL_BASE) {
  return new Request(url, { method, headers, ...(["GET", "HEAD", "OPTIONS"].includes(method) ? {} : { body: payload }) });
}
function blockNetwork(t) {
  return t.mock.method(globalThis, "fetch", async () => new Response("UNVERIFIED_ORIGIN_FIXTURE"));
}
function gateway(response) {
  const calls = [];
  return { calls, env: { PAYMENT_GATEWAY: { async fetch(req) { calls.push(req); return response; } } } };
}

test("unpaid request remains 402 without contacting any upstream", async (t) => {
  const net = blockNetwork(t);
  const g = gateway(new Response("fixture"));
  const r = await worker.fetch(request(), g.env);
  assert.equal(r.status, 402);
  assert.equal(net.mock.calls.length, 0);
  assert.equal(g.calls.length, 0);
});

test("PAYMENT-REQUIRED decodes to the exact response JSON", async (t) => {
  blockNetwork(t);
  const r = await worker.fetch(request(), {});
  const header = r.headers.get("payment-required");
  assert.ok(header, "v2 clients require PAYMENT-REQUIRED");
  assert.deepEqual(JSON.parse(Buffer.from(header, "base64").toString("utf8")), await r.json());
});

test("quoted payment terms are unchanged", async (t) => {
  blockNetwork(t);
  const b = await (await worker.fetch(request(), {})).json();
  assert.equal(b.x402Version, 2);
  assert.equal(b.accepts.length, 1);
  assert.deepEqual(b.accepts[0], { scheme: "exact", network: "eip155:8453", amount: "20000", asset: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", payTo: "0x7b133ef996852c223379d6d1245430300970291A", maxTimeoutSeconds: 3600, extra: { name: "USD Coin", version: "2" } });
  assert.ok(b.extensions.bazaar);
});

for (const value of ["1", "0", "", "untrusted"]) {
  test(`reserved caller header is rejected (${JSON.stringify(value)})`, async (t) => {
    const net = blockNetwork(t);
    const g = gateway(new Response("fixture"));
    const r = await worker.fetch(request({ "x-szl-bazaar-passthrough": value, "payment-signature": "fixture-only" }), g.env);
    assert.equal(r.status, 400);
    assert.equal(net.mock.calls.length, 0);
    assert.equal(g.calls.length, 0);
  });
}

test("browser preflight is 204 without payment or inference", async (t) => {
  const net = blockNetwork(t);
  const g = gateway(new Response("fixture"));
  const r = await worker.fetch(request({ origin: "https://a-11-oy.com", "access-control-request-method": "POST", "access-control-request-headers": "Content-Type, Payment-Signature, X-PAYMENT" }, "OPTIONS"), g.env);
  assert.equal(r.status, 204);
  assert.equal(await r.text(), "");
  assert.equal(r.headers.get("access-control-allow-origin"), "*");
  assert.equal(r.headers.get("access-control-allow-credentials"), null);
  assert.match(r.headers.get("access-control-allow-headers"), /PAYMENT-SIGNATURE/i);
  assert.equal(g.calls.length + net.mock.calls.length, 0);
});

test("preflight rejects unsupported methods and headers", async (t) => {
  const net = blockNetwork(t);
  assert.equal((await worker.fetch(request({ "access-control-request-method": "DELETE" }, "OPTIONS"), {})).status, 405);
  assert.equal((await worker.fetch(request({ "access-control-request-headers": "x-szl-bazaar-passthrough" }, "OPTIONS"), {})).status, 400);
  assert.equal(net.mock.calls.length, 0);
});

for (const method of ["GET", "PUT", "DELETE"]) {
  test(`${method} is not an inference method`, async (t) => {
    const net = blockNetwork(t);
    const r = await worker.fetch(request({}, method), {});
    assert.equal(r.status, 405);
    assert.equal(r.headers.get("allow"), "POST, OPTIONS");
    assert.equal(net.mock.calls.length, 0);
  });
}

test("other paths are not claimed", async (t) => {
  const net = blockNetwork(t);
  assert.equal((await worker.fetch(request({}, "POST", "https://inference.a-11-oy.com/v1/models"), {})).status, 404);
  assert.equal(net.mock.calls.length, 0);
});

test("empty payment header is unpaid", async (t) => {
  const net = blockNetwork(t);
  assert.equal((await worker.fetch(request({ "payment-signature": "  " }), {})).status, 402);
  assert.equal(net.mock.calls.length, 0);
});

test("payment-bearing request with no trusted binding fails closed", async (t) => {
  const net = blockNetwork(t);
  for (const env of [undefined, {}, { PAYMENT_GATEWAY: {} }]) {
    assert.equal((await worker.fetch(request({ "payment-signature": "fixture-only" }), env)).status, 503);
  }
  assert.equal(net.mock.calls.length, 0);
});

test("payment-bearing request uses only explicit service binding", async (t) => {
  const net = blockNetwork(t);
  const g = gateway(new Response("fixture-completion", { headers: { "payment-response": settlement, "extension-responses": "fixture-extension" } }));
  const r = await worker.fetch(request({ "payment-signature": "fixture-only" }), g.env);
  assert.equal(g.calls.length, 1);
  assert.equal(g.calls[0].url, URL_BASE);
  assert.equal(g.calls[0].method, "POST");
  assert.equal(g.calls[0].redirect, "manual");
  assert.equal(g.calls[0].headers.get("payment-signature"), "fixture-only");
  assert.equal(g.calls[0].headers.get("x-szl-bazaar-passthrough"), null);
  assert.equal(await g.calls[0].text(), payload);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), "fixture-completion");
  assert.equal(r.headers.get("payment-response"), settlement);
  assert.match(r.headers.get("access-control-expose-headers"), /EXTENSION-RESPONSES/);
  assert.equal(net.mock.calls.length, 0);
});

test("legacy header is forwarded unchanged to verifier, not locally accepted", async (t) => {
  const net = blockNetwork(t);
  const g = gateway(new Response("rejected-fixture", { status: 402 }));
  const r = await worker.fetch(request({ "X-PAYMENT": "legacy-fixture" }), g.env);
  assert.equal(r.status, 402);
  assert.equal(g.calls[0].headers.get("X-PAYMENT"), "legacy-fixture");
  assert.equal(net.mock.calls.length, 0);
});

for (const status of [401, 402, 403, 429, 500]) {
  test(`gateway ${status} is preserved, never relabeled as success`, async (t) => {
    const net = blockNetwork(t);
    const g = gateway(new Response("denied-fixture", { status }));
    const r = await worker.fetch(request({ "payment-signature": "fixture-only" }), g.env);
    assert.equal(r.status, status);
    assert.equal(await r.text(), "denied-fixture");
    assert.equal(r.headers.get("cache-control"), "private, no-store");
    assert.equal(net.mock.calls.length, 0);
  });
}

test("gateway redirects never escape the verification boundary", async (t) => {
  const net = blockNetwork(t);
  const g = gateway(new Response(null, { status: 302, headers: { location: "https://example.invalid/raw-origin" } }));
  const r = await worker.fetch(request({ "payment-signature": "fixture-only" }), g.env);
  assert.equal(r.status, 502);
  assert.equal(r.headers.get("location"), null);
  assert.equal(net.mock.calls.length, 0);
});

test("upstream failure is bounded and does not disclose exception text", async (t) => {
  const net = blockNetwork(t);
  const r = await worker.fetch(request({ "payment-signature": "fixture-only" }), { PAYMENT_GATEWAY: { async fetch() { throw new Error("PRIVATE_FIXTURE_MUST_NOT_LEAK"); } } });
  assert.equal(r.status, 502);
  assert.doesNotMatch(await r.text(), /PRIVATE_FIXTURE/);
  assert.equal(net.mock.calls.length, 0);
});

test("successful content requires a plausible successful settlement response", async (t) => {
  const net = blockNetwork(t);
  for (const header of [null, "", "not-base64", Buffer.from(JSON.stringify({ success: false })).toString("base64"), Buffer.from(JSON.stringify({ success: true, network: "wrong-network", transaction: "fixture" })).toString("base64")]) {
    const g = gateway(new Response("unverified-fixture", { headers: header === null ? {} : { "payment-response": header } }));
    const r = await worker.fetch(request({ "payment-signature": "fixture-only" }), g.env);
    assert.equal(r.status, 502);
    assert.doesNotMatch(await r.text(), /unverified-fixture/);
  }
  assert.equal(net.mock.calls.length, 0);
});

test("all local responses are non-cacheable and browser-readable", async (t) => {
  blockNetwork(t);
  for (const req of [request(), request({}, "GET"), request({ "payment-signature": "fixture-only" })]) {
    const r = await worker.fetch(req, {});
    assert.equal(r.headers.get("cache-control"), "private, no-store");
    assert.equal(r.headers.get("access-control-allow-origin"), "*");
    assert.equal(r.headers.get("access-control-allow-credentials"), null);
  }
});

import { compareUnpaidChallenge, probeLive } from "./live-witness.mjs";

test("read-only witness matches source terms but never claims settlement", async (t) => {
  blockNetwork(t);
  const baseline = await (await worker.fetch(request(), {})).json();
  const encoded = Buffer.from(JSON.stringify(baseline)).toString("base64");
  assert.deepEqual(compareUnpaidChallenge(baseline, 402, encoded), {
    state: "MATCHED_UNPAID_PROTOCOL_ONLY", reason: "SOURCE_LIVE_CHALLENGE_PARITY",
  });
  const calls = [];
  const result = await probeLive(async (url, options) => {
    calls.push({ url, options });
    return new Response(null, { status: 402, headers: { "payment-required": encoded } });
  });
  assert.equal(result.state, "MATCHED_UNPAID_PROTOCOL_ONLY");
  assert.equal(result.http_status, 402);
  assert.match(result.source_worker_sha256, /^[a-f0-9]{64}$/);
  assert.equal(result.payment_settlement_verified, false);
  assert.equal(result.live_inference_verified, false);
  assert.equal(result.deployment_source_parity_verified, false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, URL_BASE);
  assert.equal(calls[0].options.method, "HEAD");
  assert.equal(calls[0].options.redirect, "manual");
  assert.equal(calls[0].options.headers, undefined);
});

test("witness refuses price, payee, network, URL, or atomic-unit drift", async (t) => {
  blockNetwork(t);
  const baseline = await (await worker.fetch(request(), {})).json();
  const edits = [
    (x) => { x.accepts[0].amount = "20001"; },
    (x) => { x.accepts[0].payTo = "different-payee"; },
    (x) => { x.accepts[0].network = "eip155:1"; },
    (x) => { x.accepts[0].asset = "different-asset"; },
    (x) => { x.resource.url = "https://another.example/v1/chat/completions"; },
    (x) => { x.x402Version = 1; },
  ];
  for (const edit of edits) {
    const altered = structuredClone(baseline);
    edit(altered);
    const encoded = Buffer.from(JSON.stringify(altered)).toString("base64");
    const decision = compareUnpaidChallenge(baseline, 402, encoded);
    assert.equal(decision.state, "DRIFT");
  }
});

test("witness fails closed on bad status and malformed headers", async (t) => {
  blockNetwork(t);
  const baseline = await (await worker.fetch(request(), {})).json();
  for (const header of [null, "", "not-base64!!", "e30=", "eyJ4NDAyVmVyc2lvbiI6MX0="]) {
    assert.equal(compareUnpaidChallenge(baseline, 402, header).state, "DRIFT");
  }
  const encoded = Buffer.from(JSON.stringify(baseline)).toString("base64");
  assert.deepEqual(compareUnpaidChallenge(baseline, 200, encoded), {
    state: "DRIFT", reason: "UNPAID_STATUS_NOT_402",
  });
  const failed = await probeLive(async () => { throw new Error("PRIVATE_ERROR"); });
  assert.equal(failed.state, "UNAVAILABLE");
  assert.equal(failed.reason, "NETWORK_OR_TIMEOUT");
  assert.equal(failed.http_status, null);
  assert.equal(failed.payment_settlement_verified, false);
  assert.doesNotMatch(JSON.stringify(failed), /PRIVATE_ERROR/);
});
