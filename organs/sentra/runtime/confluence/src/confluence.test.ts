// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: sentra/confluence — TH5

import { describe, it, expect } from "vitest";
import { mergeReplayPaths, checkDiamondProperty, type ReplayPath } from "./confluence.js";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";

const AXES: Axes = {
  moralGrounding:       0.96,
  measurabilityHonesty: 0.96,
  epistemicHumility:    0.92,
  harmAvoidance:        0.92,
  logicalCoherence:     0.93,
  citationIntegrity:    0.91,
  noveltyContribution:  0.91,
  reproducibility:      0.92,
  stakeholderAlignment: 0.91,
};

// All hashes must match /^[0-9a-f]{64}$/ — only hex chars.
const H_FORK = "f".repeat(64);
const H_A1   = "a".repeat(64);
const H_A2   = "a1".repeat(32);
const H_B1   = "b".repeat(64);
const H_B2   = "b1".repeat(32);
const H_JOIN = "c".repeat(64);

function makeR(hash: string): Receipt {
  return parseReceipt({
    hash,
    timestamp:   "2026-05-16T00:00:00.000Z",
    lambda:      0.93,
    axes:        AXES,
    payloadRef:  `test:${hash.slice(0, 4)}`,
    doctrineVer: "6",
  });
}

const store = new Map<string, Receipt>([
  [H_FORK, makeR(H_FORK)],
  [H_A1,   makeR(H_A1)],
  [H_A2,   makeR(H_A2)],
  [H_B1,   makeR(H_B1)],
  [H_B2,   makeR(H_B2)],
  [H_JOIN, makeR(H_JOIN)],
]);

const lookup = (h: string) => store.get(h);

describe("mergeReplayPaths — divergent, no common ancestor", () => {
  const pathA: ReplayPath = { steps: [H_A1, H_A2], label: "A" };
  const pathB: ReplayPath = { steps: [H_B1, H_B2], label: "B" };

  it("produces a join receipt", async () => {
    const result = await mergeReplayPaths(pathA, pathB, lookup);
    expect(result.joinReceipt.hash).toHaveLength(64);
  });

  it("join receipt has lambda ≥ 0.90", async () => {
    const result = await mergeReplayPaths(pathA, pathB, lookup);
    expect(result.joinReceipt.lambda).toBeGreaterThanOrEqual(0.90);
  });

  it("is deterministic: same paths → same join hash", async () => {
    const r1 = await mergeReplayPaths(pathA, pathB, lookup);
    const r2 = await mergeReplayPaths(pathA, pathB, lookup);
    expect(r1.joinReceipt.hash).toBe(r2.joinReceipt.hash);
  });
});

describe("mergeReplayPaths — paths sharing a common ancestor", () => {
  const shared: ReplayPath = {
    steps: [H_FORK, H_A1, H_A2],
    label: "shared-A",
  };
  const overlap: ReplayPath = {
    steps: [H_FORK, H_B1],
    label: "shared-B",
  };

  it("detects common ancestor and marks confluent", async () => {
    const result = await mergeReplayPaths(shared, overlap, lookup);
    expect(result.confluent).toBe(true);
  });
});

describe("mergeReplayPaths — validation", () => {
  it("throws when path has zero steps", async () => {
    await expect(
      mergeReplayPaths({ steps: [], label: "empty" }, { steps: [H_A1], label: "A" }, lookup),
    ).rejects.toThrow(/at least one step/);
  });
});

describe("checkDiamondProperty", () => {
  it("returns true when paths converge", async () => {
    const pathA: ReplayPath = { steps: [H_FORK, H_A1], label: "A" };
    const pathB: ReplayPath = { steps: [H_FORK, H_B1], label: "B" };
    // Both share H_FORK
    const result = await checkDiamondProperty(H_FORK, pathA, pathB, lookup);
    expect(result).toBe(true);
  });
});
