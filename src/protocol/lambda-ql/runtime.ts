/**
 * Λ-QL Runtime — Executes a QueryPlan against amaru + sentra + ouroboros
 * File: a11oy/src/protocol/lambda-ql/runtime.ts
 *
 * Doctrine v2 binding. Zero external dependencies in this file.
 *
 * Execution model (phd5_protocol.md §5.3):
 *   QueryPlan → amaru.chunk_store.query() → sentra.gate() →
 *   reranker.score() → ReceiptBuilder → anchor → LambdaOmegaLeaf
 *
 * Stub boundaries: amaru, sentra, ouroboros stubs are marked with
 * [REQUIRES_REPO_CONTEXT] where actual API calls would be made.
 * All stubs return typed data so downstream consumers work correctly.
 */

import type {
  QueryPlan,
  ExecutionResult,
  RetrievedChunk,
  LambdaReceipt,
  LambdaOmegaLeaf,
  SentraPredicate,
  PlanStep,
  ReceiptSpec,
} from "./types.js";
import { LambdaQLRuntimeError } from "./types.js";
import { compileLambdaQL } from "./compiler.js";
import { randomUUID, sha256Hex, nowISO, truncate } from "./util.js";

// ─── Amaru stub ───────────────────────────────────────────────────────────────

interface AmaruChunkCandidate {
  chunkId: string;
  content: string;
  sourceUri: string;
  bm25Score: number;
  denseScore: number;
  lateScore: number;
  doctrineGrade: number;
  embeddingModelSha: string;
  corpusSnapshotSha: string;
  ingestReceiptId: string;
}

/**
 * [REQUIRES_REPO_CONTEXT] — Stub for amaru.chunk_store.query().
 * Real implementation calls amaru's BM25 inverted index + ANN index.
 * Returns BM25 + dense + late interaction candidates pre-merge.
 */
async function amaruQuery(
  corpusRef: string,
  query: string,
  bm25MaxCandidates: number,
  denseThreshold: number,
  denseMaxCandidates: number
): Promise<AmaruChunkCandidate[]> {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   import { ChunkStore } from "@szl/amaru/chunk-store";
  //   const store = ChunkStore.connect(corpusRef);
  //   return store.hybridQuery({ query, bm25MaxCandidates, denseThreshold, denseMaxCandidates });

  // Deterministic stub — returns synthetic candidates for testing
  const seeds = Array.from({ length: bm25MaxCandidates }, (_, i) => i);
  return seeds.map(i => ({
    chunkId: `chunk-${corpusRef.replace(/\W/g, "-")}-${i}`,
    content: `Stub content for chunk ${i} from ${corpusRef}: "${query}" context [UNVERIFIED]`,
    sourceUri: `${corpusRef}://doc/${i}.md#chunk-${i}`,
    bm25Score: Math.max(0, 1 - i * 0.04 + Math.sin(i) * 0.05),
    denseScore: Math.max(0, 1 - i * 0.03 + Math.cos(i) * 0.04),
    lateScore: Math.max(0, 1 - i * 0.035 + Math.sin(i + 1) * 0.03),
    doctrineGrade: Math.max(0.7, 1 - i * 0.015),
    embeddingModelSha: "sha256:baai-bge-m3-v1.0-stub-hash",
    corpusSnapshotSha: `sha3-256:amaru-snapshot-${corpusRef.replace(/\W/g, "-")}`,
    ingestReceiptId: `ingest-receipt-${i}-${corpusRef.replace(/\W/g, "-")}`,
  }));
}

// ─── Sentra stub ──────────────────────────────────────────────────────────────

interface SentraGateResult {
  passed: boolean;
  faithfulness_score: number;
  pii_risk_score: number;
  hallucination_risk_score: number;
  policy_checks_passed: string[];
  evaluated_at: string;
}

/**
 * [REQUIRES_REPO_CONTEXT] — Stub for sentra runtime gate.
 * Real implementation calls sentra.gate.evaluate(predicates, chunk).
 * Evaluated per-chunk at runtime after BM25+dense retrieval.
 */
