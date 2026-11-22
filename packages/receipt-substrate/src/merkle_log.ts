// RFC 9162 section 2.1 Merkle tree over receipts: tree head, inclusion proofs and
// consistency proofs. Hash is SHA-256 (the RFC 9162 / RFC 6962 default, and what
// Rekor and CT logs use), with the 0x00 leaf / 0x01 node domain separation.
//
// Why: the existing chain is a linear hash chain (prev_receipt_hash). A verifier
// holding only the newest receipt cannot check that an older receipt is part of
// it without replaying the whole chain, and two parties cannot prove to each
// other that one chain head extends another (append-only) without the full chain.
// A Merkle tree head gives O(log n) inclusion and consistency proofs that any
// RFC 9162 / Trillian / Rekor verifier can check. Additive: it does not change
// receipt contents or hashes.
//
// Spec: https://www.rfc-editor.org/rfc/rfc9162#section-2.1
import * as crypto from "node:crypto";
import { canonicalJson, type OperationalReceipt } from "./index.ts";

export type Hash = Buffer;

const HASH_LEN = 32;

function sha256(...parts: Buffer[]): Hash {
  const h = crypto.createHash("sha256");
  for (const p of parts) h.update(p);
  return h.digest();
}

/** MTH({}) = HASH() */
export function emptyRoot(): Hash {
  return sha256();
}

/** MTH({d(0)}) = HASH(0x00 || d(0)) */
export function hashLeaf(data: Buffer): Hash {
  return sha256(Buffer.from([0x00]), data);
}

/** HASH(0x01 || left || right) */
export function hashChildren(left: Hash, right: Hash): Hash {
  return sha256(Buffer.from([0x01]), left, right);
}

/** Largest power of two strictly smaller than n (n >= 2). */
function splitPoint(n: number): number {
  let k = 1;
  while (k * 2 < n) k *= 2;
  return k;
}

function assertHashes(hashes: readonly Hash[]): void {
  for (const h of hashes) {
    if (!Buffer.isBuffer(h) || h.length !== HASH_LEN) throw new Error("merkle: every hash must be a 32-byte Buffer");
  }
}

/** MTH(D[n]) over already-hashed leaves. */
export function treeHash(leafHashes: readonly Hash[]): Hash {
  assertHashes(leafHashes);
  const mth = (lo: number, hi: number): Hash => {
    const n = hi - lo;
    if (n === 0) return emptyRoot();
    if (n === 1) return leafHashes[lo];
    const k = splitPoint(n);
    return hashChildren(mth(lo, lo + k), mth(lo + k, hi));
  };
  return mth(0, leafHashes.length);
}

/** RFC 9162 2.1.3.1 PATH(m, D[n]). */
export function inclusionProof(leafIndex: number, leafHashes: readonly Hash[]): Hash[] {
  assertHashes(leafHashes);
  if (!Number.isInteger(leafIndex) || leafIndex < 0 || leafIndex >= leafHashes.length) {
    throw new Error("merkle: leaf index out of range");
  }
  const path = (m: number, lo: number, hi: number): Hash[] => {
    const n = hi - lo;
    if (n === 1) return [];
    const k = splitPoint(n);
    return m < k
      ? [...path(m, lo, lo + k), treeHash(leafHashes.slice(lo + k, hi))]
      : [...path(m - k, lo + k, hi), treeHash(leafHashes.slice(lo, lo + k))];
  };
  return path(leafIndex, 0, leafHashes.length);
}

