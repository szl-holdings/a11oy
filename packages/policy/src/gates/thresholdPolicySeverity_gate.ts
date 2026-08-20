// SPDX-License-Identifier: Apache-2.0
// (c) 2026 Lutar, Stephen P. -- SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Layer 6 -- severity-indexed witness threshold policy gate.
//
// Policy rationale:
//   High-consequence actions should not pass on a flat confidence score. The
//   evidence threshold rises with severity, and the witness quorum rises from
//   2-of-N for ordinary/property actions to 3-of-N for capital/critical actions.
//   This runtime gate is TypeScript-only: it does not claim Lean closure.
//
//   Policy: allow iff confidence >= severity-adjusted threshold and the attested
//   unique witness count meets the required quorum. Allowed decisions emit a
//   deterministic DSSE-shaped HMAC receipt for downstream audit.

import { createHmac, createHash } from "node:crypto";

export type SeverityClass = "low" | "medium" | "high" | "critical" | "capital";
export type DecisionClass = "ordinary" | "property" | "capital";

export interface SeverityWitness {
  id: string;
  role: string;
  attested: boolean;
}

export interface DsseSignature {
  keyid: string;
  sig: string;
}

export interface DsseEnvelope {
  payloadType: "application/vnd.szl.threshold-policy.v1+json";
  payload: string;
  signatures: DsseSignature[];
}

export interface ThresholdPolicySeverityGateConfig {
  baseThreshold?: number;
  severitySlope?: number;
  maxThreshold?: number;
  standardWitnesses?: number;
  capitalWitnesses?: number;
  signingKey?: string;
  keyId?: string;
}

export interface ThresholdPolicySeverityGateOpts {
  actionId: string;
  severity: SeverityClass;
  decisionClass?: DecisionClass;
  confidence: number;
  witnesses: readonly SeverityWitness[];
}

export interface ThresholdPolicySeverityDecision {
  allow: boolean;
  rationale: string;
  formula: "ThresholdPolicySeverity";
  claimStatus: "verified-runtime";
  leanTheorem: null;
  leanFile: null;
  leanCommitSha: null;
  actionId: string;
  severity: SeverityClass;
  decisionClass: DecisionClass;
  confidence: number;
  requiredThreshold: number;
  requiredWitnesses: number;
  attestedWitnesses: number;
  witnessIds: readonly string[];
  lambdaScore: number;
  dsseReceipt?: DsseEnvelope;
}

const DEFAULT_BASE_THRESHOLD = 0.70;
const DEFAULT_SEVERITY_SLOPE = 0.20;
const DEFAULT_MAX_THRESHOLD = 0.95;
const DEFAULT_STANDARD_WITNESSES = 2;
const DEFAULT_CAPITAL_WITNESSES = 3;
// DEMO ONLY — not non-repudiable. DEFAULT_SIGNING_KEY is a hard-coded symmetric
// HMAC secret for local/dev use. HMAC-SHA-256 gives integrity + authenticity to
// key-holders but is NOT an asymmetric signature: anyone with read access to the
// key can mint receipts and there is zero non-repudiation. In production replace
// with an Ed25519 keypair (production signature scheme — non-repudiable) or a
// Sigstore keyless flow (https://docs.sigstore.dev/cosign/signing/signing_with_blobs/).
// See PhD Crypto Verdict 2026-05-30 Finding A2.
const DEFAULT_SIGNING_KEY = "a11oy-threshold-policy-dev-key";
const DEFAULT_KEY_ID = "hmac-sha256:a11oy-threshold-policy-dev";

const SEVERITY_WEIGHT: Record<SeverityClass, number> = {
  low: 0,
  medium: 0.35,
  high: 0.65,
  critical: 0.9,
  capital: 1,
};

function assertUnit(name: string, value: number): void {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`ThresholdPolicySeverityGate: ${name} must be in [0,1]; got ${value}`);
  }
}

