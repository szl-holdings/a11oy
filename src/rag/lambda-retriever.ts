/**
 * Λ-Retriever — Orchestrates amaru + sentra + ouroboros retrieval pipeline
 * File: a11oy/src/rag/lambda-retriever.ts
 *
 * Doctrine v2 binding.
 *
 * This module is the primary retrieval entry point for a11oy.
 * It orchestrates:
 *   1. Λ-QL query compilation (compiler.ts)
 *   2. BM25 + dense + late interaction via HybridReceiptedRetriever
 *   3. Sentra policy gates (compile-time + runtime)
 *   4. Doctrine grading filter
 *   5. Λ_Ω Merkle leaf emission
 *   6. Optional Zenodo anchor
 *
 * Emits: LambdaOmegaLeaf — consumed by RAGReceiptExplorer UI
 * Source: 99_synthesis_a11oy_rag.md §2.1, phd1_retrieval.md §5
 */

import type {
  LambdaOmegaLeaf,
  LambdaReceipt,
  RetrievedChunk,
  QueryPlan,
} from "../protocol/lambda-ql/types.js";
import { compileLambdaQL } from "../protocol/lambda-ql/compiler.js";
import { LambdaQLRuntime } from "../protocol/lambda-ql/runtime.js";
import {
  HybridReceiptedRetriever,
  type HybridRetrieverConfig,
} from "./retrievers/hybrid-receipted.js";
import { randomUUID, sha256Hex, nowISO } from "../protocol/lambda-ql/util.js";

// ─── Retriever config ─────────────────────────────────────────────────────────

export interface LambdaRetrieverConfig {
  corpusRef?: string;
  embeddingModel?: string;
  rerankerModel?: string;
  /** RRF constant — k=60 optimal per phd1_retrieval.md */
  rrfK?: number;
  /** Max BM25 first-stage candidates */
  bm25MaxCandidates?: number;
  /** Max dense first-stage candidates */
  denseMaxCandidates?: number;
  /** Final top-K after reranking */
  topK?: number;
  /** Emit Zenodo anchor for receipt (adds async latency) */
  zenodoAnchor?: boolean;
}

// ─── Zenodo stub ──────────────────────────────────────────────────────────────

/**
 * [REQUIRES_REPO_CONTEXT] Zenodo deposit stub.
 * Real implementation uses Zenodo REST API with api_credentials=["zenodo.org"].
 * Returns DOI string or null if anchoring disabled/failed.
 */
