/**
 * wrap_dsse.test.ts — Vitest tests for W3C VC JSON-LD wrapping
 */

import { describe, it, expect } from "vitest";
import {
  wrapDSSEinVC,
  buildVerifiablePresentation,
  batchWrapReceipts,
  wrapForSCITT,
  serializeVC,
  prettySerializeVC,
  type SZLReceiptRecord,
} from "./wrap_dsse.js";
import { generateKeyPairSync } from "node:crypto";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const SAMPLE_RECEIPT: SZLReceiptRecord = {
  receiptId: "szl-2026-001",
  timestamp: "2026-05-29T22:00:00Z",
  organId: "sentra",
  action: "deploy",
  outcome: "success",
  operatorDID: "did:key:z6MkHaXVHmX5w9RJqKYyDfAcgM6r8s1W",
  policyRef: "https://szl.io/policy/doctrine-v6",
  envelope: {
    payloadType: "application/vnd.szl.receipt.v1+json",
    payload: Buffer.from(
      JSON.stringify({
        receiptId: "szl-2026-001",
        organ: "sentra",
        action: "deploy",
      })
    ).toString("base64url"),
    signatures: [{ sig: "dGVzdHNpZw==", keyid: "szl-dev-key-v1" }],
  },
  rekorAttestation: {
    uuid: "382898f8ae6ab0b4bf51dbf1b1df8f10b4ba2b5a8d8e47534c6e7e0ea7a2e4c",
    logIndex: 42_000_000,
    rekorEntryUrl:
      "https://rekor.sigstore.dev/api/v1/log/entries/382898f8ae6ab0b4",
  },
};

// ---------------------------------------------------------------------------
// @context compliance (W3C VC 2.0)
// ---------------------------------------------------------------------------

describe("wrapDSSEinVC — W3C VC 2.0 compliance", () => {
  it("produces a valid @context array starting with W3C credentials URL", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(Array.isArray(vc["@context"])).toBe(true);
    expect(vc["@context"][0]).toBe("https://www.w3.org/ns/credentials/v2");
  });

  it("type includes VerifiableCredential and SZLGovernanceReceipt", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.type).toContain("VerifiableCredential");
    expect(vc.type).toContain("SZLGovernanceReceipt");
  });

  it("id is a urn:szl:receipt:<receiptId> URI", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.id).toBe("urn:szl:receipt:szl-2026-001");
  });

  it("issuer.id is a DID", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.issuer.id).toMatch(/^did:/);
  });

  it("validFrom is an ISO-8601 string", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.validFrom).toBe("2026-05-29T22:00:00Z");
  });

  it("credentialSubject contains organId, action, payloadHash", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.credentialSubject.organId).toBe("sentra");
    expect(vc.credentialSubject.action).toBe("deploy");
    expect(vc.credentialSubject.payloadHash).toHaveLength(64); // hex SHA-256
  });

  it("credentialSubject.id is set to operatorDID", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.credentialSubject.id).toBe(
      "did:key:z6MkHaXVHmX5w9RJqKYyDfAcgM6r8s1W"
    );
  });

  it("embeds rekorAttestation when present", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.credentialSubject.rekorAttestation?.uuid).toBe(
      "382898f8ae6ab0b4bf51dbf1b1df8f10b4ba2b5a8d8e47534c6e7e0ea7a2e4c"
    );
  });

  it("omits rekorAttestation when not in receipt", () => {
    const r = { ...SAMPLE_RECEIPT, rekorAttestation: undefined };
    const vc = wrapDSSEinVC(r);
    expect(vc.credentialSubject.rekorAttestation).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Proof tests
// ---------------------------------------------------------------------------

describe("wrapDSSEinVC — proof", () => {
  it("uses DSSESignature2024 when no signingKeyPem", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.proof.type).toBe("DataIntegrityProof");
    expect(vc.proof.cryptosuite).toBe("DSSESignature2024");
    expect(vc.proof.proofPurpose).toBe("assertionMethod");
  });

  it("uses ecdsa-rdfc-2022 when signingKeyPem provided", () => {
    const { privateKey } = generateKeyPairSync("ec", {
      namedCurve: "P-256",
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
      publicKeyEncoding: { type: "spki", format: "pem" },
    });
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT, {
      signingKeyPem: privateKey as string,
    });
    expect(vc.proof.cryptosuite).toBe("ecdsa-rdfc-2022");
    expect(vc.proof.proofValue).toMatch(/^z/); // base58btc multibase prefix
  });

  it("proof.created is a valid ISO date", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(new Date(vc.proof.created).getTime()).not.toBeNaN();
  });

  it("proof.verificationMethod defaults to did:web:szl.io#key-1", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    expect(vc.proof.verificationMethod).toBe("did:web:szl.io#key-1");
  });

  it("accepts custom verificationMethod", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT, {
      verificationMethod: "did:key:z6Mk123#key-1",
    });
    expect(vc.proof.verificationMethod).toBe("did:key:z6Mk123#key-1");
  });
});

