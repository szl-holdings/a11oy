// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("./worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const BASE = "https://reference.invalid";
const payload = JSON.stringify({ model: "fixture-model", messages: [{ role: "user", content: "fixture" }] });

function request(path = "/v1/inference", { method = "POST", headers = {} } = {}) {
  return new Request(BASE + path, {
    method, headers,
    ...(["GET", "HEAD", "OPTIONS"].includes(method) ? {} : { body: payload }),
  });
}

function observeSideEffects(t) {
  // Responses and headers below are fixtures, never payment or settlement evidence.
  const network = t.mock.method(globalThis, "fetch", async () => new Response("UNVERIFIED_ORIGIN_FIXTURE"));
  const uuid = t.mock.method(globalThis.crypto, "randomUUID", () => "fixture-not-a-receipt");
  const gateway = t.mock.fn(async () => new Response("UNVERIFIED_GATEWAY_FIXTURE"));
  return {
    env: { PAYMENT_GATEWAY: { fetch: gateway } },
    assertNone() {
      assert.equal(network.mock.calls.length, 0, "reference must never contact an origin");
      assert.equal(gateway.mock.calls.length, 0, "an environment object must not activate the reference");
      assert.equal(uuid.mock.calls.length, 0, "reference must not mint a receipt identifier");
    },
  };
}

function assertNoPaidClaims(response) {
  for (const name of [
    "payment-required", "payment-response", "payment-settlement",
    "x-ouroboros-passport-digest", "x-ouroboros-promotion",
    "x-ouroboros-model-revision", "x-ouroboros-receipt-id",
  ]) {
    assert.equal(response.headers.get(name), null, name);
  }
  assert.equal(response.headers.get("cache-control"), "private, no-store");
}

test("payment-shaped input never unlocks the reference origin", async (t) => {
  const effects = observeSideEffects(t);
  for (const headers of [
    {},
    { "X-PAYMENT": "" },
    { "X-PAYMENT": "arbitrary-nonempty-fixture" },
    { "PAYMENT-SIGNATURE": "fixture-only" },
    { "PAYMENT-CONTEXT": "fixture.invalid.signature" },
    {
      "X-PAYMENT": "fixture-only",
      "PAYMENT-RESPONSE": Buffer.from(JSON.stringify({ success: true, transaction: "fixture-not-a-payment" })).toString("base64"),
      "X-Ouroboros-Passport-Digest": "a".repeat(64),
      "X-Ouroboros-Promotion": "PROMOTED",
    },
  ]) {
    const req = request("/v1/inference", { headers });
    const result = await worker.fetch(req, effects.env);
    assert.equal(result.status, 503);
    assert.deepEqual(await result.json(), {
      error: "reference_gateway_unconfigured",
      state: "BLOCKED",
    });
    assert.equal(req.bodyUsed, false);
    assertNoPaidClaims(result);
  }
  effects.assertNone();
});

test("model selection cannot activate placeholder or inherited catalog entries", async (t) => {
  const effects = observeSideEffects(t);
  for (const model of ["ternary-bonsai-2-27b-pq2_0", "unknown", "__proto__", "constructor"]) {
    const result = await worker.fetch(request("/v1/inference?model=" + model, {
      headers: { "X-PAYMENT": "fixture-only" },
    }), effects.env);
    assert.equal(result.status, 503);
    assertNoPaidClaims(result);
  }
  effects.assertNone();
});

test("catalog advertises no admitted model, placeholder digest, or payment price", async (t) => {
  const effects = observeSideEffects(t);
  const result = await worker.fetch(request("/v1/models", { method: "GET" }), effects.env);
  assert.equal(result.status, 200);
  assert.deepEqual(await result.json(), { object: "list", data: [], state: "BLOCKED" });
  assertNoPaidClaims(result);
  effects.assertNone();
});

test("route methods are bounded and cannot trigger inference", async (t) => {
  const effects = observeSideEffects(t);
  for (const [path, allowed, methods] of [
    ["/v1/models", "GET, OPTIONS", ["POST", "PUT", "DELETE"]],
    ["/v1/inference", "POST, OPTIONS", ["GET", "PUT", "DELETE"]],
  ]) {
    for (const method of methods) {
      const result = await worker.fetch(request(path, { method }), effects.env);
      assert.equal(result.status, 405);
      assert.equal(result.headers.get("allow"), allowed);
      assertNoPaidClaims(result);
    }
  }
  effects.assertNone();
});

test("known-route preflights are inert and unimplemented routes remain unavailable", async (t) => {
  const effects = observeSideEffects(t);
  for (const path of ["/v1/models", "/v1/inference"]) {
    const result = await worker.fetch(request(path, { method: "OPTIONS" }), effects.env);
    assert.equal(result.status, 204);
    assert.equal(await result.text(), "");
    assertNoPaidClaims(result);
    assert.equal(result.headers.get("access-control-allow-credentials"), null);
  }
  for (const path of ["/v1/chat/completions", "/v1/models/fixture/passport", "/v1/models/fixture/promotion", "/v1/inference/fixture/receipt", "/unknown"]) {
    for (const method of ["GET", "POST", "OPTIONS"]) {
      const result = await worker.fetch(request(path, { method }), effects.env);
      assert.equal(result.status, 404);
      assertNoPaidClaims(result);
    }
  }
  effects.assertNone();
});
