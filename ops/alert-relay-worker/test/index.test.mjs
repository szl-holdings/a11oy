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

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function flushAfterDeadline(pending) {
  return Promise.race([
    pending,
    new Promise((resolve) => setImmediate(() => resolve(null))),
  ]);
}

for (const method of ["POST", "PUT"]) {
  test(`a stalled ${method} is aborted once and returns an unknown-delivery timeout`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const started = deferred();
    let attempts = 0;
    let forwarded;
    const pending = handleRequest(
      relayRequest("/opaque-topic", { method, body: "canary fixture only" }),
      (request) => {
        attempts += 1;
        forwarded = request;
        started.resolve();
        return new Promise((resolve, reject) => {
          request.signal.addEventListener("abort", () => reject(request.signal.reason), { once: true });
        });
      },
    );
    await started.promise;
    t.mock.timers.tick(25000);
    const response = await flushAfterDeadline(pending);
    assert.ok(response instanceof Response, "stalled publication must settle within its deadline");
    assert.equal(response.status, 504);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.deepEqual(await response.json(), {
      error: "upstream_timeout",
      delivery_status: "UNKNOWN",
    });
    assert.equal(forwarded.signal.aborted, true);
    assert.equal(attempts, 1, "an unknown delivery must never be retried automatically");
  });
}

test("a publication acknowledged at the measured 19.5 s delivery latency completes", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const started = deferred();
  let forwarded;
  let acknowledge;
  const pending = handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture" }),
    (request) => {
      forwarded = request;
      started.resolve();
      return new Promise((resolve) => { acknowledge = resolve; });
    },
  );
  await started.promise;
  t.mock.timers.tick(19500);
  acknowledge(new Response('{"id":"fixture"}', { status: 200 }));
  const response = await pending;
  assert.equal(response.status, 200, "a real delivery inside the measured latency must not time out");
  assert.equal(await response.text(), '{"id":"fixture"}');
  assert.equal(forwarded.signal.aborted, false);
});

test("publication deadline includes a stalled acknowledgement body", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const bodyStarted = deferred();
  let bodyCancelled = false;
  const body = new ReadableStream({
    pull() { bodyStarted.resolve(); },
    cancel() { bodyCancelled = true; },
  }, { highWaterMark: 0 });
  const pending = handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture" }),
    async () => new Response(body, { status: 200 }),
  );
  await bodyStarted.promise;
  t.mock.timers.tick(25000);
  const response = await flushAfterDeadline(pending);
  assert.ok(response instanceof Response, "partial acknowledgements must not hang");
  assert.equal(response.status, 504, "headers alone must not claim delivery");
  assert.equal((await response.json()).delivery_status, "UNKNOWN");
  assert.equal(bodyCancelled, true);
});

test("completed publication preserves bytes and status, then releases its deadline and abort listener", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const caller = new AbortController();
  let forwarded;
  const bytes = new Uint8Array([0, 255, 13, 10]);
  const response = await handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture", signal: caller.signal }),
    async (request) => {
      forwarded = request;
      return new Response(bytes, { status: 429, headers: { "retry-after": "12" } });
    },
  );
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "12");
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
  t.mock.timers.tick(25000);
  assert.equal(forwarded.signal.aborted, false, "completed requests must not retain a deadline");
  caller.abort();
  assert.equal(forwarded.signal.aborted, false, "completed requests must detach caller cancellation");
});

test("publication transport rejection remains 502 and cleans up its timer", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let forwarded;
  const response = await handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture" }),
    async (request) => {
      forwarded = request;
      throw new TypeError("synthetic unavailable upstream");
    },
  );
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { error: "upstream_unavailable" });
  t.mock.timers.tick(25000);
  assert.equal(forwarded.signal.aborted, false);
});

test("large publication acknowledgements are cancelled with unknown delivery", async () => {
  let cancelled = false;
  const response = await handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture" }),
    async () => new Response(new ReadableStream({
      start(controller) { controller.enqueue(new Uint8Array(64 * 1024 + 1)); },
      cancel() { cancelled = true; },
    }), { status: 200 }),
  );
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), {
    error: "upstream_response_too_large",
    delivery_status: "UNKNOWN",
  });
  assert.equal(cancelled, true);
});

test("subscription GET remains streaming beyond the publication deadline", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  let stream;
  let forwarded;
  const response = await handleRequest(
    relayRequest("/opaque-topic/sse", { method: "GET" }),
    async (request) => {
      forwarded = request;
      return new Response(new ReadableStream({
        start(controller) { stream = controller; },
      }), { headers: { "content-type": "text/event-stream" } });
    },
  );
  assert.equal(response.status, 200);
  const reader = response.body.getReader();
  t.mock.timers.tick(12000);
  assert.equal(forwarded.signal.aborted, false);
  stream.enqueue(new TextEncoder().encode("data: fixture\n\n"));
  assert.equal(new TextDecoder().decode((await reader.read()).value), "data: fixture\n\n");
  stream.close();
  assert.equal((await reader.read()).done, true);
  reader.releaseLock();
});

test("a transport ignoring cancellation still times out and its late body is cancelled", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const started = deferred();
  const lateResponse = deferred();
  let attempts = 0;
  let lateBodyCancelled = false;
  const pending = handleRequest(
    relayRequest("/opaque-topic", { method: "POST", body: "fixture" }),
    () => {
      attempts += 1;
      started.resolve();
      return lateResponse.promise;
    },
  );
  await started.promise;
  t.mock.timers.tick(25000);
  const response = await flushAfterDeadline(pending);
  assert.ok(response instanceof Response, "cancellation must not depend on transport cooperation");
  assert.equal(response.status, 504);
  lateResponse.resolve(new Response(new ReadableStream({
    cancel() { lateBodyCancelled = true; },
  }), { status: 200 }));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(lateBodyCancelled, true);
  assert.equal(attempts, 1);
});

for (const [label, contentType, body] of [
  ["JSON", "application/json", JSON.stringify({ text: "fixture" })],
  ["plain text", "text/plain", "fixture"],
]) {
  test(`caller abort reaches an in-flight ${label} publication`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const caller = new AbortController();
    const started = deferred();
    let attempts = 0;
    let forwarded;
    const pending = handleRequest(
      relayRequest("/opaque-topic", {
        method: "POST",
        headers: { "content-type": contentType },
        body,
        signal: caller.signal,
      }),
      (request) => {
        attempts += 1;
        forwarded = request;
        started.resolve();
        return new Promise((resolve, reject) => {
          request.signal.addEventListener("abort", () => reject(request.signal.reason), { once: true });
        });
      },
    );
    await started.promise;
    caller.abort();
    const response = await flushAfterDeadline(pending);
    assert.ok(response instanceof Response, "caller cancellation must not wait for the publication deadline");
    assert.equal(forwarded.signal.aborted, true);
    assert.equal(response.status, 502);
    assert.equal(attempts, 1);
  });

  test(`an already-aborted ${label} caller never starts publication`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const caller = new AbortController();
    caller.abort();
    let attempts = 0;
    const response = await handleRequest(
      relayRequest("/opaque-topic", {
        method: "POST",
        headers: { "content-type": contentType },
        body,
        signal: caller.signal,
      }),
      async () => {
        attempts += 1;
        return new Response(null, { status: 204 });
      },
    );
    assert.equal(attempts, 0);
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { error: "upstream_unavailable" });
  });
}
