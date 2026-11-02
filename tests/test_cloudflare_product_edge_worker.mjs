import assert from "node:assert/strict";
import test from "node:test";

import {
  canonicalLocation,
  handleRequest,
  originLocation,
  resolveOriginPath,
  rewriteOriginLocation,
} from "../cloudflare/a11oy-product-root-worker.mjs";

const BLOCKED_RESPONSE_HEADERS = [
  "traceparent",
  "tracestate",
  "x-backend-server",
  "x-hf-replica",
  "x-proxied-host",
  "x-proxied-path",
  "x-proxied-replica",
  "x-replica",
  "x-replica-id",
  "x-span-id",
  "x-trace-id",
  "x-upstream-addr",
  "x-upstream-address",
  "x-upstream-host",
  "x-vsp-otel",
];

function corsHeaderNames(headers) {
  return [...headers.keys()].filter((name) =>
    name.toLowerCase().startsWith("access-control-"),
  );
}

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
        origin: "https://a-11-oy.com",
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
  assert.match(response.headers.get("vary"), /(?:^|,\s*)Origin(?:,|$)/i);
});

test("apex strips final-hop topology and trace headers and collapses canonical Link", async () => {
  const upstreamHeaders = new Headers({
    "access-control-expose-headers": "*",
    "access-control-future-policy": "unsafe",
    "access-control-allow-origin": "*",
    "x-request-id": "public-correlation-id",
  });
  for (const name of BLOCKED_RESPONSE_HEADERS) {
    upstreamHeaders.set(name, "private-origin-value");
  }
  upstreamHeaders.append(
    "link",
    '<https://a-11-oy.com/stale>; rel="canonical"',
  );
  upstreamHeaders.append(
    "link",
    '<https://huggingface.co/spaces/SZLHOLDINGS/a11oy>; rel="canonical"',
  );

  const response = await handleRequest(
    new Request("https://a-11-oy.com/trust?campaign=private"),
    async () => new Response("ok", { headers: upstreamHeaders }),
  );

  for (const name of BLOCKED_RESPONSE_HEADERS) {
    assert.equal(response.headers.get(name), null, `${name} must be stripped`);
  }
  assert.deepEqual(corsHeaderNames(response.headers), []);
  assert.equal(response.headers.get("x-request-id"), "public-correlation-id");
  assert.equal(response.headers.get("x-szl-edge"), "a11oy-product-edge-v3");
  assert.equal(
    response.headers.get("link"),
    '<https://a-11-oy.com/trust>; rel="canonical"',
  );
  assert.equal(
    [...response.headers.keys()].filter((name) => name === "link").length,
    1,
  );
});

test("CORS is rebuilt from the request and rejects untrusted preflights", async () => {
  const broadOrigin = async () =>
    new Response(null, {
      status: 204,
      headers: {
        "access-control-allow-credentials": "true",
        "access-control-allow-headers": "*",
        "access-control-allow-methods": "*",
        "access-control-allow-origin": "*",
        "access-control-allow-private-network": "true",
        "access-control-expose-headers": "*",
        "access-control-max-age": "86400",
      },
    });

  const allowed = await handleRequest(
    new Request("https://a-11-oy.com/api/a11oy/healthz", {
      method: "OPTIONS",
      headers: {
        origin: "https://immune.a-11-oy.com",
        "access-control-request-method": "GET",
        "access-control-request-headers": "Authorization, X-Requested-With",
      },
    }),
    broadOrigin,
  );
  assert.equal(
    allowed.headers.get("access-control-allow-origin"),
    "https://immune.a-11-oy.com",
  );
  assert.equal(
    allowed.headers.get("access-control-allow-methods"),
    "GET, HEAD, POST, OPTIONS",
  );
  assert.equal(
    allowed.headers.get("access-control-allow-headers"),
    "Content-Type, Authorization, X-Requested-With, X-A11oy-Second-Approver",
  );
  assert.equal(allowed.headers.get("access-control-allow-credentials"), null);
  assert.equal(allowed.headers.get("access-control-expose-headers"), null);
  assert.equal(allowed.headers.get("access-control-allow-private-network"), null);
  for (const name of [
    "Origin",
    "Access-Control-Request-Method",
    "Access-Control-Request-Headers",
  ]) {
    assert.match(
      allowed.headers.get("vary"),
      new RegExp(`(?:^|,\\s*)${name}(?:,|$)`, "i"),
    );
  }

  for (const headers of [
    {
      origin: "https://edge-probe.invalid",
      "access-control-request-method": "GET",
    },
    {
      origin: "https://a-11-oy.com",
      "access-control-request-method": "DELETE",
    },
    {
      origin: "https://a-11-oy.com",
      "access-control-request-method": "GET",
      "access-control-request-headers": "X-Untrusted",
    },
    {
      origin: "https://a-11-oy.com",
      "access-control-request-method": "GET",
      "access-control-request-private-network": "true",
    },
  ]) {
    const denied = await handleRequest(
      new Request("https://a-11-oy.com/api/a11oy/healthz", {
        method: "OPTIONS",
        headers,
      }),
      broadOrigin,
    );
    assert.deepEqual(corsHeaderNames(denied.headers), []);
    assert.match(denied.headers.get("vary"), /(?:^|,\s*)Origin(?:,|$)/i);
  }
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