async function sentraGate(
  predicates: SentraPredicate[],
  chunk: AmaruChunkCandidate
): Promise<SentraGateResult> {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   import { PolicyGate } from "@szl/sentra/policy";
  //   return PolicyGate.evaluate(predicates, { content: chunk.content, docId: chunk.chunkId });

  // Stub: evaluate thresholds against chunk.doctrineGrade as proxy
  const faithfulness = chunk.doctrineGrade;
  const pii_risk = 0.02;
  const hallucination_risk = 1 - chunk.doctrineGrade;

  const checks_passed: string[] = [];
  let passed = true;

  for (const pred of predicates) {
    let actual: number;
    switch (pred.metric) {
      case "faithfulness":        actual = faithfulness;        break;
      case "pii_risk":            actual = pii_risk;            break;
      case "hallucination_risk":  actual = hallucination_risk;  break;
      default:                    actual = 0.95;                break;
    }
    const ok = evalCompOp(actual, pred.op, pred.value);
    if (ok) {
      checks_passed.push(`${pred.metric}${pred.op}${pred.value}`);
    } else {
      passed = false;
    }
  }

  return {
    passed,
    faithfulness_score: faithfulness,
    pii_risk_score: pii_risk,
    hallucination_risk_score: hallucination_risk,
    policy_checks_passed: checks_passed,
    evaluated_at: nowISO(),
  };
}

function evalCompOp(actual: number, op: string, threshold: number): boolean {
  switch (op) {
    case ">=": return actual >= threshold;
    case "<=": return actual <= threshold;
    case ">":  return actual >  threshold;
    case "<":  return actual <  threshold;
    case "=":  return actual === threshold;
    case "!=":
    case "<>": return actual !== threshold;
    default:   return false;
  }
}

// ─── Reranker stub ────────────────────────────────────────────────────────────

/**
 * [REQUIRES_REPO_CONTEXT] — Stub for cross-encoder reranker.
 * Real implementation uses BAAI/bge-reranker-v2-m3 or Cohere Rerank 3.5.
 * Returns chunks sorted by reranker logit descending.
 */
async function rerank(
  query: string,
  chunks: AmaruChunkCandidate[],
  model: string,
  topK: number
): Promise<Array<AmaruChunkCandidate & { rerankerLogit: number }>> {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   import { Reranker } from "@szl/a11oy/rerankers";
  //   return Reranker.connect(model).rerank(query, chunks, topK);

  // Stub: weight dense + BM25 + late scores as proxy for cross-encoder logit
  const scored = chunks.map(c => ({
    ...c,
    rerankerLogit: 0.5 * c.denseScore + 0.3 * c.bm25Score + 0.2 * c.lateScore,
  }));
  scored.sort((a, b) => b.rerankerLogit - a.rerankerLogit);
  return scored.slice(0, topK);
}

// ─── Ouroboros budget gate stub ───────────────────────────────────────────────

/**
 * [REQUIRES_REPO_CONTEXT] — Stub for ouroboros bounded loop / budget gate.
 * Real implementation calls ouroboros.budget_gate.validate(plan, elapsed).
 * The Lutar Invariant guarantees termination within declared budget bounds.
 */
function ouroborosBudgetCheck(
  startMs: number,
  latencyBudgetMs: number,
  chunksReturned: number,
  maxChunks: number
): { ok: boolean; reason?: string } {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   import { BudgetGate } from "@szl/ouroboros/budget";
  //   return BudgetGate.check({ startMs, latencyBudgetMs, chunksReturned, maxChunks });

  const elapsed = Date.now() - startMs;
  if (elapsed > latencyBudgetMs) {
    return { ok: false, reason: `Latency budget exceeded: ${elapsed}ms > ${latencyBudgetMs}ms` };
  }
  if (chunksReturned > maxChunks) {
    return { ok: false, reason: `Chunk budget exceeded: ${chunksReturned} > ${maxChunks}` };
  }
  return { ok: true };
}

// ─── RRF merge ────────────────────────────────────────────────────────────────

/**
 * Reciprocal Rank Fusion merge.
 * k=60 per phd1_retrieval.md §1.3 — optimal, domain-insensitive constant.
 * Source: learn.microsoft.com Azure Hybrid Search RRF
 */
