/**
 * attest.test.ts — Vitest tests for WebAuthn human-in-the-loop attestation
 */

import { describe, it, expect, beforeEach } from "vitest";
import { createHash } from "node:crypto";
import {
  createSZLWebAuthnRP,
  generateRegistrationOptions,
  verifyRegistration,
  generateSigningOptions,
  verifyAssertionAndEmitDSSE,
  augmentDSSEWithWebAuthn,
  augmentReceiptWithWebAuthn,
  mcpWebAuthnRegister,
  mcpWebAuthnApprove,
  COSE_ALGORITHMS,
  type SZLWebAuthnRP,
  type WebAuthnAssertionResult,
} from "./attest.js";
import type { DSSEEnvelope } from "../sigstore/rekor_submit.js";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const RP_ID = "szl.io";
const ORIGIN = "https://szl.io";
const OPERATOR_DID = "did:key:z6MkHaXVHmX5w9RJqKYyDfAcgM6r8s1W";
const USER_NAME = "alice@szl.io";

const SAMPLE_PAYLOAD = Buffer.from(
  JSON.stringify({ receiptId: "szl-2026-001", organ: "sentra", action: "deploy" })
);
const SAMPLE_PAYLOAD_B64URL = SAMPLE_PAYLOAD.toString("base64url");

function encodeBase64url(buf: Buffer): string {
  return buf.toString("base64url");
}

