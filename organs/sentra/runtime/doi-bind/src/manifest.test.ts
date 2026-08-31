// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Tests: sentra/doi-bind — TH2

import { describe, it, expect } from "vitest";
import { buildManifest, computeChainHash, ZenodoManifestSchema } from "./manifest.js";
import { parseReceipt, type Axes } from "@szl/ouroboros-types";

const AXES: Axes = {
  moralGrounding:       0.96,
  measurabilityHonesty: 0.96,
  epistemicHumility:    0.92,
  harmAvoidance:        0.91,
  logicalCoherence:     0.93,
  citationIntegrity:    0.91,
  noveltyContribution:  0.91,
  reproducibility:      0.92,
  stakeholderAlignment: 0.91,
};

const R1 = parseReceipt({
  hash:        "a".repeat(64),
  timestamp:   "2026-05-16T00:00:00.000Z",
  lambda:      0.93,
  axes:        AXES,
  payloadRef:  "ipfs://r1",
  doctrineVer: "6",
});

const R2 = parseReceipt({
  hash:        "b".repeat(64),
  timestamp:   "2026-05-16T00:00:00.000Z",
  lambda:      0.91,
  axes:        AXES,
  payloadRef:  "ipfs://r2",
  doctrineVer: "6",
});

const OPTS = {
  title:       "SZL Holdings — Ouroboros Receipt Chain",
  description: "Replay-root receipt chain for DOI minting (TH2)",
  creators:    [
    { name: "Lutar, Stephen P.", orcid: "0009-0001-0110-4173", affiliation: "SZL Holdings" },
  ],
  keywords:    ["ouroboros", "lambda-gate"],
  version:     "1.0.0",
};

describe("buildManifest", () => {
  it("builds a valid manifest from a replay root", () => {
    const { manifest } = buildManifest([R1, R2], OPTS);
    expect(manifest.sha256).toHaveLength(64);
    expect(manifest.replayRoot).toHaveLength(2);
    expect(manifest.pendingMint).toBe(true);
    expect(manifest.metadata.upload_type).toBe("dataset");
  });

  it("computes lambda as mean of chain lambdas", () => {
    const { manifest } = buildManifest([R1, R2], OPTS);
    expect(manifest.lambda).toBeCloseTo((0.93 + 0.91) / 2, 5);
  });

  it("emits related_identifiers for each receipt", () => {
    const { manifest } = buildManifest([R1, R2], OPTS);
    expect(manifest.metadata.related_identifiers).toHaveLength(2);
    expect(manifest.metadata.related_identifiers![0]!.identifier).toContain("sha256:");
  });

  it("throws when replayRoot is empty", () => {
    expect(() => buildManifest([], OPTS)).toThrow(/at least one/);
  });

  it("produces valid Zod-parseable manifest", () => {
    const { manifest } = buildManifest([R1], OPTS);
    expect(() => ZenodoManifestSchema.parse(manifest)).not.toThrow();
  });

  it("depositJson has files array with filename", () => {
    const { depositJson } = buildManifest([R1, R2], OPTS);
    const d = depositJson as { files: { filename: string }[] };
    expect(d.files[0]!.filename).toBe("receipt-chain.json");
  });
});

describe("computeChainHash", () => {
  it("is deterministic regardless of input order", () => {
    const h1 = computeChainHash([R1, R2]);
    const h2 = computeChainHash([R2, R1]);
    expect(h1).toBe(h2);
  });

  it("returns a 64-char hex string", () => {
    expect(computeChainHash([R1])).toHaveLength(64);
  });
});
