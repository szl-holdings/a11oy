#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// reason-serve.ts — a11oy's reason HTTP server (`a11oy reason-serve`).
//
// This composes the base read/verify routes from serve.ts and adds the
// cross-app *wire* the mining report flagged as missing between the skeleton
// (a11oy) and the brain (amaru):
//
//   POST /v1/reason  — proxy a reason request to amaru's chakra runtime and
//                      return amaru's rationale. The request and the returned
//                      verdict are hash-chained into a11oy's receipt ledger
//                      (the bloodstream) so the reasoning is tamper-evident and
//                      verifiable via the existing /v1/verify route. Wire C.
//
// Every cross-app call carries a W3C traceparent so amaru's evaluation span is
// a child of the a11oy reason span (nervous-system wire, Wire E).
//
// This file is ADDITIVE: it does not modify serve.ts (owned by the in-flight
// `feat/a11oy-serve` work). It imports serve.ts's pure router for the unchanged
// routes and only adds the new /v1/reason route.

import * as http from "node:http";
import * as fs from "node:fs";
import {
  appendReceiptJsonl,
  createToolEnvelope,
  emitReceipt,
  readReceiptJsonl,
  type OperationalReceipt,
} from "./index.ts";
import { handleRoute, parseServeConfig, type ServeConfig } from "./serve.ts";
import { reasonViaAmaru } from "./mesh_amaru.ts";
import { childTraceparent, newTraceparent, traceIdOf } from "./mesh_trace.ts";

export interface ReasonConfig extends ServeConfig {
  /** amaru sidecar base URL; when unset the reason wire is reported "not configured". */
  readonly amaruUrl: string | null;
  /** fail-open on amaru unreachable (default false → fail-closed "hold"). */
  readonly amaruFailOpen: boolean;
}

export function parseReasonConfig(argv: readonly string[]): ReasonConfig {
  const base = parseServeConfig(argv);
  const args = new Map<string, string>();
  for (let i = 0; i < argv.length; i += 1) {
    const t = argv[i];
    if (!t.startsWith("--")) continue;
    const v = argv[i + 1];
    if (v !== undefined && !v.startsWith("--")) {
      args.set(t.slice(2), v);
      i += 1;
    }
  }
  const amaruUrl =
    args.get("amaru-url") ?? process.env.AMARU_URL ?? process.env.AMARU_BASE_URL ?? null;
  const amaruFailOpen =
    (args.get("amaru-fail-open") ?? process.env.AMARU_FAIL_OPEN ?? "false")
      .toLowerCase() === "true";
  return { ...base, amaruUrl, amaruFailOpen };
}

interface JsonResponse {
  status: number;
  body: unknown;
}

/** Append a hash-chained receipt for a reason call; returns the receipt. */
export function recordReasonReceipt(
  config: ReasonConfig,
  payload: Record<string, unknown>,
  traceparent: string,
): OperationalReceipt {
  const chain = fs.existsSync(config.ledgerPath)
    ? readReceiptJsonl(config.ledgerPath)
    : [];
  const previous = chain.length > 0 ? chain[chain.length - 1] : null;
  const envelope = createToolEnvelope({
    protocol: "a11oy",
    actor_id: "a11oy:reason-serve",
    tool_name: "a11oy_reason",
    lambda_axes: ["provenanceIntegrity", "measurabilityHonesty", "operatorReversibility"],
    payload: { ...payload, traceparent, traceId: traceIdOf(traceparent) },
    metadata: { wire: "a11oy->amaru(reason)", traceparent },
  });
  const receipt = emitReceipt(envelope, {
    previousReceipt: previous,
    eventType: "A11OY_OPERATION",
    policy: { vertical: "anatomy-mesh", regime: "doctrine-v7" },
  });
  appendReceiptJsonl(config.ledgerPath, receipt);
  return receipt;
}

/**
 * Reason about an envelope: proxy to amaru's chakra runtime, surface amaru's
 * rationale, mint a hash-chained receipt, and return a ReasonResponse.
 * The request body is { chakra: "<name>", envelope: {...} }.
 */
