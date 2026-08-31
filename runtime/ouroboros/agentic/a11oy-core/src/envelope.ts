// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Machine-to-Machine Envelope — anti-hallucination contract.
// Every cross-agent message MUST satisfy this validator.

import { REPLAY_ROOT, lambdaGate, mkAxisScore, type Axes } from "../../formulas/src/index.js";

const FORBIDDEN = [
  /\bJr\./i, /AlloyScape/i, /Glass\s*Wing/i, /Glasswing/i,
  /\bMythos\b/i, /Stephen\s*Paul/i, /Perplexity\s*Computer/i, /\banonymous\b/i,
];

const KNOWN_LLM_DOMAINS = [
  "openai.com", "anthropic.com", "perplexity.ai",
  "chat.openai.com", "claude.ai", "you.com", "phind.com",
];

const seenNonces = new Set<string>();

export type EvidenceKind =
  | { kind: "url"; url: string }
  | { kind: "file"; path: string; sha256: string }
  | { kind: "formula"; name: string; inputs: unknown; output: unknown }
  | { kind: "test"; command: string; exitCode: number; stdoutSha256: string }
  | { kind: "i_dont_know" };

export interface Claim {
  text: string;
  evidence: EvidenceKind[];
}

export interface Envelope<T = unknown> {
  replayRoot: string;
  agent: "cursor" | "claude" | "replit" | "a11oy" | "mcp";
  agentVersion: string;
  nonce: string;
  ts: string;
  // R7+R8 cannot be omitted; lambda + 9 axis scores are required on every envelope.
  doctrine: {
    lambda: number;
    axes: Record<keyof Axes, number>;
    forbiddenScanned: true;
    licenseAllowlistOk: true;
  };
  claims: Claim[];
  action?: { name: string; blocked?: boolean; reasons?: string[] };
  payload: T;
  hmac?: string;
}

export interface ValidationResult {
  ok: boolean;
  rejections: string[];
}

export function validateEnvelope<T>(e: Envelope<T>): ValidationResult {
  const r: string[] = [];

  // R1 — replayRoot must match
  if (e.replayRoot !== REPLAY_ROOT) r.push("R1: replayRoot mismatch or missing");

  // R4 — agent value
  const validAgents = new Set(["cursor", "claude", "replit", "a11oy", "mcp"]);
  if (!validAgents.has(e.agent)) r.push(`R4: invalid agent '${e.agent}'`);

  // R5 — doctrine flags
  if (!e.doctrine?.forbiddenScanned) r.push("R5: forbiddenScanned must be true");
  if (!e.doctrine?.licenseAllowlistOk) r.push("R5: licenseAllowlistOk must be true");

  // R6 — forbidden patterns across all string fields
  const blob = JSON.stringify(e);
  for (const re of FORBIDDEN) {
    if (re.test(blob)) {
      r.push(`R6: forbidden pattern hit: ${re.source}`);
    }
  }

  // R7 — Λ gate. lambda is REQUIRED; omission is a violation.
  if (typeof e.doctrine?.lambda !== "number") {
    r.push("R7: doctrine.lambda is required (missing)");
  } else if (e.doctrine.lambda < 0.90) {
    r.push(`R7: lambda ${e.doctrine.lambda} < 0.90`);
  }

  // R8 — hard floors. All 9 axes REQUIRED; omission of either hard-floor axis is a violation.
  const REQUIRED_AXES = [
    "semanticCoherence","empiricalGrounding","logicalConsistency",
    "moralGrounding","epistemicHumility","measurabilityHonesty",
    "reversibility","provenance","replayability",
  ] as const;
  if (!e.doctrine?.axes) {
    r.push("R8: doctrine.axes is required (missing)");
  } else {
    for (const k of REQUIRED_AXES) {
      if (typeof (e.doctrine.axes as any)[k] !== "number") {
        r.push(`R8: doctrine.axes.${k} is required (missing)`);
      }
    }
    if (typeof e.doctrine.axes.moralGrounding === "number" && e.doctrine.axes.moralGrounding < 0.95) {
      r.push("R8: moralGrounding < 0.95");
    }
    if (typeof e.doctrine.axes.measurabilityHonesty === "number" && e.doctrine.axes.measurabilityHonesty < 0.95) {
      r.push("R8: measurabilityHonesty < 0.95");
    }
  }

  // R2 — every claim needs evidence
  for (const [i, c] of e.claims.entries()) {
    if (!Array.isArray(c.evidence) || c.evidence.length === 0) {
      r.push(`R2: claim[${i}] has no evidence`);
      continue;
    }
    // R3 — claim's only evidence is a URL on a known LLM domain
    if (c.evidence.length === 1 && c.evidence[0].kind === "url") {
      try {
        const u = new URL(c.evidence[0].url);
        if (KNOWN_LLM_DOMAINS.some(d => u.hostname.endsWith(d))) {
          r.push(`R3: claim[${i}] only cites an LLM-output domain`);
        }
      } catch { r.push(`R3: claim[${i}] has malformed URL`); }
    }
  }

  // R9 — nonce replay
  if (!e.nonce || typeof e.nonce !== "string" || e.nonce.length < 8) {
    r.push("R9: nonce missing or too short");
  } else if (seenNonces.has(e.nonce)) {
    r.push(`R9: nonce '${e.nonce}' already seen`);
  } else {
    seenNonces.add(e.nonce);
    if (seenNonces.size > 100_000) {
      // bounded set — drop the oldest half to avoid unbounded growth
      const arr = Array.from(seenNonces);
      seenNonces.clear();
      for (const n of arr.slice(arr.length / 2)) seenNonces.add(n);
    }
  }

  // R10 — timestamp window
  const t = Date.parse(e.ts);
  if (!Number.isFinite(t)) {
    r.push("R10: ts not parseable");
  } else {
    const now = Date.now();
    if (t - now > 60_000) r.push("R10: ts > 60s in the future");
    if (now - t > 10 * 60_000) r.push("R10: ts > 10min in the past");
  }

  return { ok: r.length === 0, rejections: r };
}

// makeEnvelope now REQUIRES all 9 axes — the doctrine 9-axis gate cannot be
// constructed with missing axes. This prevents the R7/R8 bypass identified in
// the audit (omitted lambda/axes used to silently skip the gate).
export function makeEnvelope<T>(args: {
  agent: Envelope["agent"];
  payload: T;
  claims: Claim[];
  action?: Envelope["action"];
  axes: Record<keyof Axes, number>;   // REQUIRED
  ts?: string;                         // optional injection for replay determinism
  nonce?: string;                      // optional injection for replay determinism
}): Envelope<T> {
  const values = Object.values(args.axes);
  if (values.length !== 9) {
    throw new Error(`makeEnvelope: requires all 9 axes (got ${values.length})`);
  }
  const lambda = Math.min(...values);
  return {
    replayRoot: REPLAY_ROOT,
    agent: args.agent,
    agentVersion: "1.0.0",
    nonce: args.nonce ?? crypto.randomUUID(),
    ts: args.ts ?? new Date().toISOString(),
    doctrine: { lambda, axes: args.axes, forbiddenScanned: true, licenseAllowlistOk: true },
    claims: args.claims,
    action: args.action,
    payload: args.payload,
  };
}
