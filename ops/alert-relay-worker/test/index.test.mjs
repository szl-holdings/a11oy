import assert from "node:assert/strict";
import test from "node:test";

import { handleRequest, toUpstreamUrl } from "../src/index.mjs";

function relayRequest(path, init = {}) {
  return new Request(`https://ntfy.a11oy.net${path}`, init);
}

test("pins every upstream request to ntfy.sh", () => {
  const upstream = toUpstreamUrl(
    "https://ntfy.a11oy.net//attacker.example/topic?token=opaque",
  );
  assert.equal(upstream.origin, "https://ntfy.sh");
  assert.equal(upstream.pathname, "//attacker.example/topic");
  assert.equal(upstream.search, "?token=opaque");
});

test("translates Slack-compatible JSON without changing the opaque route", async () => {
  let forwarded;
  const response = await handleRequest(
    relayRequest("/private-topic?token=opaque", {
      method: "POST",
      headers: {
        "content-type": "application/json; charset=utf-8",
        cookie: "must-not-leave-cloudflare=1",
      },
      body: JSON.stringify({ text: "receipt guard failed" }),
    }),
    async (request) => {
      forwarded = request;
      return new Response(null, { status: 204 });
    },
  );

  assert.equal(response.status, 204);
  assert.equal(forwarded.url, "https://ntfy.sh/private-topic?token=opaque");
  assert.equal(forwarded.redirect, "manual");
  assert.equal(forwarded.headers.get("cookie"), null);
  assert.match(forwarded.headers.get("content-type"), /^text\/plain/);
  assert.equal(await forwarded.text(), "receipt guard failed");
});

test("streams native ntfy publishes and preserves upstream failure", async () => {
  let body;
  const response = await handleRequest(
    relayRequest("/private-topic", {
      method: "POST",
      headers: { "content-type": "text/plain" },
      body: "bounded canary",
    }),
    async (request) => {
      body = await request.text();
      return new Response("method rejected", { status: 405 });
    },
  );

  assert.equal(body, "bounded canary");
  assert.equal(response.status, 405);
  assert.equal(await response.text(), "method rejected");
});

test("rejects malformed, oversized, root, and unsupported publishes", async () => {
  const neverFetch = async () => {
    assert.fail("upstream fetch must not run");
  };

  const malformed = await handleRequest(
    relayRequest("/topic", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{",
    }),
    neverFetch,
  );
  assert.equal(malformed.status, 400);

  const oversized = await handleRequest(
    relayRequest("/topic", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "content-length": String(64 * 1024 + 1),
      },
      body: "{}",
    }),
    neverFetch,
  );
  assert.equal(oversized.status, 413);

  const root = await handleRequest(
    relayRequest("/", { method: "POST", body: "message" }),
    neverFetch,
  );
  assert.equal(root.status, 404);

  const deleted = await handleRequest(
    relayRequest("/topic", { method: "DELETE" }),
    neverFetch,
  );
  assert.equal(deleted.status, 405);
});

test("rejects alternate hosts and reports transport failure as 502", async () => {
  const wrongHost = await handleRequest(
    new Request("https://example.com/private-topic", {
      method: "POST",
      body: "message",
    }),
  );
  assert.equal(wrongHost.status, 421);

  const unavailable = await handleRequest(
    relayRequest("/private-topic", {
      method: "POST",
      body: "message",
    }),
    async () => {
      throw new TypeError("network failure");
    },
  );
  assert.equal(unavailable.status, 502);
});
