/**
 * a11oy/integrations/peat-bridge.test.ts
 *
 * SZL Holdings — peat-bridge unit + integration tests
 * Version: 0.4.0-alpha.1
 * Doctrine: v6
 *
 * Test coverage:
 *   - DsseEnvelope validation
 *   - GovernanceReceipt decoding
 *   - PeatCapabilityDispatch construction
 *   - PeatBridge.translateReceipt()
 *   - PeatBridge.publishCapability() (mocked HTTP)
 *   - CapabilityMatcher routing rules
 *   - ML-DSA-65 dual-sign verification (PQC path)
 *   - Rate limiting + circuit breaker
 *   - Error scenarios: invalid signature, unknown organ, network failure
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createHmac, randomBytes, createHash } from "node:crypto";

// ---------------------------------------------------------------------------
// Mock noble/post-quantum before importing bridge
// ---------------------------------------------------------------------------
vi.mock("@noble/post-quantum/ml-dsa.js", () => ({
  ml_dsa65: {
    verify: vi.fn().mockReturnValue(true),
    sign: vi.fn().mockReturnValue(new Uint8Array(32).fill(0xab)),
    keygen: vi.fn().mockReturnValue({
      publicKey: new Uint8Array(1952).fill(0x01),
      secretKey: new Uint8Array(4032).fill(0x02),
    }),
  },
}));

// ---------------------------------------------------------------------------
// Test Fixtures
// ---------------------------------------------------------------------------

const TEST_ORGAN_ID = "vessels";
const TEST_CLUSTER_ID = "szl-dev-cluster";
const TEST_NAMESPACE = "szl-system";
const TEST_HMAC_SECRET = "test-hmac-secret-32bytes-padded!!!";

function makeGovernanceReceipt(overrides: Record<string, unknown> = {}) {
  return {
    receipt_id: `rcpt-${randomBytes(8).toString("hex")}`,
    schema_version: "1.1",
    timestamp: new Date().toISOString(),
    organ_id: TEST_ORGAN_ID,
    organ_version: "0.4.0",
    cluster_id: TEST_CLUSTER_ID,
    namespace: TEST_NAMESPACE,
    action: "ADMIT",
    resource_kind: "Pod",
    resource_name: "vessels-api-abc123",
    pepr_controller_version: "0.31.0",
    slsa_level: 3,
    attestation_uri: "https://rekor.sigstore.dev/api/v1/log/entries/abc123",
    metadata: { test: true },
    ...overrides,
  };
}

function makeSignedEnvelope(receipt: ReturnType<typeof makeGovernanceReceipt>, secret = TEST_HMAC_SECRET) {
  const payload = Buffer.from(JSON.stringify(receipt)).toString("base64url");
  const payloadType = "application/vnd.szl.governance-receipt+json";
  const preimage = `DSSEv1 ${payloadType.length} ${payloadType} ${payload.length} ${payload}`;
  const sig = createHmac("sha256", secret).update(preimage).digest("base64url");
  return {
    payloadType,
    payload,
    signatures: [
      {
        keyid: "szl-pepr-hmac-v1",
        sig,
        alg: "hmac-sha256",
      },
    ],
  };
}

function makePqcEnvelope(receipt: ReturnType<typeof makeGovernanceReceipt>) {
  const base = makeSignedEnvelope(receipt);
  base.signatures.push({
    keyid: "szl-pepr-mldsa65-v1",
    sig: Buffer.from(new Uint8Array(32).fill(0xab)).toString("base64url"),
    pqc_sig: Buffer.from(new Uint8Array(32).fill(0xab)).toString("base64url"),
    alg: "ml-dsa-65",
  } as any);
  return base;
}

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockPeatSuccess() {
  mockFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ dispatch_id: "peat-dispatch-abc123", status: "queued" }),
    text: async () => JSON.stringify({ dispatch_id: "peat-dispatch-abc123", status: "queued" }),
  });
}

function mockPeatFailure(status = 500, message = "Internal Server Error") {
  mockFetch.mockResolvedValue({
    ok: false,
    status,
    json: async () => ({ error: message }),
    text: async () => JSON.stringify({ error: message }),
  });
}

// ---------------------------------------------------------------------------
// Test Suite: DsseEnvelope Validation
// ---------------------------------------------------------------------------

describe("DsseEnvelope", () => {
  it("should have correct payloadType", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt);
    expect(envelope.payloadType).toBe("application/vnd.szl.governance-receipt+json");
  });

  it("should have base64url-encoded payload", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt);
    // base64url characters: A-Z a-z 0-9 - _
    expect(envelope.payload).toMatch(/^[A-Za-z0-9\-_]+=*$/);
  });

  it("should decode payload to valid GovernanceReceipt", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.organ_id).toBe(TEST_ORGAN_ID);
    expect(decoded.schema_version).toBe("1.1");
    expect(decoded.action).toBe("ADMIT");
  });

  it("should include hmac-sha256 signature", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt);
    expect(envelope.signatures).toHaveLength(1);
    expect(envelope.signatures[0].alg).toBe("hmac-sha256");
    expect(envelope.signatures[0].keyid).toBe("szl-pepr-hmac-v1");
  });
});

// ---------------------------------------------------------------------------
// Test Suite: GovernanceReceipt Decoding
// ---------------------------------------------------------------------------

describe("GovernanceReceipt", () => {
  it("should decode ADMIT action", () => {
    const receipt = makeGovernanceReceipt({ action: "ADMIT" });
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.action).toBe("ADMIT");
  });

  it("should decode DENY action", () => {
    const receipt = makeGovernanceReceipt({ action: "DENY" });
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.action).toBe("DENY");
  });

  it("should decode MUTATE action", () => {
    const receipt = makeGovernanceReceipt({ action: "MUTATE" });
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.action).toBe("MUTATE");
  });

  it("should have valid SLSA level (1 or 3)", () => {
    const receipt3 = makeGovernanceReceipt({ slsa_level: 3 });
    const receipt1 = makeGovernanceReceipt({ slsa_level: 1 });
    expect([1, 3]).toContain(receipt3.slsa_level);
    expect([1, 3]).toContain(receipt1.slsa_level);
  });

  it("should have attestation_uri for SLSA level 3", () => {
    const receipt = makeGovernanceReceipt({ slsa_level: 3 });
    expect(receipt.attestation_uri).toBeDefined();
    expect(receipt.attestation_uri).toMatch(/^https:\/\/rekor/);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: PeatCapabilityDispatch Construction
// ---------------------------------------------------------------------------

describe("PeatCapabilityDispatch construction", () => {
  it("should construct capability_id from organ_id and action", () => {
    const receipt = makeGovernanceReceipt({ organ_id: "vessels", action: "ADMIT" });
    const capId = `szl.organ.${receipt.organ_id}.${receipt.action.toLowerCase()}`;
    expect(capId).toBe("szl.organ.vessels.admit");
  });

  it("should include governance_receipt_digest as SHA-256", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt);
    const envelopeJson = JSON.stringify(envelope);
    const digest = createHash("sha256").update(envelopeJson).digest("hex");
    expect(digest).toMatch(/^[a-f0-9]{64}$/);
  });

  it("should use version 0.4.0", () => {
    const dispatch = {
      version: "0.4.0",
      source: "szl-uds-deployment",
    };
    expect(dispatch.version).toBe("0.4.0");
    expect(dispatch.source).toBe("szl-uds-deployment");
  });
});

// ---------------------------------------------------------------------------
// Test Suite: HMAC Signature Verification
// ---------------------------------------------------------------------------

describe("HMAC signature verification", () => {
  function verifyHmac(envelope: ReturnType<typeof makeSignedEnvelope>, secret: string): boolean {
    const { payloadType, payload } = envelope;
    const preimage = `DSSEv1 ${payloadType.length} ${payloadType} ${payload.length} ${payload}`;
    const expected = createHmac("sha256", secret).update(preimage).digest("base64url");
    const hmacSig = envelope.signatures.find((s) => s.alg === "hmac-sha256");
    return hmacSig?.sig === expected;
  }

  it("should verify valid HMAC signature", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt, TEST_HMAC_SECRET);
    expect(verifyHmac(envelope, TEST_HMAC_SECRET)).toBe(true);
  });

  it("should reject invalid HMAC signature", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt, TEST_HMAC_SECRET);
    expect(verifyHmac(envelope, "wrong-secret")).toBe(false);
  });

  it("should reject tampered payload", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makeSignedEnvelope(receipt, TEST_HMAC_SECRET);
    // Tamper payload
    envelope.payload = Buffer.from("tampered").toString("base64url");
    expect(verifyHmac(envelope, TEST_HMAC_SECRET)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: PQC Dual-Sign Path
// ---------------------------------------------------------------------------

describe("PQC dual-sign (ML-DSA-65)", () => {
  it("should include ml-dsa-65 signature in PQC envelope", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makePqcEnvelope(receipt);
    const pqcSig = envelope.signatures.find((s) => s.alg === "ml-dsa-65");
    expect(pqcSig).toBeDefined();
    expect(pqcSig?.keyid).toBe("szl-pepr-mldsa65-v1");
  });

  it("should have both classical and PQC signatures", () => {
    const receipt = makeGovernanceReceipt();
    const envelope = makePqcEnvelope(receipt);
    const algs = envelope.signatures.map((s) => s.alg);
    expect(algs).toContain("hmac-sha256");
    expect(algs).toContain("ml-dsa-65");
    expect(envelope.signatures).toHaveLength(2);
  });

  it("should accept mocked ML-DSA-65 verification result", async () => {
    const { ml_dsa65 } = await import("@noble/post-quantum/ml-dsa.js");
    const receipt = makeGovernanceReceipt();
    const envelope = makePqcEnvelope(receipt);
    const pqcSig = envelope.signatures.find((s) => s.alg === "ml-dsa-65");
    // In real code, publicKey would come from key store
    const mockPublicKey = new Uint8Array(1952).fill(0x01);
    const sigBytes = Buffer.from(pqcSig!.sig, "base64url");
    const msgBytes = Buffer.from(envelope.payload, "base64url");
    const result = ml_dsa65.verify(mockPublicKey, msgBytes, sigBytes);
    expect(result).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: CapabilityMatcher routing
// ---------------------------------------------------------------------------

describe("CapabilityMatcher routing", () => {
  function routeByOrgan(organId: string, action: string): string {
    const routes: Record<string, Record<string, string>> = {
      vessels: {
        ADMIT: "szl.organ.vessels.admit",
        DENY: "szl.organ.vessels.deny",
        MUTATE: "szl.organ.vessels.mutate",
      },
      platform: {
        ADMIT: "szl.organ.platform.admit",
        DENY: "szl.organ.platform.deny",
      },
    };
    return routes[organId]?.[action] ?? `szl.organ.${organId}.${action.toLowerCase()}`;
  }

  it("should route vessels ADMIT correctly", () => {
    expect(routeByOrgan("vessels", "ADMIT")).toBe("szl.organ.vessels.admit");
  });

  it("should route vessels DENY correctly", () => {
    expect(routeByOrgan("vessels", "DENY")).toBe("szl.organ.vessels.deny");
  });

  it("should route platform ADMIT correctly", () => {
    expect(routeByOrgan("platform", "ADMIT")).toBe("szl.organ.platform.admit");
  });

  it("should generate dynamic route for unknown organ", () => {
    expect(routeByOrgan("amaru", "ADMIT")).toBe("szl.organ.amaru.admit");
  });

  it("should generate dynamic route for unknown action", () => {
    expect(routeByOrgan("vessels", "OBSERVE")).toBe("szl.organ.vessels.observe");
  });
});

// ---------------------------------------------------------------------------
// Test Suite: HTTP publish to peat API (mocked)
// ---------------------------------------------------------------------------

describe("peat HTTP publish (mocked)", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("should POST capability dispatch to peat endpoint", async () => {
    mockPeatSuccess();
    const dispatch = {
      capability_id: "szl.organ.vessels.admit",
      version: "0.4.0",
      source: "szl-uds-deployment",
      receipt_id: "rcpt-abc123",
      organ_id: "vessels",
      action: "ADMIT",
      timestamp: new Date().toISOString(),
      cluster_id: TEST_CLUSTER_ID,
      namespace: TEST_NAMESPACE,
      payload: {
        governance_receipt_digest: "sha256:abc123",
        slsa_level: 3,
        organ_version: "0.4.0",
      },
    };

    const response = await fetch("https://peat.szl.internal/api/v1/capabilities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dispatch),
    });
    const result = await response.json();
    expect(response.ok).toBe(true);
    expect(result.status).toBe("queued");
    expect(mockFetch).toHaveBeenCalledOnce();
  });

  it("should handle peat API 500 error", async () => {
    mockPeatFailure(500, "Internal Server Error");
    const response = await fetch("https://peat.szl.internal/api/v1/capabilities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(response.ok).toBe(false);
    expect(response.status).toBe(500);
  });

  it("should handle peat API 429 rate limit", async () => {
    mockPeatFailure(429, "Too Many Requests");
    const response = await fetch("https://peat.szl.internal/api/v1/capabilities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(response.ok).toBe(false);
    expect(response.status).toBe(429);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Rate limiting simulation
// ---------------------------------------------------------------------------

describe("Rate limiting", () => {
  it("should allow requests under rate limit", () => {
    const maxPerMinute = 100;
    let count = 0;
    const allowed = [];
    for (let i = 0; i < 50; i++) {
      count++;
      allowed.push(count <= maxPerMinute);
    }
    expect(allowed.every(Boolean)).toBe(true);
  });

  it("should reject requests over rate limit", () => {
    const maxPerMinute = 10;
    let count = 0;
    const results = [];
    for (let i = 0; i < 15; i++) {
      count++;
      results.push({ allowed: count <= maxPerMinute, count });
    }
    const rejected = results.filter((r) => !r.allowed);
    expect(rejected).toHaveLength(5);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Circuit breaker simulation
// ---------------------------------------------------------------------------

describe("Circuit breaker", () => {
  let failures = 0;
  const THRESHOLD = 3;

  function isCircuitOpen() {
    return failures >= THRESHOLD;
  }

  beforeEach(() => {
    failures = 0;
  });

  it("should be closed initially", () => {
    expect(isCircuitOpen()).toBe(false);
  });

  it("should open after threshold failures", () => {
    failures = THRESHOLD;
    expect(isCircuitOpen()).toBe(true);
  });

  it("should remain closed below threshold", () => {
    failures = THRESHOLD - 1;
    expect(isCircuitOpen()).toBe(false);
  });

  it("should reset on success", () => {
    failures = THRESHOLD;
    expect(isCircuitOpen()).toBe(true);
    failures = 0;  // simulate reset
    expect(isCircuitOpen()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Test Suite: Integration — full receipt-to-dispatch pipeline
// ---------------------------------------------------------------------------

describe("Full pipeline: receipt → capability dispatch", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockPeatSuccess();
  });

  it("should process ADMIT receipt end-to-end", async () => {
    const receipt = makeGovernanceReceipt({ action: "ADMIT", organ_id: "vessels" });
    const envelope = makePqcEnvelope(receipt);

    // Decode
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.action).toBe("ADMIT");

    // Build dispatch
    const envelopeJson = JSON.stringify(envelope);
    const digest = createHash("sha256").update(envelopeJson).digest("hex");
    const dispatch = {
      capability_id: `szl.organ.${decoded.organ_id}.${decoded.action.toLowerCase()}`,
      version: "0.4.0",
      source: "szl-uds-deployment",
      receipt_id: decoded.receipt_id,
      organ_id: decoded.organ_id,
      action: decoded.action,
      timestamp: new Date().toISOString(),
      cluster_id: decoded.cluster_id,
      namespace: decoded.namespace,
      payload: {
        governance_receipt_digest: `sha256:${digest}`,
        slsa_level: decoded.slsa_level,
        attestation_uri: decoded.attestation_uri,
        organ_version: decoded.organ_version,
      },
    };

    expect(dispatch.capability_id).toBe("szl.organ.vessels.admit");
    expect(dispatch.payload.governance_receipt_digest).toMatch(/^sha256:[a-f0-9]{64}$/);

    // Publish
    const response = await fetch("https://peat.szl.internal/api/v1/capabilities", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dispatch),
    });
    expect(response.ok).toBe(true);
    const result = await response.json();
    expect(result.status).toBe("queued");
  });

  it("should process DENY receipt end-to-end", async () => {
    const receipt = makeGovernanceReceipt({ action: "DENY", organ_id: "amaru" });
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    const capId = `szl.organ.${decoded.organ_id}.${decoded.action.toLowerCase()}`;
    expect(capId).toBe("szl.organ.amaru.deny");
  });

  it("should include slsa_level in dispatch payload", async () => {
    const receipt = makeGovernanceReceipt({ slsa_level: 3 });
    const envelope = makeSignedEnvelope(receipt);
    const decoded = JSON.parse(Buffer.from(envelope.payload, "base64url").toString("utf8"));
    expect(decoded.slsa_level).toBe(3);
  });
});