// ---------------------------------------------------------------------------
// Additional types
// ---------------------------------------------------------------------------

describe("wrapDSSEinVC — additionalTypes", () => {
  it("includes additional types in vc.type array", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT, {
      additionalTypes: ["SCITTReceipt", "EUDIWCredential"],
    });
    expect(vc.type).toContain("SCITTReceipt");
    expect(vc.type).toContain("EUDIWCredential");
  });
});

// ---------------------------------------------------------------------------
// Verifiable Presentation
// ---------------------------------------------------------------------------

describe("buildVerifiablePresentation", () => {
  it("wraps multiple VCs in a VP", () => {
    const vc1 = wrapDSSEinVC(SAMPLE_RECEIPT);
    const vc2 = wrapDSSEinVC({ ...SAMPLE_RECEIPT, receiptId: "szl-2026-002" });
    const vp = buildVerifiablePresentation([vc1, vc2], "did:web:szl.io");

    expect(vp.type).toContain("VerifiablePresentation");
    expect(vp.verifiableCredential).toHaveLength(2);
    expect(vp.holder).toBe("did:web:szl.io");
    expect(vp["@context"][0]).toBe("https://www.w3.org/ns/credentials/v2");
  });
});

// ---------------------------------------------------------------------------
// Batch + SCITT
// ---------------------------------------------------------------------------

describe("batchWrapReceipts", () => {
  it("converts multiple receipts to VCs", () => {
    const receipts = [
      SAMPLE_RECEIPT,
      { ...SAMPLE_RECEIPT, receiptId: "szl-2026-003" },
    ];
    const vcs = batchWrapReceipts(receipts);
    expect(vcs).toHaveLength(2);
    expect(vcs[0].id).toBe("urn:szl:receipt:szl-2026-001");
    expect(vcs[1].id).toBe("urn:szl:receipt:szl-2026-003");
  });
});

describe("wrapForSCITT", () => {
  it("returns a VP with SZLGovernanceAuditPresentation type", () => {
    const vp = wrapForSCITT([SAMPLE_RECEIPT], "did:web:szl.io");
    expect(vp.type).toContain("SZLGovernanceAuditPresentation");
    expect(vp.id).toMatch(/^urn:szl:scitt:/);
    expect(vp.holder).toBe("did:web:szl.io");
  });
});

// ---------------------------------------------------------------------------
// Serialization
// ---------------------------------------------------------------------------

describe("serialization helpers", () => {
  it("serializeVC produces valid JSON parseable to original shape", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    const json = serializeVC(vc);
    const parsed = JSON.parse(json);
    expect(parsed.id).toBe(vc.id);
    expect(parsed.proof).toBeDefined();
  });

  it("prettySerializeVC produces formatted JSON", () => {
    const vc = wrapDSSEinVC(SAMPLE_RECEIPT);
    const pretty = prettySerializeVC(vc);
    expect(pretty).toContain("\n");
    expect(pretty).toContain("  ");
  });
});