function assertPositiveInteger(name: string, value: number): void {
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`ThresholdPolicySeverityGate: ${name} must be a positive integer; got ${value}`);
  }
}

function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`).join(",")}}`;
  }
  throw new Error("ThresholdPolicySeverityGate: unsupported receipt payload value");
}

function b64url(input: string): string {
  return Buffer.from(input, "utf8").toString("base64url");
}

/**
 * Pre-Authentication Encoding for this gate's DSSE-shaped receipt.
 *
 * NOTE — this is NOT the canonical DSSE v1 PAE. The DSSE spec
 * (https://github.com/secure-systems-lab/dsse/blob/master/protocol.md) defines:
 *   PAE = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
 * where "DSSEv1" is a LITERAL prefix (not length-counted) and SP = 0x20.
 * This implementation instead treats "DSSEv1" as a length-counted piece, emitting
 *   LEN("DSSEv1") SP "DSSEv1" SP LEN(type) SP type SP LEN(payload) SP payload
 * so receipts from this gate are NOT wire-compatible with an upstream DSSE
 * verifier or with the canonical encoding being unified in rae1 (a11oy#149).
 * Documented for the comment sweep; logic intentionally unchanged here.
 * See PhD Crypto Verdict 2026-05-30 Finding A1 (three incompatible PAE encodings).
 */
function pae(payloadType: string, payload: string): string {
  const pieces = ["DSSEv1", payloadType, payload];
  return pieces.map((piece) => `${Buffer.byteLength(piece, "utf8")} ${piece}`).join(" ");
}

function signDsse(payload: Record<string, unknown>, signingKey: string, keyid: string): DsseEnvelope {
  const payloadType = "application/vnd.szl.threshold-policy.v1+json" as const;
  const encodedPayload = b64url(canonicalJson(payload));
  // DEMO ONLY — not non-repudiable: this is a symmetric HMAC-SHA-256 MAC tag
  // placed in the DSSE `signatures[].sig` field, not an asymmetric signature.
  // Verifiable only by holders of `signingKey`. See Finding A2 (crypto verdict).
  const sig = createHmac("sha256", signingKey)
    .update(pae(payloadType, encodedPayload), "utf8")
    .digest("base64url");
  return {
    payloadType,
    payload: encodedPayload,
    signatures: [{ keyid, sig }],
  };
}

function uniqueAttestedWitnesses(witnesses: readonly SeverityWitness[]): SeverityWitness[] {
  const seen = new Set<string>();
  const unique: SeverityWitness[] = [];
  for (const witness of witnesses) {
    if (typeof witness.id !== "string" || witness.id.trim() === "") {
      throw new Error("ThresholdPolicySeverityGate: witness id is required");
    }
    if (typeof witness.role !== "string" || witness.role.trim() === "") {
      throw new Error(`ThresholdPolicySeverityGate: witness role is required for ${witness.id}`);
    }
    const id = witness.id.normalize("NFC");
    if (witness.attested && !seen.has(id)) {
      seen.add(id);
      unique.push({ ...witness, id, role: witness.role.normalize("NFC") });
    }
  }
  return unique;
}