async function zenodoAnchorStub(receipt: LambdaReceipt): Promise<string | null> {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   const res = await fetch("https://zenodo.org/api/deposit/depositions", {
  //     method: "POST",
  //     headers: { "Authorization": `Bearer ${process.env.ZENODO_TOKEN}`, "Content-Type": "application/json" },
  //     body: JSON.stringify({ metadata: { title: `Λ-QL Receipt ${receipt.receipt_id}`, ... } })
  //   });
  //   const dep = await res.json();
  //   await uploadReceiptFile(dep.id, receipt);
  //   await publishDeposition(dep.id);
  //   return dep.doi;
  console.info(`[Λ-Retriever] Zenodo anchor stub: would anchor receipt ${receipt.receipt_id}`);
  return null; // Production: return "10.5281/zenodo.XXXXXXXX"
}

// ─── Main retriever class ─────────────────────────────────────────────────────

export class LambdaRetriever {
  private readonly hybrid: HybridReceiptedRetriever;
  private readonly runtime: LambdaQLRuntime;
  private readonly config: Required<LambdaRetrieverConfig>;

  constructor(config: LambdaRetrieverConfig = {}) {
    this.config = {
      corpusRef: config.corpusRef ?? "amaru.corpus",
      embeddingModel: config.embeddingModel ?? "BAAI/bge-m3",
      rerankerModel: config.rerankerModel ?? "BAAI/bge-reranker-v2-m3",
      rrfK: config.rrfK ?? 60,
      bm25MaxCandidates: config.bm25MaxCandidates ?? 100,
      denseMaxCandidates: config.denseMaxCandidates ?? 100,
      topK: config.topK ?? 20,
      zenodoAnchor: config.zenodoAnchor ?? false,
    };

    const hybridConfig: Partial<HybridRetrieverConfig> = {
      corpusRef: this.config.corpusRef,
      embeddingModel: this.config.embeddingModel,
      rerankerModel: this.config.rerankerModel,
      rrfK: this.config.rrfK,
      bm25MaxCandidates: this.config.bm25MaxCandidates,
      denseMaxCandidates: this.config.denseMaxCandidates,
      rerankerTopK: this.config.topK,
    };

    this.hybrid = new HybridReceiptedRetriever(hybridConfig);
    this.runtime = new LambdaQLRuntime();
  }

  /**
   * Retrieve chunks for a natural language query.
   * Uses BM25 + dense + late interaction + RRF + rerank pipeline.
   * Emits a LambdaOmegaLeaf with full provenance receipt.
   *
   * @param query - Natural language retrieval query
   * @param options - Optional sentra/doctrine thresholds
   * @returns Retrieved chunks + Λ_Ω leaf
   */
  async retrieve(
    query: string,
    options: {
      sentraFaithfulnessMin?: number;
      doctrineGradeMin?: number;
      limit?: number;
    } = {}
  ): Promise<{
    chunks: RetrievedChunk[];
    leaf: LambdaOmegaLeaf;
    durationMs: number;
  }> {
    const { chunks, leaf, durationMs } = await this.hybrid.retrieve(query, {
      doctrineMinGrade: options.doctrineGradeMin ?? 0.0,
      limit: options.limit ?? this.config.topK,
    });

    // Optionally anchor to Zenodo
    if (this.config.zenodoAnchor) {
      const doi = await zenodoAnchorStub(leaf.receipt);
      if (doi) {
        (leaf.receipt as any).zenodo_doi = doi;
      }
    }

    return { chunks, leaf, durationMs };
  }

  /**
   * Execute a Λ-QL query string end-to-end.
   * Compiles → validates → retrieves → receipts → (optionally anchors).
   *
   * @param lambdaQLQuery - Λ-QL query string
   * @returns Full ExecutionResult with chunks, context window, and receipt
   */
  async runQuery(lambdaQLQuery: string): Promise<{
    chunks: RetrievedChunk[];
    leaf: LambdaOmegaLeaf;
    contextWindow: string;
    receipt: LambdaReceipt;
    plan: QueryPlan;
    durationMs: number;
    explain?: string;
  }> {
    const startMs = Date.now();

    // Compile to plan (includes compile-time sentra + doctrine validation)
    const plan = compileLambdaQL(lambdaQLQuery);

    // Execute via runtime (handles sentra gate + rerank + receipt build)
    const result = await this.runtime.execute(plan, lambdaQLQuery);

    // Optionally anchor receipt
    if (plan.anchorTarget === "zenodo" && this.config.zenodoAnchor) {
      const doi = await zenodoAnchorStub(result.receipt);
      if (doi) {
        (result.receipt as any).zenodo_doi = doi;
        (result.leaf.receipt as any).zenodo_doi = doi;
      }
    }

    return {
      chunks: result.chunks,
      leaf: result.leaf,
      contextWindow: result.contextWindow,
      receipt: result.receipt,
      plan,
      durationMs: Date.now() - startMs,
    };
  }

  /**
   * Build a Λ-QL EXPLAIN plan without executing.
   * Returns the QueryPlan for UI display in RAGReceiptExplorer.
   */
  explainQuery(lambdaQLQuery: string): QueryPlan {
    const fullQuery = lambdaQLQuery.trimEnd().replace(/;?\s*$/, "");
    return compileLambdaQL(`EXPLAIN ${fullQuery};`);
  }
}

// ─── Public singleton ─────────────────────────────────────────────────────────

export const lambdaRetriever = new LambdaRetriever();

/**
 * Convenience function: retrieve chunks for a natural language query.
 * Uses default config (amaru.corpus, BGE-M3, bge-reranker-v2-m3).
 */
export async function retrieveWithReceipt(
  query: string,
  options?: {
    sentraFaithfulnessMin?: number;
    doctrineGradeMin?: number;
    limit?: number;
    corpusRef?: string;
  }
): Promise<{ chunks: RetrievedChunk[]; leaf: LambdaOmegaLeaf; durationMs: number }> {
  const retriever = options?.corpusRef
    ? new LambdaRetriever({ corpusRef: options.corpusRef })
    : lambdaRetriever;
  return retriever.retrieve(query, options);
}

/**
 * Convenience function: run a full Λ-QL query string.
 */
export async function runLambdaQuery(lambdaQLQuery: string) {
  return lambdaRetriever.runQuery(lambdaQLQuery);
}
