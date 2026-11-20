// DSSE v1.0.2 conformance vectors and fail-closed behaviour for dsse_verify.ts.
// Spec vector: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md "Test Vectors"
// Run: node --test src/jsonld/dsse_verify.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { createPublicKey, generateKeyPairSync, createHmac, sign, type KeyObject } from "node:crypto";
import { dssePAE, decodeDsseBase64, verifyDSSEEnvelope, type DsseTrustedKey } from "./dsse_verify.ts";

const SPEC_TYPE = "http://example.com/HelloWorld";
const SPEC_BODY = Buffer.from("hello world");
const SPEC_ENVELOPE = {
  payload: "aGVsbG8gd29ybGQ=",
  payloadType: SPEC_TYPE,
  signatures: [{ sig: "A3JqsQGtVsJ2O2xqrI5IcnXip5GToJ3F+FnZ+O88SjtR6rDAajabZKciJTfUiHqJPcIAriEGAHTVeCUjW2JIZA==" }],
};
// Public key from the spec (ECDSA P-256, SHA-256, deterministic RFC 6979, raw r||s). Only X,Y are used.
const X = 46950820868899156662930047687818585632848591499744589407958293238635476079160n;
const Y = 5640078356564379163099075877009565129882514886557779369047442380624545832820n;
const b64u = (n: bigint) => Buffer.from(n.toString(16).padStart(64, "0"), "hex").toString("base64url");
const SPEC_KEY: KeyObject = createPublicKey({ key: { kty: "EC", crv: "P-256", x: b64u(X), y: b64u(Y) }, format: "jwk" });
const specTrusted = (): DsseTrustedKey => ({ id: "spec-key", algorithm: "ecdsa-p256-sha256-p1363", publicKey: SPEC_KEY });
const accept = [SPEC_TYPE];

test("PAE matches the DSSE spec test vector byte for byte", () => {
  assert.equal(dssePAE(SPEC_TYPE, SPEC_BODY).toString("utf8"), "DSSEv1 29 http://example.com/HelloWorld 11 hello world");
});

test("PAE lengths are byte lengths of the UTF-8 encoding, not character counts", () => {
  assert.equal(dssePAE("t\u00e9", Buffer.from([0xff, 0x00])).toString("latin1"), "DSSEv1 3 t\u00c3\u00a9 2 \u00ff\u0000");
  assert.equal(dssePAE("", Buffer.alloc(0)).toString("ascii"), "DSSEv1 0  0 ");
  assert.throws(() => dssePAE("bad\ud800", SPEC_BODY), /not valid UTF-8/);
});

test("spec envelope verifies (ECDSA P-256 over the standard PAE) and returns the verified bytes", () => {
  const r = verifyDSSEEnvelope(SPEC_ENVELOPE, { keys: [specTrusted()], acceptedPayloadTypes: accept });
  assert.equal(r.valid, true, r.errors.join("; "));
  assert.equal(r.payload?.toString(), "hello world");
  assert.deepEqual(r.acceptedKeyIds, ["spec-key"]);
});

test("changing the payload, the payload type, or the signature breaks verification", () => {
  const opts = { keys: [specTrusted()], acceptedPayloadTypes: [SPEC_TYPE, "http://example.com/Other"] };
  assert.equal(verifyDSSEEnvelope({ ...SPEC_ENVELOPE, payload: Buffer.from("hello w0rld").toString("base64") }, opts).valid, false);
  assert.equal(verifyDSSEEnvelope({ ...SPEC_ENVELOPE, payloadType: "http://example.com/Other" }, opts).valid, false);
  const sig = SPEC_ENVELOPE.signatures[0].sig;
  assert.equal(verifyDSSEEnvelope({ ...SPEC_ENVELOPE, signatures: [{ sig: sig.replace("A3Jq", "A3Jr") }] }, opts).valid, false);
});

test("payload type must be on the allow-list, and an empty allow-list is a configuration error", () => {
  assert.match(verifyDSSEEnvelope(SPEC_ENVELOPE, { keys: [specTrusted()], acceptedPayloadTypes: ["application/vnd.in-toto+json"] }).errors.join(), /accepted list/);
  assert.match(verifyDSSEEnvelope(SPEC_ENVELOPE, { keys: [specTrusted()], acceptedPayloadTypes: [] }).errors.join(), /misconfigured/);
});

