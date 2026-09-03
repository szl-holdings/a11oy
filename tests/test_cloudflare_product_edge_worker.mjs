import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalLocation,
  handleRequest,
  originLocation,
  resolveOriginPath,
  rewriteOriginLocation,
} from "../cloudflare/a11oy-product-root-worker.mjs";

test("www redirects permanently while preserving path and query", async () => {
  const response = await handleRequest(
    new Request("https://www.a-11-oy.com/console/view?tab=proof&n=1"),
    async () => assert.fail("www must not fetch the origin"),
  );
  assert.equal(response.status, 301);
  assert.equal(
    response.headers.get("location"),
    "https://a-11-oy.com/console/view?tab=proof&n=1",
  );
  assert.equal(response.headers.get("x-szl-edge"), "a11oy-product-edge-v3");
});

test("apex proxies the exact path to the fixed Space origin", async () => {
  let forwarded;
  const response = await handleRequest(
    new Request("https://a-11-oy.com/api/a11oy/v1/honest?fresh=1", {
      headers: {
        authorization: "Bearer opaque",
        "cf-connecting-ip": "192.0.2.1",
        "x-forwarded-for": "192.0.2.1",
      },
    }),
    async (request) => {
      forwarded = request;
      return new Response(JSON.stringify({ organ: "a11oy" }), {
        status: 200,
        headers: {
          "content-type": "application/json",
          location: "https://szlholdings-a11oy.hf.space/console?from=origin",
          "access-control-allow-origin": "https://szlholdings-a11oy.hf.space",
        },
      });
    },
  );

  assert.equal(
    forwarded.url,
    "https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest?fresh=1",
  );
  assert.equal(forwarded.headers.get("authorization"), "Bearer opaque");
  assert.equal(forwarded.headers.get("cf-connecting-ip"), null);
  assert.equal(forwarded.headers.get("x-forwarded-for"), null);
  assert.equal(forwarded.headers.get("x-forwarded-host"), "a-11-oy.com");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("x-szl-edge"), "a11oy-product-edge-v3");
  assert.equal(
    response.headers.get("location"),
    "https://a-11-oy.com/console?from=origin",
  );
  assert.equal(
    response.headers.get("access-control-allow-origin"),
    "https://a-11-oy.com",
  );
  assert.equal(
    response.headers.get("link"),
    '<https://a-11-oy.com/api/a11oy/v1/honest>; rel="canonical"',
  );
});

test("public spectral and controller aliases resolve to canonical origin routes", async () => {
  const observed = [];
  for (const [path, expected] of [
    ["/spectral?mode=proof", "/static/3d/holographic.html?mode=proof"],
    ["/spectral/?mode=proof", "/static/3d/holographic.html?mode=proof"],
    ["/controller?fresh=1", "/api/a11oy/v1/honest?fresh=1"],
    ["/controller/?fresh=1", "/api/a11oy/v1/honest?fresh=1"],
  ]) {
    const response = await handleRequest(
      new Request(`https://a-11-oy.com${path}`),
      async (request) => {
        observed.push(new URL(request.url));
        return new Response("origin-bytes", { status: 200 });
      },
    );
    const incoming = new URL(`https://a-11-oy.com${path}`);
    const expectedUrl = new URL(`https://szlholdings-a11oy.hf.space${expected}`);
    assert.equal(observed.at(-1).toString(), expectedUrl.toString());
    assert.equal(
      response.headers.get("x-szl-edge-alias"),
      `${incoming.pathname}->${expectedUrl.pathname}`,
    );
    assert.equal(response.status, 200);
    assert.equal(await response.text(), "origin-bytes");
  }
});

test("aliases are read-only and preserve upstream failure status", async () => {
  assert.equal(resolveOriginPath("/controller", "POST"), "/controller");
  assert.equal(
    originLocation("https://a-11-oy.com/controller?x=1", "POST").toString(),
    "https://szlholdings-a11oy.hf.space/controller?x=1",
  );

  let forwarded;
  const response = await handleRequest(
    new Request("https://a-11-oy.com/spectral", { method: "GET" }),
    async (request) => {
      forwarded = request;
      return new Response("not present", { status: 404 });
    },
  );
  assert.equal(
    forwarded.url,
    "https://szlholdings-a11oy.hf.space/static/3d/holographic.html",
  );
  assert.equal(response.status, 404);
  assert.equal(await response.text(), "not present");
});

test("relative and hf.space redirects are rewritten to the apex", () => {
  assert.equal(
    rewriteOriginLocation("/login?next=%2Fconsole"),
    "https://a-11-oy.com/login?next=%2Fconsole",
  );
  assert.equal(
    rewriteOriginLocation("https://other.hf.space/path"),
    "https://a-11-oy.com/path",
  );
  assert.equal(
    rewriteOriginLocation("https://example.com/path"),
    "https://example.com/path",
  );
  assert.equal(
    canonicalLocation("http://www.a-11-oy.com/x?q=1"),
    "https://a-11-oy.com/x?q=1",
  );
});

test("unexpected hosts and origin failures fail closed", async () => {
  const wrongHost = await handleRequest(new Request("https://example.com/"));
  assert.equal(wrongHost.status, 421);

  const unavailable = await handleRequest(
    new Request("https://a-11-oy.com/"),
    async () => {
      throw new TypeError("network down");
    },
  );
  assert.equal(unavailable.status, 502);
  assert.deepEqual(await unavailable.json(), { error: "origin_unavailable" });
});

test("apex preserves bounded application write methods and bodies", async () => {
  let forwarded;
  const response = await handleRequest(
    new Request("https://a-11-oy.com/govern/infer", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "prove it" }),
    }),
    async (request) => {
      forwarded = request;
      return Response.json({ decision: "review" }, { status: 200 });
    },
  );
  assert.equal(forwarded.method, "POST");
  assert.equal(forwarded.url, "https://szlholdings-a11oy.hf.space/govern/infer");
  assert.deepEqual(JSON.parse(await forwarded.text()), { prompt: "prove it" });
  assert.equal(response.status, 200);
});

test("HEAD reaches the fixed origin but never emits an upstream body", async () => {
  let forwarded;
  const response = await handleRequest(
    new Request("https://a-11-oy.com/healthz", { method: "HEAD" }),
    async (request) => {
      forwarded = request;
      return new Response("upstream-body-must-not-be-emitted", {
        status: 200,
        headers: { "content-type": "text/plain" },
      });
    },
  );
  assert.equal(forwarded.method, "HEAD");
  assert.equal(forwarded.url, "https://szlholdings-a11oy.hf.space/healthz");
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "");
});