/** RFC 9162 2.1.4.1 PROOF(m, D[n]) for 0 < m < n; empty when m === n (nothing to prove). */
export function consistencyProof(first: number, leafHashes: readonly Hash[]): Hash[] {
  assertHashes(leafHashes);
  const n = leafHashes.length;
  if (!Number.isInteger(first) || first < 1 || first > n) throw new Error("merkle: first tree size out of range");
  if (first === n) return [];
  const sub = (m: number, lo: number, hi: number, complete: boolean): Hash[] => {
    const size = hi - lo;
    if (m === size) return complete ? [] : [treeHash(leafHashes.slice(lo, hi))];
    const k = splitPoint(size);
    return m <= k
      ? [...sub(m, lo, lo + k, complete), treeHash(leafHashes.slice(lo + k, hi))]
      : [...sub(m - k, lo + k, hi, false), treeHash(leafHashes.slice(lo, lo + k))];
  };
  return sub(first, 0, n, true);
}

function sameHash(a: Hash, b: Hash): boolean {
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/** RFC 9162 2.1.3.2. Returns false (never throws) for any malformed or mismatching input. */
export function verifyInclusion(leafHash: Hash, leafIndex: number, treeSize: number, path: readonly Hash[], rootHash: Hash): boolean {
  try {
    assertHashes([leafHash, rootHash, ...path]);
    if (![leafIndex, treeSize].every(Number.isSafeInteger) || leafIndex < 0 || leafIndex >= treeSize) return false;
    let fn = leafIndex;
    let sn = treeSize - 1;
    let r = leafHash;
    for (const p of path) {
      if (sn === 0) return false;
      if (fn % 2 === 1 || fn === sn) {
        r = hashChildren(p, r);
        if (fn % 2 === 0) {
          while (fn % 2 === 0 && fn !== 0) {
            fn = Math.floor(fn / 2);
            sn = Math.floor(sn / 2);
          }
        }
      } else {
        r = hashChildren(r, p);
      }
      fn = Math.floor(fn / 2);
      sn = Math.floor(sn / 2);
    }
    return sn === 0 && sameHash(r, rootHash);
  } catch {
    return false;
  }
}

/** RFC 9162 2.1.4.2. Requires 0 < first < second. Returns false (never throws) on any failure. */
export function verifyConsistency(
  first: number,
  second: number,
  firstHash: Hash,
  secondHash: Hash,
  path: readonly Hash[],
): boolean {
  try {
    assertHashes([firstHash, secondHash, ...path]);
    if (![first, second].every(Number.isSafeInteger) || first < 1 || first >= second) return false;
    const proof = [...path];
    if (proof.length === 0) return false;
    if ((first & (first - 1)) === 0) proof.unshift(firstHash); // first is a power of two
    let fn = first - 1;
    let sn = second - 1;
    while (fn % 2 === 1) {
      fn = Math.floor(fn / 2);
      sn = Math.floor(sn / 2);
    }
    let fr = proof[0];
    let sr = proof[0];
    for (const c of proof.slice(1)) {
      if (sn === 0) return false;
      if (fn % 2 === 1 || fn === sn) {
        fr = hashChildren(c, fr);
        sr = hashChildren(c, sr);
        if (fn % 2 === 0) {
          while (fn % 2 === 0 && fn !== 0) {
            fn = Math.floor(fn / 2);
            sn = Math.floor(sn / 2);
          }
        }
      } else {
        sr = hashChildren(sr, c);
      }
      fn = Math.floor(fn / 2);
      sn = Math.floor(sn / 2);
    }
    return sn === 0 && sameHash(fr, firstHash) && sameHash(sr, secondHash);
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Receipt chain binding
// ---------------------------------------------------------------------------

/** Leaf input for a receipt: the UTF-8 bytes of its canonicalJson (covers every field, including merkle_root). */
export function receiptLeafData(receipt: OperationalReceipt): Buffer {
  return Buffer.from(canonicalJson(receipt), "utf8");
}

export function receiptLeafHashes(chain: readonly OperationalReceipt[]): Hash[] {
  return chain.map((r) => hashLeaf(receiptLeafData(r)));
}

export interface TreeHead {
  readonly size: number;
  readonly rootHash: string; // hex
}

export function chainTreeHead(chain: readonly OperationalReceipt[]): TreeHead {
  return { size: chain.length, rootHash: treeHash(receiptLeafHashes(chain)).toString("hex") };
}
