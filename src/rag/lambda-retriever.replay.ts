/**
 * Λ-Retriever Replay — 5× variance check
 * File: a11oy/src/rag/lambda-retriever.replay.ts
 *
 * Doctrine v2 binding. Seeds: [42, 137, 256, 512, 1024]
 * Validates: retrieve() + runQuery() emit valid LambdaOmegaLeaf receipts
 */

import { LambdaRetriever, retrieveWithReceipt } from "./lambda-retriever.js";
import { compileLambdaQL } from "../protocol/lambda-ql/compiler.js";

const SEEDS = [42, 137, 256, 512, 1024] as const;

// ─── Test cases ───────────────────────────────────────────────────────────────

async function testNaturalLanguageRetrieve(seed: number): Promise<void> {
  const retriever = new LambdaRetriever({ corpusRef: "amaru.corpus" });
  const query = `What are the key provisions of the sanctions regime? seed=${seed}`;
  const { chunks, leaf, durationMs } = await retriever.retrieve(query, { limit: 5 });

  if (chunks.length === 0) throw new Error("No chunks returned");
  if (!leaf.leaf_id) throw new Error("Missing leaf_id");
  if (!leaf.receipt.receipt_id) throw new Error("Missing receipt_id");
  if (!leaf.receipt.merkle_root) throw new Error("Missing merkle_root");
  if (!leaf.receipt.corpus_snapshot_sha) throw new Error("Missing corpus_snapshot_sha");
  if (!leaf.receipt.embedding_model_sha) throw new Error("Missing embedding_model_sha");
  if (chunks.length > 5) throw new Error(`Expected ≤5 chunks, got ${chunks.length}`);

  // Validate chunk structure
  for (const chunk of chunks) {
    if (!chunk.chunkId) throw new Error("Chunk missing chunkId");
    if (!chunk.content) throw new Error("Chunk missing content");
    if (!chunk.sourceUri) throw new Error("Chunk missing sourceUri");
    if (typeof chunk.bm25Score !== "number") throw new Error("Chunk missing bm25Score");
    if (typeof chunk.denseScore !== "number") throw new Error("Chunk missing denseScore");
  }

  console.log(`    seed=${seed}: ${chunks.length} chunks, leaf=${leaf.leaf_id.slice(0, 8)}…, ${durationMs}ms`);
}

async function testLambdaQLQuery(seed: number): Promise<void> {
  const retriever = new LambdaRetriever();
  const result = await retriever.runQuery(`
    SELECT chunks
    FROM amaru.corpus
    WHERE sentra.faithfulness >= 0.95
      AND doctrine.grade >= 0.9
    LIMIT ${5 + (seed % 5)}
    EMIT lambda_receipt
    ANCHORED zenodo;
  `);

  if (!result.receipt.receipt_id) throw new Error("Missing receipt_id");
  if (!result.receipt.merkle_root) throw new Error("Missing merkle_root");
  if (!result.contextWindow) throw new Error("Missing contextWindow");
  if (!result.plan.planId) throw new Error("Missing planId");
  if (result.plan.sentraPredicates.length === 0) throw new Error("Missing sentra predicates in plan");
  console.log(`    seed=${seed}: planId=${result.plan.planId.slice(0, 8)}…, ${result.chunks.length} chunks, ${result.durationMs}ms`);
}

async function testHybridRetrieverRFF(seed: number): Promise<void> {
  // Validate RRF scores are monotonically decreasing (sorted correctly)
  const { chunks } = await retrieveWithReceipt(
    `test query seed ${seed}`,
    { limit: 10 }
  );
  for (let i = 1; i < chunks.length; i++) {
    const prev = chunks[i - 1].rrfScore ?? 0;
    const curr = chunks[i].rrfScore ?? 0;
    if (prev < curr) {
      throw new Error(`RRF scores not monotonically decreasing at rank ${i}: ${prev} < ${curr}`);
    }
  }
  console.log(`    seed=${seed}: RRF monotonicity OK for ${chunks.length} chunks`);
}

