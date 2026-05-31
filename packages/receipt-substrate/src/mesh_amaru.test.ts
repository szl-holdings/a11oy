// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
//
// Integration test for Wire C (a11oy → amaru reason proxy).
//
// This is a REAL cross-process integration: it boots
//   1. the real amaru FastAPI sidecar (uvicorn, sidecar/src/amaru/app.py)
//   2. the real a11oy reason server (this package's reason-serve.ts)
// and drives a11oy's /v1/reason over real TCP. No mock of amaru — the rationale
// is produced by amaru's real chakra kernels.
//
// Proves:
//   - a11oy /v1/reason round-trips to amaru and returns amaru's rationale and
//     verdict (decidedBy = amaru.brain, reachedAmaru = true).
//   - the verdict carries amaru's own receipt hash (the brain's ledger entry).
//   - every reason call is hash-chained into a11oy's ledger and verifies clean
//     via the existing /v1/verify route (the bloodstream is tamper-evident).
//   - amaru's evaluation span's traceparent is a child of the a11oy reason span
//     (same trace-id, different span-id) — the nervous-system wire (Wire E).
//   - an unknown chakra is held with an explicit rationale (fail-closed).
//
// Run: node --experimental-strip-types --test src/mesh_amaru.test.ts
// (requires python3 with fastapi+uvicorn; the amaru repo is resolved relative
// to this clone — a11oy and amaru are cloned side-by-side under mining_clones/)

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import * as http from "node:http";
import * as net from "node:net";
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs";
import { spawn, type ChildProcess } from "node:child_process";
import { startReasonServer, type ReasonConfig } from "./reason-serve.ts";
import { parseTraceparent } from "./mesh_trace.ts";

// Resolve amaru's sidecar relative to the sibling clone.
const AMARU_SIDECAR = path.resolve(import.meta.dirname, "../../../../amaru/sidecar");

let amaruProc: ChildProcess | null = null;
let amaruUrl = "";
let a11oyServer: http.Server | null = null;
let a11oyBase = "";
let ledgerPath = "";

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const addr = srv.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

function waitForHealthz(base: string, timeoutMs = 20000): Promise<void> {
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
      setTimeout(tick, 200);
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

function getJson(
  base: string,
  pathname: string,
): Promise<{ status: number; json: any }> {
  return new Promise((resolve, reject) => {
    http
      .get(base + pathname, (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () =>
          resolve({
            status: res.statusCode ?? 0,
            json: JSON.parse(Buffer.concat(chunks).toString("utf8")),
          }),
        );
      })
      .on("error", reject);
  });
}

before(async () => {
  assert.ok(
    fs.existsSync(path.join(AMARU_SIDECAR, "src/amaru/app.py")),
    `amaru app not found at ${AMARU_SIDECAR}`,
  );
  // Boot the real amaru FastAPI app via uvicorn on a free port.
  const amaruPort = await freePort();
  amaruProc = spawn(
    "python3",
    ["-m", "uvicorn", "amaru.app:app", "--host", "127.0.0.1", "--port", String(amaruPort), "--log-level", "warning"],
    {
      cwd: AMARU_SIDECAR,
      env: { ...process.env, PYTHONPATH: path.join(AMARU_SIDECAR, "src") },
      stdio: ["ignore", "inherit", "inherit"],
    },
  );
  amaruUrl = `http://127.0.0.1:${amaruPort}`;
  await waitForHealthz(amaruUrl);

  // Boot a11oy reason server (Node) on an ephemeral port, pointing at amaru.
  ledgerPath = path.join(os.tmpdir(), `a11oy-reason-test-${process.pid}-${Date.now()}.jsonl`);
  const config: ReasonConfig = {
    port: 0,
    host: "127.0.0.1",
    ledgerPath,
    sha: "test",
    amaruUrl,
    amaruFailOpen: false,
  };
  a11oyServer = await startReasonServer(config);
  const addr = a11oyServer.address();
  const a11oyPort = typeof addr === "object" && addr ? addr.port : 0;
  a11oyBase = `http://127.0.0.1:${a11oyPort}`;
  await waitForHealthz(a11oyBase);
});

after(async () => {
  if (a11oyServer) await new Promise<void>((r) => a11oyServer!.close(() => r()));
  if (amaruProc) amaruProc.kill("SIGTERM");
  if (ledgerPath && fs.existsSync(ledgerPath)) fs.unlinkSync(ledgerPath);
});

test("a11oy /v1/reason round-trips to amaru and returns the brain's rationale", async () => {
  const parentTrace = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01";
  const res = await postJson(
    a11oyBase,
    "/v1/reason",
    { chakra: "heart", envelope: { actor_id: "rosie", action: "deploy", care: 0.9, harm: 0.1 } },
    { traceparent: parentTrace },
  );
  assert.equal(res.status, 200, "reason should return 200");
  assert.equal(res.json.reachedAmaru, true, "the brain must actually be reached (no mock)");
  assert.equal(res.json.decidedBy, "amaru.brain", "the rationale comes from amaru");
  assert.equal(res.json.chakra, "heart");
  assert.ok(typeof res.json.verdict === "string" && res.json.verdict.length > 0, "verdict present");
  assert.match(res.json.rationale, /amaru\.heart/, "rationale references the amaru kernel");
  assert.ok(
    typeof res.json.amaruReceiptHash === "string" && res.json.amaruReceiptHash.length === 64,
    "amaru's own receipt hash is surfaced",
  );

  // Nervous-system wire: amaru's span is a child of the a11oy reason span.
  const reasonSpan = parseTraceparent(res.json.traceparent);
  const inboundSpan = parseTraceparent(parentTrace);
  assert.ok(reasonSpan, "reason traceparent parses");
  assert.equal(reasonSpan!.traceId, inboundSpan!.traceId, "same trace-id propagated");
  assert.notEqual(reasonSpan!.spanId, inboundSpan!.spanId, "fresh span-id (child span)");
  // The response echoes the reason span on a traceparent header.
  assert.equal(res.headers["traceparent"], res.json.traceparent, "traceparent echoed on header");
});

test("a11oy /v1/reason can address each chakra kernel by name", async () => {
  for (const chakra of ["root", "throat", "crown"]) {
    const res = await postJson(a11oyBase, "/v1/reason", { chakra, envelope: { x: 1 } });
    assert.equal(res.status, 200, `${chakra} should return 200`);
    assert.equal(res.json.chakra, chakra);
    assert.equal(res.json.reachedAmaru, true);
  }
});

test("unknown chakra is held fail-closed with an explicit rationale", async () => {
  const res = await postJson(a11oyBase, "/v1/reason", { chakra: "nonexistent", envelope: {} });
  assert.equal(res.status, 200);
  assert.equal(res.json.verdict, "hold");
  assert.match(res.json.rationale, /unknown chakra/);
});

test("every reason call is hash-chained into a11oy's ledger and verifies clean", async () => {
  // Read the ledger via the base /v1/ledger route and verify the chain.
  const ledger = await getJson(a11oyBase, "/v1/ledger?limit=100");
  assert.equal(ledger.status, 200);
  assert.ok(ledger.json.count >= 3, "at least the reason calls above are recorded");

  const verify = await postJson(a11oyBase, "/v1/verify", { ledger: ledger.json.receipts });
  assert.equal(verify.status, 200);
  assert.equal(verify.json.valid, true, "the bloodstream is tamper-evident and verifies clean");
});
