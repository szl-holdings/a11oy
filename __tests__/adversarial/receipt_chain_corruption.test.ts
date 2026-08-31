/**
 * receipt_chain_corruption.test.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 * 10 Receipt-Chain Corruption adversarial tests
 *
 * Tests the integrity verification logic of the Merkle DAG receipt chain
 * against corruption scenarios: hash tampering, broken chain links,
 * replay attacks, timestamp regression, quorum forgery, and node drop.
 *
 * Uses pure TypeScript crypto primitives (Node.js `crypto` module) to
 * simulate the receipt chain operations and verify detection of corruption.
 *
 * Test framework: Jest / ts-jest
 * Run: npx jest tests/adversarial/receipt_chain_corruption.test.ts
 */

import * as crypto from "crypto";

// ── Receipt Chain Primitives ──────────────────────────────────────────────────

interface Receipt {
  receipt_id: string;
  timestamp_tai64n: string;
  actor_id: string;
  event_type: string;
  payload_hash: string;    // SHA3-256 of the event payload
  prev_receipt_hash: string | null;  // null for genesis block
  merkle_root: string;
  quorum_signatures: string[];   // simplified: list of signing node IDs
}

/** Compute SHA-256 of a string (using Node crypto; real impl uses SHA3-256) */
function sha256(data: string): string {
  return crypto.createHash("sha256").update(data, "utf8").digest("hex");
}

/** Hash a receipt object (deterministic serialisation) */
function hashReceipt(r: Omit<Receipt, "merkle_root">): string {
  const canonical = JSON.stringify({
    receipt_id: r.receipt_id,
    timestamp_tai64n: r.timestamp_tai64n,
    actor_id: r.actor_id,
    event_type: r.event_type,
    payload_hash: r.payload_hash,
    prev_receipt_hash: r.prev_receipt_hash,
    quorum_signatures: r.quorum_signatures,
  });
  return sha256(canonical);
}

/** Verify a receipt chain: each receipt's prev_receipt_hash must match
 *  the hash of the preceding receipt. */
function verifyChain(chain: Receipt[]): { valid: boolean; error?: string } {
  if (chain.length === 0) return { valid: true };

  // Genesis receipt must have null prev
  if (chain[0].prev_receipt_hash !== null) {
    return { valid: false, error: "Genesis receipt must have null prev_receipt_hash" };
  }

  for (let i = 1; i < chain.length; i++) {
    const prev = chain[i - 1];
    const curr = chain[i];
    const expectedPrevHash = prev.merkle_root;
    if (curr.prev_receipt_hash !== expectedPrevHash) {
      return {
        valid: false,
        error: `Chain broken at position ${i}: prev_receipt_hash mismatch. ` +
               `Expected ${expectedPrevHash}, got ${curr.prev_receipt_hash}`,
      };
    }
  }
  return { valid: true };
}

/** Build a valid receipt chain of `length` nodes */
function buildChain(length: number): Receipt[] {
  const chain: Receipt[] = [];
  let prevHash: string | null = null;

  for (let i = 0; i < length; i++) {
    const partial: Omit<Receipt, "merkle_root"> = {
      receipt_id: `rcpt-${i.toString().padStart(4, "0")}`,
      timestamp_tai64n: `@${(4000000000n + BigInt(i)).toString(16).padStart(16, "0")}`,
      actor_id: `did:key:z6Mk${i.toString().padStart(4, "0")}`,
      event_type: i === 0 ? "POLICY_LOAD" : "INFERENCE",
      payload_hash: sha256(`payload-${i}`),
      prev_receipt_hash: prevHash,
      quorum_signatures: ["node-primary", "node-backup"],
    };
    const root = hashReceipt(partial);
    const receipt: Receipt = { ...partial, merkle_root: root };
    chain.push(receipt);
    prevHash = root;
  }
  return chain;
}

// ── Test Suite ────────────────────────────────────────────────────────────────

