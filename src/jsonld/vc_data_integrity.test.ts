// ecdsa-jcs-2019 Data Integrity proofs (W3C vc-di-ecdsa) and a documented comparison with
// the proof wrap_dsse.ts produces today. Test keys are ephemeral, in memory only.
// Run: node --test src/jsonld/vc_data_integrity.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createVerify } from "node:crypto";
import { base58btcEncode, base58btcDecode, createProof, verifyProof, jcs } from "./vc_data_integrity.ts";
import { wrapDSSEinVC, type SZLReceiptRecord } from "./wrap_dsse.ts";

const VM = "did:web:szl.example#key-1";
const DOC = {
  "@context": ["https://www.w3.org/ns/credentials/v2"],
  type: ["VerifiableCredential"],
  issuer: "did:web:szl.example",
  validFrom: "2026-11-19T00:00:00Z",
  credentialSubject: { id: "urn:szl:organ:sentra", action: "deploy", outcome: "success" },
};
const OPTS = { verificationMethod: VM, proofPurpose: "assertionMethod", created: "2026-11-19T08:00:00Z" };

function keys() {
  return generateKeyPairSync("ec", { namedCurve: "P-256" });
}

test("base58btc: known vectors and round trips (zero-valued prefix bytes become '1')", () => {
  assert.equal(base58btcEncode(Buffer.from("hello world")), "StV1DL6CwTryKyV");
  assert.equal(base58btcEncode(Buffer.from("Hello World!")), "2NEpo7TZRRrLZSi2U");
  assert.equal(base58btcEncode(Buffer.from([0, 0, 0, 0])), "1111");
  assert.equal(base58btcEncode(Buffer.alloc(0)), "");
  for (const hex of ["00", "0001", "ff", "00ff00", "deadbeef", "0000000100"]) {
    assert.equal(base58btcDecode(base58btcEncode(Buffer.from(hex, "hex")))?.toString("hex"), hex);
  }
  assert.equal(base58btcDecode("0OIl"), null); // characters outside the alphabet
});

test("create then verify: the proof is a registered suite with a 64-byte base58-btc proofValue", () => {
  const { privateKey, publicKey } = keys();
  const secured = createProof(DOC, OPTS, privateKey);
  assert.equal(secured.proof.cryptosuite, "ecdsa-jcs-2019");
  assert.equal(secured.proof.type, "DataIntegrityProof");
  assert.deepEqual(secured.proof["@context"], DOC["@context"]);
  const value = secured.proof.proofValue as string;
  assert.ok(value.startsWith("z"));
  assert.equal(base58btcDecode(value.slice(1))?.length, 64);
  const r = verifyProof(secured, { keys: { [VM]: publicKey }, expectedProofPurpose: "assertionMethod" });
  assert.equal(r.valid, true, r.errors.join("; "));
});

test("the signature covers the proof options: changing created, verificationMethod or proofPurpose fails", () => {
  const { privateKey, publicKey } = keys();
  const other = keys();
  const secured = createProof(DOC, OPTS, privateKey);
  const trust = { keys: { [VM]: publicKey, "did:web:other#k": publicKey } };
  const mutate = (patch: Record<string, unknown>) => ({ ...secured, proof: { ...secured.proof, ...patch } });
  assert.equal(verifyProof(mutate({ created: "2020-01-01T00:00:00Z" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ verificationMethod: "did:web:other#k" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ proofPurpose: "authentication" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ "@context": ["https://example.com/other"] }), trust).valid, false);
  // and it covers the document
  assert.equal(verifyProof({ ...secured, credentialSubject: { ...DOC.credentialSubject, outcome: "failure" } }, trust).valid, false);
  // a different key under the same verificationMethod URL does not verify
  assert.equal(verifyProof(secured, { keys: { [VM]: other.publicKey } }).valid, false);
});