export async function reason(
  body: string,
  config: ReasonConfig,
  inboundTraceparent: string,
): Promise<JsonResponse> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body || "{}");
  } catch {
    return { status: 400, body: { error: "invalid JSON body" } };
  }
  const p = parsed as { chakra?: unknown; envelope?: unknown };
  const chakra = typeof p.chakra === "string" ? p.chakra : "heart";
  const envelope =
    p.envelope && typeof p.envelope === "object"
      ? (p.envelope as Record<string, unknown>)
      : {};

  if (!config.amaruUrl) {
    return {
      status: 503,
      body: {
        chakra,
        verdict: "hold",
        rationale: "reason wire not configured (no AMARU_URL)",
        reachedAmaru: false,
        decidedBy: "a11oy.reason",
      },
    };
  }

  // Child span of the inbound trace; forwarded to amaru so amaru's span is a
  // grandchild of the caller and a child of this reason span.
  const reasonTraceparent = childTraceparent(inboundTraceparent);

  const result = await reasonViaAmaru(chakra, envelope, {
    baseUrl: config.amaruUrl,
    traceparent: reasonTraceparent,
    failOpen: config.amaruFailOpen,
  });

  const receipt = recordReasonReceipt(
    config,
    {
      chakra: result.chakra,
      verdict: result.verdict,
      proofId: result.proofId,
      reachedAmaru: result.reachedAmaru,
      amaruReceiptHash: result.receiptHash,
    },
    reasonTraceparent,
  );

  return {
    status: 200,
    body: {
      chakra: result.chakra,
      verdict: result.verdict,
      rationale: result.rationale,
      proofId: result.proofId,
      output: result.output,
      decidedBy: "amaru.brain",
      reachedAmaru: result.reachedAmaru,
      amaruReceiptHash: result.receiptHash,
      receiptHash: receipt.merkle_root,
      traceparent: reasonTraceparent,
    },
  };
}

export function createReasonServer(config: ReasonConfig): http.Server {
  return http.createServer(async (req, res) => {
    const send = (r: JsonResponse) => {
      const payload = JSON.stringify(r.body);
      res.writeHead(r.status, {
        "content-type": "application/json; charset=utf-8",
        "content-length": Buffer.byteLength(payload),
      });
      res.end(payload);
    };
    try {
      const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
      const inbound =
        (req.headers["traceparent"] as string | undefined) ?? newTraceparent();
      const body =
        req.method === "POST" || req.method === "PUT" ? await readBody(req) : "";

      // Mesh-special route: reason via amaru's brain runtime.
      if (req.method === "POST" && url.pathname === "/v1/reason") {
        const r = await reason(body, config, inbound);
        if (r.body && typeof r.body === "object" && "traceparent" in r.body) {
          res.setHeader("traceparent", (r.body as { traceparent: string }).traceparent);
        }
        send(r);
        return;
      }

      // Everything else: delegate to the base router (unchanged routes).
      send(handleRoute(req.method ?? "GET", url, body, config));
    } catch (error) {
      send({ status: 500, body: { error: (error as Error).message } });
    }
  });
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    const MAX = 8 * 1024 * 1024;
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

export function startReasonServer(config: ReasonConfig): Promise<http.Server> {
  const server = createReasonServer(config);
  return new Promise((resolve) => {
    server.listen(config.port, config.host, () => {
      const addr = server.address();
      const boundPort = typeof addr === "object" && addr ? addr.port : config.port;
      console.log(
        JSON.stringify({
          msg: "a11oy reason-serve listening",
          host: config.host,
          port: boundPort,
          ledger: config.ledgerPath,
          amaru: config.amaruUrl ?? "(not configured)",
        }),
      );
      resolve(server);
    });
  });
}

function main(): void {
  const config = parseReasonConfig(process.argv.slice(2));
  void startReasonServer(config);
}

const invokedDirectly =
  process.argv[1] !== undefined && process.argv[1].endsWith("reason-serve.ts");
if (invokedDirectly) {
  main();
}
