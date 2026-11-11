import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  appendReceipt,
  canonicalJson,
  createToolEnvelope,
  emitReceipt,
  parseQuorum,
  qecWitness,
  readReceiptJsonl,
  verifyChain,
  verifyReceipt,
  type OperationalReceipt,
} from "./index.ts";

const policy = {
  algorithm: "SHA3-256" as const,
  chaining: "hash_chain" as const,
  quorum: "2-of-3",
  nodes: ["node-primary", "node-backup", "node-witness"],
};

function envelope(payload: unknown = { query: "status", limit: 3 }) {
  return createToolEnvelope({
    protocol: "mcp",
    actor_id: "did:key:z6MkOperator",
    tool_name: "receipted_retrieval",
    lambda_axes: ["Λ7", "Λ2"],
    payload,
  });
}

assert.equal(canonicalJson({ b: 2, a: 1 }), canonicalJson({ a: 1, b: 2 }));
assert.equal(canonicalJson({ value: "e\u0301" }), canonicalJson({ value: "é" }));
assert.deepEqual(parseQuorum("2-of-3"), { required: 2, total: 3 });
assert.throws(() => parseQuorum("4-of-3"), /Invalid quorum/);

const genesis = emitReceipt(envelope(), {
  policy,
  quorumSignatures: ["node-backup", "node-primary"],
  timestamp: new Date("2026-05-29T00:00:00.000Z"),
});
assert.equal(verifyReceipt(genesis).valid, true);
assert.equal(genesis.prev_receipt_hash, null);
assert.equal(genesis.sequence, 0);
assert.equal(genesis.qec_witness.css_consistent, true);

const chain = appendReceipt([genesis], envelope({ query: "next", limit: 1 }), {
  policy,
  quorumSignatures: ["node-primary", "node-witness"],
  timestamp: new Date("2026-05-29T00:00:01.000Z"),
});
assert.equal(chain.length, 2);
assert.equal(verifyChain(chain).valid, true);
assert.equal(chain[1].prev_receipt_hash, genesis.merkle_root);

const tamperedPayload = [{ ...genesis, envelope: { ...genesis.envelope, payload: { query: "tampered" } } }, chain[1]];
const tamperedPayloadResult = verifyChain(tamperedPayload, policy);
assert.equal(tamperedPayloadResult.valid, false);
assert.match(tamperedPayloadResult.errors.join("\n"), /payload_hash mismatch|merkle_root mismatch/);

const tamperedReceiptId = [{ ...genesis, receipt_id: "or-tampered" }];
const tamperedReceiptIdResult = verifyChain(tamperedReceiptId, policy);
assert.equal(tamperedReceiptIdResult.valid, false);
assert.match(tamperedReceiptIdResult.errors.join("\n"), /receipt_id mismatch/);

const replayed = [...chain, chain[0]];
const replayResult = verifyChain(replayed, policy);
assert.equal(replayResult.valid, false);
assert.match(replayResult.errors.join("\n"), /duplicate receipt_id|prev_receipt_hash mismatch|timestamp regression/);

const skippedSequence = [{ ...genesis, sequence: 3 }];
const skippedSequenceResult = verifyChain(skippedSequence, policy);
assert.equal(skippedSequenceResult.valid, false);
assert.match(skippedSequenceResult.errors.join("\n"), /sequence mismatch|receipt_id mismatch|merkle_root mismatch/);

const weakQuorum = [{ ...genesis, quorum_signatures: ["node-primary"] }];
const weakQuorumResult = verifyChain(weakQuorum, policy);
assert.equal(weakQuorumResult.valid, false);
assert.match(weakQuorumResult.errors.join("\n"), /insufficient quorum/);

const impossibleQuorum = [{ ...genesis, policy: { ...genesis.policy!, quorum: "3-of-4" } }];
const impossibleQuorumResult = verifyChain(impossibleQuorum, policy);
assert.equal(impossibleQuorumResult.valid, false);
assert.match(impossibleQuorumResult.errors.join("\n"), /quorum total exceeds known nodes|merkle_root mismatch|receipt_id mismatch/);

const witness = qecWitness(genesis.payload_hash);
assert.equal(witness.shor_repetition_count, 9);
assert.equal(witness.payload_byte, witness.shor_majority_payload);
assert.equal(witness.css_consistent, true);

// A JSON "__proto__" key is payload data. It must stay in the canonical form,
// so adding one to a stored receipt changes its hashes.
const protoPayload = JSON.parse('{"b":1,"__proto__":{"x":1},"a":"e\\u0301"}');
assert.equal(canonicalJson(protoPayload), '{"__proto__":{"x":1},"a":"é","b":1}');
assert.notEqual(canonicalJson(protoPayload), canonicalJson({ b: 1, a: "é" }));
assert.equal(({} as Record<string, unknown>).x, undefined);

const protoTampered = JSON.parse(JSON.stringify(genesis).replace(
  '"payload":{"query":"status","limit":3}',
  '"payload":{"query":"status","limit":3,"__proto__":{"approved":true}}',
)) as OperationalReceipt;
assert.equal(Object.hasOwn(protoTampered.envelope.payload as object, "__proto__"), true);
const protoTamperedResult = verifyChain([protoTampered], policy);
assert.equal(protoTamperedResult.valid, false);
assert.match(protoTamperedResult.errors.join("\n"), /payload_hash mismatch/);

const protoEnvelope = createToolEnvelope({
  actor_id: "did:key:z6MkOperator",
  tool_name: "receipted_retrieval",
  payload: JSON.parse('{"query":"status","__proto__":{"x":1}}'),
  metadata: { source: "receipt-substrate-test" },
});
assert.deepEqual(Object.keys(protoEnvelope.payload as object), ["query", "__proto__"]);
assert.equal(Object.getPrototypeOf(protoEnvelope.payload), Object.prototype);
assert.equal((protoEnvelope.payload as Record<string, unknown>).x, undefined);
assert.equal(Object.getPrototypeOf(protoEnvelope.metadata), Object.prototype);
assert.deepEqual(envelope().payload, { query: "status", limit: 3 });

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "a11oy-receipt-substrate-"));
const tmp = path.join(tmpDir, "receipts.jsonl");
try {
  fs.writeFileSync(tmp, `${JSON.stringify(genesis)}\n${JSON.stringify(chain[1])}\n`, "utf8");
  assert.equal(readReceiptJsonl(tmp).length, 2);
} finally {
  fs.rmSync(tmpDir, { recursive: true, force: true });
}

console.log("[receipt-substrate] OK 15 tests");
