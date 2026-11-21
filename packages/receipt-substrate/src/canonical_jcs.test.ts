// RFC 8785 (JSON Canonicalization Scheme) conformance vectors for canonicalJson().
//
// jcsCanonicalize() (src/jcs.ts) is the strict RFC 8785 serializer and must match
// every vector. canonicalJson() (the receipt hash path) is JCS plus documented
// deviations, asserted below so a change to any of them is deliberate:
//   D1  strings and keys are NFC-normalised first (RFC 8785 does not normalise);
//   D2  members whose value is `undefined` are skipped (JSON.stringify semantics);
//   D3  NFC-colliding keys are refused (see canonical_proto.test.ts);
//   D4  integer-like keys ("1", "10", "2") enumerate in numeric order before other
//       keys, so the bytes differ from RFC 8785 (FINDING, not yet changed: fixing
//       it alters stored receipt hashes and needs a schema bump + approval). Vectors are copied from
// https://www.rfc-editor.org/rfc/rfc8785 (Section 3.2.2 sample / 3.2.3 sort test /
// 3.2.4 bytes / Appendix B number table).
import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalJson, createToolEnvelope, appendReceipt, verifyChain } from "./index.ts";
import { jcsCanonicalize } from "./jcs.ts";

function f64(hex: string): number {
  const b = Buffer.from(hex, "hex");
  return b.readDoubleBE(0);
}

test("RFC 8785 Appendix B: ECMAScript number serialisation table", () => {
  const rows: [string, string][] = [
    ["0000000000000000", "0"],
    ["8000000000000000", "0"], // minus zero
    ["0000000000000001", "5e-324"],
    ["8000000000000001", "-5e-324"],
    ["7fefffffffffffff", "1.7976931348623157e+308"],
    ["ffefffffffffffff", "-1.7976931348623157e+308"],
    ["4340000000000000", "9007199254740992"],
    ["c340000000000000", "-9007199254740992"],
    ["4430000000000000", "295147905179352830000"],
    ["44b52d02c7e14af5", "9.999999999999997e+22"],
    ["44b52d02c7e14af6", "1e+23"],
    ["44b52d02c7e14af7", "1.0000000000000001e+23"],
    ["444b1ae4d6e2ef4e", "999999999999999700000"],
    ["444b1ae4d6e2ef4f", "999999999999999900000"],
    ["444b1ae4d6e2ef50", "1e+21"],
    ["3eb0c6f7a0b5ed8c", "9.999999999999997e-7"],
    ["3eb0c6f7a0b5ed8d", "0.000001"],
    ["41b3de4355555553", "333333333.3333332"],
    ["41b3de4355555554", "333333333.33333325"],
    ["41b3de4355555555", "333333333.3333333"],
    ["41b3de4355555556", "333333333.3333334"],
    ["41b3de4355555557", "333333333.33333343"],
    ["becbf647612f3696", "-0.0000033333333333333333"],
    ["43143ff3c1cb0959", "1424953923781206.2"],
  ];
  for (const [hex, expected] of rows) {
    assert.equal(canonicalJson(f64(hex)), expected, `canonicalJson IEEE754 ${hex}`);
    assert.equal(jcsCanonicalize(f64(hex)), expected, `jcs IEEE754 ${hex}`);
  }
});

test("RFC 8785 Appendix B: NaN and Infinity terminate with an error", () => {
  for (const hex of ["7fffffffffffffff", "7ff0000000000000", "fff0000000000000"]) {
    assert.throws(() => canonicalJson(f64(hex)), /non-finite/);
    assert.throws(() => jcsCanonicalize(f64(hex)), /NaN and Infinity/);
  }
});

test("RFC 8785 Section 3.2.2/3.2.4: structured sample canonicalises to the RFC bytes", () => {
  const input = JSON.parse(
    '{"numbers":[333333333.33333329,1E30,4.50,2e-3,0.000000000000000000000000001],' +
      '"string":"\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"/","literals":[null,true,false]}',
  );
  const expectedHex =
    "7b226c69746572616c73223a5b6e756c6c2c747275652c66616c73655d2c226e756d62657273223a5b3333333333333333332e333333333333332c31652b33302c342e352c302e3030322c31652d32375d2c22737472696e67223a22e282ac245c7530303066 5c6e4127425c225c5c5c5c5c222f227d".replace(/ /g, "");
  assert.equal(Buffer.from(canonicalJson(input), "utf8").toString("hex"), expectedHex);
  assert.equal(Buffer.from(jcsCanonicalize(input), "utf8").toString("hex"), expectedHex);
});

test("RFC 8785 Section 3.2.3: jcsCanonicalize sorts the full RFC property vector by UTF-16 code units", () => {
  const input = JSON.parse(
    '{"\\u20ac":"Euro Sign","\\r":"Carriage Return","\\ufb33":"Hebrew Letter Dalet With Dagesh","1":"One",' +
      '"\\ud83d\\ude00":"Emoji: Grinning Face","\\u0080":"Control","\\u00f6":"Latin Small Letter O With Diaeresis"}',
  );
  const text = jcsCanonicalize(input);
  const order = [
    "Carriage Return",
    "One",
    "Control",
    "Latin Small Letter O With Diaeresis",
    "Euro Sign",
    "Emoji: Grinning Face",
    "Hebrew Letter Dalet With Dagesh",
  ];
  const positions = order.map((v) => text.indexOf(`"${v}"`));
  assert.ok(positions.every((p) => p >= 0));
  assert.deepEqual([...positions].sort((x, y) => x - y), positions);
});

