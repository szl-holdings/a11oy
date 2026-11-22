// Regression tests for verifyMerkleInclusionProof in rekor_verify.ts (RFC 9162 2.1.3.2).
// Vectors: transparency-dev/merkle testonly/constants.go (RFC 6962 hashing) and RFC 9162 2.1.5.
// Run: node --test src/sigstore/rekor_merkle.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { verifyMerkleInclusionProof } from "./rekor_verify.ts";

const sha = (...p: Buffer[]) => {
  const h = createHash("sha256");
  for (const x of p) h.update(x);
  return h.digest();
};
const leaf = (d: Buffer) => sha(Buffer.from([0]), d);
const node = (l: Buffer, r: Buffer) => sha(Buffer.from([1]), l, r);
const DATA = ["", "00", "10", "2021", "3031", "40414243", "5051525354555657", "606162636465666768696a6b6c6d6e6f"].map((h) => Buffer.from(h, "hex"));
const L = DATA.map(leaf);

function mth(hs: Buffer[]): Buffer {
  if (hs.length === 0) return sha();
  if (hs.length === 1) return hs[0];
  let k = 1;
  while (k * 2 < hs.length) k *= 2;
  return node(mth(hs.slice(0, k)), mth(hs.slice(k)));
}
function path(m: number, hs: Buffer[]): Buffer[] {
  if (hs.length === 1) return [];
  let k = 1;
  while (k * 2 < hs.length) k *= 2;
  return m < k ? [...path(m, hs.slice(0, k)), mth(hs.slice(k))] : [...path(m - k, hs.slice(k)), mth(hs.slice(0, k))];
}
const hex = (b: Buffer[]) => b.map((x) => x.toString("hex"));

test("pinned root for 8 leaves equals the transparency-dev reference value", () => {
  assert.equal(mth(L).toString("hex"), "5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328");
});

test("accepts every valid inclusion proof for every tree size 1..8 (including non-power-of-two sizes)", () => {
  for (let n = 1; n <= 8; n += 1) {
    const hs = L.slice(0, n);
    const root = mth(hs).toString("hex");
    for (let m = 0; m < n; m += 1) {
      assert.equal(verifyMerkleInclusionProof(hs[m], hex(path(m, hs)), m, n, root), true, `n=${n} m=${m}`);
    }
  }
});

test("rejects tampered proofs: wrong leaf/index/root, truncated or extended path, malformed hex", () => {
  const hs = L.slice(0, 7);
  const root = mth(hs).toString("hex");
  const p = hex(path(6, hs));
  assert.equal(verifyMerkleInclusionProof(hs[6], p, 6, 7, root), true);
  assert.equal(verifyMerkleInclusionProof(hs[5], p, 6, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p, 5, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p, 6, 7, "00".repeat(32)), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p.slice(1), 6, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], [...p, root], 6, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], [...p.slice(0, -1), "zz"], 6, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], [...p.slice(0, -1), ""], 6, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p, 7, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p, -1, 7, root), false);
  assert.equal(verifyMerkleInclusionProof(hs[6], p, 6, 7, root.slice(2)), false);
  assert.equal(verifyMerkleInclusionProof(null as never, p, 6, 7, root), false);
});

test("single-leaf tree: empty path proves the leaf is the root; any extra path element fails", () => {
  assert.equal(verifyMerkleInclusionProof(L[0], [], 0, 1, L[0].toString("hex")), true);
  assert.equal(verifyMerkleInclusionProof(L[0], [L[1].toString("hex")], 0, 1, L[0].toString("hex")), false);
});

// A verbatim copy of the pre-fix algorithm (rekor_verify.ts at 8b87bc4f, lines 189-241), kept to
// show which valid proofs it rejected. Not exported by the module.
function legacy(leafHash: Buffer, auditPath: string[], leafIndex: number, treeSize: number, expectedRootHash: string): boolean {
  let h = leafHash;
  let idx = leafIndex;
  let last = treeSize - 1;
  for (const s of auditPath) {
    const sb = Buffer.from(s, "hex");
    if (idx % 2 === 1 || idx === last) {
      if (idx % 2 === 1) h = sha(Buffer.from([1]), sb, h);
      else h = sha(Buffer.from([1]), h, sb);
    } else h = sha(Buffer.from([1]), h, sb);
    idx = Math.floor(idx / 2);
    last = Math.floor(last / 2);
  }
  return h.toString("hex") === expectedRootHash;
}

test("FINDING: the pre-fix algorithm rejected valid proofs for non-power-of-two trees", () => {
  const rejected: string[] = [];
  const falselyAccepted: string[] = [];
  for (let n = 1; n <= 8; n += 1) {
    const hs = L.slice(0, n);
    const root = mth(hs).toString("hex");
    for (let m = 0; m < n; m += 1) {
      if (!legacy(hs[m], hex(path(m, hs)), m, n, root)) rejected.push(`${m}/${n}`);
    }
  }
  // wrong tree size claimed with a valid-looking path: the old code never checks the path was fully consumed
  const hs = L.slice(0, 4);
  if (legacy(hs[0], hex(path(0, hs)), 0, 99, mth(hs).toString("hex"))) falselyAccepted.push("size 99 for a size-4 tree");
  assert.ok(rejected.length > 0, "expected the legacy algorithm to reject at least one valid proof");
  assert.ok(falselyAccepted.length > 0, "expected the legacy algorithm to accept an impossible tree size");
  assert.equal(verifyMerkleInclusionProof(hs[0], hex(path(0, hs)), 0, 99, mth(hs).toString("hex")), false);
});
