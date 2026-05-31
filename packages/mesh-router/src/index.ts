// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// mesh-router — typed HTTP router from a11oy (the substrate) to its sibling
// organs. a11oy is the skeleton: it routes reasoning to amaru (the brain),
// policy verdicts to sentra (the immune organ), and operator I/O to rosie
// (the operator console). This module is the substrate-side client for those
// network calls.
//
// Source of this instillation: the mesh "wires that SHOULD exist but DON'T"
// findings (MINING_REPORT.md §4 #2 and #3) — a11oy -> sentra delegation and
// a11oy -> amaru memory query had no runtime client in a11oy. This package is
// that client. Strategy: C (wire over HTTP using each producer's existing
// server), per the instillation strategy preference order.
//
// Honesty note (Doctrine v7 §2): amaru exposes a FastAPI sidecar with the
// routes called here (GET /state, GET /receipts, POST /chakra/{name}/evaluate
// — verified in the cross-repo mining server index). Sentra ships
// runtime/immune_server.py (sentra PR #96) exposing POST /v1/inspect — the
// real inbound immune endpoint. The 2026-05-31 post-merge re-test wave found
// Wire B was contract-mismatched (a11oy was calling /v1/verdict; sentra serves
// /v1/inspect). This module now targets the deployed sentra contract:
//   path:  POST /v1/inspect
//   body:  {actionId, action, traceparent?}
//   resp:  {actionId, decision: "allow"|"deny", gate, decidedBy, rationale,
//           lambdaScore, receiptHash, traceparent}
// The exposed SentraVerdict shape ({decision, reason}) is preserved for
// existing callers; `reason` is populated from sentra's `rationale` field on
// allow + deny.
//
// No mocked data path: every function issues a real HTTP request via
// node:http/https and parses the real response. The accompanying tests boot a
// real loopback server and exercise these functions over real TCP.
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import * as http from "node:http";
import * as https from "node:https";

/** A resolved endpoint for one sibling organ. */
export interface OrganEndpoint {
  /** Base URL, e.g. "http://amaru.svc:8000". No trailing slash required. */
  readonly baseUrl: string;
  /** Per-request timeout in milliseconds. */
  readonly timeoutMs?: number;
}

/** The three organs a11oy routes to. */
export interface MeshConfig {
  /** amaru — reasoning / memory (the brain). */
  readonly amaru?: OrganEndpoint;
  /** sentra — policy / threat verdicts (the immune organ). */
  readonly sentra?: OrganEndpoint;
  /** rosie — operator I/O (the operator console). */
  readonly rosie?: OrganEndpoint;
}

/** A structured transport result; never throws on a non-2xx status. */
export interface MeshResponse<T = unknown> {
  readonly ok: boolean;
  readonly status: number;
  readonly body: T | null;
  /** Populated when the call could not complete (timeout, connection, parse). */
  readonly error?: string;
}

const DEFAULT_TIMEOUT_MS = 5_000;

function trimSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

/**
 * Issue a single JSON HTTP request. Pure transport: it resolves with a
 * MeshResponse for any HTTP status, and only sets `error` for transport-level
 * failures (DNS, connect, timeout, body parse). It never throws.
 */
export function meshRequest<T = unknown>(
  endpoint: OrganEndpoint,
  method: "GET" | "POST",
  path: string,
  payload?: unknown,
): Promise<MeshResponse<T>> {
  const url = new URL(trimSlash(endpoint.baseUrl) + path);
  const isHttps = url.protocol === "https:";
  const lib = isHttps ? https : http;
  const data = payload === undefined ? undefined : JSON.stringify(payload);
  const timeoutMs = endpoint.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  return new Promise<MeshResponse<T>>((resolve) => {
    const req = lib.request(
      {
        protocol: url.protocol,
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + url.search,
        method,
        headers: {
          accept: "application/json",
          ...(data !== undefined
            ? {
                "content-type": "application/json",
                "content-length": Buffer.byteLength(data),
              }
            : {}),
        },
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c: Buffer) => chunks.push(c));
        res.on("end", () => {
          const raw = Buffer.concat(chunks).toString("utf8");
          const status = res.statusCode ?? 0;
          let body: T | null = null;
          let parseError: string | undefined;
          if (raw.length > 0) {
            try {
              body = JSON.parse(raw) as T;
            } catch {
              parseError = "response body was not valid JSON";
            }
          }
          resolve({
            ok: status >= 200 && status < 300 && parseError === undefined,
            status,
            body,
            error: parseError,
          });
        });
      },
    );

    req.on("error", (err) => {
      resolve({ ok: false, status: 0, body: null, error: err.message });
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve({ ok: false, status: 0, body: null, error: `timeout after ${timeoutMs}ms` });
    });

    if (data !== undefined) req.write(data);
    req.end();
  });
}

// --- amaru: the brain (reasoning / memory) ---------------------------------

export interface AmaruState {
  readonly [key: string]: unknown;
}

/** Query amaru's current memory/overwatch state (GET /state). */
export function queryAmaruState(cfg: MeshConfig): Promise<MeshResponse<AmaruState>> {
  if (!cfg.amaru) {
    return Promise.resolve({ ok: false, status: 0, body: null, error: "amaru endpoint not configured" });
  }
  return meshRequest<AmaruState>(cfg.amaru, "GET", "/state");
}