async function testReceiptIntegrity(seed: number): Promise<void> {
  const retriever = new LambdaRetriever();
  const { receipt } = await retriever.runQuery(
    `SELECT chunks FROM amaru.corpus WHERE doctrine.grade >= 0.8 EMIT lambda_receipt;`
  );

  // Receipt schema v0.1 required fields
  if (receipt.receipt_version !== "0.1") throw new Error(`Expected v0.1, got ${receipt.receipt_version}`);
  if (!receipt.timestamp_iso.match(/^\d{4}-\d{2}-\d{2}T/)) throw new Error("Bad timestamp_iso");
  if (!receipt.query_hash) throw new Error("Missing query_hash");
  if (!receipt.corpus_snapshot_sha) throw new Error("Missing corpus_snapshot_sha");
  if (!receipt.context_window_sha) throw new Error("Missing context_window_sha");
  if (!receipt.merkle_root) throw new Error("Missing merkle_root");
  if (!receipt.sentra_attestation) throw new Error("Missing sentra_attestation");
  if (!receipt.doctrine_grade) throw new Error("Missing doctrine_grade");
  if (receipt.doctrine_grade.composite < 0 || receipt.doctrine_grade.composite > 1)
    throw new Error(`doctrine_grade.composite out of range: ${receipt.doctrine_grade.composite}`);

  console.log(`    seed=${seed}: receipt v${receipt.receipt_version} integrity OK, merkle=${receipt.merkle_root.slice(0, 12)}…`);
}

async function testCompilePlanRoundtrip(seed: number): Promise<void> {
  const query = `SELECT chunks, chunks.hash FROM amaru.corpus WHERE sentra.faithfulness >= 0.9 AND doctrine.cleanliness >= 0.85 LIMIT 10 BUDGET (latency_ms: 1000, max_chunks: 10) EMIT lambda_receipt(include_chunk_hashes, include_embedding_sha) ANCHORED zenodo;`;
  const plan = compileLambdaQL(query);

  if (plan.steps.length === 0) throw new Error("Empty plan");
  if (plan.budget.latencyMs !== 1000) throw new Error(`Expected latencyMs=1000, got ${plan.budget.latencyMs}`);
  if (plan.limit !== 10) throw new Error(`Expected limit=10, got ${plan.limit}`);
  if (!plan.receiptSpec.includeChunkHashes) throw new Error("Expected includeChunkHashes");
  if (!plan.receiptSpec.includeEmbeddingSha) throw new Error("Expected includeEmbeddingSha");

  // Execute from plan
  const retriever = new LambdaRetriever();
  const result = await retriever.runQuery(query);
  if (!result.receipt.merkle_root) throw new Error("No merkle_root from executed plan");
  console.log(`    seed=${seed}: compile→execute roundtrip OK, ${plan.steps.length} steps, ${result.chunks.length} chunks`);
}

// ─── Runner ───────────────────────────────────────────────────────────────────

const SUITES = [
  { name: "Natural language retrieve() with receipt", fn: testNaturalLanguageRetrieve },
  { name: "Full Λ-QL query end-to-end", fn: testLambdaQLQuery },
  { name: "RRF score monotonicity", fn: testHybridRetrieverRFF },
  { name: "Receipt integrity (schema v0.1)", fn: testReceiptIntegrity },
  { name: "Compile → execute roundtrip", fn: testCompilePlanRoundtrip },
];

async function main(): Promise<void> {
  console.log("=== Λ-Retriever Replay — 5× Variance Check ===\n");

  let passed = 0;
  let failed = 0;

  for (const suite of SUITES) {
    console.log(`[TEST] ${suite.name}`);
    let suiteFailed = false;
    for (const seed of SEEDS) {
      try {
        await suite.fn(seed);
      } catch (err) {
        console.log(`  [FAIL] seed=${seed}: ${err}`);
        suiteFailed = true;
      }
    }
    if (suiteFailed) { failed++; console.log(`  → FAIL\n`); }
    else             { passed++; console.log(`  → PASS\n`); }
  }

  console.log(`=== Results: ${passed}/${SUITES.length} passed ===`);
  if (failed > 0) process.exit(1);
  console.log("[DOCTRINE PASS] All retriever replay tests passed.");
}

main().catch(err => { console.error(err); process.exit(1); });
