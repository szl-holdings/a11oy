/**
 * SPDX-License-Identifier: Apache-2.0
 * (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
 * PurIQ receipt v1 schema, canonical hash, chain, and UNSIGNED conformance.
 */

import fs from "node:fs";
import path from "node:path";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";

const receiptV1 = require("../../static/shared/puriq_receipt_v1.js");

type Receipt = Record<string, any>;
type Vector = {
  name: string;
  receipts: Receipt[];
  expected: {
    valid: boolean;
    receipt_count: number;
    first_failure_receipt_id: string | null;
  };
};

const root = path.resolve(__dirname, "../..");
const schema = JSON.parse(
  fs.readFileSync(path.join(root, "schemas/puriq-receipt-v1.json"), "utf8")
);
const vectorDocument = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/puriq-receipt-v1-vectors.json"),
    "utf8"
  )
);
const vectors: Vector[] = vectorDocument.vectors;

const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);

function vector(name: string): Vector {
  const found = vectors.find((candidate) => candidate.name === name);
  if (!found) throw new Error(`missing vector ${name}`);
  return found;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value));
}

describe("PurIQ receipt payload v1", () => {
  test("schema accepts every literal receipt, with no unbound extra fields", () => {
    for (const testVector of vectors) {
      for (const receipt of testVector.receipts) {
        expect(validate(receipt)).toBe(true);
      }
    }

    const withExtra = clone(vector("single_receipt_session").receipts[0]);
    withExtra.unbound = "not-hashed";
    expect(validate(withExtra)).toBe(false);
    expect(receiptV1.validateReceipt(withExtra)).toContain("receipt_shape");
    return expect(receiptV1.computePayloadHash(withExtra)).rejects.toThrow(
      /exactly the PurIQ v1 fields|invalid PurIQ v1 receipt/
    );
  });

  test("canonical JSON is key-sorted, UTF-8 text with no insignificant whitespace", async () => {
    const canonical = receiptV1.canonicalJSON({ b: [true, 1], a: "café" });
    expect(canonical).toBe('{"a":"café","b":[true,1]}');
    expect(await receiptV1.sha256Hex(canonical)).toBe(
      "1b0ca46c91b5146b4490f7169251bc00d2e78a95f7ef65117dc7936afbf791b5"
    );
  });

  test("canonical edge vectors fix number spelling and Unicode key ordering", async () => {
    const value = {
      "\uE000": "private-use",
      "\u{1F600}": "astral",
      values: [-0, 1.0, 1e-7, 1e-6, 1e20, 1e21],
      unicode: "café\n\"\\\u2028"
    };
    const expected = '{"unicode":"café\\n\\\"\\\\\u2028","values":[0,1,1e-7,0.000001,100000000000000000000,1e+21],"😀":"astral","\uE000":"private-use"}';
    expect(receiptV1.canonicalJSON(value)).toBe(expected);
    expect(vectorDocument.canonical_vectors[0].canonical).toBe(expected);
    expect(await receiptV1.sha256Hex(expected)).toBe(vectorDocument.canonical_vectors[0].sha256);
    expect(receiptV1.canonicalJSON(vectorDocument.canonical_vectors[0].value)).toBe(expected);
    for (const invalid of [NaN, Infinity, undefined, new Date(), "\uD800", { "\uDC00": 1 }]) {
      expect(() => receiptV1.canonicalJSON(invalid)).toThrow(TypeError);
    }
  });

  test.each(vectors)("literal vector $name has its declared verdict", async (testVector) => {
    const verdict = await receiptV1.verifySession(testVector.receipts);
    expect({
      valid: verdict.valid,
      receipt_count: verdict.receipt_count,
      first_failure_receipt_id: verdict.first_failure_receipt_id
    }).toEqual(testVector.expected);
  });

  test("100-receipt vector recomputes every payload hash and link", async () => {
    const verdict = await receiptV1.verifySession(
      vector("hundred_receipt_session").receipts
    );
    expect(verdict.results).toHaveLength(100);
    for (const result of verdict.results) {
      expect(result.valid).toBe(true);
      expect(result.payload_hash_valid).toBe(true);
      expect(result.sequence_valid).toBe(true);
      expect(result.link_valid).toBe(true);
      expect(result.signature_valid).toBeNull();
      expect(result.signature_state).toBe("UNSIGNED");
      expect(result.errors).toEqual([]);
    }
  });

  test("a chain break invalidates that receipt and every later receipt", async () => {
    const broken = vector("chain_broken_session");
    const verdict = await receiptV1.verifySession(broken.receipts);
    expect(verdict.valid).toBe(false);
    expect(verdict.first_failure_receipt_id).toBe(broken.receipts[1].receipt_id);
    expect(verdict.results[1].errors).toEqual(
      expect.arrayContaining(["prev_receipt_hash_mismatch", "payload_hash_mismatch"])
    );
    expect(verdict.results[2].errors).toContain("upstream_invalid");
  });

  test("UNSIGNED is valid only when key_id is null", async () => {
    const receipts = clone(vector("unsigned_session").receipts);
    expect((await receiptV1.verifySession(receipts)).valid).toBe(true);
    receipts[0].signature.key_id = "placeholder-key";
    expect(validate(receipts[0])).toBe(false);
    const verdict = await receiptV1.verifySession(receipts);
    expect(verdict.valid).toBe(false);
    expect(verdict.results[0].errors).toContain("unsigned_key_id");
  });

  test.each([null, 3, "receipt", [], false])("malformed session entry %p fails without throwing", async (bad) => {
    const receipt = clone(vector("single_receipt_session").receipts[0]);
    const verdict = await receiptV1.verifySession([bad, receipt]);
    expect(verdict.valid).toBe(false);
    expect(verdict.first_failure_index).toBe(0);
    expect(verdict.first_failure_receipt_id).toBeNull();
    expect(verdict.results[0].errors).toContain("receipt_shape");
    expect(verdict.results[1].errors).toContain("upstream_invalid");
  });

  test("non-array session input is explicitly rejected", async () => {
    await expect(receiptV1.verifySession(null)).rejects.toThrow("receipts must be an array");
  });

  test.each([null, {}, 1, "failure"])("malformed gate failures %p fail without throwing", async (bad) => {
    const receipt = clone(vector("single_receipt_session").receipts[0]);
    receipt.gate.failures = bad;
    expect(validate(receipt)).toBe(false);
    expect(receiptV1.validateReceipt(receipt)).toContain("gate_failures");
    expect((await receiptV1.verifySession([receipt])).valid).toBe(false);
  });

  test.each([
    "2026-02-29T16:00:00Z", "2026-04-31T16:00:00Z", "2026-13-04T16:00:00Z",
    "2026-09-04T24:00:00Z", "2026-09-04T16:60:00Z", "2026-09-04T16:00:60Z"
  ])("calendar-invalid timestamp %s is rejected by schema and client", (issuedAt) => {
    const receipt = clone(vector("single_receipt_session").receipts[0]);
    receipt.issued_at = issuedAt;
    expect(validate(receipt)).toBe(false);
    expect(receiptV1.validateReceipt(receipt)).toContain("issued_at");
  });

  test.each(["2024-02-29T16:00:00.123456789Z", "2016-12-31T23:59:60Z"])(
    "valid leap timestamp %s is accepted by schema and client", (issuedAt) => {
      const receipt = clone(vector("single_receipt_session").receipts[0]);
      receipt.issued_at = issuedAt;
      expect(validate(receipt)).toBe(true);
      expect(receiptV1.validateReceipt(receipt)).toEqual([]);
    }
  );

  test("unsafe sequence numbers and malformed SemVer are rejected", () => {
    const receipt = clone(vector("single_receipt_session").receipts[0]);
    receipt.sequence = 9007199254740992;
    expect(validate(receipt)).toBe(false);
    expect(receiptV1.validateReceipt(receipt)).toContain("sequence");
    receipt.sequence = 0;
    receipt.subject.parser_version = "1.0.0-01";
    expect(validate(receipt)).toBe(false);
    expect(receiptV1.validateReceipt(receipt)).toContain("parser_version");
    receipt.subject.parser_version = "1.0.0-rc.1+build.001";
    expect(validate(receipt)).toBe(true);
    expect(receiptV1.validateReceipt(receipt)).toEqual([]);
  });

  test("failed Yuyay-13 gates never verify as emitted receipts", async () => {
    const receipts = clone(vector("single_receipt_session").receipts);
    receipts[0].gate.result = "fail";
    receipts[0].gate.failures = ["reference-failure"];
    receipts[0].payload_hash = await receiptV1.computePayloadHash(receipts[0]);
    const verdict = await receiptV1.verifySession(receipts);
    expect(verdict.valid).toBe(false);
    expect(verdict.results[0].errors).toContain("gate_failed_receipt");
  });

  test("signed receipts require an affirmative server verification callback", async () => {
    const receipts = clone(vector("single_receipt_session").receipts);
    const serverKey = randomBytes(32);
    receipts[0].signature = {
      algorithm: "HMAC-SHA256",
      key_id: "server-held-reference-key",
      value: createHmac("sha256", serverKey).update(receipts[0].payload_hash).digest("hex")
    };

    const withoutServer = await receiptV1.verifySession(receipts);
    expect(withoutServer.valid).toBe(false);
    expect(withoutServer.results[0].errors).toContain("signed_receipt_unverified");

    const rejected = await receiptV1.verifySession(receipts, {
      verifySignature: async () => false
    });
    expect(rejected.valid).toBe(false);
    expect(rejected.results[0].errors).toContain("signature_invalid");

    const accepted = await receiptV1.verifySession(receipts, {
      verifySignature: async (request: Record<string, string>) =>
        request.receipt_id === receipts[0].receipt_id &&
        request.payload_hash === receipts[0].payload_hash &&
        request.key_id === receipts[0].signature.key_id &&
        timingSafeEqual(
          Buffer.from(request.signature, "hex"),
          createHmac("sha256", serverKey).update(request.payload_hash).digest()
        )
    });
    expect(accepted.valid).toBe(true);
    expect(accepted.results[0].signature_valid).toBe(true);
    expect(accepted.results[0].signature_state).toBe("VERIFIED");
  });

  test("unsupported signature algorithms never reach the verifier or look verified", async () => {
    const receipts = clone(vector("single_receipt_session").receipts);
    receipts[0].signature = {
      algorithm: "Ed25519",
      key_id: "unsupported-reference-key",
      value: "b".repeat(64)
    };
    const verifySignature = jest.fn(async () => true);

    const verdict = await receiptV1.verifySession(receipts, { verifySignature });

    expect(verdict.valid).toBe(false);
    expect(verdict.results[0].errors).toContain("signature_algorithm");
    expect(verdict.results[0].signature_valid).toBe(false);
    expect(verdict.results[0].signature_state).toBe("INVALID");
    expect(verifySignature).not.toHaveBeenCalled();
  });

  test("payload_hash excludes signature but includes every field through gate", async () => {
    const original = clone(vector("single_receipt_session").receipts[0]);
    const changedSignature = clone(original);
    changedSignature.signature = {
      algorithm: "HMAC-SHA256",
      key_id: "server-held-reference-key",
      value: "b".repeat(64)
    };
    expect(await receiptV1.computePayloadHash(changedSignature)).toBe(
      original.payload_hash
    );

    const changedGate = clone(original);
    changedGate.gate.name = "not-yuyay-13";
    expect(receiptV1.validateReceipt(changedGate)).toContain("gate_name");
    await expect(receiptV1.computePayloadHash(changedGate)).rejects.toThrow(
      /gate_name/
    );
  });
});
