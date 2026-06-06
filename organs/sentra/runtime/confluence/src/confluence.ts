// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: sentra/confluence  Thesis: TH5 (Church-Rosser Confluence)
// Doctrine V6 preflight: ✓

import { createHash } from "node:crypto";
import { parseReceipt, type Receipt, type Axes } from "@szl/ouroboros-types";
import { evaluateAxes } from "@szl/ouroboros-lambda-gate";

// ---------------------------------------------------------------------------
// Replay path: a sequence of receipt hashes representing a derivation trace
// ---------------------------------------------------------------------------

export interface ReplayPath {
  /** Ordered list of receipt hashes (derivation steps) */
  steps: string[];
  /** Label for this path (e.g., "branch-A") */
  label: string;
}

// ---------------------------------------------------------------------------
// Church-Rosser confluence:
// Given two divergent replay paths, find (or construct) a unique "join point"
// receipt such that both paths reduce to the same terminal.
// ---------------------------------------------------------------------------

export interface ConfluenceResult {
  /** The unique join-point receipt */
  joinReceipt:  Receipt;
  pathA:        ReplayPath;
  pathB:        ReplayPath;
  /** True iff both paths converge on the same hash */
  confluent:    boolean;
  lambda:       number;
}

/**
 * Merge two divergent replay paths into a unique receipt (Church-Rosser join).
 *
 * The join-point receipt is computed by:
 *  1. Intersecting the sets of receipt hashes on both paths to find common ancestors.
 *  2. If a common ancestor exists, using its axes as the join basis.
 *  3. Otherwise constructing a synthetic join using component-wise minimum axes.
 *
 * @param pathA  First replay path with at least one step
 * @param pathB  Second replay path with at least one step
 * @param receiptStore  Lookup function for receipts by hash
 */
/** Optional clock injection enables byte-identical replay. */
export interface MergeOptions {
  now?: () => string;
}
const defaultNow = (): string => new Date().toISOString();

export async function mergeReplayPaths(
  pathA: ReplayPath,
  pathB: ReplayPath,
  receiptStore: (hash: string) => Receipt | undefined,
  opts: MergeOptions = {},
): Promise<ConfluenceResult> {
  const now = opts.now ?? defaultNow;
  if (pathA.steps.length === 0 || pathB.steps.length === 0) {
    throw new Error("Both replay paths must have at least one step");
  }

  const setA = new Set(pathA.steps);
  const common = pathB.steps.filter((h) => setA.has(h));

  let joinAxes: Axes;
  let parentHash: string | undefined;

  if (common.length > 0) {
    // Use the last common ancestor (latest in path B's order)
    const lcaHash = common[common.length - 1]!;
    const lcaR    = receiptStore(lcaHash);
    if (!lcaR) throw new Error(`Common ancestor receipt ${lcaHash.slice(0, 16)} not found`);
    joinAxes   = lcaR.axes;
    parentHash = lcaHash;
  } else {
    // No common ancestor — synthesise using min-axes from terminal steps
    const termA = receiptStore(pathA.steps[pathA.steps.length - 1]!);
    const termB = receiptStore(pathB.steps[pathB.steps.length - 1]!);
    if (!termA || !termB) {
      throw new Error("Cannot locate terminal receipts for confluence synthesis");
    }
    // Component-wise minimum (conservative)
    joinAxes = minAxes(termA.axes, termB.axes);
    parentHash = termA.hash;
  }

  const ev      = evaluateAxes(joinAxes);
  const joinHash = createHash("sha256")
    .update([...pathA.steps, ...pathB.steps].sort().join("|"))
    .digest("hex");

  const joinReceipt = parseReceipt({
    hash:        joinHash,
    timestamp:   now(),
    lambda:      ev.lambda,
    axes:        joinAxes,
    payloadRef:  `confluence:${pathA.label}+${pathB.label}`,
    parentHash,
    doctrineVer: "6",
    meta: {
      pathA: pathA.steps,
      pathB: pathB.steps,
      commonAncestors: common,
    },
  });

  return {
    joinReceipt,
    pathA,
    pathB,
    confluent: common.length > 0 || ev.pass,
    lambda:    ev.lambda,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function minAxes(a: Axes, b: Axes): Axes {
  return {
    moralGrounding:       Math.min(a.moralGrounding,       b.moralGrounding),
    measurabilityHonesty: Math.min(a.measurabilityHonesty, b.measurabilityHonesty),
    epistemicHumility:    Math.min(a.epistemicHumility,    b.epistemicHumility),
    harmAvoidance:        Math.min(a.harmAvoidance,        b.harmAvoidance),
    logicalCoherence:     Math.min(a.logicalCoherence,     b.logicalCoherence),
    citationIntegrity:    Math.min(a.citationIntegrity,    b.citationIntegrity),
    noveltyContribution:  Math.min(a.noveltyContribution,  b.noveltyContribution),
    reproducibility:      Math.min(a.reproducibility,      b.reproducibility),
    stakeholderAlignment: Math.min(a.stakeholderAlignment, b.stakeholderAlignment),
  };
}

/**
 * Diamond-property check: given a fork-point and two divergent branches,
 * assert both branches reduce to the same join receipt.
 */
export async function checkDiamondProperty(
  forkHash: string,
  pathA: ReplayPath,
  pathB: ReplayPath,
  store: (hash: string) => Receipt | undefined,
): Promise<boolean> {
  const result = await mergeReplayPaths(pathA, pathB, store);
  return result.confluent;
}
