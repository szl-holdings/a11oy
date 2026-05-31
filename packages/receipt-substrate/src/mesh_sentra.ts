// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// mesh_sentra.ts — a11oy → sentra immune delegation client (Wire B).
//
// The 8-gate severity policy already runs in a11oy (thresholdPolicySeverity).
// The *immune* verdict (threat-signature / egress inspection) lives in sentra.
// Rather than duplicate sentra's threat logic in a11oy, a11oy delegates: it
// POSTs the action to sentra's immune endpoint and consumes the verdict before
// admission. This is the wire the mining report flagged as missing
// (anatomy-alive layer 7 = NOT-YET-WIRED; "no sibling repo calls sentra").
//
// The call carries a W3C `traceparent` header so the immune span is a child of
// the a11oy evaluation span (nervous-system wire, Wire E). The client fails
// CLOSED by policy default: if sentra is unreachable, the immune verdict is a
// deny with reason "immune system unreachable", honoring the doctrine principle
// "Governance Before Velocity". Callers can opt into fail-open for non-critical
// paths via { failOpen: true }.

export interface SentraImmuneVerdict {
  readonly actionId: string;
  readonly decision: "allow" | "deny";
  readonly gate: string;
  readonly decidedBy: "sentra.immune";
  readonly rationale: string;
  readonly lambdaScore: number;
  readonly receiptHash: string;
  readonly traceparent: string;
  /** True when the verdict came from sentra; false when synthesized (e.g. unreachable). */
  readonly reachedSentra: boolean;
}

export interface SentraClientOptions {
  /** Base URL of sentra's immune endpoint, e.g. http://127.0.0.1:8090 */
  readonly baseUrl: string;
  /** traceparent of the parent (a11oy) span; forwarded so sentra makes a child. */
  readonly traceparent?: string;
  /** Per-call timeout in ms (default 2000). */
  readonly timeoutMs?: number;
  /** If sentra is unreachable, allow instead of deny. Default false (fail-closed). */
  readonly failOpen?: boolean;
}

/**
 * Ask sentra's immune system to inspect an action. Returns a verdict shaped
 * like a PolicyDecision (decidedBy = "sentra.immune").
 */
export async function inspectViaSentra(
  actionId: string,
  action: Record<string, unknown>,
  opts: SentraClientOptions,
): Promise<SentraImmuneVerdict> {
  const timeoutMs = opts.timeoutMs ?? 2000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.traceparent) headers["traceparent"] = opts.traceparent;
    const res = await fetch(`${opts.baseUrl.replace(/\/$/, "")}/v1/inspect`, {
      method: "POST",
      headers,
      body: JSON.stringify({ actionId, action, traceparent: opts.traceparent }),
      signal: controller.signal,
    });
    if (!res.ok) {
      return unreachable(actionId, opts, `sentra returned HTTP ${res.status}`);
    }
    const body = (await res.json()) as Partial<SentraImmuneVerdict>;
    return {
      actionId: body.actionId ?? actionId,
      decision: body.decision === "deny" ? "deny" : "allow",
      gate: body.gate ?? "sentra.immune.signature-scan",
      decidedBy: "sentra.immune",
      rationale: body.rationale ?? "sentra immune verdict",
      lambdaScore: typeof body.lambdaScore === "number" ? body.lambdaScore : 0,
      receiptHash: body.receiptHash ?? "",
      traceparent: body.traceparent ?? opts.traceparent ?? "",
      reachedSentra: true,
    };
  } catch (error) {
    return unreachable(actionId, opts, `immune system unreachable: ${(error as Error).message}`);
  } finally {
    clearTimeout(timer);
  }
}

function unreachable(
  actionId: string,
  opts: SentraClientOptions,
  reason: string,
): SentraImmuneVerdict {
  const failOpen = opts.failOpen ?? false;
  return {
    actionId,
    decision: failOpen ? "allow" : "deny",
    gate: "sentra.immune.unreachable",
    decidedBy: "sentra.immune",
    rationale: failOpen
      ? `${reason} — fail-open configured, action not immune-screened`
      : `${reason} — fail-closed (Governance Before Velocity)`,
    lambdaScore: 0,
    receiptHash: "",
    traceparent: opts.traceparent ?? "",
    reachedSentra: false,
  };
}
