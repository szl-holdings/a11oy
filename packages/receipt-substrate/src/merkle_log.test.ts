// RFC 9162 section 2.1 conformance for merkle_log.ts.
// Vectors: (a) transparency-dev/merkle testonly/constants.go (RFC 6962 hashing, the
// reference vectors used by Google's CT and Trillian code), (b) the 7-leaf worked
// example in RFC 9162 section 2.1.5.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyRoot,
  hashLeaf,
  hashChildren,
  treeHash,
  inclusionProof,
  consistencyProof,
  verifyInclusion,
  verifyConsistency,
  chainTreeHead,
  receiptLeafHashes,
} from "./merkle_log.ts";
import { createToolEnvelope, appendReceipt, type OperationalReceipt } from "./index.ts";

const hx = (s: string) => Buffer.from(s, "hex");
const LEAVES = ["", "00", "10", "2021", "3031", "40414243", "5051525354555657", "606162636465666768696a6b6c6d6e6f"].map(hx);
const ROOTS = [
  "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d",
  "fac54203e7cc696cf0dfcb42c92a1d9dbaf70ad9e621f4bd8d98662f00e3c125",
  "aeb6bcfe274b70a14fb067a5e5578264db0fa9b51af5e0ba159158f329e06e77",
  "d37ee418976dd95753c1c73862b9398fa2a2cf9b4ff0fdfe8b30cd95209614b7",
  "4e3bbb1f7b478dcfe71fb631631519a3bca12c9aefca1612bfce4c13a86264d4",
  "76e67dadbcdf1e10e1b74ddc608abd2f98dfb16fbce75277b5232a127f2087ef",
  "ddb89be403809e325750d3d263cd78929c2942b7942a34b77e122c9594a74c8c",
  "5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328",
];
const leafHashes = LEAVES.map(hashLeaf);

test("tree heads for sizes 0..8 match the RFC 6962/9162 reference vectors", () => {
  assert.equal(emptyRoot().toString("hex"), ROOTS[0]);
  for (let n = 0; n <= 8; n += 1) {
    assert.equal(treeHash(leafHashes.slice(0, n)).toString("hex"), ROOTS[n], `size ${n}`);
  }
});

test("RFC 9162 2.1.5 worked example: 7 leaves, named nodes, inclusion and consistency paths", () => {
  const d = leafHashes.slice(0, 7);
  const [a, b, c, dd, e, f, j] = d;
  const g = hashChildren(a, b);
  const h = hashChildren(c, dd);
  const i = hashChildren(e, f);
  const k = hashChildren(g, h);
  const l = hashChildren(i, j);
  const root = hashChildren(k, l);
  assert.deepEqual(treeHash(d), root);
  assert.deepEqual(inclusionProof(0, d), [b, h, l]);
  assert.deepEqual(inclusionProof(3, d), [c, g, l]);
  assert.deepEqual(inclusionProof(4, d), [f, j, k]);
  assert.deepEqual(inclusionProof(6, d), [i, k]);
  assert.deepEqual(consistencyProof(3, d), [c, dd, g, l]);
  assert.deepEqual(consistencyProof(4, d), [l]);
  assert.deepEqual(consistencyProof(6, d), [i, j, k]);
});

test("every inclusion proof verifies for every leaf and tree size 1..8, and breaks under any tamper", () => {
  for (let n = 1; n <= 8; n += 1) {
    const hs = leafHashes.slice(0, n);
    const root = treeHash(hs);
    for (let m = 0; m < n; m += 1) {
      const proof = inclusionProof(m, hs);
      assert.equal(verifyInclusion(hs[m], m, n, proof, root), true, `n=${n} m=${m}`);
      // wrong index, wrong size, wrong leaf, wrong root, extended / truncated / mutated path
      if (n > 1) assert.equal(verifyInclusion(hs[m], (m + 1) % n, n, proof, root), n > 1 && (m + 1) % n === m);
      // Note: the size is not bound by the proof itself (the RFC 9162 algorithm accepts e.g. n=3 proof
      // for n=4 against the size-3 root). Callers must take (size, root) together from a signed checkpoint.
      assert.equal(verifyInclusion(hashLeaf(Buffer.from("x")), m, n, proof, root), false);
      assert.equal(verifyInclusion(hs[m], m, n, proof, hashLeaf(Buffer.from("y"))), false);
      assert.equal(verifyInclusion(hs[m], m, n, [...proof, root], root), false);
      if (proof.length > 0) {
        assert.equal(verifyInclusion(hs[m], m, n, proof.slice(1), root), false);
        const bad = proof.map((p) => Buffer.from(p));
        bad[0][0] ^= 1;
        assert.equal(verifyInclusion(hs[m], m, n, bad, root), false);
      }
    }
  }
});

