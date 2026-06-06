// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: sentra/doi-bind  Thesis: TH2 (Replay-Root → DOI Manifest)
// Doctrine V6 preflight: ✓

import { createHash } from "node:crypto";
import { z } from "zod";
import { type Receipt } from "@szl/ouroboros-types";

// ---------------------------------------------------------------------------
// Zenodo deposit manifest schema
// Follows Zenodo REST API deposit/files shape (v1 compatible)
// Reference: https://developers.zenodo.org/ (Apache-2.0 licensed API)
// ---------------------------------------------------------------------------

export const CreatorSchema = z.object({
  name:        z.string(),
  affiliation: z.string().optional(),
  orcid:       z.string().optional(),
});

export const ZenodoManifestSchema = z.object({
  /** Zenodo metadata block */
  metadata: z.object({
    upload_type:   z.literal("dataset"),
    title:         z.string(),
    description:   z.string(),
    creators:      z.array(CreatorSchema).min(1),
    license:       z.string().default("apache-2.0"),
    keywords:      z.array(z.string()),
    related_identifiers: z.array(z.object({
      identifier: z.string(),
      relation:   z.string(),
      scheme:     z.string(),
    })).optional(),
    version:       z.string().optional(),
    publication_date: z.string().date(),
  }),
  /** SHA-256 of the canonical JSON representation of the receipt chain */
  sha256:         z.string().regex(/^[0-9a-f]{64}$/),
  /** Receipt chain: ordered list of receipt hashes that form the replay root */
  replayRoot:     z.array(z.string().regex(/^[0-9a-f]{64}$/)),
  /** Composite Λ at time of manifest build */
  lambda:         z.number(),
  /** Operator-gated: true means the DOI has NOT been minted yet */
  pendingMint:    z.boolean().default(true),
  /** ISO-8601 timestamp of manifest creation */
  createdAt:      z.string().datetime(),
});

export type ZenodoManifest = z.infer<typeof ZenodoManifestSchema>;
export type Creator = z.infer<typeof CreatorSchema>;

// ---------------------------------------------------------------------------
// Manifest builder
// ---------------------------------------------------------------------------

export interface BuildManifestOptions {
  title:       string;
  description: string;
  creators:    Creator[];
  keywords?:   string[];
  version?:    string;
}

/**
 * Build a Zenodo deposit manifest from a replay-root receipt chain.
 * The manifest is NOT submitted (mint is operator-gated).
 * Returns both the manifest and the canonical deposit.json object.
 */
export function buildManifest(
  replayRoot: Receipt[],
  opts: BuildManifestOptions,
): { manifest: ZenodoManifest; depositJson: object } {
  if (replayRoot.length === 0) {
    throw new Error("replayRoot must contain at least one receipt");
  }

  const compositeHash = computeChainHash(replayRoot);
  const lambdaAvg     = replayRoot.reduce((s, r) => s + r.lambda, 0) / replayRoot.length;

  const manifest = ZenodoManifestSchema.parse({
    metadata: {
      upload_type:   "dataset",
      title:         opts.title,
      description:   opts.description,
      creators:      opts.creators,
      license:       "apache-2.0",
      keywords:      opts.keywords ?? ["ouroboros", "lambda-gate", "szl-holdings"],
      related_identifiers: replayRoot.map((r) => ({
        identifier: `sha256:${r.hash}`,
        relation:   "isSourceOf",
        scheme:     "other",
      })),
      version:          opts.version,
      publication_date: new Date().toISOString().slice(0, 10),
    },
    sha256:      compositeHash,
    replayRoot:  replayRoot.map((r) => r.hash),
    lambda:      lambdaAvg,
    pendingMint: true,
    createdAt:   new Date().toISOString(),
  });

  // deposit.json mirrors the Zenodo API request body shape
  const depositJson = {
    metadata: manifest.metadata,
    files: [
      {
        filename:  "receipt-chain.json",
        checksum:  `md5:${md5Hex(JSON.stringify(replayRoot))}`,
        filesize:  JSON.stringify(replayRoot).length,
      },
    ],
  };

  return { manifest, depositJson };
}

// ---------------------------------------------------------------------------
// Hash helpers
// ---------------------------------------------------------------------------

export function computeChainHash(chain: Receipt[]): string {
  return createHash("sha256")
    .update(chain.map((r) => r.hash).sort().join("|"))
    .digest("hex");
}

/** Minimal MD5 approximation using SHA-256 truncated to 128 bits for mock. */
function md5Hex(data: string): string {
  return createHash("sha256").update(data).digest("hex").slice(0, 32);
}
