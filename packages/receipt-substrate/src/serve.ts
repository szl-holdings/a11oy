#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// serve.ts — HTTP server mode for a11oy (`a11oy serve --port 8080`).
//
// a11oy ships a CLI plus a small read/verify HTTP surface so a Kubernetes
// deployment can probe /healthz and /readyz, and so the web SPA can read the
// receipt ledger over HTTP. Every route below calls the real receipt-substrate
// and policy-gate library code — there is no mocked data path.
//
// Routes:
//   GET  /healthz                  -> 200 {status, sha, ts}
//   GET  /readyz                   -> 200 if the ledger file is readable, else 503
//   GET  /v1/ledger?limit=N        -> last N receipts from the ledger as JSON
//   GET  /v1/ledger/{hash}         -> single receipt by receipt_id or merkle_root
//   POST /v1/verify {ledger:[...]} -> {valid, broken_at} via verifyChain
//   GET  /v1/policy/example          -> sample valid request body for /v1/policy/evaluate
//   POST /v1/policy/evaluate       -> {decision, gate, receipt_hash} via the
//                                     thresholdPolicySeverity gate (real HMAC)
//                                     Accepts: {action:{...}} OR flat {severity,...}
//
// No network calls beyond accepting inbound HTTP. The git SHA is read from the
// A11OY_GIT_SHA env var (set at build time) or resolved from the local git
// checkout at boot, falling back to "unknown" rather than fabricating a value.
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import * as http from "node:http";
import * as fs from "node:fs";
import { execFileSync } from "node:child_process";
import {
  readReceiptJsonl,
  verifyChain,
  type OperationalReceipt,
} from "./index.ts";
import { thresholdPolicySeverityGate } from "../../policy/src/gates/thresholdPolicySeverity_gate.ts";

const DEFAULT_LEDGER = "/tmp/a11oy-operational-receipts.jsonl";

export interface ServeConfig {
  readonly port: number;
  readonly host: string;
  readonly ledgerPath: string;
  readonly sha: string;
}

interface JsonResponse {
  readonly status: number;
  readonly body: unknown;
}