function decodeBase64url(s: string): Buffer {
  return Buffer.from(s.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

/** Build a synthetic clientDataJSON for registration */
function makeClientDataJSON(
  type: string,
  challenge: string,
  origin: string
): string {
  return encodeBase64url(
    Buffer.from(JSON.stringify({ type, challenge, origin, crossOrigin: false }))
  );
}

/** Build synthetic authenticatorData bytes */
function makeAuthenticatorData(
  rpId: string,
  options: { userPresent: boolean; userVerified: boolean; signCount: number }
): Buffer {
  const rpIdHash = createHash("sha256").update(rpId).digest();
  let flags = 0;
  if (options.userPresent) flags |= 0x01;  // UP bit
  if (options.userVerified) flags |= 0x04; // UV bit
  const buf = Buffer.alloc(37);
  rpIdHash.copy(buf, 0);
  buf[32] = flags;
  buf.writeUInt32BE(options.signCount, 33);
  return buf;
}

// ---------------------------------------------------------------------------
// createSZLWebAuthnRP
// ---------------------------------------------------------------------------

describe("createSZLWebAuthnRP", () => {
  it("creates RP with correct rpId and empty stores", () => {
    const rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
    expect(rp.rpId).toBe(RP_ID);
    expect(rp.origin).toBe(ORIGIN);
    expect(rp.credentials.size).toBe(0);
    expect(rp.pendingChallenges.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// generateRegistrationOptions
// ---------------------------------------------------------------------------

describe("generateRegistrationOptions", () => {
  let rp: SZLWebAuthnRP;

  beforeEach(() => {
    rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
  });

  it("returns valid registration options with challenge", () => {
    const opts = generateRegistrationOptions(rp, OPERATOR_DID, USER_NAME, "Alice's MacBook");

    expect(opts.rpId).toBe(RP_ID);
    expect(opts.rpName).toBe("SZL Holdings Governance");
    expect(opts.challenge).toBeTruthy();
    expect(opts.challenge.length).toBeGreaterThan(10);
    expect(opts.authenticatorSelection.requireResidentKey).toBe(true);
    expect(opts.authenticatorSelection.userVerification).toBe("required");
    expect(opts.attestation).toBe("none");
    expect(opts.pubKeyCredParams.length).toBeGreaterThan(0);
    expect(opts.pubKeyCredParams.some((p) => p.alg === -7)).toBe(true); // ES256
  });

  it("stores pending challenge for operator", () => {
    generateRegistrationOptions(rp, OPERATOR_DID, USER_NAME, "Alice's MacBook");
    expect(rp.pendingChallenges.has(OPERATOR_DID)).toBe(true);
  });

  it("excludes already-registered credentials", () => {
    rp.credentials.set("cred-1", {
      credentialId: "cred-1",
      publicKeyCOSE: "",
      counter: 0,
      aaguid: "00000000-0000-0000-0000-000000000000",
      deviceType: "singleDevice",
      backedUp: false,
      transports: ["internal"],
      displayName: "Old Device",
      rpId: RP_ID,
      operatorDID: OPERATOR_DID,
      registeredAt: "2026-01-01T00:00:00Z",
    });

    const opts = generateRegistrationOptions(
      rp,
      OPERATOR_DID,
      USER_NAME,
      "New Device",
      Array.from(rp.credentials.values())
    );

    expect(opts.excludeCredentials.length).toBe(1);
    expect(opts.excludeCredentials[0].id).toBe("cred-1");
  });
});

// ---------------------------------------------------------------------------
// verifyRegistration
// ---------------------------------------------------------------------------

describe("verifyRegistration", () => {
  let rp: SZLWebAuthnRP;

  beforeEach(() => {
    rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
  });

  it("stores credential on successful verification", async () => {
    const opts = generateRegistrationOptions(rp, OPERATOR_DID, USER_NAME, "Alice's MacBook");
    const challenge = opts.challenge;

    const registrationResponse = {
      id: "cred-abc123",
      rawId: "cred-abc123",
      response: {
        clientDataJSON: makeClientDataJSON("webauthn.create", challenge, ORIGIN),
        attestationObject: encodeBase64url(Buffer.from("{}")), // STAGED-ADVISORY placeholder
      },
      type: "public-key" as const,
      transports: ["internal"],
    };

    const cred = await verifyRegistration(
      rp,
      OPERATOR_DID,
      registrationResponse,
      "Alice's MacBook"
    );

    expect(cred.credentialId).toBe("cred-abc123");
    expect(cred.operatorDID).toBe(OPERATOR_DID);
    expect(cred.rpId).toBe(RP_ID);
    expect(cred.displayName).toBe("Alice's MacBook");
    expect(rp.credentials.has("cred-abc123")).toBe(true);
    expect(rp.pendingChallenges.has(OPERATOR_DID)).toBe(false); // cleared
  });

  it("throws if no pending challenge", async () => {
    await expect(
      verifyRegistration(rp, OPERATOR_DID, {
        id: "x",
        rawId: "x",
        response: { clientDataJSON: "", attestationObject: "" },
        type: "public-key",
      }, "Device")
    ).rejects.toThrow("No pending challenge");
  });

  it("throws on challenge mismatch", async () => {
    generateRegistrationOptions(rp, OPERATOR_DID, USER_NAME, "Alice's MacBook");
    await expect(
      verifyRegistration(rp, OPERATOR_DID, {
        id: "x",
        rawId: "x",
        response: {
          clientDataJSON: makeClientDataJSON("webauthn.create", "WRONG_CHALLENGE", ORIGIN),
          attestationObject: encodeBase64url(Buffer.from("{}")),
        },
        type: "public-key",
      }, "Device")
    ).rejects.toThrow("Challenge mismatch");
  });

  it("throws on origin mismatch", async () => {
    const opts = generateRegistrationOptions(rp, OPERATOR_DID, USER_NAME, "Alice's MacBook");
    await expect(
      verifyRegistration(rp, OPERATOR_DID, {
        id: "x",
        rawId: "x",
        response: {
          clientDataJSON: makeClientDataJSON("webauthn.create", opts.challenge, "https://evil.com"),
          attestationObject: encodeBase64url(Buffer.from("{}")),
        },
        type: "public-key",
      }, "Device")
    ).rejects.toThrow("Origin mismatch");
  });
});

// ---------------------------------------------------------------------------
// generateSigningOptions
// ---------------------------------------------------------------------------

describe("generateSigningOptions", () => {
  let rp: SZLWebAuthnRP;

  beforeEach(() => {
    rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
    rp.credentials.set("cred-1", {
      credentialId: "cred-1",
      publicKeyCOSE: "",
      counter: 5,
      aaguid: "00000000-0000-0000-0000-000000000000",
      deviceType: "singleDevice",
      backedUp: false,
      transports: ["internal"],
      displayName: "Alice's MacBook",
      rpId: RP_ID,
      operatorDID: OPERATOR_DID,
      registeredAt: "2026-05-01T00:00:00Z",
    });
  });

  it("sets challenge to SHA-256(dssePayload) as base64url", () => {
    const opts = generateSigningOptions(
      rp,
      OPERATOR_DID,
      SAMPLE_PAYLOAD_B64URL,
      Array.from(rp.credentials.values())
    );

    const expectedChallenge = encodeBase64url(
      createHash("sha256").update(SAMPLE_PAYLOAD).digest()
    );
    expect(opts.challenge).toBe(expectedChallenge);
  });

  it("includes allowed credentials", () => {
    const opts = generateSigningOptions(
      rp,
      OPERATOR_DID,
      SAMPLE_PAYLOAD_B64URL,
      Array.from(rp.credentials.values())
    );
    expect(opts.allowCredentials.length).toBe(1);
    expect(opts.allowCredentials[0].id).toBe("cred-1");
  });

  it("userVerification is required", () => {
    const opts = generateSigningOptions(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, Array.from(rp.credentials.values())
    );
    expect(opts.userVerification).toBe("required");
  });
});

// ---------------------------------------------------------------------------
// verifyAssertionAndEmitDSSE
// ---------------------------------------------------------------------------

describe("verifyAssertionAndEmitDSSE", () => {
  let rp: SZLWebAuthnRP;

  beforeEach(() => {
    rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
    rp.credentials.set("cred-1", {
      credentialId: "cred-1",
      publicKeyCOSE: "",
      counter: 5,
      aaguid: "00000000-0000-0000-0000-000000000000",
      deviceType: "singleDevice",
      backedUp: false,
      transports: ["internal"],
      displayName: "Alice's MacBook",
      rpId: RP_ID,
      operatorDID: OPERATOR_DID,
      registeredAt: "2026-05-01T00:00:00Z",
    });
  });

  function makeValidAssertion(): WebAuthnAssertionResult {
    // Generate signing options to set up the pending challenge
    generateSigningOptions(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, Array.from(rp.credentials.values())
    );

    const expectedChallenge = encodeBase64url(
      createHash("sha256").update(SAMPLE_PAYLOAD).digest()
    );

    const clientDataJSON = makeClientDataJSON("webauthn.get", expectedChallenge, ORIGIN);
    const authenticatorData = encodeBase64url(
      makeAuthenticatorData(RP_ID, { userPresent: true, userVerified: true, signCount: 6 })
    );

    return {
      credentialId: "cred-1",
      clientDataJSON,
      authenticatorData,
      signature: encodeBase64url(Buffer.from("fake-ecdsa-sig")),
    };
  }

  it("returns WebAuthn DSSE signature on valid assertion", async () => {
    const assertion = makeValidAssertion();
    const sig = await verifyAssertionAndEmitDSSE(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, assertion
    );

    expect(sig.keyid).toBe("webauthn:cred-1");
    expect(sig.sig).toBe(assertion.signature);
    expect(sig.webauthn.operatorDID).toBe(OPERATOR_DID);
    expect(sig.webauthn.rpId).toBe(RP_ID);
    expect(sig.webauthn.deviceDisplayName).toBe("Alice's MacBook");
    expect(sig.webauthn.assertedAt).toBeTruthy();
  });

  it("updates signature counter after successful assertion", async () => {
    const assertion = makeValidAssertion();
    await verifyAssertionAndEmitDSSE(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, assertion
    );
    expect(rp.credentials.get("cred-1")!.counter).toBe(6);
  });

  it("clears pending challenge after verification", async () => {
    const assertion = makeValidAssertion();
    await verifyAssertionAndEmitDSSE(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, assertion
    );
    expect(rp.pendingChallenges.has(`sign:${OPERATOR_DID}`)).toBe(false);
  });

  it("throws on wrong payload (challenge mismatch)", async () => {
    generateSigningOptions(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, Array.from(rp.credentials.values())
    );
    const wrongChallenge = encodeBase64url(Buffer.from("wrong-hash"));
    const clientDataJSON = makeClientDataJSON("webauthn.get", wrongChallenge, ORIGIN);
    const authenticatorData = encodeBase64url(
      makeAuthenticatorData(RP_ID, { userPresent: true, userVerified: true, signCount: 6 })
    );

    await expect(
      verifyAssertionAndEmitDSSE(rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, {
        credentialId: "cred-1",
        clientDataJSON,
        authenticatorData,
        signature: encodeBase64url(Buffer.from("sig")),
      })
    ).rejects.toThrow("Challenge/payload mismatch");
  });

  it("throws on counter replay (signCount <= stored counter)", async () => {
    generateSigningOptions(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, Array.from(rp.credentials.values())
    );
    const expectedChallenge = encodeBase64url(
      createHash("sha256").update(SAMPLE_PAYLOAD).digest()
    );
    const clientDataJSON = makeClientDataJSON("webauthn.get", expectedChallenge, ORIGIN);
    // signCount = 3 < stored counter = 5
    const authenticatorData = encodeBase64url(
      makeAuthenticatorData(RP_ID, { userPresent: true, userVerified: true, signCount: 3 })
    );

    await expect(
      verifyAssertionAndEmitDSSE(rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, {
        credentialId: "cred-1",
        clientDataJSON,
        authenticatorData,
        signature: encodeBase64url(Buffer.from("sig")),
      })
    ).rejects.toThrow("counter replay");
  });

  it("throws when UV flag not set", async () => {
    generateSigningOptions(
      rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, Array.from(rp.credentials.values())
    );
    const expectedChallenge = encodeBase64url(
      createHash("sha256").update(SAMPLE_PAYLOAD).digest()
    );
    const clientDataJSON = makeClientDataJSON("webauthn.get", expectedChallenge, ORIGIN);
    // UV=false
    const authenticatorData = encodeBase64url(
      makeAuthenticatorData(RP_ID, { userPresent: true, userVerified: false, signCount: 6 })
    );

    await expect(
      verifyAssertionAndEmitDSSE(rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL, {
        credentialId: "cred-1",
        clientDataJSON,
        authenticatorData,
        signature: encodeBase64url(Buffer.from("sig")),
      })
    ).rejects.toThrow("User verification flag not set");
  });
});

// ---------------------------------------------------------------------------
// augmentDSSEWithWebAuthn
// ---------------------------------------------------------------------------

describe("augmentDSSEWithWebAuthn", () => {
  it("appends WebAuthn signature to envelope without removing existing sigs", () => {
    const envelope: DSSEEnvelope = {
      payloadType: "application/vnd.szl.receipt.v1+json",
      payload: SAMPLE_PAYLOAD_B64URL,
      signatures: [{ sig: "hmac-sig", keyid: "szl-dev-key-v1" }],
    };

    const webAuthnSig = {
      sig: "webauthn-sig",
      keyid: "webauthn:cred-1",
      webauthn: {
        clientDataJSON: "cdjson",
        authenticatorData: "authdata",
        credentialId: "cred-1",
        rpId: RP_ID,
        operatorDID: OPERATOR_DID,
        deviceDisplayName: "Alice's MacBook",
        assertedAt: "2026-05-29T22:00:00Z",
      },
    };

    const augmented = augmentDSSEWithWebAuthn(envelope, webAuthnSig);
    expect(augmented.signatures).toHaveLength(2);
    expect(augmented.signatures[0].keyid).toBe("szl-dev-key-v1");
    expect(augmented.signatures[1].keyid).toBe("webauthn:cred-1");
    expect(augmented.payload).toBe(SAMPLE_PAYLOAD_B64URL);
  });
});

// ---------------------------------------------------------------------------
// augmentReceiptWithWebAuthn
// ---------------------------------------------------------------------------

describe("augmentReceiptWithWebAuthn", () => {
  it("adds humanAttestation block to receipt", () => {
    const receipt = { receiptId: "r1" };
    const webAuthnSig = {
      sig: "sig",
      keyid: "webauthn:cred-1",
      webauthn: {
        clientDataJSON: "cdj",
        authenticatorData: "ad",
        credentialId: "cred-1",
        rpId: RP_ID,
        operatorDID: OPERATOR_DID,
        deviceDisplayName: "Alice's MacBook",
        assertedAt: "2026-05-29T22:00:00Z",
      },
    };

    const augmented = augmentReceiptWithWebAuthn(receipt, webAuthnSig, OPERATOR_DID);
    expect(augmented).toHaveProperty("humanAttestation");
    const att = augmented.humanAttestation as Record<string, unknown>;
    expect(att.type).toBe("WebAuthnPasskeyAttestation");
    expect(att.operatorDID).toBe(OPERATOR_DID);
    expect(att.deviceDisplayName).toBe("Alice's MacBook");
    expect(typeof att.verificationNote).toBe("string");
  });
});

// ---------------------------------------------------------------------------
// MCP surface functions
// ---------------------------------------------------------------------------

describe("mcpWebAuthnRegister", () => {
  it("returns registration options via MCP wrapper", () => {
    const rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
    const opts = mcpWebAuthnRegister(rp, OPERATOR_DID, USER_NAME);
    expect(opts.rpId).toBe(RP_ID);
    expect(opts.challenge).toBeTruthy();
  });
});

describe("mcpWebAuthnApprove", () => {
  it("throws when no credentials registered", () => {
    const rp = createSZLWebAuthnRP(RP_ID, ORIGIN);
    expect(() => mcpWebAuthnApprove(rp, OPERATOR_DID, SAMPLE_PAYLOAD_B64URL))
      .toThrow("No registered passkeys");
  });
});

// ---------------------------------------------------------------------------
// COSE_ALGORITHMS
// ---------------------------------------------------------------------------

describe("COSE_ALGORITHMS", () => {
  it("includes ES256 (-7)", () => {
    expect(COSE_ALGORITHMS.some((a) => a.alg === -7)).toBe(true);
  });
  it("includes EdDSA (-8)", () => {
    expect(COSE_ALGORITHMS.some((a) => a.alg === -8)).toBe(true);
  });
});