test("keyid is only a hint: a bogus or missing keyid does not change the outcome", () => {
  const withBogus = { ...SPEC_ENVELOPE, signatures: [{ keyid: "attacker-chosen", sig: SPEC_ENVELOPE.signatures[0].sig }] };
  assert.equal(verifyDSSEEnvelope(withBogus, { keys: [specTrusted()], acceptedPayloadTypes: accept }).valid, true);
});

test("an untrusted key cannot vouch for itself, even with a perfectly valid signature", () => {
  const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  const signed = dssePAE(SPEC_TYPE, SPEC_BODY);
  const sig = sign("sha256", signed, { key: privateKey, dsaEncoding: "ieee-p1363" }).toString("base64");
  const env = { payload: SPEC_ENVELOPE.payload, payloadType: SPEC_TYPE, signatures: [{ keyid: "spec-key", sig }] };
  assert.equal(verifyDSSEEnvelope(env, { keys: [specTrusted()], acceptedPayloadTypes: accept }).valid, false);
  assert.equal(verifyDSSEEnvelope(env, { keys: [{ id: "mine", algorithm: "ecdsa-p256-sha256-p1363", publicKey }], acceptedPayloadTypes: accept }).valid, true);
});

test("(t, n) rule: duplicates of one key do not count twice; t unique trusted keys are required", () => {
  const a = generateKeyPairSync("ed25519");
  const b = generateKeyPairSync("ed25519");
  const signed = dssePAE(SPEC_TYPE, SPEC_BODY);
  const sa = sign(null, signed, a.privateKey).toString("base64url");
  const sb = sign(null, signed, b.privateKey).toString("base64url");
  const keys: DsseTrustedKey[] = [
    { id: "a", algorithm: "ed25519", publicKey: a.publicKey },
    { id: "b", algorithm: "ed25519", publicKey: b.publicKey },
  ];
  const base = { payload: SPEC_ENVELOPE.payload, payloadType: SPEC_TYPE };
  const opts = (threshold: number) => ({ keys, acceptedPayloadTypes: accept, threshold });
  assert.equal(verifyDSSEEnvelope({ ...base, signatures: [{ sig: sa }, { sig: sa }] }, opts(2)).valid, false);
  assert.equal(verifyDSSEEnvelope({ ...base, signatures: [{ sig: sa }, { sig: "!!!" }, { sig: sb }] }, opts(2)).valid, true);
  assert.equal(verifyDSSEEnvelope({ ...base, signatures: [{ sig: sa }] }, opts(2)).valid, false);
  assert.match(verifyDSSEEnvelope({ ...base, signatures: [{ sig: sa }] }, opts(3)).errors.join(), /threshold exceeds/);
  assert.equal(verifyDSSEEnvelope({ ...base, signatures: [{ sig: sa }] }, opts(0)).valid, false);
});

test("HMAC-SHA-256 keys (as used by the RAE-1 receipts) verify over the standard PAE only", () => {
  const secret = Buffer.from("test-only-shared-secret-not-a-real-key");
  const mac = (pae: Buffer) => createHmac("sha256", secret).update(pae).digest().toString("base64url");
  const key: DsseTrustedKey = { id: "hmac", algorithm: "hmac-sha256", secret };
  const env = (sig: string) => ({ payload: SPEC_ENVELOPE.payload, payloadType: SPEC_TYPE, signatures: [{ sig }] });
  assert.equal(verifyDSSEEnvelope(env(mac(dssePAE(SPEC_TYPE, SPEC_BODY))), { keys: [key], acceptedPayloadTypes: accept }).valid, true);
  assert.equal(verifyDSSEEnvelope(env(mac(Buffer.from("hello world"))), { keys: [key], acceptedPayloadTypes: accept }).valid, false);
  assert.equal(verifyDSSEEnvelope(env(mac(dssePAE(SPEC_TYPE, SPEC_BODY))), { keys: [{ id: "hmac", algorithm: "hmac-sha256", secret: Buffer.alloc(0) }], acceptedPayloadTypes: accept }).valid, false);
});

