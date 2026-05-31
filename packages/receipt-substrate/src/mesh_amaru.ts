// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// mesh_amaru.ts — a11oy → amaru reason proxy client (Wire C).
//
// The mining report found that a11oy never queried amaru: the brain
// (amaru, the 7-chakra runtime) and the skeleton/heart (a11oy) were not wired.
// `/v1/reason` closes that gap. a11oy proxies a reason request to amaru's
// `POST /chakra/{name}/evaluate`, reads the chakra kernel output, and returns a
// rationale a caller (e.g. rosie) can render. amaru stays the source of truth
// for reasoning; a11oy does not duplicate any chakra logic.
//
// The call carries a W3C `traceparent` header so amaru's evaluation span is a
// child of the a11oy reason span (nervous-system wire, Wire E). The client
// fails CLOSED by policy default: if amaru is unreachable, the reason verdict
// is "hold" with an explicit rationale, honoring "Governance Before Velocity".

const CHAKRAS = [
  "root",
  "sacral",
  "solar",
  "heart",
  "throat",
  "third_eye",
  "crown",
] as const;

export type ChakraName = (typeof CHAKRAS)[number];

export function isChakra(value: string): value is ChakraName {
  return (CHAKRAS as readonly string[]).includes(value);
}

export interface AmaruReasonResult {
  readonly chakra: string;
  /** amaru's proof identifier for the kernel that produced this rationale. */
  readonly proofId: string | null;
  /** Kernel verdict surfaced from amaru's output (e.g. "guard", "hold", "go"). */
  readonly verdict: string;
  /** Human-readable rationale synthesized from amaru's kernel output. */
  readonly rationale: string;
  /** Raw chakra kernel output (opaque to a11oy). */
  readonly output: unknown;
  /** amaru receipt hash for the evaluation (the brain's own ledger entry). */
  readonly receiptHash: string | null;
  /** True when the rationale came from amaru; false when synthesized locally. */
  readonly reachedAmaru: boolean;
  /** traceparent forwarded to amaru (parent span = the a11oy reason span). */
  readonly traceparent: string;
}

export interface AmaruClientOptions {
  /** Base URL of amaru's FastAPI sidecar, e.g. http://127.0.0.1:8731 */
  readonly baseUrl: string;
  /** traceparent of the parent (a11oy) span; forwarded so amaru makes a child. */
  readonly traceparent?: string;
  /** Per-call timeout in ms (default 3000). */
  readonly timeoutMs?: number;
  /** If amaru is unreachable, return verdict "review" instead of "hold". Default false. */
  readonly failOpen?: boolean;
}

/**
 * Extract a verdict string from a chakra kernel output. amaru kernels emit
 * a `verdict` field (e.g. "guard"/"hold"/"go"); fall back to "unknown".
 */
function verdictOf(output: unknown): string {
  if (output && typeof output === "object" && "verdict" in output) {
    const v = (output as { verdict?: unknown }).verdict;
    if (typeof v === "string") return v;
  }
  return "unknown";
}

/**
 * Ask amaru's brain runtime to reason about an envelope through a named chakra
 * kernel. Returns a rationale shaped for the ReasonResponse contract.
 */
export async function reasonViaAmaru(
  chakra: string,
  envelope: Record<string, unknown>,
  opts: AmaruClientOptions,
): Promise<AmaruReasonResult> {
  if (!isChakra(chakra)) {
    return {
      chakra,
      proofId: null,
      verdict: "hold",
      rationale: `unknown chakra "${chakra}"; valid: ${CHAKRAS.join(", ")}`,
      output: null,
      receiptHash: null,
      reachedAmaru: false,
      traceparent: opts.traceparent ?? "",
    };
  }
  const timeoutMs = opts.timeoutMs ?? 3000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (opts.traceparent) headers["traceparent"] = opts.traceparent;
    const res = await fetch(
      `${opts.baseUrl.replace(/\/$/, "")}/chakra/${encodeURIComponent(chakra)}/evaluate`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ envelope }),
        signal: controller.signal,
      },
    );
    if (!res.ok) {
      return unreachable(chakra, opts, `amaru returned HTTP ${res.status}`);
    }
    const body = (await res.json()) as {
      chakra?: string;
      proof_id?: string | null;
      output?: unknown;
      error?: string | null;
      receipt?: { selfHash?: string } | null;
    };
    const verdict = verdictOf(body.output);
    const receiptHash =
      body.receipt && typeof body.receipt.selfHash === "string"
        ? body.receipt.selfHash
        : null;
    const rationale = body.error
      ? `amaru.${chakra} surfaced an error: ${body.error}`
      : `amaru.${chakra} verdict=${verdict} (proof ${body.proof_id ?? "n/a"})`;
    return {
      chakra: body.chakra ?? chakra,
      proofId: body.proof_id ?? null,
      verdict,
      rationale,
      output: body.output ?? null,
      receiptHash,
      reachedAmaru: true,
      traceparent: opts.traceparent ?? "",
    };
  } catch (error) {
    return unreachable(chakra, opts, `brain unreachable: ${(error as Error).message}`);
  } finally {
    clearTimeout(timer);
  }
}

function unreachable(
  chakra: string,
  opts: AmaruClientOptions,
  reason: string,
): AmaruReasonResult {
  const failOpen = opts.failOpen ?? false;
  return {
    chakra,
    proofId: null,
    verdict: failOpen ? "review" : "hold",
    rationale: failOpen
      ? `${reason} — fail-open configured, reasoning not consulted`
      : `${reason} — fail-closed (Governance Before Velocity)`,
    output: null,
    receiptHash: null,
    reachedAmaru: false,
    traceparent: opts.traceparent ?? "",
  };
}

export { CHAKRAS };