/** Read amaru's published receipts (GET /receipts). */
export function queryAmaruReceipts(cfg: MeshConfig): Promise<MeshResponse> {
  if (!cfg.amaru) {
    return Promise.resolve({ ok: false, status: 0, body: null, error: "amaru endpoint not configured" });
  }
  return meshRequest(cfg.amaru, "GET", "/receipts");
}

/** Ask amaru to evaluate a named chakra (POST /chakra/{name}/evaluate). */
export function evaluateAmaruChakra(
  cfg: MeshConfig,
  chakra: string,
  input: unknown,
): Promise<MeshResponse> {
  if (!cfg.amaru) {
    return Promise.resolve({ ok: false, status: 0, body: null, error: "amaru endpoint not configured" });
  }
  return meshRequest(cfg.amaru, "POST", `/chakra/${encodeURIComponent(chakra)}/evaluate`, input);
}

// --- sentra: the immune organ (policy / threat verdicts) -------------------

export interface SentraVerdictRequest {
  readonly actionId: string;
  readonly kind: "egress" | "threat" | "admission";
  /** Arbitrary action payload sentra inspects (cmd, url, headers, etc.). */
  readonly payload: unknown;
  /** Optional W3C traceparent so the immune call joins the parent trace. */
  readonly traceparent?: string;
}

/**
 * Externally exposed verdict shape — kept small for callers. The full sentra
 * response is mapped down to {decision, reason} via inspectResponseToVerdict.
 */
export interface SentraVerdict {
  readonly decision: "allow" | "deny";
  readonly reason?: string;
}

/**
 * Sentra's /v1/inspect response shape (anatomy-contracts PolicyDecision). We
 * declare it locally rather than importing to keep mesh-router dependency-free.
 */
interface SentraInspectResponse {
  readonly actionId: string;
  readonly decision: "allow" | "deny";
  readonly gate?: string;
  readonly decidedBy?: string;
  readonly rationale?: string;
  readonly lambdaScore?: number;
  readonly receiptHash?: string;
  readonly traceparent?: string;
}

function inspectResponseToVerdict(r: SentraInspectResponse): SentraVerdict {
  return {
    decision: r.decision,
    reason: r.rationale,
  };
}

/**
 * Translate the public SentraVerdictRequest to sentra's actual /v1/inspect
 * body. sentra accepts `{action, actionId, traceparent}` — the `kind` field on
 * our public request is folded into `action.kind` so sentra's signature-scan
 * can still see it.
 */
function verdictRequestToInspectBody(req: SentraVerdictRequest): {
  action: Record<string, unknown>;
  actionId: string;
  traceparent?: string;
} {
  const action: Record<string, unknown> =
    req.payload && typeof req.payload === "object" && req.payload !== null
      ? { ...(req.payload as Record<string, unknown>), kind: req.kind }
      : { payload: req.payload, kind: req.kind };
  const body: { action: Record<string, unknown>; actionId: string; traceparent?: string } = {
    action,
    actionId: req.actionId,
  };
  if (req.traceparent) body.traceparent = req.traceparent;
  return body;
}

/**
 * Request an admission/egress verdict from sentra before a11oy admits an
 * action. Targets sentra's deployed POST /v1/inspect route. Fails closed
 * (deny) on transport error, missing config, or any non-2xx — so a missing or
 * crashed immune organ never silently allows.
 */
export async function requestSentraVerdict(
  cfg: MeshConfig,
  request: SentraVerdictRequest,
): Promise<SentraVerdict> {
  if (!cfg.sentra) {
    return { decision: "deny", reason: "sentra endpoint not configured (fail closed)" };
  }
  const body = verdictRequestToInspectBody(request);
  const res = await meshRequest<SentraInspectResponse>(
    cfg.sentra,
    "POST",
    "/v1/inspect",
    body,
  );
  if (!res.ok || res.body === null) {
    return { decision: "deny", reason: res.error ?? `sentra returned ${res.status} (fail closed)` };
  }
  // Defensive: if sentra returned an unexpected shape, fail closed.
  if (res.body.decision !== "allow" && res.body.decision !== "deny") {
    return { decision: "deny", reason: `sentra returned unrecognised decision (fail closed)` };
  }
  return inspectResponseToVerdict(res.body);
}

// --- rosie: the operator console (operator I/O) ----------------------------

/** Push an operator-facing event to rosie (POST /v1/events). */
export function notifyRosie(cfg: MeshConfig, event: unknown): Promise<MeshResponse> {
  if (!cfg.rosie) {
    return Promise.resolve({ ok: false, status: 0, body: null, error: "rosie endpoint not configured" });
  }
  return meshRequest(cfg.rosie, "POST", "/v1/events", event);
}

/** Build a MeshConfig from environment variables (all optional). */
export function meshConfigFromEnv(env: NodeJS.ProcessEnv = process.env): MeshConfig {
  const opt = (v: string | undefined): OrganEndpoint | undefined =>
    v && v.trim() ? { baseUrl: v.trim() } : undefined;
  return {
    amaru: opt(env.A11OY_AMARU_URL),
    sentra: opt(env.A11OY_SENTRA_URL),
    rosie: opt(env.A11OY_ROSIE_URL),
  };
}
