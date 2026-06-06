// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
// Doctrine v7
/**
 * a11oy-policy-client.ts — rosie → a11oy policy evaluation client (Wire D).
 *
 * rosie is the operator console: when the assistant proposes a consequential
 * action, the human-in-the-loop gate must reflect a REAL policy verdict, not a
 * UI guess. The cross-repo mining report found the rosie → a11oy client
 * missing. This client closes that gap: before the "Propose Action" panel
 * offers a Confirm button, it POSTs the proposed action to a11oy's
 * `/v1/policy/evaluate` and consumes the PolicyDecision (which itself folds in
 * sentra's immune verdict via Wire B).
 *
 * Network discipline mirrors api-client.ts:
 *  - No request until a non-empty a11oy base URL is configured.
 *  - A W3C `traceparent` is forwarded so a11oy's evaluation span is a child of
 *    the operator's proposal span (nervous-system wire, Wire E).
 *  - Fails CLOSED: any error => decision "deny" ("Governance Before Velocity").
 *    The panel renders a denied proposal as non-confirmable.
 */

/** The action shape a11oy's gate expects (matches @szl-holdings/anatomy-contracts ActionProposal). */
export interface PolicyActionInput {
  readonly actionId: string;
  readonly action?: string;
  readonly target?: string;
  readonly severity?: 'low' | 'medium' | 'high' | 'critical';
  readonly decisionClass?: string;
  readonly confidence?: number;
  readonly witnesses?: readonly unknown[];
}

/** a11oy's PolicyDecision (matches the serve.ts /v1/policy/evaluate response). */
export interface PolicyDecision {
  readonly actionId: string;
  readonly decision: 'allow' | 'deny';
  readonly gate: string;
  readonly decidedBy: 'a11oy.gate' | 'sentra.immune' | 'a11oy.gate+sentra.immune';
  readonly rationale: string;
  readonly lambdaScore: number | null;
  readonly receiptHash: string;
  readonly traceparent: string;
  /** True when a11oy actually returned a verdict; false when synthesized (deny on error). */
  readonly reachedA11oy: boolean;
}

export interface PolicyClientOptions {
  /** a11oy mesh-serve base URL, e.g. http://127.0.0.1:8088. Empty => unconfigured. */
  readonly a11oyBase: string;
  /** traceparent of the operator proposal span; forwarded so a11oy makes a child. */
  readonly traceparent?: string;
  /** Per-call timeout in ms (default 3000). */
  readonly timeoutMs?: number;
  /** Optional bearer token forwarded as Authorization (never logged). */
  readonly token?: string;
}

export class A11oyNotConfiguredError extends Error {
  constructor() {
    super('rosie: a11oy base URL is not configured');
    this.name = 'A11oyNotConfiguredError';
  }
}

/**
 * Ask a11oy to evaluate a proposed action. Returns a PolicyDecision. Fails
 * CLOSED: on any network/parse error or non-2xx, returns decision "deny" with
 * reachedA11oy=false so the panel cannot offer Confirm.
 */
export async function evaluateProposal(
  action: PolicyActionInput,
  opts: PolicyClientOptions,
): Promise<PolicyDecision> {
  const base = (opts.a11oyBase ?? '').replace(/\/+$/, '');
  if (!base) throw new A11oyNotConfiguredError();

  const timeoutMs = opts.timeoutMs ?? 3000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  if (opts.traceparent) headers['traceparent'] = opts.traceparent;
  if (opts.token) headers['Authorization'] = `Bearer ${opts.token}`;

  try {
    const res = await fetch(`${base}/v1/policy/evaluate`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ action }),
      signal: controller.signal,
    });
    if (!res.ok) {
      return denied(action.actionId, opts, `a11oy returned HTTP ${res.status}`, false);
    }
    const body = (await res.json()) as Partial<PolicyDecision> & {
      receipt_hash?: string;
      lambda_score?: number | null;
    };
    return {
      actionId: body.actionId ?? action.actionId,
      decision: body.decision === 'deny' ? 'deny' : 'allow',
      gate: body.gate ?? 'a11oy.gate',
      decidedBy: body.decidedBy ?? 'a11oy.gate',
      rationale: body.rationale ?? 'a11oy policy verdict',
      // Accept both the mesh-serve shape (lambdaScore) and the base serve shape (lambda_score).
      lambdaScore:
        typeof body.lambdaScore === 'number'
          ? body.lambdaScore
          : typeof body.lambda_score === 'number'
            ? body.lambda_score
            : null,
      receiptHash: body.receiptHash ?? body.receipt_hash ?? '',
      traceparent: body.traceparent ?? opts.traceparent ?? '',
      reachedA11oy: true,
    };
  } catch (error) {
    return denied(action.actionId, opts, `a11oy unreachable: ${(error as Error).message}`, false);
  } finally {
    clearTimeout(timer);
  }
}

function denied(
  actionId: string,
  opts: PolicyClientOptions,
  reason: string,
  reachedA11oy: boolean,
): PolicyDecision {
  return {
    actionId,
    decision: 'deny',
    gate: 'a11oy.unreachable',
    decidedBy: 'a11oy.gate',
    rationale: `${reason} — fail-closed (Governance Before Velocity)`,
    lambdaScore: null,
    receiptHash: '',
    traceparent: opts.traceparent ?? '',
    reachedA11oy,
  };
}
