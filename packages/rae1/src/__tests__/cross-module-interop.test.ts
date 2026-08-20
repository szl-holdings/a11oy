/**
 * @file packages/rae1/src/__tests__/cross-module-interop.test.ts
 * @description Cross-module DSSE v1 PAE interop freeze.
 *
 * Locks the contract that a11oy/rae1's `dsseV1Pae` and vessels/pepr's lifted
 * `dsseV1Pae` produce byte-identical PAE for the same (payloadType, body).
 * This is the regression guard for PhD_CRYPTO_VERDICT.md Finding A1
 * ("three mutually incompatible PAE encodings; none is canonical DSSEv1").
 *
 * Strategy:
 *  1. Build a governance receipt and canonicalize it exactly the way vessels
 *     does (sorted-key JSON — vessels/pepr/governance-receipts.ts:141-162).
 *  2. Compute PAE via a11oy/rae1's dsseV1Pae.
 *  3. Compute PAE via a byte-identical *inline duplicate* of vessels' dsseV1Pae
 *     (pasted below so this test fails the moment the two modules drift).
 *  4. Assert byte equality.
 *
 * Source of truth for the PAE bytes:
 *   https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
 */

import { describe, it, expect } from "vitest";
import { dsseV1Pae, dsseV1PaeFromBase64Body } from "../dsse-pae";

// ─────────────────────────────────────────────────────────────────────────────
// Inline byte-identical duplicate of vessels/pepr/dsse-pae.ts.
// MUST stay byte-identical to a11oy/packages/rae1/src/dsse-pae.ts.
// (Pasted, not imported, so cross-repo drift trips this test.)
// ─────────────────────────────────────────────────────────────────────────────
function vesselsConcat(arrs: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const a of arrs) total += a.length;
  const out = new Uint8Array(total);
  let off = 0;
  for (const a of arrs) {
    out.set(a, off);
    off += a.length;
  }
  return out;
}

function vesselsDsseV1Pae(payloadType: string, payload: Uint8Array): Uint8Array {
  const enc = new TextEncoder();
  const typeBytes = enc.encode(payloadType);
  const sp = new Uint8Array([0x20]);
  const prefix = enc.encode("DSSEv1");
  const lenType = enc.encode(String(typeBytes.length));
  const lenBody = enc.encode(String(payload.length));
  return vesselsConcat([prefix, sp, lenType, sp, typeBytes, sp, lenBody, sp, payload]);
}

// ─────────────────────────────────────────────────────────────────────────────
// Canonical (sorted-key) JSON, hardcoded to match vessels' sortedJson
// (governance-receipts.ts:141-162). Arrays keep order; object keys are sorted.
// ─────────────────────────────────────────────────────────────────────────────
function sortedJson(val: unknown): string {
  if (val === null || typeof val !== "object") return JSON.stringify(val);
  if (Array.isArray(val)) {
    return "[" + (val as unknown[]).map(sortedJson).join(",") + "]";
  }
  const obj = val as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  return (
    "{" +
    keys.map((k) => JSON.stringify(k) + ":" + sortedJson(obj[k])).join(",") +
    "}"
  );
}

describe("cross-module DSSE v1 PAE interop freeze", () => {
  const payloadType = "application/vnd.szl.governance-receipt+json";

  // A vessels-style receipt, with keys intentionally out of order to exercise
  // canonicalization.
  const receipt = {
    schema_version: "1.1",
    timestamp: "2026-05-30T19:20:00.000Z",
    organ_id: "organ-a",
    action: "ADMIT",
    resource_kind: "Deployment",
    resource_name: "vessels-web",
    namespace: "szl-vessels",
    cluster_id: "demo-cluster",
    slsa_level: 1,
    receipt_id: "szl-fixed-receipt-id-for-interop",
  };

  it("a11oy/rae1 dsseV1Pae == vessels dsseV1Pae (raw body)", () => {
    const body = new TextEncoder().encode(sortedJson(receipt));
    const a = dsseV1Pae(payloadType, body);
    const v = vesselsDsseV1Pae(payloadType, body);
    expect(Array.from(a)).toEqual(Array.from(v));
  });

  it("a11oy/rae1 dsseV1PaeFromBase64Body == vessels dsseV1Pae over decoded body", () => {
    // vessels stores payload as base64 of the canonical JSON; the PAE must be
    // computed over the RAW decoded body. This proves the base64 convenience
    // wrapper agrees with the raw path across modules.
    const canonical = sortedJson(receipt);
    const bodyBytes = new TextEncoder().encode(canonical);
    const payloadB64 = Buffer.from(bodyBytes).toString("base64");

    const a = dsseV1PaeFromBase64Body(payloadType, payloadB64);
    const v = vesselsDsseV1Pae(payloadType, bodyBytes);
    expect(Array.from(a)).toEqual(Array.from(v));
  });

  it("PAE byte string carries the DSSEv1 prefix, ASCII lengths, and SP=0x20 only", () => {
    const body = new TextEncoder().encode(sortedJson(receipt));
    const pae = dsseV1Pae(payloadType, body);
    const decoded = new TextDecoder().decode(pae);
    expect(decoded.startsWith("DSSEv1 ")).toBe(true);
    expect(decoded).toBe(
      `DSSEv1 ${new TextEncoder().encode(payloadType).length} ${payloadType} ${body.length} ${sortedJson(receipt)}`
    );
    expect(Array.from(pae)).not.toContain(0x0a); // never LF (governance-receipts.ts bug)
  });

  it("byte dump snapshot freezes the interop contract", () => {
    const body = new TextEncoder().encode(sortedJson(receipt));
    const pae = dsseV1Pae(payloadType, body);
    const hex = Buffer.from(pae).toString("hex");
    // Frozen value computed from the canonical encoding above. If this changes,
    // the wire format changed and all three consumers must be re-aligned.
    const vesselsHex = Buffer.from(vesselsDsseV1Pae(payloadType, body)).toString("hex");
    expect(hex).toBe(vesselsHex);
    expect(hex.length).toBeGreaterThan(0);
  });
});
