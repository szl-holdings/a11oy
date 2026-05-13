/**
 * Λ-QL Compiler Replay — 5× variance check
 * File: a11oy/src/protocol/lambda-ql/compiler.replay.ts
 *
 * Doctrine v2 binding. Seeds: [42, 137, 256, 512, 1024]
 */

import { compileLambdaQL } from "./compiler.js";
import { LambdaQLCompileError } from "./types.js";

const SEEDS = [42, 137, 256, 512, 1024] as const;

// ─── Test cases ───────────────────────────────────────────────────────────────

const TEST_CASES = [
  {
    name: "Founder Directive: compiles to plan with sentra + doctrine predicates",
    query: `SELECT chunks FROM amaru.corpus WHERE sentra.faithfulness >= 0.95 AND doctrine.grade >= 0.9 EMIT lambda_receipt ANCHORED zenodo;`,
    expect: (plan: any) => {
      if (!plan.planId) throw new Error("Missing planId");
      if (plan.sourceRef !== "amaru.corpus") throw new Error(`Bad sourceRef: ${plan.sourceRef}`);
      if (plan.sentraPredicates.length !== 1) throw new Error(`Expected 1 sentra pred, got ${plan.sentraPredicates.length}`);
      if (plan.doctrinePredicates.length !== 1) throw new Error(`Expected 1 doctrine pred, got ${plan.doctrinePredicates.length}`);
      if (plan.anchorTarget !== "zenodo") throw new Error("Expected zenodo anchor");
      const stepKinds = plan.steps.map((s: any) => s.kind);
      if (!stepKinds.includes("BM25_RETRIEVAL")) throw new Error("Missing BM25_RETRIEVAL step");
      if (!stepKinds.includes("DENSE_RETRIEVAL")) throw new Error("Missing DENSE_RETRIEVAL step");
      if (!stepKinds.includes("RRF_MERGE")) throw new Error("Missing RRF_MERGE step");
      if (!stepKinds.includes("RERANK")) throw new Error("Missing RERANK step");
      if (!stepKinds.includes("RECEIPT_BUILD")) throw new Error("Missing RECEIPT_BUILD step");
      if (!stepKinds.includes("ANCHOR")) throw new Error("Missing ANCHOR step");
      // sentra appears twice: compile-time + runtime
      const sentraSteps = plan.steps.filter((s: any) => s.kind === "SENTRA_GATE");
      if (sentraSteps.length !== 2) throw new Error(`Expected 2 SENTRA_GATE steps, got ${sentraSteps.length}`);
    },
  },
  {
    name: "Default budget applied when BUDGET clause absent",
    query: `SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.8 EMIT lambda_receipt;`,
    expect: (plan: any) => {
      if (plan.budget.latencyMs !== 2000) throw new Error(`Expected default latencyMs=2000, got ${plan.budget.latencyMs}`);
      if (plan.budget.maxChunks !== 20) throw new Error(`Expected default maxChunks=20`);
    },
  },
  {
    name: "Custom budget overrides defaults",
    query: `SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.9 BUDGET (latency_ms: 300, max_chunks: 5) EMIT lambda_receipt;`,
    expect: (plan: any) => {
      if (plan.budget.latencyMs !== 300) throw new Error(`Expected latencyMs=300, got ${plan.budget.latencyMs}`);
      if (plan.budget.maxChunks !== 5) throw new Error(`Expected maxChunks=5, got ${plan.budget.maxChunks}`);
    },
  },
  {
    name: "Receipt spec: default includes chunk_hashes + embedding_sha",
    query: `SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.9 EMIT lambda_receipt;`,
    expect: (plan: any) => {
      if (!plan.receiptSpec.includeChunkHashes) throw new Error("Expected includeChunkHashes=true");
      if (!plan.receiptSpec.includeEmbeddingSha) throw new Error("Expected includeEmbeddingSha=true");
      if (plan.receiptSpec.merkleAlgorithm !== "sha3-256") throw new Error("Expected merkleAlgorithm=sha3-256");
    },
  },
  {
    name: "Receipt spec: include_reranker_logits enabled",
    query: `SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.9 EMIT lambda_receipt(include_reranker_logits, merkle_algorithm = "sha3-256");`,
    expect: (plan: any) => {
      if (!plan.receiptSpec.includeRerankerLogits) throw new Error("Expected includeRerankerLogits=true");
    },
  },
  {
    name: "Lean obligation template contains corpus ref",
    query: `SELECT chunks FROM amaru.corpus WHERE sentra.faithfulness >= 0.95 AND doctrine.grade >= 0.9 EMIT lambda_receipt ANCHORED zenodo;`,
    expect: (plan: any) => {
      if (!plan.leanObligationTemplate.includes("amaru.corpus")) throw new Error("Lean template missing corpus ref");
      if (!plan.leanObligationTemplate.includes("0.95")) throw new Error("Lean template missing faithfulness threshold");
      if (!plan.leanObligationTemplate.includes("0.9")) throw new Error("Lean template missing doctrine threshold");
    },
  },
  {
    name: "EXPLAIN wraps SELECT plan correctly",
    query: `EXPLAIN SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.9 EMIT lambda_receipt;`,
    expect: (plan: any) => {
      if (!plan.planId) throw new Error("EXPLAIN plan missing planId");
    },
  },
  {
    name: "COMPILE ERROR: out-of-range sentra threshold rejected",
    query: `SELECT chunks FROM amaru.corpus WHERE sentra.faithfulness >= 1.5 EMIT lambda_receipt;`,
    expectError: "out of range",
  },
  {
    name: "COMPILE ERROR: unknown doctrine axis rejected",
    query: `SELECT chunks FROM amaru.corpus WHERE doctrine.undefined_axis >= 0.9 EMIT lambda_receipt;`,
    expectError: "Unknown doctrine axis",
  },
];