test("FINDING: the PAE variants in src/rae1/schema.ts (doc) and a11oy/integrations/peat-bridge.ts differ from DSSE v1", () => {
  const le64 = (n: number) => {
    const b = Buffer.alloc(8);
    b.writeBigUInt64LE(BigInt(n));
    return b;
  };
  // src/rae1/schema.ts:246-250 documents: LE64(2) || LE64(len(type)) || type || LE64(len(payload)) || payload
  const rae1Doc = Buffer.concat([le64(2), le64(Buffer.byteLength(SPEC_TYPE)), Buffer.from(SPEC_TYPE), le64(SPEC_BODY.length), SPEC_BODY]);
  // a11oy/integrations/peat-bridge.ts:192-206 (buildPAE): "DSSEv1 " || LE64(len)||type || " " || LE64(len)||payload-as-base64-text
  const peat = Buffer.concat([
    Buffer.from("DSSEv1 "),
    le64(Buffer.byteLength(SPEC_TYPE)),
    Buffer.from(SPEC_TYPE),
    Buffer.from(" "),
    le64(Buffer.byteLength(SPEC_ENVELOPE.payload)),
    Buffer.from(SPEC_ENVELOPE.payload),
  ]);
  const standard = dssePAE(SPEC_TYPE, SPEC_BODY);
  assert.notDeepEqual(rae1Doc, standard);
  assert.notDeepEqual(peat, standard);
  // A signature over either variant is not a DSSE signature: an independent verifier rejects it.
  const { privateKey, publicKey } = generateKeyPairSync("ed25519");
  const key: DsseTrustedKey = { id: "k", algorithm: "ed25519", publicKey };
  for (const variant of [rae1Doc, peat]) {
    const sig = sign(null, variant, privateKey).toString("base64");
    assert.equal(verifyDSSEEnvelope({ ...SPEC_ENVELOPE, signatures: [{ sig }] }, { keys: [key], acceptedPayloadTypes: accept }).valid, false);
  }
});

test("base64 handling: both alphabets accepted, mixed/garbage/non-canonical rejected", () => {
  assert.equal(decodeDsseBase64("aGVsbG8gd29ybGQ=")?.toString(), "hello world");
  assert.equal(decodeDsseBase64("aGVsbG8gd29ybGQ")?.toString(), "hello world");
  assert.equal(decodeDsseBase64("-_-_")?.length, 3);
  assert.equal(decodeDsseBase64("+/+/")?.length, 3);
  assert.equal(decodeDsseBase64("+_+_"), null);
  assert.equal(decodeDsseBase64("aGVsbG8gd29ybGR="), null); // non-zero trailing bits
  assert.equal(decodeDsseBase64("a"), null);
  assert.equal(decodeDsseBase64(""), null);
  assert.equal(decodeDsseBase64("aGVs bG8="), null);
  assert.equal(decodeDsseBase64(42), null);
});

test("malformed envelopes fail closed without throwing", () => {
  const opts = { keys: [specTrusted()], acceptedPayloadTypes: accept };
  for (const bad of [null, undefined, 1, "x", [], {}, { payloadType: SPEC_TYPE }, { ...SPEC_ENVELOPE, signatures: [] }, { ...SPEC_ENVELOPE, signatures: "x" }, { ...SPEC_ENVELOPE, payload: 5 }, { ...SPEC_ENVELOPE, payloadType: "" }, { ...SPEC_ENVELOPE, signatures: [null, 3, {}] }]) {
    const r = verifyDSSEEnvelope(bad, opts);
    assert.equal(r.valid, false);
    assert.equal(r.payload, undefined);
  }
  assert.equal(verifyDSSEEnvelope(SPEC_ENVELOPE, undefined as never).valid, false);
  assert.equal(verifyDSSEEnvelope(SPEC_ENVELOPE, { keys: [specTrusted(), specTrusted()], acceptedPayloadTypes: accept }).valid, false); // duplicate key ids
});
