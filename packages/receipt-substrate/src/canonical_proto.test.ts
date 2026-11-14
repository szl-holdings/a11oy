// Regression tests: canonicalJson keeps "__proto__" members as data, refuses
// NFC-colliding keys, and verifyChain reports malformed input as invalid
// instead of throwing (POST /v1/verify must answer valid:false, not HTTP 500).
import { test } from "node:test";
import assert from "node:assert/strict";
import { canonicalJson, hashHex, createToolEnvelope, appendReceipt, receiptToJsonl, parseJsonlReceipts, verifyChain } from "./index.ts";

test("distinct payloads do not share a canonical hash", () => {
  const a = JSON.parse('{"x":1,"__proto__":{"y":2}}');
  const b = JSON.parse('{"x":1}');
  assert.notEqual(canonicalJson(a), canonicalJson(b));
  assert.notEqual(hashHex(a), hashHex(b));
});

test("verifyChain rejects a receipt with an injected nested __proto__ payload member", () => {
  const env = createToolEnvelope({ actor_id: "did:example:operator", tool_name: "t", payload: { query: "status", items: [{ k: 1 }] } });
  const line = receiptToJsonl(appendReceipt([], env)[0]);
  const tampered = line.replace('{"k":1}', '{"__proto__":{"role":"admin"},"k":1}');
  assert.notEqual(tampered, line);
  assert.equal(verifyChain(parseJsonlReceipts(tampered)).valid, false);
});

test("NFC-colliding keys are refused instead of silently merged", () => {
  assert.throws(() => canonicalJson({ "\u00e9": 1, "e\u0301": 2 }), /duplicate NFC key/);
});

test("verifyChain reports NFC-colliding keys and non-object entries as invalid instead of throwing", () => {
  const env = createToolEnvelope({ actor_id: "did:example:operator", tool_name: "t", payload: { q: 1 } });
  const rec = JSON.parse(receiptToJsonl(appendReceipt([], env)[0]));
  rec.envelope.payload = { "\u00e9": 1, "e\u0301": 2 };
  const r = verifyChain([rec]);
  assert.equal(r.valid, false);
  assert.match(r.errors.join(" "), /duplicate NFC key/);
  assert.equal(verifyChain([null as never]).valid, false);
  assert.equal(verifyChain([rec, null as never, rec]).valid, false);
});

test("every non-object verifyChain entry is invalid and does not skip later checks into valid:true", () => {
  const env = createToolEnvelope({ actor_id: "did:example:operator", tool_name: "t", payload: { q: 1 } });
  const good = JSON.parse(receiptToJsonl(appendReceipt([], env)[0]));
  const hittingGuard = [
    null,
    undefined,
    0,
    1,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    "",
    "x",
    false,
    true,
    1n,
    Symbol("s"),
    function receipt() {},
    [],
    [1],
    [{ a: 1 }],
    Array(1)[0],
  ];
  for (const value of hittingGuard) {
    const alone = verifyChain([value as never]);
    assert.equal(alone.valid, false);
    assert.deepEqual(alone.errors, ["position 0: receipt must be an object"]);
    const before = verifyChain([value as never, good]);
    assert.equal(before.valid, false);
    assert.equal(before.errors[0], "position 0: receipt must be an object");
    const after = verifyChain([good, value as never]);
    assert.equal(after.valid, false);
    assert.ok(after.errors.includes("position 1: receipt must be an object"));
  }
  assert.equal(verifyChain([good]).valid, true);
  const emptyObject = verifyChain([{} as never]);
  assert.equal(emptyObject.valid, false);
  assert.match(emptyObject.errors.join(" "), /canonicalJson: unsupported root value/);
  assert.ok(emptyObject.errors.some((error) => error.includes("prev_receipt_hash mismatch")));
});