function rrfMerge(
  candidates: AmaruChunkCandidate[],
  k: number = 60
): AmaruChunkCandidate[] {
  const scores = new Map<string, number>();

  // BM25 ranking
  const bm25Ranked = [...candidates].sort((a, b) => b.bm25Score - a.bm25Score);
  bm25Ranked.forEach((c, rank) => {
    scores.set(c.chunkId, (scores.get(c.chunkId) ?? 0) + 1 / (k + rank + 1));
  });

  // Dense ranking
  const denseRanked = [...candidates].sort((a, b) => b.denseScore - a.denseScore);
  denseRanked.forEach((c, rank) => {
    scores.set(c.chunkId, (scores.get(c.chunkId) ?? 0) + 1 / (k + rank + 1));
  });

  // Late interaction ranking
  const lateRanked = [...candidates].sort((a, b) => b.lateScore - a.lateScore);
  lateRanked.forEach((c, rank) => {
    scores.set(c.chunkId, (scores.get(c.chunkId) ?? 0) + 1 / (k + rank + 1));
  });

  // Sort by merged RRF score, inject rrfScore into candidate
  const deduplicated = new Map<string, AmaruChunkCandidate>();
  for (const c of candidates) deduplicated.set(c.chunkId, c);

  return [...deduplicated.values()]
    .map(c => ({ ...c, rrfScore: scores.get(c.chunkId) ?? 0 }))
    .sort((a, b) => ((b as any).rrfScore ?? 0) - ((a as any).rrfScore ?? 0));
}

// ─── Receipt builder ──────────────────────────────────────────────────────────

async function buildReceipt(
  plan: QueryPlan,
  query: string,
  chunks: Array<AmaruChunkCandidate & { rerankerLogit?: number; rrfScore?: number }>,
  contextWindow: string,
  sentraResults: SentraGateResult[],
  spec: ReceiptSpec
): Promise<LambdaReceipt> {
  const queryHash = await sha256Hex(query.trim().toLowerCase());
  const contextWindowSha = spec.includeContextWindowSha
    ? await sha256Hex(contextWindow)
    : "omitted";

  const leanStub = plan.leanObligationTemplate
    .replace("[TIMESTAMP_PLACEHOLDER]", nowISO())
    .replace("[PLAN_ID_PLACEHOLDER]", plan.planId);

  const leanObligationSha = spec.includeLeanObligationSha
    ? await sha256Hex(leanStub)
    : undefined;

  const chunkHashes = spec.includeChunkHashes
    ? await Promise.all(chunks.map(c => sha256Hex(c.content)))
    : [];

  // Compute RRF scores array from chunks
  const rrfScores = chunks.map(c => (c as any).rrfScore ?? 0);
  const bm25Scores = chunks.map(c => c.bm25Score);
  const denseScores = chunks.map(c => c.denseScore);
  const mergeInput = [...bm25Scores, ...denseScores].map(String).join(",");
  const mergeHash = await sha256Hex(mergeInput);

  // Aggregate sentra attestation
  const faithfulness_score = sentraResults.length > 0
    ? sentraResults.reduce((sum, r) => sum + r.faithfulness_score, 0) / sentraResults.length
    : 1.0;
  const allPassed = new Set<string>(sentraResults.flatMap(r => r.policy_checks_passed));

  // Reranker logit hash
  const rerankerLogitsSha = spec.includeRerankerLogits
    ? await sha256Hex(chunks.map(c => c.rerankerLogit ?? 0).join(","))
    : undefined;

  const embeddingModelSha = spec.includeEmbeddingSha
    ? (chunks[0]?.embeddingModelSha ?? "sha256:unknown")
    : "omitted";

  const doctrineGrade = chunks.length > 0
    ? chunks.reduce((sum, c) => sum + c.doctrineGrade, 0) / chunks.length
    : 0.9;

  const corpusSnapshotSha = chunks[0]?.corpusSnapshotSha ?? "sha3-256:unknown";

  // Build Merkle root: hash of all fields
  const merkleInput = [
    queryHash,
    embeddingModelSha,
    corpusSnapshotSha,
    chunkHashes.join(","),
    contextWindowSha,
    String(faithfulness_score),
    String(doctrineGrade),
    leanObligationSha ?? "",
  ].join("|");
  const merkleRoot = await sha256Hex(merkleInput);

  const receipt: LambdaReceipt = {
    receipt_version: "0.1",
    receipt_id: randomUUID(),
    timestamp_iso: nowISO(),
    query_hash: queryHash,
    query_text_preview: truncate(query, 120),
    embedding_model_sha: embeddingModelSha,
    corpus_snapshot_sha: corpusSnapshotSha,
    corpus_ref: `${plan.sourceRef}@${nowISO()}`,
    chunk_hashes: chunkHashes,
    chunk_source_uris: chunks.map(c => c.sourceUri),
    chunk_doctrine_grades: chunks.map(c => c.doctrineGrade),
    bm25_scores: bm25Scores,
    dense_scores: denseScores,
    rrf_scores: rrfScores,
    merge_hash: mergeHash,
    reranker_model_sha: spec.includeEmbeddingSha
      ? await sha256Hex("BAAI/bge-reranker-v2-m3")
      : undefined,
    reranker_logits_sha: rerankerLogitsSha,
    context_window_sha: contextWindowSha,
    sentra_attestation: {
      faithfulness_score,
      pii_risk_score: sentraResults[0]?.pii_risk_score,
      hallucination_risk_score: sentraResults[0]?.hallucination_risk_score,
      policy_checks_passed: [...allPassed],
      evaluated_at: nowISO(),
    },
    doctrine_grade: {
      composite: doctrineGrade,
    },
    lean_obligation_sha: leanObligationSha,
    lean_obligation_stub: leanStub,
    merkle_root: merkleRoot,
    merkle_algorithm: spec.merkleAlgorithm,
  };

  return receipt;
}