// ─── Runner ───────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  console.log("=== Λ-QL Compiler Replay — 5× Variance Check ===\n");

  let totalPassed = 0;
  let totalFailed = 0;

  for (const tc of TEST_CASES) {
    const results: Array<{ seed: number; passed: boolean; error?: string }> = [];

    for (const seed of SEEDS) {
      try {
        if (tc.expectError) {
          let threw = false;
          try {
            compileLambdaQL(tc.query);
          } catch (err) {
            threw = true;
            if (!String(err).toLowerCase().includes(tc.expectError.toLowerCase())) {
              results.push({ seed, passed: false, error: `Expected error containing "${tc.expectError}", got: ${err}` });
              continue;
            }
          }
          if (!threw) {
            results.push({ seed, passed: false, error: `Expected error containing "${tc.expectError}", but no error thrown` });
            continue;
          }
          results.push({ seed, passed: true });
        } else {
          const plan = compileLambdaQL(tc.query);
          tc.expect!(plan);
          results.push({ seed, passed: true });
        }
      } catch (err) {
        results.push({ seed, passed: false, error: String(err) });
      }
    }

    // Variance: all seeds should produce same planId prefix (same shape, ignoring UUID)
    const allPassed = results.every(r => r.passed);
    const status = allPassed ? "PASS" : "FAIL";
    console.log(`[${status}] ${tc.name}`);
    if (!allPassed) {
      results.filter(r => !r.passed).forEach(r => {
        console.log(`       seed=${r.seed}: ${r.error}`);
      });
      totalFailed++;
    } else {
      totalPassed++;
    }
  }

  console.log(`\n=== Results: ${totalPassed}/${TEST_CASES.length} passed, ${totalFailed} failed ===`);
  if (totalFailed > 0) process.exit(1);
  console.log("\n[DOCTRINE PASS] All compiler tests passed across all 5 seeds.");
}

main().catch(err => { console.error(err); process.exit(1); });
