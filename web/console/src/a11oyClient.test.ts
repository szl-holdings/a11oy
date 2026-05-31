// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// a11oyClient.test.ts — integration tests for the operator-console data layer.
// Boots a real node:http server that mimics a11oy's `serve` route surface and
// exercises every A11oyClient method over real TCP via Node's global fetch.
// No mocked transport: the request crosses a socket and the real JSON response
// is parsed back. This proves the 5 console routes' backing calls work against
// the a11oy serve contract.
//
// Run: node --experimental-strip-types src/a11oyClient.test.ts
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import * as http from "node:http";
import { test } from "node:test";
import assert from "node:assert/strict";
import { A11oyClient, CONSOLE_ROUTES } from "./a11oyClient.ts";

function bootA11oyLike(): Promise<{ base: string; close: () => Promise<void> }> {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const reply = (status: number, body: unknown) => {
        res.writeHead(status, { "content-type": "application/json" });
        res.end(JSON.stringify(body));
      };
      if (req.method === "GET" && url.pathname === "/healthz") {
        return reply(200, { status: "ok", sha: "abc123", ts: "2026-05-31T00:00:00Z" });
      }
      if (req.method === "GET" && url.pathname === "/readyz") {
        return reply(200, { status: "ready", ledger: "/tmp/x.jsonl" });
      }
      if (req.method === "GET" && url.pathname === "/v1/ledger") {
        const limit = Number(url.searchParams.get("limit") ?? "20");
        return reply(200, { count: 1, total: 1, receipts: [{ receipt_id: "r-1", merkle_root: "m-1", limit }] });
      }
      if (req.method === "GET" && url.pathname.startsWith("/v1/ledger/")) {
        const hash = decodeURIComponent(url.pathname.slice("/v1/ledger/".length));
        return reply(200, { receipt: { receipt_id: hash } });
      }
      if (req.method === "POST" && url.pathname === "/v1/verify") {
        const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
        const valid = Array.isArray(body.ledger) && body.ledger.length > 0;
        return reply(200, { valid, broken_at: valid ? null : 0, errors: valid ? [] : ["position 0: empty"] });
      }
      if (req.method === "POST" && url.pathname === "/v1/policy/evaluate") {
        const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
        const sev = body.action?.severity ?? "medium";
        const allow = sev === "low" || sev === "medium";
        return reply(200, {
          decision: allow ? "allow" : "deny",
          gate: "thresholdPolicySeverity",
          receipt_hash: allow ? "sig-xyz" : "",
          rationale: `severity=${sev}`,
        });
      }
      reply(404, { error: "not found", path: url.pathname });
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      resolve({ base: `http://127.0.0.1:${port}`, close: () => new Promise<void>((r) => server.close(() => r())) });
    });
  });
}

test("there are exactly 5 console routes, each citing its a11oy source endpoint", () => {
  assert.equal(CONSOLE_ROUTES.length, 5);
  for (const r of CONSOLE_ROUTES) assert.ok(r.source.length > 0);
});

test("health + readiness routes read /healthz and /readyz", async () => {
  const srv = await bootA11oyLike();
  try {
    const c = new A11oyClient(srv.base);
    const h = await c.health();
    assert.equal(h.status, "ok");
    assert.equal(h.sha, "abc123");
    const r = await c.readiness();
    assert.equal(r.status, "ready");
  } finally {
    await srv.close();
  }
});

test("proof-ledger route reads /v1/ledger with the limit", async () => {
  const srv = await bootA11oyLike();
  try {
    const c = new A11oyClient(srv.base);
    const page = await c.ledger(5);
    assert.equal(page.count, 1);
    assert.equal(page.receipts[0].limit, 5);
  } finally {
    await srv.close();
  }
});

test("receipt route reads /v1/ledger/{hash}", async () => {
  const srv = await bootA11oyLike();
  try {
    const c = new A11oyClient(srv.base);
    const out = await c.receipt("m-1");
    assert.equal(out.receipt.receipt_id, "m-1");
  } finally {
    await srv.close();
  }
});

test("verify route POSTs the ledger and returns the real verdict", async () => {
  const srv = await bootA11oyLike();
  try {
    const c = new A11oyClient(srv.base);
    const ok = await c.verify([{ receipt_id: "r-1" }]);
    assert.equal(ok.valid, true);
    const empty = await c.verify([]);
    assert.equal(empty.valid, false);
    assert.equal(empty.broken_at, 0);
  } finally {
    await srv.close();
  }
});

test("policy route POSTs the action and returns allow/deny", async () => {
  const srv = await bootA11oyLike();
  try {
    const c = new A11oyClient(srv.base);
    const allow = await c.evaluatePolicy({ actionId: "a", severity: "low", confidence: 0.9 });
    assert.equal(allow.decision, "allow");
    assert.equal(allow.gate, "thresholdPolicySeverity");
    const deny = await c.evaluatePolicy({ actionId: "b", severity: "critical" });
    assert.equal(deny.decision, "deny");
  } finally {
    await srv.close();
  }
});