test("FINDING D4: canonicalJson puts integer-like keys first; RFC 8785 does not", () => {
  const input = { b: 1, "10": 2, "2": 3, a: 4 };
  // RFC 8785: "10" < "2" < "a" < "b" (code-unit order).
  assert.equal(jcsCanonicalize(input), '{"10":2,"2":3,"a":4,"b":1}');
  // Current receipt hash path: ECMAScript integer-key enumeration order.
  assert.equal(canonicalJson(input), '{"2":3,"10":2,"a":4,"b":1}');
  assert.notEqual(canonicalJson(input), jcsCanonicalize(input));
});

test("canonicalJson equals strict JCS for NFC-stable data without integer-like keys", () => {
  const input = JSON.parse(
    '{"z":[1,{"y":null,"x":"\\u00e9"}],"a":{"\\u20ac":true,"\\ud83d\\ude00":0.1,"m":-0},"s":"line\\nbreak"}',
  );
  assert.equal(canonicalJson(input), jcsCanonicalize(input));
});

test("jcsCanonicalize keeps __proto__ as data and accepts only plain JSON", () => {
  const withProto = JSON.parse('{"x":1,"__proto__":{"y":2}}');
  assert.equal(jcsCanonicalize(withProto), '{"__proto__":{"y":2},"x":1}');
  assert.throws(() => jcsCanonicalize({ d: new Date(0) }), /plain JSON/);
  assert.throws(() => jcsCanonicalize({ u: undefined }), /unsupported undefined/);
  assert.throws(() => jcsCanonicalize({ f() {} }), /unsupported function/);
  assert.throws(() => jcsCanonicalize(10n), /unsupported bigint/);
});

test("documented deviation D1: NFC rewrites U+FB33, so the RFC sort vector is not byte-identical for that key", () => {
  assert.equal("\ufb33".normalize("NFC"), "\u05d3\u05bc");
  assert.equal(canonicalJson({ "\ufb33": 1 }), '{"\u05d3\u05bc":1}');
});

test("JSON string escaping follows RFC 8785 Section 3.2.2.2", () => {
  assert.equal(canonicalJson("\b\t\n\f\r"), '"\\b\\t\\n\\f\\r"');
  assert.equal(canonicalJson("\u0000\u001f"), '"\\u0000\\u001f"');
  assert.equal(canonicalJson('"\\'), '"\\"\\\\"');
  assert.equal(canonicalJson("\u007f\u2028"), '"\u007f\u2028"');
});

test("RFC 8785 Section 3.2.2.2: lone surrogates terminate with an error (value, key, nested)", () => {
  assert.throws(() => canonicalJson("\udead"), /lone surrogate/);
  assert.throws(() => canonicalJson("\ud83d"), /lone surrogate/);
  assert.throws(() => canonicalJson({ ["a\ude00b"]: 1 }), /lone surrogate/);
  assert.throws(() => canonicalJson({ a: [{ b: "x\ud800" }] }), /lone surrogate/);
  assert.throws(() => jcsCanonicalize("\udead"), /lone surrogate/);
  assert.throws(() => jcsCanonicalize({ ["a\ude00b"]: 1 }), /lone surrogate/);
  // A well-formed pair is fine.
  assert.equal(canonicalJson("\ud83d\ude00"), '"\u{1F600}"');
});

test("verifyChain reports a lone-surrogate receipt as invalid (fail closed) instead of throwing", () => {
  const env = createToolEnvelope({ actor_id: "did:example:operator", tool_name: "t", payload: { q: 1 } });
  const rec = JSON.parse(JSON.stringify(appendReceipt([], env)[0]));
  rec.envelope.payload = { q: "bad\udead" };
  const r = verifyChain([rec]);
  assert.equal(r.valid, false);
  assert.match(r.errors.join(" "), /lone surrogate/);
});

test("emitting a receipt for a lone-surrogate payload is refused rather than hashed", () => {
  assert.throws(
    () => appendReceipt([], createToolEnvelope({ actor_id: "a", tool_name: "t", payload: { q: "\udead" } })),
    /lone surrogate/,
  );
});

test("documented deviation D2: undefined members are dropped, null members are kept", () => {
  assert.equal(canonicalJson({ a: undefined, b: null }), '{"b":null}');
});

test("FINDING D5: non-JSON objects (Date, Map, Set) all collapse to {} in canonicalJson, so distinct payloads share a hash", () => {
  // Recorded, not changed: rejecting them could break callers that pass a Date today.
  // jcsCanonicalize() refuses them, which is the behaviour RFC 8785 (JSON data only) implies.
  assert.equal(canonicalJson({ v: new Date(0) }), '{"v":{}}');
  assert.equal(canonicalJson({ v: new Date(86400000) }), canonicalJson({ v: new Map([[1, 2]]) }));
  assert.throws(() => jcsCanonicalize({ v: new Date(0) }), /plain JSON/);
});
