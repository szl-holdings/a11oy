// Negative + regression tests: "__proto__" keys must be covered by every
// canonicaliser that feeds a hash or a signature (sibling sites of the
// receipt-substrate fix tracked in PRs #3326/#3247/#3244).
// Run: node --test tests/proto_canonicalisers.test.mjs   (Node >= 22.18, type stripping)
import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, createVerify } from "node:crypto";
import { canonicalJson as workerCanonicalJson } from "../cloudflare/a11oy-governed-inference-worker.mjs";
import { wrapDSSEinVC } from "../src/jsonld/wrap_dsse.ts";

const tampered = JSON.parse('{"amount":1,"__proto__":{"role":"admin"}}');
const plain = { amount: 1 };

// Reference canonicaliser with a null-prototype target (what the bytes must be).
function ref(v) {
  if (Array.isArray(v)) return v.map(ref);
  if (v && typeof v === "object") {
    const o = Object.create(null);
    for (const k of Object.keys(v).sort()) o[k] = ref(v[k]);
    return o;
  }
  return v;
}

for (const [name, fn] of [["worker canonicalJson", workerCanonicalJson]]) {
  test(`${name}: __proto__ member is hashed (negative)`, () => {
    assert.notEqual(fn(tampered), fn(plain));
    assert.match(fn(tampered), /"__proto__":\{"role":"admin"\}/);
  });
  test(`${name}: nested and in-array __proto__ is hashed (negative)`, () => {
    const nested = JSON.parse('{"a":{"__proto__":{"x":1}},"b":[{"__proto__":2}]}');
    assert.equal(fn(nested), '{"a":{"__proto__":{"x":1}},"b":[{"__proto__":2}]}');
  });
  test(`${name}: ordinary input bytes unchanged (regression)`, () => {
    assert.equal(fn({ b: [2, { d: 1, c: null }], a: "x" }), '{"a":"x","b":[2,{"c":null,"d":1}]}');
  });
}

test("wrapDSSEinVC: signature covers a __proto__ member in rekorAttestation (negative)", () => {
  const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  const receipt = JSON.parse(JSON.stringify({
    receiptId: "r-1", timestamp: "2026-11-12T00:00:00Z", organId: "amaru", action: "verify",
    envelope: { payload: Buffer.from("{}").toString("base64url"), payloadType: "application/vnd.szl+json", signatures: [] },
  }));
  receipt.rekorAttestation = JSON.parse('{"logIndex":7,"__proto__":{"logIndex":999}}');
  const vc = wrapDSSEinVC(receipt, { signingKeyPem: privateKey.export({ type: "pkcs8", format: "pem" }) });
  const { proof, ...unsigned } = vc;
  const der = Buffer.from(proof.proofValue.slice(1), "base64url");
  const v = createVerify("SHA256"); v.update(Buffer.from(JSON.stringify(ref(unsigned)))); v.end();
  assert.equal(v.verify(publicKey, der), true, "signed bytes must include the __proto__ member");
});