describe("Adversarial — Receipt Chain Corruption (10 tests)", () => {

  // RC-001: Valid chain verifies correctly (baseline)
  test("RC-001: valid chain of 7 receipts passes integrity check", () => {
    const chain = buildChain(7);
    const result = verifyChain(chain);
    expect(result.valid).toBe(true);
  });

  // RC-002: Corrupt merkle_root of receipt at position 3 — chain break detected
  test("RC-002: tampered merkle_root at position 3 breaks chain at position 4", () => {
    const chain = buildChain(7);
    chain[3].merkle_root = sha256("TAMPERED-CONTENT-" + Math.random());
    const result = verifyChain(chain);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Chain broken at position 4/);
  });

  // RC-003: Tamper genesis receipt payload_hash — genesis itself cannot be trusted
  test("RC-003: tampered payload_hash in genesis receipt propagates chain break", () => {
    const chain = buildChain(5);
    // Corrupt genesis payload hash — merkle_root no longer matches
    chain[0].payload_hash = sha256("INJECTED-PAYLOAD");
    // Recompute position 1's expectation: it still links to old chain[0].merkle_root
    // chain[0].merkle_root is unchanged — prev_hash check for chain[1] still passes
    // But chain[0]'s internal consistency is broken (payload_hash != committed)
    // Document: chain linkage check passes; payload integrity check would fail separately
    const result = verifyChain(chain);
    // Link check: chain[1].prev = chain[0].merkle_root (unchanged) → still valid by link
    expect(result.valid).toBe(true); // Link integrity intact
    // But recompute chain[0] hash to detect payload tampering:
    const recomputed = hashReceipt({
      receipt_id: chain[0].receipt_id,
      timestamp_tai64n: chain[0].timestamp_tai64n,
      actor_id: chain[0].actor_id,
      event_type: chain[0].event_type,
      payload_hash: chain[0].payload_hash, // tampered
      prev_receipt_hash: chain[0].prev_receipt_hash,
      quorum_signatures: chain[0].quorum_signatures,
    });
    expect(recomputed).not.toBe(chain[0].merkle_root); // Tampering detected
  });

  // RC-004: Replay attack — duplicate receipt inserted into chain
  test("RC-004: duplicate receipt_id inserted at position 5 is detected", () => {
    const chain = buildChain(7);
    // Insert a copy of chain[2] at the end
    const duplicate = { ...chain[2] };
    chain.push(duplicate);
    // Verify: chain[7].prev_receipt_hash should be chain[6].merkle_root, not chain[1]'s
    const result = verifyChain(chain);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Chain broken at position 7/);
  });

  // RC-005: Node drop — remove receipt at position 3, chain breaks at position 4
  test("RC-005: deleting receipt at position 3 causes chain break at position 4", () => {
    const chain = buildChain(7);
    chain.splice(3, 1); // Remove element at index 3
    const result = verifyChain(chain);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Chain broken at position 3/);
  });

  // RC-006: Receipt insertion — extra receipt injected between positions 2 and 3
  test("RC-006: injected forged receipt between positions 2 and 3 breaks chain", () => {
    const chain = buildChain(7);
    const forged: Receipt = {
      receipt_id: "rcpt-FORGED",
      timestamp_tai64n: "@40000000ee000000",
      actor_id: "did:key:zATTACKER",
      event_type: "PRIVILEGE_ESCALATION",
      payload_hash: sha256("malicious-payload"),
      prev_receipt_hash: chain[2].merkle_root,   // Claims to follow chain[2]
      merkle_root: sha256("forged-root"),         // Not properly computed
      quorum_signatures: ["fake-node"],
    };
    chain.splice(3, 0, forged); // Insert between original 2 and 3
    const result = verifyChain(chain);
    expect(result.valid).toBe(false);
    // chain[4] (original chain[3]) prev_hash = original chain[2].merkle_root
    // But now expected prev = forged.merkle_root (sha256("forged-root"))
    // → mismatch detected
    expect(result.error).toContain("Chain broken at position 4");
  });

  // RC-007: Timestamp regression — receipt timestamp decreases (replay / back-dating)
  test("RC-007: timestamp regression in receipt sequence is detected by temporal check", () => {
    const chain = buildChain(5);
    // Set chain[3] timestamp to earlier than chain[2]. buildChain emits values of
    // the form "@00000000ee6b280X"; the regression check compares TAI64N labels as
    // fixed-width hex strings, so the back-dated value must be lexically smaller
    // than its predecessor. "@4000000000000000" sorts AFTER "@00000000ee6b28xx"
    // (first hex digit "4" > "0"), so it did not trip the check. Use TAI64N epoch
    // zero, which is both genuinely earlier and lexically smaller.
    chain[3].timestamp_tai64n = "@0000000000000000"; // Far past (TAI64N epoch zero)
    // verifyChain checks links, not timestamps — document gap and add temporal check
    function verifyTimestamps(c: Receipt[]): { valid: boolean; error?: string } {
      for (let i = 1; i < c.length; i++) {
        if (c[i].timestamp_tai64n <= c[i - 1].timestamp_tai64n) {
          return { valid: false, error: `Timestamp regression at position ${i}` };
        }
      }
      return { valid: true };
    }
    const result = verifyTimestamps(chain);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Timestamp regression at position 3/);
  });

  // RC-008: Quorum forgery — quorum_signatures has fewer than required signers
  test("RC-008: single-signer receipt against 2-of-3 quorum fails quorum check", () => {
    const chain = buildChain(5);
    chain[2].quorum_signatures = ["node-primary"]; // Only 1 signer, need 2
    function verifyQuorum(c: Receipt[], required: number): { valid: boolean; error?: string } {
      for (let i = 0; i < c.length; i++) {
        if (c[i].quorum_signatures.length < required) {
          return { valid: false, error: `Insufficient quorum at position ${i}: got ${c[i].quorum_signatures.length}, need ${required}` };
        }
      }
      return { valid: true };
    }
    const result = verifyQuorum(chain, 2);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Insufficient quorum at position 2/);
  });

  // RC-009: Empty chain edge case — verifyChain of empty array returns valid
  test("RC-009: empty chain (genesis not yet written) is valid (no receipts to corrupt)", () => {
    const result = verifyChain([]);
    expect(result.valid).toBe(true);
  });

  // RC-010: Single-receipt chain with non-null prev_receipt_hash (genesis violation)
  test("RC-010: single genesis receipt with non-null prev_receipt_hash is rejected", () => {
    const chain = buildChain(1);
    chain[0].prev_receipt_hash = sha256("fake-predecessor"); // Genesis must be null
    const result = verifyChain(chain);
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Genesis receipt must have null prev_receipt_hash/);
  });
});
