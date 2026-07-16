// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// a11oyClient.ts — browser/runtime client for a11oy's HTTP server (the routes
// added by `a11oy serve`). This is the data layer behind the 5 operator-console
// routes. It is deliberately dependency-free (uses fetch) so it runs unchanged
// in the browser SPA and under node:test against a real loopback server.
//
// Endpoints (a11oy serve — see packages/receipt-substrate/src/serve.ts):
//   GET  /healthz
//   GET  /readyz
//   GET  /v1/ledger?limit=N
//   GET  /v1/ledger/{hash}
//   POST /v1/verify   {ledger:[...]}  -> {valid, broken_at, errors}
//   POST /v1/policy/evaluate {action}  -> {decision, gate, receipt_hash, ...}
//
// No mocked data path: every method issues a real fetch and returns the parsed
// real response.
//
// Authored for SZL Holdings. Signed-off per repository DCO.

export interface OperationalReceipt {
  readonly receipt_id?: string;
  readonly merkle_root?: string;
  readonly [key: string]: unknown;
}

export interface Health {
  readonly status: string;
  readonly sha: string;
  readonly ts: string;
}

export interface Readiness {
  readonly status: string;
  readonly ledger: string;
  readonly reason?: string;
}

export interface LedgerPage {
  readonly count: number;
  readonly total: number;
  readonly receipts: OperationalReceipt[];
}

export interface VerifyResult {
  readonly valid: boolean;
  readonly broken_at: number | null;
  readonly errors: string[];
}

export interface PolicyDecision {
  readonly decision: "allow" | "deny";
  readonly gate: string;
  readonly receipt_hash: string;
  readonly rationale?: string;
  readonly lambda_score?: number;
}

export interface PolicyActionInput {
  readonly actionId?: string;
  readonly severity?: "low" | "medium" | "high" | "critical";
  readonly decisionClass?: string;
  readonly confidence?: number;
  readonly witnesses?: unknown[];
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class A11oyClient {
  private readonly base: string;
  private readonly fetchImpl: FetchLike;

  constructor(baseUrl: string, fetchImpl?: FetchLike) {
    this.base = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
    // Allow injection for tests; default to global fetch (browser + Node 18+).
    this.fetchImpl = fetchImpl ?? ((i, init) => fetch(i, init));
  }

  private async getJson<T>(path: string): Promise<T> {
    const res = await this.fetchImpl(this.base + path, { method: "GET" });
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return (await res.json()) as T;
  }

  private async postJson<T>(path: string, body: unknown): Promise<T> {
    const res = await this.fetchImpl(this.base + path, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
    return (await res.json()) as T;
  }

  /** Route 1 backing call: liveness. */
  health(): Promise<Health> {
    return this.getJson<Health>("/healthz");
  }

  /** Route 1 backing call: readiness (ledger readable). */
  readiness(): Promise<Readiness> {
    return this.getJson<Readiness>("/readyz");
  }

  /** Route 2 (Proof Ledger) backing call. */
  ledger(limit = 20): Promise<LedgerPage> {
    return this.getJson<LedgerPage>(`/v1/ledger?limit=${encodeURIComponent(String(limit))}`);
  }

  /** Route 3 (Receipt detail) backing call. */
  receipt(hash: string): Promise<{ receipt: OperationalReceipt }> {
    return this.getJson<{ receipt: OperationalReceipt }>(`/v1/ledger/${encodeURIComponent(hash)}`);
  }

  /** Route 4 (Verify) backing call. */
  verify(ledger: OperationalReceipt[]): Promise<VerifyResult> {
    return this.postJson<VerifyResult>("/v1/verify", { ledger });
  }

  /** Route 5 (Policy) backing call. */
  evaluatePolicy(action: PolicyActionInput): Promise<PolicyDecision> {
    return this.postJson<PolicyDecision>("/v1/policy/evaluate", { action });
  }

  /** Route 6 (Khipu demo) backing call — same-origin, in-image recorded traces. */
  khipuDemo(): Promise<KhipuDemo> {
    return this.getJson<KhipuDemo>("/api/khipu/demo");
  }
}

export interface KhipuTrace {
  readonly caseId: string;
  readonly sourceFile: string;
  readonly category: string;
  readonly inputJson: unknown;
  readonly outputJson: string;
  readonly schemaValid: boolean;
  readonly decision: string | null;
  readonly verdict: string;
  readonly seed: number;
  readonly runtime: Record<string, unknown>;
  readonly recordedAtUtc: string;
}

export interface KhipuDemoProvenance {
  readonly label: string;
  readonly reproCommands?: string[];
  readonly harnessSource?: string;
  readonly localRunCommand?: string;
}

export interface KhipuDemo {
  readonly ok: boolean;
  readonly traces: KhipuTrace[];
  readonly provenance: KhipuDemoProvenance;
  readonly error?: string;
}

/** The 5 operator-console routes, derived from the mined a11oy MCP route surface. */
export const CONSOLE_ROUTES = [
  { path: "/", label: "Health", source: "GET /healthz + GET /readyz" },
  { path: "/ledger", label: "Proof Ledger", source: "GET /v1/ledger" },
  { path: "/receipt/:hash", label: "Receipt", source: "GET /v1/ledger/{hash}" },
  { path: "/verify", label: "Verify", source: "POST /v1/verify" },
  { path: "/policy", label: "Policy", source: "POST /v1/policy/evaluate" },
  { path: "/khipu-demo", label: "Khipu Demo", source: "GET /api/khipu/demo" },
] as const;