test("every consistency proof verifies for 1 <= m < n <= 8, and fails for the wrong sizes or roots", () => {
  for (let n = 2; n <= 8; n += 1) {
    const hs = leafHashes.slice(0, n);
    const second = treeHash(hs);
    for (let m = 1; m < n; m += 1) {
      const first = treeHash(hs.slice(0, m));
      const proof = consistencyProof(m, hs);
      assert.equal(verifyConsistency(m, n, first, second, proof), true, `m=${m} n=${n}`);
      assert.equal(verifyConsistency(m, n, hashLeaf(Buffer.from("x")), second, proof), false);
      assert.equal(verifyConsistency(m, n, first, hashLeaf(Buffer.from("y")), proof), false);
      assert.equal(verifyConsistency(m, n, first, second, proof.slice(0, -1)), false);
      assert.equal(verifyConsistency(m, n, first, second, [...proof, second]), false);
    }
  }
  // not an append-only extension: a different history of the same size
  const forked = [...leafHashes.slice(0, 3), hashLeaf(Buffer.from("forked")), ...leafHashes.slice(4, 6)];
  const honestFirst = treeHash(leafHashes.slice(0, 4));
  assert.equal(verifyConsistency(4, 6, honestFirst, treeHash(forked), consistencyProof(4, forked)), false);
});

test("verifiers fail closed on malformed input instead of throwing", () => {
  const hs = leafHashes.slice(0, 4);
  const root = treeHash(hs);
  const proof = inclusionProof(1, hs);
  assert.equal(verifyInclusion(hs[1], -1, 4, proof, root), false);
  assert.equal(verifyInclusion(hs[1], 4, 4, proof, root), false);
  assert.equal(verifyInclusion(hs[1], 1.5, 4, proof, root), false);
  assert.equal(verifyInclusion(hs[1], 1, 4, [Buffer.alloc(31)], root), false);
  assert.equal(verifyInclusion(null as never, 1, 4, proof, root), false);
  assert.equal(verifyConsistency(0, 4, root, root, proof), false);
  assert.equal(verifyConsistency(4, 4, root, root, proof), false);
  assert.equal(verifyConsistency(2, 4, root, root, []), false);
  assert.equal(verifyConsistency(2, 4, root, root, undefined as never), false);
  assert.throws(() => inclusionProof(4, hs), /out of range/);
  assert.throws(() => consistencyProof(5, hs), /out of range/);
});

test("a leaf and an interior node never collide (0x00/0x01 domain separation)", () => {
  const [x, y] = leafHashes;
  assert.notDeepEqual(hashLeaf(Buffer.concat([x, y])), hashChildren(x, y));
});

function makeChain(n: number): OperationalReceipt[] {
  let chain: OperationalReceipt[] = [];
  for (let i = 0; i < n; i += 1) {
    const env = createToolEnvelope({ actor_id: "did:example:operator", tool_name: "t", payload: { i } });
    chain = appendReceipt(chain, env, { timestamp: new Date(Date.UTC(2026, 10, 19, 0, 0, i)) });
  }
  return chain;
}

test("receipt chain: inclusion of any receipt and append-only growth are provable from tree heads", () => {
  const chain = makeChain(9);
  const head5 = chainTreeHead(chain.slice(0, 5));
  const head9 = chainTreeHead(chain);
  assert.equal(head9.size, 9);
  const all = receiptLeafHashes(chain);
  for (let m = 0; m < 9; m += 1) {
    assert.equal(verifyInclusion(all[m], m, 9, inclusionProof(m, all), hx(head9.rootHash)), true);
  }
  assert.equal(verifyConsistency(5, 9, hx(head5.rootHash), hx(head9.rootHash), consistencyProof(5, all)), true);
  // rewriting an old receipt (even keeping the chain internally consistent) changes the head
  const rewritten = makeChain(9);
  rewritten[2] = { ...rewritten[2], actor_id: "did:example:other" };
  assert.notEqual(chainTreeHead(rewritten).rootHash, head9.rootHash);
});
