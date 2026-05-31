// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// index.test.ts — integration tests for the mesh-router. Each test boots a
// real node:http server on an ephemeral port (port 0) and exercises the router
// functions over real TCP. There is no mock of the HTTP transport: the request
// is serialized, sent over a socket, received by a real server, and the real
// response is parsed back. This proves the instilled wire actually issues the
// correct method/path/body and parses the producer's response shape.
//
// Run: node --experimental-strip-types src/index.test.ts
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import * as http from "node:http";
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  evaluateAmaruChakra,
  meshConfigFromEnv,
  meshRequest,
  notifyRosie,
  queryAmaruReceipts,
  queryAmaruState,
  requestSentraVerdict,
  type MeshConfig,
} from "./index.ts";

interface Captured {
  method: string;
  url: string;
  body: string;
}

/** Boot a loopback server that records each request and replies per the route. */
function bootServer(
  handler: (req: Captured) => { status: number; json: unknown },
): Promise<{ baseUrl: string; calls: Captured[]; close: () => Promise<void> }> {
  const calls: Captured[] = [];
  const server = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const captured: Captured = {
        method: req.method ?? "",
        url: req.url ?? "",
        body: Buffer.concat(chunks).toString("utf8"),
      };
      calls.push(captured);
      const { status, json } = handler(captured);
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(json));
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      resolve({
        baseUrl: `http://127.0.0.1:${port}`,
        calls,
        close: () =>
          new Promise<void>((r) => server.close(() => r())),
      });
    });
  });
}

test("queryAmaruState issues GET /state and parses the body", async () => {
  const srv = await bootServer(() => ({ status: 200, json: { tick: 42, mood: "calm" } }));
  try {
    const cfg: MeshConfig = { amaru: { baseUrl: srv.baseUrl } };
    const res = await queryAmaruState(cfg);
    assert.equal(res.ok, true);
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { tick: 42, mood: "calm" });
    assert.equal(srv.calls[0].method, "GET");
    assert.equal(srv.calls[0].url, "/state");
  } finally {
    await srv.close();
  }
});

test("queryAmaruReceipts issues GET /receipts", async () => {
  const srv = await bootServer(() => ({ status: 200, json: { receipts: [{ id: "r1" }] } }));
  try {
    const res = await queryAmaruReceipts({ amaru: { baseUrl: srv.baseUrl } });
    assert.equal(res.ok, true);
    assert.equal(srv.calls[0].url, "/receipts");
  } finally {
    await srv.close();
  }
});

test("evaluateAmaruChakra POSTs to /chakra/{name}/evaluate with the body", async () => {
  const srv = await bootServer((req) => ({ status: 200, json: { echoed: JSON.parse(req.body) } }));
  try {
    const res = await evaluateAmaruChakra({ amaru: { baseUrl: srv.baseUrl } }, "muladhara", { signal: 0.7 });
    assert.equal(res.ok, true);
    assert.equal(srv.calls[0].method, "POST");
    assert.equal(srv.calls[0].url, "/chakra/muladhara/evaluate");
    assert.deepEqual(JSON.parse(srv.calls[0].body), { signal: 0.7 });
  } finally {
    await srv.close();
  }
});

test("requestSentraVerdict returns the real allow/deny verdict from the server", async () => {
  const srv = await bootServer(() => ({ status: 200, json: { decision: "allow", reason: "below threshold" } }));
  try {
    const verdict = await requestSentraVerdict(
      { sentra: { baseUrl: srv.baseUrl } },
      { actionId: "a-1", kind: "egress", payload: { bytes: 10 } },
    );
    assert.equal(verdict.decision, "allow");
    assert.equal(srv.calls[0].method, "POST");
    assert.equal(srv.calls[0].url, "/v1/verdict");
  } finally {
    await srv.close();
  }
});

test("requestSentraVerdict FAILS CLOSED (deny) when sentra is unreachable", async () => {
  // No server: this is the real-world state today (sentra exposes no verdict
  // route). The immune organ being absent must never silently allow.
  const verdict = await requestSentraVerdict(
    { sentra: { baseUrl: "http://127.0.0.1:1" } },
    { actionId: "a-2", kind: "threat", payload: {} },
  );
  assert.equal(verdict.decision, "deny");
  assert.ok(verdict.reason && verdict.reason.length > 0);
});

test("requestSentraVerdict FAILS CLOSED when sentra not configured", async () => {
  const verdict = await requestSentraVerdict({}, { actionId: "a-3", kind: "admission", payload: {} });
  assert.equal(verdict.decision, "deny");
});

test("notifyRosie POSTs the operator event to /v1/events", async () => {
  const srv = await bootServer(() => ({ status: 202, json: { accepted: true } }));
  try {
    const res = await notifyRosie({ rosie: { baseUrl: srv.baseUrl } }, { type: "gate.denied", actionId: "x" });
    assert.equal(res.status, 202);
    assert.equal(srv.calls[0].url, "/v1/events");
    assert.deepEqual(JSON.parse(srv.calls[0].body), { type: "gate.denied", actionId: "x" });
  } finally {
    await srv.close();
  }
});

test("meshRequest surfaces non-2xx without throwing", async () => {
  const srv = await bootServer(() => ({ status: 503, json: { error: "not ready" } }));
  try {
    const res = await meshRequest({ baseUrl: srv.baseUrl }, "GET", "/state");
    assert.equal(res.ok, false);
    assert.equal(res.status, 503);
    assert.deepEqual(res.body, { error: "not ready" });
  } finally {
    await srv.close();
  }
});

test("meshConfigFromEnv reads the three organ URLs", () => {
  const cfg = meshConfigFromEnv({
    A11OY_AMARU_URL: "http://amaru:8000",
    A11OY_SENTRA_URL: "http://sentra:9000",
    A11OY_ROSIE_URL: " ",
  } as NodeJS.ProcessEnv);
  assert.equal(cfg.amaru?.baseUrl, "http://amaru:8000");
  assert.equal(cfg.sentra?.baseUrl, "http://sentra:9000");
  assert.equal(cfg.rosie, undefined);
});
