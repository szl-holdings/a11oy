#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// mesh-serve.ts — a11oy's mesh HTTP server (`a11oy mesh-serve`).
//
// This composes the base read/verify/policy routes from serve.ts and adds the
// cross-app *wires* the mining report found missing:
//
//   POST /v1/policy/evaluate  — local threshold gate AND immune delegation to
//                               sentra. The combined verdict is hash-chained
//                               into a11oy's receipt ledger (the bloodstream)
//                               and returned as a PolicyDecision. Wire B.
//
// Every cross-app call carries a W3C traceparent so the sentra immune span is a
// child of the a11oy evaluation span (Wire E). A receipt is appended to the
// ledger for every evaluation, so the decision is tamper-evident and verifiable
// via the existing /v1/verify route (the bloodstream is hash-chained).
//
// This file is ADDITIVE: it does not modify serve.ts (owned by the in-flight
// `feat/a11oy-serve` work). It imports serve.ts's pure router for the
// unchanged routes and only special-cases /v1/policy/evaluate.

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
import { thresholdPolicySeverityGate } from "../../policy/src/gates/thresholdPolicySeverity_gate.ts";
import { inspectViaSentra } from "./mesh_sentra.ts";
import { childTraceparent, newTraceparent, traceIdOf } from "./mesh_trace.ts";

export interface MeshConfig extends ServeConfig {
  /** sentra immune base URL; when unset the immune wire is reported "not configured". */
  readonly sentraUrl: string | null;
  /** fail-open on sentra unreachable (default false → fail-closed). */
  readonly sentraFailOpen: boolean;
}

export function parseMeshConfig(argv: readonly string[]): MeshConfig {
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
  const sentraUrl =
    args.get("sentra-url") ?? process.env.SENTRA_URL ?? process.env.SENTRA_IMMUNE_URL ?? null;
  const sentraFailOpen =
    (args.get("sentra-fail-open") ?? process.env.SENTRA_FAIL_OPEN ?? "false")
      .toLowerCase() === "true";
  return { ...base, sentraUrl, sentraFailOpen };
}

interface JsonResponse {
  status: number;
  body: unknown;
}