// ─── Runtime class ────────────────────────────────────────────────────────────

export class LambdaQLRuntime {
  /**
   * Execute a compiled QueryPlan against amaru + sentra + ouroboros.
   * Returns chunks, context window, and full Λ_Ω receipt.
   */
  async execute(plan: QueryPlan, rawQuery: string = ""): Promise<ExecutionResult> {
    const startMs = Date.now();

    // Extract SIMILAR_TO query text for embedding
    const queryText = plan.similarTo?.query ?? rawQuery;

    // ── Step: BM25 + Dense + Late retrieval from amaru ──────────────────────
    const bm25Step = plan.steps.find(s => s.kind === "BM25_RETRIEVAL");
    const denseStep = plan.steps.find(s => s.kind === "DENSE_RETRIEVAL");

    const candidates = await amaruQuery(
      plan.sourceRef,
      queryText,
      (bm25Step?.params.maxCandidates as number) ?? 100,
      (denseStep?.params.threshold as number) ?? 0.75,
      (denseStep?.params.maxCandidates as number) ?? 100
    );

    // ── Step: RRF merge ──────────────────────────────────────────────────────
    const rrfStep = plan.steps.find(s => s.kind === "RRF_MERGE");
    const merged = rrfMerge(candidates, (rrfStep?.params.k as number) ?? 60);

    // ── Step: Sentra runtime gate ────────────────────────────────────────────
    const runtimeSentraPredicates = plan.sentraPredicates;
    const sentraResults: SentraGateResult[] = [];
    const passedChunks: typeof merged = [];

    for (const chunk of merged) {
      if (runtimeSentraPredicates.length > 0) {
        const gateResult = await sentraGate(runtimeSentraPredicates, chunk);
        sentraResults.push(gateResult);
        if (!gateResult.passed) continue;
      } else {
        sentraResults.push({
          passed: true,
          faithfulness_score: chunk.doctrineGrade,
          pii_risk_score: 0.02,
          hallucination_risk_score: 1 - chunk.doctrineGrade,
          policy_checks_passed: [],
          evaluated_at: nowISO(),
        });
      }
      passedChunks.push(chunk);
    }

    if (passedChunks.length === 0 && runtimeSentraPredicates.length > 0) {
      throw new LambdaQLRuntimeError(
        `All candidates rejected by sentra gate. Predicates: ${runtimeSentraPredicates.map(p => `${p.metric}${p.op}${p.value}`).join(", ")}`,
        "SENTRA_GATE"
      );
    }

    // ── Step: Reranker ───────────────────────────────────────────────────────
    const rerankStep = plan.steps.find(s => s.kind === "RERANK");
    const reranked = await rerank(
      queryText,
      passedChunks,
      (rerankStep?.params.model as string) ?? "BAAI/bge-reranker-v2-m3",
      plan.limit
    );

    // ── Step: Doctrine filter ────────────────────────────────────────────────
    const doctrinePreds = plan.doctrinePredicates;
    const doctrineFiltered = reranked.filter(c =>
      doctrinePreds.every(p => evalCompOp(c.doctrineGrade, p.op, p.value))
    );

    const finalChunks = doctrineFiltered.slice(0, plan.limit);

    // ── Budget gate (ouroboros) ───────────────────────────────────────────────
    const budgetCheck = ouroborosBudgetCheck(
      startMs,
      plan.budget.latencyMs,
      finalChunks.length,
      plan.budget.maxChunks
    );
    if (!budgetCheck.ok) {
      // Non-fatal: log but continue (soft budget exceeded on latency)
      console.warn(`[Λ-QL] Budget warning: ${budgetCheck.reason}`);
    }

    // ── Context window assembly ───────────────────────────────────────────────
    let tokenCount = 0;
    const contextParts: string[] = [];
    for (const chunk of finalChunks) {
      const approxTokens = Math.ceil(chunk.content.length / 4);
      if (tokenCount + approxTokens > plan.budget.maxTokens) break;
      contextParts.push(`[${chunk.sourceUri}]\n${chunk.content}`);
      tokenCount += approxTokens;
    }
    const contextWindow = contextParts.join("\n\n---\n\n");

    // ── Receipt build ─────────────────────────────────────────────────────────
    const receipt = await buildReceipt(
      plan,
      rawQuery || queryText,
      finalChunks,
      contextWindow,
      sentraResults,
      plan.receiptSpec
    );

    // ── Map to RetrievedChunk[] ───────────────────────────────────────────────
    const chunks = finalChunks.map((c, rank) => ({
      chunkId: c.chunkId,
      content: c.content,
      sourceUri: c.sourceUri,
      bm25Score: c.bm25Score,
      denseScore: c.denseScore,
      rrfScore: (c as any).rrfScore ?? 0,
      rerankerLogit: c.rerankerLogit,
      rank,
      doctrineGrade: c.doctrineGrade,
      chunkHash: receipt.chunk_hashes[rank] ?? "",
      ingestReceiptId: c.ingestReceiptId,
    }));

    // ── Build Λ_Ω leaf ────────────────────────────────────────────────────────
    const leaf: LambdaOmegaLeaf = {
      leaf_id: randomUUID(),
      leaf_hash: receipt.merkle_root,
      step_kind: "RECEIPT_BUILD",
      timestamp_iso: receipt.timestamp_iso,
      payload: { planId: plan.planId, chunkCount: chunks.length },
      receipt,
    };

    return {
      chunks,
      contextWindow,
      receipt,
      leaf,
      planUsed: plan,
      durationMs: Date.now() - startMs,
    };
  }

  /**
   * Execute a raw Λ-QL query string end-to-end.
   * Compiles and executes in one call.
   */
  async run(query: string): Promise<ExecutionResult> {
    const plan = compileLambdaQL(query);
    return this.execute(plan, query);
  }

  /**
   * Verify a prior receipt against current corpus state.
   * [REQUIRES_REPO_CONTEXT] Full implementation requires amaru snapshot API.
   */
  async verify(receiptId: string, corpusRef?: string): Promise<boolean> {
    // [REQUIRES_REPO_CONTEXT] Replace with:
    //   import { ReceiptVerifier } from "@szl/amaru/receipt-verifier";
    //   return ReceiptVerifier.verify(receiptId, corpusRef);
    console.warn(`[Λ-QL VERIFY] Stub: would verify receipt ${receiptId} against ${corpusRef ?? "amaru.corpus"}`);
    return true;
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

const _runtime = new LambdaQLRuntime();

/**
 * Execute a Λ-QL query string end-to-end.
 *
 * @param query - Raw Λ-QL query text
 * @returns ExecutionResult with chunks, context window, and receipt
 */
export async function runLambdaQL(query: string): Promise<ExecutionResult> {
  return _runtime.run(query);
}