test("verification fails closed: wrong suite/type, bad proofValue, untrusted method, unexpected purpose, junk input", () => {
  const { privateKey, publicKey } = keys();
  const secured = createProof(DOC, OPTS, privateKey);
  const trust = { keys: { [VM]: publicKey } };
  const mutate = (patch: Record<string, unknown>) => ({ ...secured, proof: { ...secured.proof, ...patch } });
  assert.equal(verifyProof(mutate({ cryptosuite: "ecdsa-rdfc-2022" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ type: "Ed25519Signature2020" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ proofValue: "u" + (secured.proof.proofValue as string).slice(1) }), trust).valid, false);
  assert.equal(verifyProof(mutate({ proofValue: "z1111" }), trust).valid, false);
  assert.equal(verifyProof(mutate({ created: "yesterday" }), trust).valid, false);
  assert.equal(verifyProof(secured, { keys: {} }).valid, false);
  assert.equal(verifyProof(secured, { keys: { toString: publicKey } }).valid, false);
  assert.equal(verifyProof(secured, { ...trust, expectedProofPurpose: "authentication" }).valid, false);
  const { proof: _p, ...bare } = secured;
  assert.equal(verifyProof(bare, trust).valid, false);
  assert.equal(verifyProof({ ...secured, proof: [secured.proof] }, trust).valid, false);
  for (const junk of [null, undefined, 3, "x", []]) assert.equal(verifyProof(junk, trust).valid, false);
  assert.throws(() => createProof({ ...DOC, proof: {} }, OPTS, privateKey), /already has a proof/);
  assert.throws(() => createProof(DOC, { ...OPTS, created: "now" }, privateKey), /dateTime/);
});

test("a __proto__ member of the document is covered by the signature (not dropped)", () => {
  const { privateKey, publicKey } = keys();
  const withProto = JSON.parse('{"@context":["https://www.w3.org/ns/credentials/v2"],"credentialSubject":{"a":1}}');
  const secured = createProof(withProto, OPTS, privateKey);
  const tampered = JSON.parse(JSON.stringify(secured).replace('"a":1', '"a":1,"__proto__":{"role":"admin"}'));
  assert.equal(verifyProof(secured, { keys: { [VM]: publicKey } }).valid, true);
  assert.equal(verifyProof(tampered, { keys: { [VM]: publicKey } }).valid, false);
});

test("jcs() matches RFC 8785 ordering for integer-like keys", () => {
  assert.equal(jcs({ b: 1, "10": 2, "2": 3 }), '{"10":2,"2":3,"b":1}');
});

const RECEIPT: SZLReceiptRecord = {
  receiptId: "szl-2026-001",
  timestamp: "2026-05-29T22:00:00Z",
  organId: "sentra",
  action: "deploy",
  envelope: { payloadType: "application/vnd.szl.receipt.v1+json", payload: Buffer.from('{"a":1}').toString("base64url"), signatures: [{ sig: "c2ln" }] },
};

test("FINDING: wrapDSSEinVC's dev proof (labelled ecdsa-rdfc-2022) does not cover proof options and is not the registered suite", () => {
  const { privateKey, publicKey } = keys();
  const vc = wrapDSSEinVC(RECEIPT, { signingKeyPem: privateKey.export({ type: "pkcs8", format: "pem" }) as string });
  assert.equal(vc.proof.cryptosuite, "ecdsa-rdfc-2022"); // not a registered cryptosuite name
  const value = vc.proof.proofValue;
  assert.ok(value.startsWith("z"));
  assert.equal(base58btcDecode(value.slice(1)), null, "proofValue is not base58-btc (it is z + base64url of a DER signature)");

  // Re-verify the way a consumer could: signature over JCS(document without proof), DER encoding.
  const { proof, ...unsigned } = vc as unknown as { proof: Record<string, string> } & Record<string, unknown>;
  const verifyLegacy = (p: Record<string, string>) =>
    createVerify("SHA256").update(Buffer.from(jcs(JSON.parse(JSON.stringify(unsigned))))).verify(publicKey, Buffer.from(p.proofValue.slice(1), "base64url"));
  assert.equal(verifyLegacy(proof), true);
  // Rewriting every proof option leaves the signature valid: they are not signed.
  const rewritten = { ...proof, created: "1999-01-01T00:00:00Z", verificationMethod: "did:web:attacker.example#key-1", proofPurpose: "authentication" };
  assert.equal(verifyLegacy(rewritten), true);
});