/** Append a hash-chained receipt for a cross-app decision; returns the receipt. */
export function recordDecisionReceipt(
  config: MeshConfig,
  payload: Record<string, unknown>,
  traceparent: string,
): OperationalReceipt {
  const chain = fs.existsSync(config.ledgerPath)
    ? readReceiptJsonl(config.ledgerPath)
    : [];
  const previous = chain.length > 0 ? chain[chain.length - 1] : null;
  const envelope = createToolEnvelope({
    protocol: "a11oy",
    actor_id: "a11oy:mesh-serve",
    tool_name: "a11oy_policy_evaluate",
    lambda_axes: ["provenanceIntegrity", "measurabilityHonesty", "operatorReversibility"],
    payload: { ...payload, traceparent, traceId: traceIdOf(traceparent) },
    metadata: { wire: "rosie->a11oy(+sentra immune)", traceparent },
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
 * Evaluate a policy proposal: run the local severity gate, delegate the immune
 * verdict to sentra, combine, mint a receipt, and return a PolicyDecision.
 * The combination rule: allow IFF the local gate allows AND sentra does not
 * deny. A sentra deny wins (immune system has veto), and `decidedBy` reflects
 * who actually produced the controlling verdict.
 */
export async function evaluatePolicy(
  body: string,
  config: MeshConfig,
  inboundTraceparent: string,
): Promise<JsonResponse> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body || "{}");
  } catch {
    return { status: 400, body: { error: "invalid JSON body" } };
  }
  const action = (parsed as { action?: unknown }).action;
  if (!action || typeof action !== "object") {
    return { status: 400, body: { error: "body must be {action: {...}}" } };
  }
  const a = action as Record<string, unknown>;
  const actionId = typeof a.actionId === "string" ? a.actionId : "unspecified-action";

  // Local span for this evaluation (child of the inbound trace).
  const evalTraceparent = childTraceparent(inboundTraceparent);

  // 1) Local severity gate.
  let gateAllow = false;
  let gateRationale = "";
  let gateLambda: number | null = null;
  let gateFormula = "ThresholdPolicySeverity";
  try {
    const gate = thresholdPolicySeverityGate();
    const decision = gate({
      actionId,
      severity: (a.severity ?? "medium") as Parameters<typeof gate>[0]["severity"],
      decisionClass: a.decisionClass as Parameters<typeof gate>[0]["decisionClass"],
      confidence: typeof a.confidence === "number" ? a.confidence : 0,
      witnesses: Array.isArray(a.witnesses)
        ? (a.witnesses as Parameters<typeof gate>[0]["witnesses"])
        : [],
    });
    gateAllow = decision.allow;
    gateRationale = decision.rationale;
    gateLambda = decision.lambdaScore;
    gateFormula = decision.formula;
  } catch (error) {
    return { status: 400, body: { error: (error as Error).message } };
  }

  // 2) Immune delegation to sentra (child span of this evaluation).
  let immuneDecision: "allow" | "deny" | "skipped" = "skipped";
  let immuneRationale = "immune wire not configured (no SENTRA_URL)";
  let immuneReached = false;
  if (config.sentraUrl) {
    const verdict = await inspectViaSentra(actionId, a, {
      baseUrl: config.sentraUrl,
      traceparent: evalTraceparent,
      failOpen: config.sentraFailOpen,
    });
    immuneDecision = verdict.decision;
    immuneRationale = verdict.rationale;
    immuneReached = verdict.reachedSentra;
  }

  // 3) Combine. Sentra deny has veto. Decide who controlled the verdict.
  let decision: "allow" | "deny";
  let decidedBy: "a11oy.gate" | "sentra.immune" | "a11oy.gate+sentra.immune";
  let rationale: string;
  if (immuneDecision === "deny") {
    decision = "deny";
    decidedBy = "sentra.immune";
    rationale = `immune veto: ${immuneRationale}`;
  } else if (!gateAllow) {
    decision = "deny";
    decidedBy = "a11oy.gate";
    rationale = `policy gate denied: ${gateRationale}`;
  } else {
    decision = "allow";
    decidedBy =
      immuneDecision === "allow" ? "a11oy.gate+sentra.immune" : "a11oy.gate";
    rationale =
      immuneDecision === "allow"
        ? `policy gate allowed and immune system cleared: ${gateRationale}`
        : `policy gate allowed (immune wire not configured): ${gateRationale}`;
  }

  // 4) Mint a hash-chained receipt for the decision (the bloodstream).
  const receipt = recordDecisionReceipt(
    config,
    {
      actionId,
      decision,
      decidedBy,
      gate: gateFormula,
      immune: { decision: immuneDecision, reachedSentra: immuneReached },
    },
    evalTraceparent,
  );

  return {
    status: 200,
    body: {
      actionId,
      decision,
      gate: gateFormula,
      decidedBy,
      rationale,
      lambdaScore: gateLambda,
      receiptHash: receipt.merkle_root,
      traceparent: evalTraceparent,
      immune: {
        decision: immuneDecision,
        reachedSentra: immuneReached,
        rationale: immuneRationale,
      },
    },
  };
}

export function createMeshServer(config: MeshConfig): http.Server {
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

      // Mesh-special route: policy/evaluate with immune delegation.
      if (req.method === "POST" && url.pathname === "/v1/policy/evaluate") {
        const r = await evaluatePolicy(body, config, inbound);
        // Echo the evaluation traceparent so callers can correlate.
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

export function startMeshServer(config: MeshConfig): Promise<http.Server> {
  const server = createMeshServer(config);
  return new Promise((resolve) => {
    server.listen(config.port, config.host, () => {
      const addr = server.address();
      const boundPort = typeof addr === "object" && addr ? addr.port : config.port;
      console.log(
        JSON.stringify({
          msg: "a11oy mesh-serve listening",
          host: config.host,
          port: boundPort,
          ledger: config.ledgerPath,
          sentra: config.sentraUrl ?? "(not configured)",
        }),
      );
      resolve(server);
    });
  });
}

function main(): void {
  const config = parseMeshConfig(process.argv.slice(2));
  void startMeshServer(config);
}

const invokedDirectly =
  process.argv[1] !== undefined && process.argv[1].endsWith("mesh-serve.ts");
if (invokedDirectly) {
  main();
}
