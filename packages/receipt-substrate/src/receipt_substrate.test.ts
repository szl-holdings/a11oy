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

const replayed = [...chain, chain[0]];
const replayResult = verifyChain(replayed, policy);
assert.equal(replayResult.valid, false);
assert.match(replayResult.errors.join("\n"), /duplicate receipt_id|prev_receipt_hash mismatch|timestamp regression/);

const weakQuorum = [{ ...genesis, quorum_signatures: ["node-primary"] }];
const weakQuorumResult = verifyChain(weakQuorum, policy);
assert.equal(weakQuorumResult.valid, false);
assert.match(weakQuorumResult.errors.join("\n"), /insufficient quorum/);

const witness = qecWitness(genesis.payload_hash);
assert.equal(witness.shor_repetition_count, 9);
assert.equal(witness.payload_byte, witness.shor_majority_payload);
assert.equal(witness.css_consistent, true);

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "a11oy-receipt-substrate-"));
const tmp = path.join(tmpDir, "receipts.jsonl");
try {
  fs.writeFileSync(tmp, `${JSON.stringify(genesis)}\n${JSON.stringify(chain[1])}\n`, "utf8");
  assert.equal(readReceiptJsonl(tmp).length, 2);
} finally {
  fs.rmSync(tmpDir, { recursive: true, force: true });
}

console.log("[receipt-substrate] OK 9 tests");
