import assert from "node:assert/strict";
import test from "node:test";

import { REVISION_PATH, handleRequest, toUpstreamUrl } from "../src/index.mjs";

function relayRequest(path, init = {}) {
  return new Request(`https://ntfy.a11oy.net${path}`, init);
}

test("pins every upstream request to a provider-safe derived topic", async () => {
  const upstream = await toUpstreamUrl(
    "https://ntfy.a11oy.net//attacker.example/topic?token=opaque",
  );
  assert.equal(upstream.origin, "https://ntfy.sh");
  assert.match(upstream.pathname, /^\/szl_[a-f0-9]{60}$/);
  assert.equal(upstream.pathname.length, 65);
  assert.equal(upstream.pathname.includes("attacker"), false);
  assert.equal(upstream.search, "?token=opaque");
});

test("translates Slack-compatible JSON without exposing the opaque route", async () => {
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
  const forwardedUrl = new URL(forwarded.url);
  assert.equal(forwardedUrl.origin, "https://ntfy.sh");
  assert.match(forwardedUrl.pathname, /^\/szl_[a-f0-9]{60}$/);
  assert.equal(forwardedUrl.pathname.includes("private-topic"), false);
  assert.equal(forwardedUrl.search, "?token=opaque");
  assert.equal(forwarded.redirect, "manual");
  assert.equal(forwarded.headers.get("cookie"), null);
  assert.match(forwarded.headers.get("content-type"), /^text\/plain/);
  assert.equal(await forwarded.text(), "receipt guard failed");
});

test("uses one derived topic for publish and subscription endpoints", async () => {
  const publish = await toUpstreamUrl(
    "https://ntfy.a11oy.net/private%2Ftopic?token=first",
    "POST",
  );
  const changedQuery = await toUpstreamUrl(
    "https://ntfy.a11oy.net/private%2Ftopic?token=second",
    "POST",
  );
  const subscription = await toUpstreamUrl(
    "https://ntfy.a11oy.net/private%2Ftopic/json?since=all",
    "GET",
  );

  assert.equal(publish.pathname, changedQuery.pathname);
  assert.equal(subscription.pathname, `${publish.pathname}/json`);
  assert.equal(subscription.search, "?since=all");
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

test("the reserved revision path reports the deployed commit and never relays", async () => {
  const revision = "0123456789abcdef0123456789abcdef01234567";
  const neverFetch = async () => {
    assert.fail("the revision path must not reach the upstream");
  };

  const live = await handleRequest(relayRequest(REVISION_PATH), neverFetch, {
    SOURCE_REVISION: revision,
  });
  assert.equal(live.status, 200);
  assert.equal(live.headers.get("cache-control"), "no-store");
  assert.deepEqual(await live.json(), {
    worker: "szl-alert-relay",
    source_revision: revision,
  });

  for (const SOURCE_REVISION of [undefined, "", "d739c95b", revision.toUpperCase()]) {
    const unset = await handleRequest(relayRequest(REVISION_PATH), neverFetch, {
      SOURCE_REVISION,
    });
    assert.equal((await unset.json()).source_revision, null);
  }
  const noEnv = await handleRequest(relayRequest(REVISION_PATH), neverFetch);
  assert.equal((await noEnv.json()).source_revision, null);

  for (const method of ["POST", "PUT", "HEAD", "OPTIONS"]) {
    const write = await handleRequest(
      relayRequest(REVISION_PATH, {
        method,
        ...(method === "POST" || method === "PUT" ? { body: "not a topic" } : {}),
      }),
      neverFetch,
      { SOURCE_REVISION: revision },
    );
    assert.equal(write.status, 405, method);
    assert.equal(write.headers.get("allow"), "GET");
  }

  const wrongHost = await handleRequest(
    new Request(`https://example.com${REVISION_PATH}`),
    neverFetch,
    { SOURCE_REVISION: revision },
  );
  assert.equal(wrongHost.status, 421);
});

test("nearby paths stay opaque topics, not the reserved revision path", async () => {
  for (const path of [
    `${REVISION_PATH}/json`,
    `${REVISION_PATH}x`,
    "/.well-known/other",
    REVISION_PATH.toUpperCase(),
  ]) {
    let forwarded;
    await handleRequest(relayRequest(path), async (request) => {
      forwarded = request;
      return new Response("ok");
    });
    assert.match(new URL(forwarded.url).pathname, /^\/szl_[a-f0-9]{60}(\/json)?$/, path);
  }
});