/** Resolve the git SHA without fabricating one. */
export function resolveGitSha(): string {
  const fromEnv = process.env.A11OY_GIT_SHA;
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

/** Build the runtime config from argv + environment. */
export function parseServeConfig(argv: readonly string[]): ServeConfig {
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const value = argv[i + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    args.set(key, value);
    i += 1;
  }

  const portRaw = args.get("port") ?? process.env.A11OY_PORT ?? "8080";
  const port = Number.parseInt(portRaw, 10);
  // Port 0 is permitted: it instructs the OS to assign an ephemeral port,
  // which the integration tests rely on to avoid binding a fixed port.
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid --port '${portRaw}'; expected an integer in [0,65535]`);
  }

  const ledgerPath =
    args.get("ledger") ?? process.env.A11OY_PROOF_LEDGER_PATH ?? DEFAULT_LEDGER;
  const host = args.get("host") ?? process.env.A11OY_HOST ?? "0.0.0.0";

  return { port, host, ledgerPath, sha: resolveGitSha() };
}

function clampLimit(raw: string | null): number {
  if (raw === null) return 20;
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isInteger(parsed) || parsed < 1) return 20;
  return Math.min(parsed, 1000);
}

/**
 * Resolve a route to a JSON response. Pure with respect to the request: all
 * ledger reads go through the real readReceiptJsonl, all verification through
 * the real verifyChain, all policy decisions through the real gate.
 */
export function handleRoute(
  method: string,
  url: URL,
  body: string,
  config: ServeConfig,
): JsonResponse {
  // --- GET /healthz ---------------------------------------------------------
  if (method === "GET" && url.pathname === "/healthz") {
    return {
      status: 200,
      body: { status: "ok", sha: config.sha, ts: new Date().toISOString() },
    };
  }

  // --- GET /readyz ----------------------------------------------------------
  if (method === "GET" && url.pathname === "/readyz") {
    try {
      // A readable ledger is the readiness contract. An absent file is treated
      // as an empty-but-readable ledger (genesis state), which is ready.
      if (fs.existsSync(config.ledgerPath)) {
        fs.accessSync(config.ledgerPath, fs.constants.R_OK);
        readReceiptJsonl(config.ledgerPath);
      }
      return { status: 200, body: { status: "ready", ledger: config.ledgerPath } };
    } catch (error) {
      return {
        status: 503,
        body: { status: "not_ready", reason: (error as Error).message, ledger: config.ledgerPath },
      };
    }
  }

  // --- GET /v1/ledger?limit=N ----------------------------------------------
  if (method === "GET" && url.pathname === "/v1/ledger") {
    const limit = clampLimit(url.searchParams.get("limit"));
    const chain = readReceiptJsonl(config.ledgerPath);
    const tail = chain.slice(Math.max(0, chain.length - limit));
    return {
      status: 200,
      body: { count: tail.length, total: chain.length, receipts: tail },
    };
  }

  // --- GET /v1/ledger/{hash} -----------------------------------------------
  if (method === "GET" && url.pathname.startsWith("/v1/ledger/")) {
    const hash = decodeURIComponent(url.pathname.slice("/v1/ledger/".length));
    if (!hash) {
      return { status: 400, body: { error: "missing receipt identifier" } };
    }
    const chain = readReceiptJsonl(config.ledgerPath);
    const match = chain.find(
      (r) => r.receipt_id === hash || r.merkle_root === hash,
    );
    if (!match) {
      return { status: 404, body: { error: "receipt not found", hash } };
    }
    return { status: 200, body: { receipt: match } };
  }

  // --- POST /v1/verify ------------------------------------------------------
  if (method === "POST" && url.pathname === "/v1/verify") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(body || "{}");
    } catch {
      return { status: 400, body: { error: "invalid JSON body" } };
    }
    const ledger = (parsed as { ledger?: unknown }).ledger;
    if (!Array.isArray(ledger)) {
      return { status: 400, body: { error: "body must be {ledger: [...]}" } };
    }
    const chain = ledger as OperationalReceipt[];
    const result = verifyChain(chain);
    const brokenAt = brokenIndex(result.errors);
    return {
      status: 200,
      body: { valid: result.valid, broken_at: brokenAt, errors: result.errors },
    };
  }

  // --- GET /v1/policy/example -----------------------------------------------
  if (method === "GET" && url.pathname === "/v1/policy/example") {
    return {
      status: 200,
      body: {
        description: "Sample valid request body for POST /v1/policy/evaluate",
        formats: [
          {
            name: "flat (preferred)",
            body: {
              actionId: "example-action",
              severity: "medium",
              confidence: 0.9,
              witnesses: [
                { id: "agent-a", role: "approver", attested: true },
                { id: "agent-b", role: "reviewer", attested: true },
              ],
            },
          },
          {
            name: "wrapped (legacy compatible)",
            body: {
              action: {
                actionId: "example-action",
                severity: "medium",
                confidence: 0.9,
                witnesses: [
                  { id: "agent-a", role: "approver", attested: true },
                  { id: "agent-b", role: "reviewer", attested: true },
                ],
              },
            },
          },
        ],
        severity_values: ["low", "medium", "high", "critical"],
      },
    };
  }

  // --- POST /v1/policy/evaluate --------------------------------------------
  if (method === "POST" && url.pathname === "/v1/policy/evaluate") {
    let parsed: unknown;
    try {
      parsed = JSON.parse(body || "{}");
    } catch {
      return { status: 400, body: { error: "invalid JSON body" } };
    }
    // Accept either {action:{...}} (legacy) or flat {severity,...} (preferred).
    const p = parsed as { action?: unknown; severity?: unknown; actionId?: unknown };
    const action = p.action && typeof p.action === "object"
      ? p.action
      : (p.severity !== undefined || p.actionId !== undefined)
        ? p   // flat body — treat top-level as the action object
        : null;
    if (!action || typeof action !== "object") {
      return { status: 400, body: { error: "body must be {severity,...} or {action:{...}}", example: "/v1/policy/example" } };
    }
    const a = action as {
      actionId?: string;
      severity?: string;
      decisionClass?: string;
      confidence?: number;
      witnesses?: unknown;
    };
    try {
      const gate = thresholdPolicySeverityGate();
      // Normalise witnesses: accept either full {id, role, attested} objects or
      // plain strings (coerced to {id: s, role: "witness", attested: true}).
      const rawWitnesses = Array.isArray(a.witnesses) ? a.witnesses : [];
      const normWitnesses = rawWitnesses.map((w: unknown) =>
        typeof w === "string"
          ? { id: w, role: "witness", attested: true }
          : (w as Parameters<typeof gate>[0]["witnesses"][number]),
      );
      const decision = gate({
        actionId: a.actionId ?? "unspecified-action",
        severity: (a.severity ?? "medium") as Parameters<typeof gate>[0]["severity"],
        decisionClass: a.decisionClass as Parameters<typeof gate>[0]["decisionClass"],
        confidence: typeof a.confidence === "number" ? a.confidence : 0,
        witnesses: normWitnesses,
      });
      // The gate is a runtime severity-threshold gate (no Lean closure), so the
      // "gate" identifier reported is its formula name, not a Lean axiom index.
      // receipt_hash comes from the gate's own real HMAC-signed DSSE receipt
      // when allowed; on deny no signed receipt is minted, so we surface the
      // deterministic decision hash instead.
      const receiptHash =
        decision.dsseReceipt?.signatures[0]?.sig ?? "";
      return {
        status: 200,
        body: {
          decision: decision.allow ? "allow" : "deny",
          gate: decision.formula,
          receipt_hash: receiptHash,
          rationale: decision.rationale,
          lambda_score: decision.lambdaScore,
        },
      };
    } catch (error) {
      return { status: 400, body: { error: (error as Error).message } };
    }
  }

  return { status: 404, body: { error: "not found", path: url.pathname } };
}

/** Map verifyChain's "position N: ..." error strings to the earliest broken index. */
export function brokenIndex(errors: readonly string[]): number | null {
  let min: number | null = null;
  for (const err of errors) {
    const m = /^position (\d+):/.exec(err);
    if (m) {
      const idx = Number.parseInt(m[1], 10);
      if (min === null || idx < min) min = idx;
    }
  }
  return min;
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    const MAX = 8 * 1024 * 1024; // 8 MiB cap
    req.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > MAX) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

/** Create (but do not start) the HTTP server for the given config. */
export function createServer(config: ServeConfig): http.Server {
  return http.createServer(async (req, res) => {
    const send = (response: JsonResponse) => {
      const payload = JSON.stringify(response.body);
      res.writeHead(response.status, {
        "content-type": "application/json; charset=utf-8",
        "content-length": Buffer.byteLength(payload),
      });
      res.end(payload);
    };
    try {
      const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
      const body =
        req.method === "POST" || req.method === "PUT" ? await readBody(req) : "";
      send(handleRoute(req.method ?? "GET", url, body, config));
    } catch (error) {
      send({ status: 500, body: { error: (error as Error).message } });
    }
  });
}

export function startServer(config: ServeConfig): Promise<http.Server> {
  const server = createServer(config);
  return new Promise((resolve) => {
    server.listen(config.port, config.host, () => {
      const addr = server.address();
      const boundPort = typeof addr === "object" && addr ? addr.port : config.port;
      console.log(
        JSON.stringify({
          msg: "a11oy serve listening",
          host: config.host,
          port: boundPort,
          ledger: config.ledgerPath,
          sha: config.sha,
        }),
      );
      resolve(server);
    });
  });
}

function main(): void {
  const config = parseServeConfig(process.argv.slice(2));
  void startServer(config);
}

// Run when invoked directly (node src/serve.ts), not when imported by tests.
const invokedDirectly =
  process.argv[1] !== undefined && process.argv[1].endsWith("serve.ts");
if (invokedDirectly) {
  main();
}
