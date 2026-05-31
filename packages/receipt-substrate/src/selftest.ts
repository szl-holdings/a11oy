#!/usr/bin/env node
// Copyright 2026 SZL Holdings
// SPDX-License-Identifier: Apache-2.0
//
// selftest.ts — in-process boot self-test for the receipt-substrate CLI image.
//
// The a11oy container is a CLI image, not a long-running network service, so
// it has no HTTP readiness probe. Without a self-test, a built image can ship
// with a broken or partially-copied dist/ and still "start" (the entrypoint
// prints --help and exits 0), giving a misleading green signal.
//
// This self-test exercises the real receipt path end to end against an
// ephemeral temp file: it emits a genesis receipt, appends a second receipt,
// reads the chain back from disk, and verifies the hash chain. It writes
// solely to a unique temp file under the OS temp dir, makes no network calls,
// and cleans up after itself. A non-zero exit means the bundled substrate is
// not functional in this image.
//
// Authored for SZL Holdings. Signed-off per repository DCO.

import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  appendReceiptJsonl,
  createToolEnvelope,
  emitReceipt,
  readReceiptJsonl,
  verifyChain,
  type OperationalReceipt,
} from "./index.ts";

interface SelfTestResult {
  ok: boolean;
  checks: { name: string; ok: boolean; detail?: string }[];
}

/**
 * Run the receipt-substrate boot self-test.
 *
 * Returns a structured result. Does not throw on a failed check; instead each
 * failure is recorded so the caller can report all problems at once.
 */
export function runSelfTest(): SelfTestResult {
  const checks: SelfTestResult["checks"] = [];
  const record = (name: string, ok: boolean, detail?: string) => {
    checks.push({ name, ok, detail });
  };

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "a11oy-selftest-"));
  const out = path.join(dir, "selftest-receipts.jsonl");

  const policy = {
    algorithm: "SHA3-256" as const,
    chaining: "hash_chain" as const,
    quorum: "1-of-1",
    nodes: ["selftest-node"],
  };

  const mkEnvelope = (seq: number) =>
    createToolEnvelope({
      protocol: "mcp",
      actor_id: "did:example:selftest",
      tool_name: "receipted_retrieval",
      lambda_axes: ["Λ7"],
      payload: { selftest: true, seq },
      metadata: { source: "a11oy-receipt-substrate-selftest" },
    });

  try {
    // 1. Emit a genesis receipt and persist it.
    const genesis = emitReceipt(mkEnvelope(0), { policy });
    appendReceiptJsonl(out, genesis);
    record("emit-genesis", true);

    // 2. Append a second receipt chained to the genesis.
    const second = emitReceipt(mkEnvelope(1), { previousReceipt: genesis, policy });
    appendReceiptJsonl(out, second);
    record("append-chained", true);

    // 3. Read the chain back from disk (round-trip through JSONL).
    const chain: OperationalReceipt[] = readReceiptJsonl(out);
    const readBackOk = chain.length === 2;
    record("read-back", readBackOk, readBackOk ? undefined : `expected 2 receipts, found ${chain.length}`);

    // 4. Verify the hash chain.
    const verification = verifyChain(chain, { quorum: "1-of-1", nodes: ["selftest-node"] });
    record(
      "verify-chain",
      verification.valid,
      verification.valid ? undefined : verification.errors.join("; "),
    );

    // 5. Negative control: a tampered chain must fail verification. This
    //    guards against a verifier that always returns valid.
    const tampered: OperationalReceipt[] = [
      { ...chain[0] },
      { ...chain[1], merkle_root: "0".repeat(chain[1].merkle_root.length) },
    ];
    const tamperedResult = verifyChain(tampered, { quorum: "1-of-1", nodes: ["selftest-node"] });
    record(
      "reject-tampered",
      tamperedResult.valid === false,
      tamperedResult.valid ? "tampered chain was incorrectly accepted" : undefined,
    );
  } catch (error) {
    record("unexpected-error", false, (error as Error).message);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }

  return { ok: checks.every((c) => c.ok), checks };
}

function main(): void {
  const result = runSelfTest();
  for (const c of result.checks) {
    const icon = c.ok ? "ok  " : "FAIL";
    const detail = c.detail ? `  (${c.detail})` : "";
    console.log(`  [${icon}] ${c.name}${detail}`);
  }
  if (result.ok) {
    console.log("a11oy receipt-substrate self-test: PASS");
    process.exit(0);
  }
  console.error("a11oy receipt-substrate self-test: FAIL");
  process.exit(1);
}

// Run when invoked directly (node src/selftest.ts), not when imported.
const invokedDirectly =
  process.argv[1] !== undefined && path.resolve(process.argv[1]).endsWith("selftest.ts");
if (invokedDirectly) {
  main();
}
