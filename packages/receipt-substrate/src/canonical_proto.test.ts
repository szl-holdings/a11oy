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
