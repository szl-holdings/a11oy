// SPDX-License-Identifier: Apache-2.0
// Validate the TypeScript reference verifier against the deterministic vectors.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { tally, OrganVerdict } from "../src/index.js";

const VEC = join(__dirname, "..", "..", "testdata", "vectors.json");

function run(): number {
  const v = JSON.parse(readFileSync(VEC, "utf-8"));
  const pubkeys: Record<string, string> = v.pubkeys;
  let failures = 0;
  for (const c of v.cases) {
    const sigs: (OrganVerdict | null)[] = c.signatures;
    const r = tally(v.action_hash, sigs, pubkeys, v.threshold, v.n);
    const ok = r.decision === c.expect.decision && r.consensusCount === c.expect.consensus_count;
    console.log(`[${ok ? "PASS" : "FAIL"}] ${c.name}: ${r.khipuConsensus} -> ${r.decision}`);
    if (!ok) failures++;
  }
  return failures;
}

const failures = run();
if (failures > 0) {
  console.error(`${failures} TS vector cases failed`);
  process.exit(1);
}
console.log("ALL TYPESCRIPT VECTOR TESTS PASSED");
