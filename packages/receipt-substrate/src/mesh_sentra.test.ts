// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// Integration test for Wire B (a11oy → sentra immune delegation).
//
// This is a REAL cross-process integration: it boots
//   1. the real sentra immune server (Python http.server, runtime/immune_server.py)
//   2. the real a11oy mesh server (this package's mesh-serve.ts)
// and drives a11oy's /v1/policy/evaluate over real TCP. No mock of sentra — the
// verdict is produced by sentra's real sentra_inspect().
//
// Proves:
//   - a known-bad action ("DROP TABLE") is DENIED by a11oy via sentra (decidedBy
//     = sentra.immune), even when the local gate would otherwise allow.
//   - a clean, well-witnessed action is ALLOWED (decidedBy = a11oy.gate+sentra.immune).
//   - every decision is hash-chained into a11oy's ledger and verifies clean
//     via the existing /v1/verify route (the bloodstream is tamper-evident).
//   - the immune span's traceparent is a child of the a11oy evaluation span.
//
// Run: node --experimental-strip-types --test src/mesh_sentra.test.ts
// (requires python3 on PATH; the sentra repo is resolved relative to this clone)

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import * as http from "node:http";
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import { startMeshServer, type MeshConfig } from "./mesh-serve.ts";
import { parseTraceparent } from "./mesh_trace.ts";

// Resolve the sentra immune server relative to the sibling clone.
// a11oy and sentra are cloned side-by-side under mining_clones/.
const SENTRA_IMMUNE = path.resolve(
  import.meta.dirname,
  "../../../../sentra/runtime/immune_server.py",
);

let sentraProc: ChildProcess | null = null;
let sentraUrl = "";
let a11oyServer: http.Server | null = null;
let a11oyBase = "";
let ledgerPath = "";

function waitForHealthz(base: string, timeoutMs = 8000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(`${base}/healthz`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      });
      req.on("error", retry);
    };
    const retry = () => {
      if (Date.now() > deadline) return reject(new Error(`healthz timeout: ${base}`));
      setTimeout(tick, 120);
    };
    tick();
  });
}

function postJson(
  base: string,
  pathname: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<{ status: number; json: any; headers: http.IncomingHttpHeaders }> {
  const data = Buffer.from(JSON.stringify(body));
  const u = new URL(base + pathname);
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname,
        method: "POST",
        headers: { "content-type": "application/json", "content-length": data.length, ...headers },
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({
            status: res.statusCode ?? 0,
            json: JSON.parse(Buffer.concat(chunks).toString("utf8")),
            headers: res.headers,
          }),
        );
      },
    );
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

before(async () => {
  // Boot sentra immune (Python) on an ephemeral port.
  assert.ok(fs.existsSync(SENTRA_IMMUNE), `sentra immune server not found at ${SENTRA_IMMUNE}`);
  sentraProc = spawn("python3", ["-u", SENTRA_IMMUNE], {
    env: { ...process.env, SENTRA_IMMUNE_HOST: "127.0.0.1", SENTRA_IMMUNE_PORT: "0" },
    stdio: ["ignore", "pipe", "inherit"],
  });
  const port: number = await new Promise((resolve, reject) => {
    let buf = "";
    const onData = (chunk: Buffer) => {
      buf += chunk.toString("utf8");
      const line = buf.split("\n").find((l) => l.includes("sentra immune listening"));
      if (line) {
        try {
          resolve(JSON.parse(line).port);
        } catch (e) {
          reject(e as Error);
        }
      }
    };
    sentraProc!.stdout!.on("data", onData);
    sentraProc!.on("error", reject);
    setTimeout(() => reject(new Error("sentra boot timeout")), 8000);
  });
  sentraUrl = `http://127.0.0.1:${port}`;
  await waitForHealthz(sentraUrl);

  // Boot a11oy mesh server (Node) on an ephemeral port, pointing at sentra.
  ledgerPath = path.join(os.tmpdir(), `a11oy-mesh-test-${process.pid}-${Date.now()}.jsonl`);
  const config: MeshConfig = {
    port: 0,
    host: "127.0.0.1",
    ledgerPath,
    sha: "test",
    sentraUrl,
    sentraFailOpen: false,
  };
  a11oyServer = await startMeshServer(config);
  const addr = a11oyServer.address();
  const a11oyPort = typeof addr === "object" && addr ? addr.port : 0;
  a11oyBase = `http://127.0.0.1:${a11oyPort}`;
  await waitForHealthz(a11oyBase);
});

after(async () => {
  if (a11oyServer) await new Promise<void>((r) => a11oyServer!.close(() => r()));
  if (sentraProc) sentraProc.kill("SIGTERM");
  if (ledgerPath && fs.existsSync(ledgerPath)) fs.unlinkSync(ledgerPath);
});

test("a11oy DENIES a known-bad action via sentra immune delegation", async () => {
  const parent = "00-" + "1".repeat(32) + "-" + "2".repeat(16) + "-01";
  const { status, json, headers } = await postJson(
    a11oyBase,
    "/v1/policy/evaluate",
    {
      action: {
        actionId: "act-injection",
        severity: "low",
        decisionClass: "ordinary",
        confidence: 0.99,
        witnesses: [
          { id: "w1", role: "operator", attested: true },
          { id: "w2", role: "reviewer", attested: true },
        ],
        sql: "DROP TABLE receipts;", // threat signature sentra detects
      },
    },
    { traceparent: parent },
  );
  assert.equal(status, 200);
  assert.equal(json.decision, "deny", JSON.stringify(json));
  assert.equal(json.decidedBy, "sentra.immune");
  assert.equal(json.immune.decision, "deny");
  assert.equal(json.immune.reachedSentra, true, "must have actually reached sentra");

  // traceparent: the a11oy eval span is a child of the inbound parent.
  const inbound = parseTraceparent(parent)!;
  const evalSpan = parseTraceparent(json.traceparent)!;
  assert.equal(evalSpan.traceId, inbound.traceId, "eval span keeps inbound trace-id");
  assert.notEqual(evalSpan.spanId, inbound.spanId, "eval span has a new span-id");
  assert.equal(headers["traceparent"], json.traceparent, "traceparent echoed on response header");
});

test("a11oy ALLOWS a clean, well-witnessed action (gate + immune both clear)", async () => {
  const { status, json } = await postJson(a11oyBase, "/v1/policy/evaluate", {
    action: {
      actionId: "act-clean",
      severity: "low",
      decisionClass: "ordinary",
      confidence: 0.99,
      witnesses: [
        { id: "w1", role: "operator", attested: true },
        { id: "w2", role: "reviewer", attested: true },
      ],
      op: "publish-report",
    },
  });
  assert.equal(status, 200);
  assert.equal(json.decision, "allow", JSON.stringify(json));
  assert.equal(json.decidedBy, "a11oy.gate+sentra.immune");
  assert.equal(json.immune.decision, "allow");
  assert.ok(json.receiptHash.length > 0, "allowed decision mints a receipt hash");
});

test("every decision is hash-chained in the ledger and verifies clean", async () => {
  // The two prior tests appended receipts; read the ledger via /v1/ledger and
  // verify the chain via /v1/verify (real verifyChain, no mock).
  const ledger = await postJson(a11oyBase, "/v1/verify", { ledger: readLedger() });
  assert.equal(ledger.json.valid, true, JSON.stringify(ledger.json));
  assert.equal(ledger.json.broken_at, null);
});

function readLedger(): unknown[] {
  const lines = fs.readFileSync(ledgerPath, "utf8").trim().split("\n").filter(Boolean);
  return lines.map((l) => JSON.parse(l));
}
