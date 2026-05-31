// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// serve.test.ts — integration tests for `a11oy serve`.
//
// Each test boots the real HTTP server on an ephemeral port (port 0), seeds a
// real receipt ledger on disk using the real emitReceipt/appendReceiptJsonl
// path, and hits each route over real TCP with fetch(). Nothing is mocked: the
// /v1/verify route runs the real verifyChain, and /v1/policy/evaluate runs the
// real threshold gate (real HMAC-SHA-256 receipt).
//
// Run: node --experimental-strip-types --test src/serve.test.ts
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import {
  appendReceiptJsonl,
  createToolEnvelope,
  emitReceipt,
  type OperationalReceipt,
} from "./index.ts";
import { createServer, parseServeConfig, handleRoute, brokenIndex } from "./serve.ts";

const policy = {
  algorithm: "SHA3-256" as const,
  chaining: "hash_chain" as const,
  quorum: "1-of-1",
  nodes: ["test-node"],
};

function mkEnvelope(seq: number) {
  return createToolEnvelope({
    protocol: "mcp",
    actor_id: "did:example:serve-test",
    tool_name: "receipted_retrieval",
    lambda_axes: ["Λ7"],
    payload: { test: true, seq },
    metadata: { source: "a11oy-serve-test" },
  });
}

/** Seed a real 3-receipt chain on disk. Returns the chain. */
function seedLedger(ledgerPath: string): OperationalReceipt[] {
  const chain: OperationalReceipt[] = [];
  let prev: OperationalReceipt | null = null;
  const t0 = Date.now();
  for (let i = 0; i < 3; i += 1) {
    // Distinct, monotonically increasing timestamps so the real verifyChain
    // timestamp-regression check is satisfied (it compares tai64n at ms
    // resolution).
    const r = emitReceipt(mkEnvelope(i), {
      previousReceipt: prev,
      policy,
      timestamp: new Date(t0 + i * 1000),
    });
    appendReceiptJsonl(ledgerPath, r);
    chain.push(r);
    prev = r;
  }
  return chain;
}

let dir: string;
let ledgerPath: string;
let server: Server;
let base: string;
let seeded: OperationalReceipt[];

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "a11oy-serve-test-"));
  ledgerPath = path.join(dir, "proof.jsonl");
  seeded = seedLedger(ledgerPath);
  const config = parseServeConfig(["--port", "0", "--host", "127.0.0.1", "--ledger", ledgerPath]);
  server = createServer(config);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const addr = server.address() as AddressInfo;
  base = `http://127.0.0.1:${addr.port}`;
});

after(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
  fs.rmSync(dir, { recursive: true, force: true });
});

test("GET /healthz returns 200 with status/sha/ts", async () => {
  const res = await fetch(`${base}/healthz`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "ok");
  assert.equal(typeof body.sha, "string");
  assert.ok(body.sha.length > 0);
  // ts must parse as a valid ISO timestamp.
  assert.ok(!Number.isNaN(Date.parse(body.ts)));
});

test("GET /readyz returns 200 when the ledger is readable", async () => {
  const res = await fetch(`${base}/readyz`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "ready");
});

test("GET /readyz returns 503 with a reason when the ledger is unreadable", async () => {
  // Point a fresh server at a path inside a non-existent directory chain that
  // also can't be created as a plain readReceiptJsonl target. Use a directory
  // as the ledger path so readReceiptJsonl throws (EISDIR on read).
  const badConfig = parseServeConfig(["--ledger", dir]); // dir is a directory
  const r = handleRoute("GET", new URL("http://x/readyz"), "", badConfig);
  assert.equal(r.status, 503);
  const body = r.body as { status: string; reason: string };
  assert.equal(body.status, "not_ready");
  assert.ok(body.reason.length > 0);
});

test("GET /v1/ledger?limit=2 returns the last 2 real receipts", async () => {
  const res = await fetch(`${base}/v1/ledger?limit=2`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.total, 3);
  assert.equal(body.count, 2);
  assert.equal(body.receipts.length, 2);
  // Last two by sequence.
  assert.equal(body.receipts[0].sequence, 1);
  assert.equal(body.receipts[1].sequence, 2);
  // Real receipt_id/merkle_root match what we seeded.
  assert.equal(body.receipts[1].merkle_root, seeded[2].merkle_root);
});

test("GET /v1/ledger/{hash} returns the matching receipt by merkle_root", async () => {
  const target = seeded[1];
  const res = await fetch(`${base}/v1/ledger/${encodeURIComponent(target.merkle_root)}`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.receipt.receipt_id, target.receipt_id);
  assert.equal(body.receipt.merkle_root, target.merkle_root);
});

test("GET /v1/ledger/{hash} returns 404 for an unknown hash", async () => {
  const res = await fetch(`${base}/v1/ledger/${"0".repeat(64)}`);
  assert.equal(res.status, 404);
});

test("POST /v1/verify accepts a valid real chain (broken_at null)", async () => {
  const res = await fetch(`${base}/v1/verify`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ledger: seeded }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.valid, true);
  assert.equal(body.broken_at, null);
});

test("POST /v1/verify flags a tampered chain with broken_at index", async () => {
  // Tamper the second receipt's merkle_root — real verifyChain must catch it.
  const tampered = seeded.map((r) => ({ ...r }));
  tampered[1] = { ...tampered[1], merkle_root: "0".repeat(tampered[1].merkle_root.length) };
  const res = await fetch(`${base}/v1/verify`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ledger: tampered }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.valid, false);
  assert.equal(typeof body.broken_at, "number");
  assert.ok(body.broken_at >= 1);
});

test("POST /v1/policy/evaluate allows a well-attested action with a real receipt_hash", async () => {
  const res = await fetch(`${base}/v1/policy/evaluate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      action: {
        actionId: "deploy-123",
        severity: "low",
        confidence: 0.95,
        witnesses: [
          { id: "w1", role: "operator", attested: true },
          { id: "w2", role: "reviewer", attested: true },
        ],
      },
    }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.decision, "allow");
  assert.equal(body.gate, "ThresholdPolicySeverity");
  // Real HMAC-SHA-256 signature is non-empty on allow.
  assert.equal(typeof body.receipt_hash, "string");
  assert.ok(body.receipt_hash.length > 0);
});

test("POST /v1/policy/evaluate denies an under-attested high-severity action", async () => {
  const res = await fetch(`${base}/v1/policy/evaluate`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      action: {
        actionId: "wire-funds-1",
        severity: "critical",
        confidence: 0.5,
        witnesses: [{ id: "w1", role: "operator", attested: true }],
      },
    }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.decision, "deny");
  assert.equal(body.gate, "ThresholdPolicySeverity");
});

test("brokenIndex maps verifyChain position errors to the earliest index", () => {
  assert.equal(brokenIndex(["position 2: merkle_root mismatch", "position 5: x"]), 2);
  assert.equal(brokenIndex([]), null);
});
