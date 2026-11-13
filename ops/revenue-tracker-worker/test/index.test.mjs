import assert from "node:assert/strict";
import test from "node:test";

import { classifyClient, handleRequest, visitorKey } from "../src/index.mjs";

const SECRET = "s".repeat(40);
const BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36";

function recorder() {
  const points = [];
  return { points, ANALYTICS: { writeDataPoint: (point) => points.push(point) } };
}

function tracked(path = "/api/a11oy/v1/version", headers = {}, cf = {}) {
  const request = new Request(`https://a-11-oy.com${path}?q=secret-token`, {
    headers: { "cf-connecting-ip": "203.0.113.7", "user-agent": BROWSER, ...headers },
  });
  Object.defineProperty(request, "cf", { value: { country: "US", asn: 13335, colo: "IAD", ...cf } });
  return request;
}

test("forwards the request unchanged and returns the origin response", async () => {
  let forwarded;
  const env = recorder();
  const response = await handleRequest(tracked(), env, async (request) => {
    forwarded = request;
    return new Response("origin body", { status: 418, headers: { "x-origin": "1" } });
  }, () => 1_700_000_000_000);
  assert.equal(new URL(forwarded.url).pathname, "/api/a11oy/v1/version");
  assert.equal(new URL(forwarded.url).search, "?q=secret-token");
  assert.equal(response.status, 418);
  assert.equal(await response.text(), "origin body");
  assert.equal(response.headers.get("x-origin"), "1");
  assert.equal(response.headers.get("x-szl-tracker"), "written");
});

test("writes a v2 point with visitor dimensions and never the IP, user agent or query", async () => {
  const env = { ...recorder(), VISITOR_KEY_SECRET: SECRET };
  let clock = 1_700_000_000_000;
  await handleRequest(tracked(), env, async () => {
    clock += 42;
    return new Response(null, { status: 204 });
  }, () => clock);
  assert.equal(env.points.length, 1);
  const [point] = env.points;
  assert.deepEqual(point.indexes, ["/api/a11oy/v1/version"]);
  assert.deepEqual(point.blobs.slice(0, 9), [
    "v2", "GET", "/api/a11oy/v1/version", "a-11-oy.com", "US", "13335", "IAD", "browser", "",
  ]);
  assert.match(point.blobs[9], /^[a-f0-9]{32}$/);
  assert.equal(point.blobs[10], "HMAC_DAILY");
  assert.deepEqual(point.doubles, [1_700_000_000_000, 204, 42]);
  const stored = JSON.stringify(point);
  for (const forbidden of ["203.0.113.7", "Chrome/131", "secret-token", SECRET]) {
    assert.equal(stored.includes(forbidden), false, forbidden);
  }
});

test("without a valid secret the visitor key is honestly unavailable", async () => {
  for (const secret of [undefined, "", "too-short"]) {
    const env = { ...recorder(), VISITOR_KEY_SECRET: secret };
    await handleRequest(tracked(), env, async () => new Response("ok"), () => 1);
    assert.equal(env.points[0].blobs[9], "");
    assert.equal(env.points[0].blobs[10], "UNAVAILABLE");
  }
});

test("the visitor key is stable within a UTC day and rotates across days", async () => {
  const day1 = await visitorKey(SECRET, "2026-11-12", "203.0.113.7", BROWSER);
  assert.equal(await visitorKey(SECRET, "2026-11-12", "203.0.113.7", BROWSER), day1);
  assert.notEqual(await visitorKey(SECRET, "2026-11-13", "203.0.113.7", BROWSER), day1);
  assert.notEqual(await visitorKey(SECRET, "2026-11-12", "203.0.113.8", BROWSER), day1);
  assert.notEqual(await visitorKey("t".repeat(40), "2026-11-12", "203.0.113.7", BROWSER), day1);
});

test("classifies clients without trusting a user agent over Cloudflare's verified-bot signal", () => {
  assert.equal(classifyClient(BROWSER, ""), "browser");
  assert.equal(classifyClient(BROWSER, "Search Engine Crawler"), "verified-bot");
  assert.equal(classifyClient("Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)", ""), "crawler");
  assert.equal(classifyClient("Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/131.0 Safari/537.36", ""), "crawler");
  assert.equal(classifyClient("curl/8.5.0", ""), "cli");
  assert.equal(classifyClient("python-requests/2.32.3", ""), "library");
  assert.equal(classifyClient("Python-urllib/3.12", ""), "library");
  assert.equal(classifyClient("node", ""), "library");
  assert.equal(classifyClient("", ""), "empty");
  assert.equal(classifyClient("SomethingElse/1.0", ""), "other");
});

test("a missing binding or a failing write never changes the response", async () => {
  const origin = async () => new Response("ok", { status: 200 });
  const unbound = await handleRequest(tracked(), {}, origin, () => 1);
  assert.equal(unbound.status, 200);
  assert.equal(unbound.headers.get("x-szl-tracker"), "no-binding");
  const failing = await handleRequest(tracked(), {
    ANALYTICS: { writeDataPoint: () => { throw new Error("quota 203.0.113.7"); } },
  }, origin, () => 1);
  assert.equal(failing.status, 200);
  assert.equal(await failing.text(), "ok");
  assert.equal(failing.headers.get("x-szl-tracker"), "error");
});

test("an origin failure is passed through, not replaced, and is still recorded", async () => {
  const env = recorder();
  await assert.rejects(handleRequest(tracked(), env, async () => { throw new TypeError("network"); }, () => 1),
    /network/);
  assert.equal(env.points.length, 1);
  assert.equal(env.points[0].doubles[1], 0);
});

test("the source config pins the live Worker's name, routes and dataset", async () => {
  const { readFile } = await import("node:fs/promises");
  const config = JSON.parse(await readFile(new URL("../wrangler.jsonc", import.meta.url), "utf8"));
  assert.equal(config.name, "szl-revenue-tracker");
  assert.equal(config.main, "src/index.mjs");
  assert.equal(config.compatibility_date, "2024-09-01");
  assert.equal(config.workers_dev, false);
  assert.deepEqual(config.routes.map((route) => route.pattern),
    ["a-11-oy.com/api/a11oy/v1/*", "a-11-oy.com/v1/*"]);
  assert.deepEqual(config.analytics_engine_datasets, [{ binding: "ANALYTICS", dataset: "x402_revenue" }]);
  assert.equal(JSON.stringify(config).includes("VISITOR_KEY_SECRET"), false);
});
