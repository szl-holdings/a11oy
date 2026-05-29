import { describe, it, expect } from "vitest";
import { admit, type SparseAttentionEnvelope, type AdmissionPolicy } from "../envelope.js";
import { jaccard, probe } from "../contradiction-probe.js";
import { scoreIndex, topKCommit, executeSparse } from "../two-level-commit.js";
import { recordedRouter } from "../recorded-router.js";
import { recordIo } from "../io-budget.js";
import { isSparseReceiptClass, RECEIPT_CLASSES } from "../receipts.js";

const baseEnv: SparseAttentionEnvelope = {
  regimeId: "regime-1",
  tenantClass: "operator",
  maxBlocks: 8,
  maxHopDepth: 4,
  minIndexAgreement: 0.7,
  blockSizeTokens: 64,
  ioBudgetBytes: 1024 * 1024,
  ttlSeconds: 60,
  freshnessNonce: "nonce-1",
  issuedAt: "2026-05-27T00:00:00Z",
};

const policy: AdmissionPolicy = {
  maxBlockSizeTokens: 128,
  maxHopDepth: 8,
  minIndexAgreement: 0.5,
  maxTtlSeconds: 300,
  permittedTenantClasses: ["operator", "reviewer"],
};

describe("envelope.admit", () => {
  it("admits a well-formed regime", () => {
    const r = admit({ proposed: baseEnv, policy, tenant: "t1" });
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.receipt.receiptClass).toBe("sparse.regime.admitted.v1");
  });
  it("rejects an unpermitted tenant class", () => {
    const r = admit({ proposed: { ...baseEnv, tenantClass: "control-plane" }, policy, tenant: "t1" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.receipt.violatedRule).toBe("tenant-not-permitted");
  });
  it("rejects an oversized block", () => {
    const r = admit({ proposed: { ...baseEnv, blockSizeTokens: 999 }, policy, tenant: "t1" });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.receipt.violatedRule).toBe("block-size-too-large");
  });
});

describe("contradiction-probe", () => {
  it("jaccard returns 1 on identical sets", () => {
    expect(jaccard([1, 2, 3], [3, 2, 1])).toBe(1);
  });
  it("jaccard returns 0 on disjoint sets", () => {
    expect(jaccard([1, 2], [3, 4])).toBe(0);
  });
  it("probe passes on full agreement", () => {
    const r = probe({ envelope: baseEnv, indexBlocks: [1, 2, 3], sparseBlocks: [1, 2, 3], tenant: "t", nonce: "n" });
    expect(r.contradicted).toBe(false);
  });
  it("probe emits contradiction + escalation below threshold", () => {
    const r = probe({ envelope: baseEnv, indexBlocks: [1, 2, 3], sparseBlocks: [9, 8, 7], tenant: "t", nonce: "n" });
    expect(r.contradicted).toBe(true);
    if (r.contradicted) {
      expect(r.contradiction.receiptClass).toBe("sparse.contradiction.v1");
      expect(r.escalation.receiptClass).toBe("sparse.escalated.v1");
      expect(r.escalation.toMode).toBe("full");
    }
  });
});

describe("two-level-commit", () => {
  it("scoreIndex sorts candidates descending", () => {
    const r = scoreIndex({
      regimeRef: "r",
      tenant: "t",
      nonce: "n",
      candidates: [
        { blockId: 1, score: 0.1 },
        { blockId: 2, score: 0.9 },
      ],
    });
    expect(r.eligibleBlocks[0].blockId).toBe(2);
  });
  it("topKCommit fails closed when budget exceeds eligible", () => {
    const idx = scoreIndex({
      regimeRef: "r",
      tenant: "t",
      nonce: "n1",
      candidates: [{ blockId: 1, score: 1 }],
    });
    const c = topKCommit({ regimeRef: "r", indexReceipt: idx, budgetK: 5, tenant: "t", nonce: "n2" });
    expect(c.ok).toBe(false);
    if (!c.ok) expect(c.receipt.receiptClass).toBe("sparse.budget.exhausted.v1");
  });
  it("executeSparse chains to commit", () => {
    const idx = scoreIndex({
      regimeRef: "r",
      tenant: "t",
      nonce: "n1",
      candidates: [
        { blockId: 1, score: 0.9 },
        { blockId: 2, score: 0.8 },
      ],
    });
    const c = topKCommit({ regimeRef: "r", indexReceipt: idx, budgetK: 2, tenant: "t", nonce: "n2" });
    expect(c.ok).toBe(true);
    if (!c.ok) return;
    const e = executeSparse({ regimeRef: "r", commitReceipt: c.receipt, attendedBlocks: [1, 2], tenant: "t", nonce: "n3" });
    expect(e.receiptClass).toBe("sparse.execute.v1");
    expect(e.attendedBlocks).toEqual([1, 2]);
  });
});

describe("recorded-router", () => {
  it("emits trace receipt and flags envelope breach", () => {
    const rr = recordedRouter({
      routerRef: "router-1",
      envelope: { ...baseEnv, maxBlocks: 2 },
      tenant: "t",
      select: () => ({ blocksSelected: [1, 2, 3, 4], scoreDistribution: [0.4, 0.3, 0.2, 0.1] }),
    });
    const out = rr.route("q-1", "nonce");
    expect(out.trace.receiptClass).toBe("sparse.router.trace.v1");
    expect(out.envelopeBreach).toBe(true);
  });
});

describe("io-budget", () => {
  it("records within-budget execution", () => {
    const r = recordIo({
      regimeRef: "r",
      executeReceiptRef: "e",
      ioBudgetBytes: 1000,
      ioConsumedBytes: 500,
      tenant: "t",
      nonce: "n",
    });
    expect(r.overrun).toBe(false);
    if (!r.overrun) expect(r.receipt.receiptClass).toBe("sparse.io.budget.v1");
  });
  it("flags overrun with ratio", () => {
    const r = recordIo({
      regimeRef: "r",
      executeReceiptRef: "e",
      ioBudgetBytes: 1000,
      ioConsumedBytes: 1500,
      tenant: "t",
      nonce: "n",
    });
    expect(r.overrun).toBe(true);
    if (r.overrun) expect(r.receipt.overrunRatio).toBeCloseTo(1.5);
  });
});

describe("receipts", () => {
  it("isSparseReceiptClass guard works", () => {
    expect(isSparseReceiptClass("sparse.execute.v1")).toBe(true);
    expect(isSparseReceiptClass("foo")).toBe(false);
  });
  it("RECEIPT_CLASSES has the 12 documented classes", () => {
    expect(RECEIPT_CLASSES.length).toBe(12);
  });
});