export function thresholdPolicySeverityGate(
  config: ThresholdPolicySeverityGateConfig = {}
): (opts: ThresholdPolicySeverityGateOpts) => ThresholdPolicySeverityDecision {
  const baseThreshold = config.baseThreshold ?? DEFAULT_BASE_THRESHOLD;
  const severitySlope = config.severitySlope ?? DEFAULT_SEVERITY_SLOPE;
  const maxThreshold = config.maxThreshold ?? DEFAULT_MAX_THRESHOLD;
  const standardWitnesses = config.standardWitnesses ?? DEFAULT_STANDARD_WITNESSES;
  const capitalWitnesses = config.capitalWitnesses ?? DEFAULT_CAPITAL_WITNESSES;
  const signingKey = config.signingKey ?? DEFAULT_SIGNING_KEY;
  const keyId = config.keyId ?? DEFAULT_KEY_ID;

  assertUnit("baseThreshold", baseThreshold);
  assertUnit("severitySlope", severitySlope);
  assertUnit("maxThreshold", maxThreshold);
  assertPositiveInteger("standardWitnesses", standardWitnesses);
  assertPositiveInteger("capitalWitnesses", capitalWitnesses);
  if (maxThreshold < baseThreshold) {
    throw new Error("ThresholdPolicySeverityGate: maxThreshold must be >= baseThreshold");
  }

  return function gate(opts: ThresholdPolicySeverityGateOpts): ThresholdPolicySeverityDecision {
    if (!opts.actionId || typeof opts.actionId !== "string") {
      throw new Error("ThresholdPolicySeverityGate: actionId is required");
    }
    if (!(opts.severity in SEVERITY_WEIGHT)) {
      throw new Error(`ThresholdPolicySeverityGate: unknown severity ${String(opts.severity)}`);
    }
    assertUnit("confidence", opts.confidence);
    if (!Array.isArray(opts.witnesses)) {
      throw new Error("ThresholdPolicySeverityGate: witnesses must be an array");
    }

    const decisionClass = opts.decisionClass ?? (opts.severity === "capital" ? "capital" : "ordinary");
    if (!["ordinary", "property", "capital"].includes(decisionClass)) {
      throw new Error(`ThresholdPolicySeverityGate: unknown decisionClass ${String(decisionClass)}`);
    }

    const requiredThreshold = Math.min(
      maxThreshold,
      baseThreshold + severitySlope * SEVERITY_WEIGHT[opts.severity],
    );
    const requiredWitnesses =
      decisionClass === "capital" || opts.severity === "capital" || opts.severity === "critical"
        ? capitalWitnesses
        : standardWitnesses;
    const attested = uniqueAttestedWitnesses(opts.witnesses);
    const witnessIds = attested.map((witness) => witness.id).sort();
    const confidencePass = opts.confidence >= requiredThreshold;
    const witnessPass = attested.length >= requiredWitnesses;
    const allow = confidencePass && witnessPass;
    const lambdaScore = Math.min(opts.confidence / requiredThreshold, attested.length / requiredWitnesses, 1);

    const receiptPayload = {
      actionId: opts.actionId.normalize("NFC"),
      attestedWitnesses: attested.length,
      confidence: opts.confidence,
      decisionClass,
      formula: "ThresholdPolicySeverity",
      requiredThreshold,
      requiredWitnesses,
      severity: opts.severity,
      witnessIds,
    };
    const receiptHash = createHash("sha256").update(canonicalJson(receiptPayload), "utf8").digest("hex");

    const rationale = allow
      ? `ThresholdPolicySeverity action ${opts.actionId}: confidence ${opts.confidence.toFixed(3)} >= ` +
        `${requiredThreshold.toFixed(3)} and ${attested.length}/${requiredWitnesses} witnesses attested. ` +
        `DSSE receipt sha256=${receiptHash.slice(0, 16)}`
      : `ThresholdPolicySeverity action ${opts.actionId}: ` +
        `${confidencePass ? "confidence pass" : `confidence ${opts.confidence.toFixed(3)} < ${requiredThreshold.toFixed(3)}`}; ` +
        `${witnessPass ? "witness pass" : `${attested.length}/${requiredWitnesses} witnesses attested`} — deny.`;

    return {
      allow,
      rationale,
      formula: "ThresholdPolicySeverity",
      claimStatus: "verified-runtime",
      leanTheorem: null,
      leanFile: null,
      leanCommitSha: null,
      actionId: opts.actionId.normalize("NFC"),
      severity: opts.severity,
      decisionClass,
      confidence: opts.confidence,
      requiredThreshold,
      requiredWitnesses,
      attestedWitnesses: attested.length,
      witnessIds,
      lambdaScore,
      dsseReceipt: allow ? signDsse({ ...receiptPayload, receiptHash }, signingKey, keyId) : undefined,
    };
  };
}
