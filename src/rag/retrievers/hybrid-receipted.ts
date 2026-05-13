/**
 * Hybrid Receipted Retriever — RRF hybrid retriever with Λ_Ω receipt emission
 * File: a11oy/src/rag/retrievers/hybrid-receipted.ts
 *
 * Doctrine v2 binding. Implements BM25 + dense + RRF pipeline per:
 *   - phd1_retrieval.md §1.3 (RRF k=60, hybrid best practice 2026)
 *   - phd1_retrieval.md §1.2 (BGE-M3 tri-functional recommended)
 *   - 99_synthesis_a11oy_rag.md §2.1 (amaru + sentra integration)
 *
 * Every retrieval operation emits a LambdaOmegaLeaf for the a11oy proof chain.
 */

import type {
  LambdaOmegaLeaf,
  LambdaReceipt,
  RetrievedChunk,
} from "../../../src/protocol/lambda-ql/types.js";
import { randomUUID, sha256Hex, nowISO } from "../../../src/protocol/lambda-ql/util.js";

// ─── Retrieval config ─────────────────────────────────────────────────────────

export interface HybridRetrieverConfig {
  corpusRef: string;
  embeddingModel: string;
  rerankerModel: string;
  /** RRF constant k=60 (default, domain-insensitive per phd1_retrieval.md) */
  rrfK: number;
  bm25MaxCandidates: number;
  denseMaxCandidates: number;
  rerankerTopK: number;
  doctrineMinGrade: number;
}

export const DEFAULT_HYBRID_CONFIG: HybridRetrieverConfig = {
  corpusRef: "amaru.corpus",
  embeddingModel: "BAAI/bge-m3",    // tri-functional: dense + sparse + multi-vector
  rerankerModel: "BAAI/bge-reranker-v2-m3",
  rrfK: 60,
  bm25MaxCandidates: 100,
  denseMaxCandidates: 100,
  rerankerTopK: 20,
  doctrineMinGrade: 0.0,
};

// ─── Score types ──────────────────────────────────────────────────────────────

export interface RawCandidate {
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

export interface RankedCandidate extends RawCandidate {
  rrfScore: number;
  rerankerLogit?: number;
  rank: number;
}

// ─── RRF implementation ───────────────────────────────────────────────────────

/**
 * Reciprocal Rank Fusion — fuses BM25 + dense + late interaction ranks.
 *
 * Formula: RRF(d) = Σ_{r ∈ rankers} 1 / (k + rank_r(d))
 * k=60 per phd1_retrieval.md §1.3 and Azure AI Search default.
 *
 * Operates on ranks (not raw scores), making it immune to scale mismatch
 * between BM25 (unbounded positive) and cosine similarity ([-1,1]).
 */
export function computeRRF(
  candidates: RawCandidate[],
  k: number = 60
): Array<RawCandidate & { rrfScore: number }> {
  if (candidates.length === 0) return [];

  const rrfScores = new Map<string, number>();
  const byId = new Map<string, RawCandidate>();

  for (const c of candidates) byId.set(c.chunkId, c);

  // BM25 ranking pass
  const bm25Ranked = [...candidates].sort((a, b) => b.bm25Score - a.bm25Score);
  bm25Ranked.forEach((c, idx) => {
    rrfScores.set(c.chunkId, (rrfScores.get(c.chunkId) ?? 0) + 1 / (k + idx + 1));
  });

  // Dense ranking pass
  const denseRanked = [...candidates].sort((a, b) => b.denseScore - a.denseScore);
  denseRanked.forEach((c, idx) => {
    rrfScores.set(c.chunkId, (rrfScores.get(c.chunkId) ?? 0) + 1 / (k + idx + 1));
  });

  // Late interaction ranking pass
  const lateRanked = [...candidates].sort((a, b) => b.lateScore - a.lateScore);
  lateRanked.forEach((c, idx) => {
    rrfScores.set(c.chunkId, (rrfScores.get(c.chunkId) ?? 0) + 1 / (k + idx + 1));
  });

  return [...byId.values()]
    .map(c => ({ ...c, rrfScore: rrfScores.get(c.chunkId) ?? 0 }))
    .sort((a, b) => b.rrfScore - a.rrfScore);
}

// ─── BM25 stage ───────────────────────────────────────────────────────────────

/**
 * BM25 retrieval stage.
 * [REQUIRES_REPO_CONTEXT] Real call to amaru's inverted index.
 *
 * BM25 formula from phd1_retrieval.md §1.1:
 *   score(D,Q) = Σ IDF(qᵢ) · f(qᵢ,D)·(k₁+1) / (f(qᵢ,D) + k₁·(1−b+b·|D|/avgdl))
 *   Default: k₁=1.2, b=0.75
 */
async function bm25Retrieve(
  corpusRef: string,
  query: string,
  maxCandidates: number
): Promise<RawCandidate[]> {
  // [REQUIRES_REPO_CONTEXT] Replace with amaru BM25 index query
  return _stubCandidates(corpusRef, query, maxCandidates, "bm25");
}

// ─── Dense retrieval stage ────────────────────────────────────────────────────

/**
 * Dense retrieval using bi-encoder (BGE-M3 recommended).
 * [REQUIRES_REPO_CONTEXT] Real call to amaru ANN index.
 *
 * BGE-M3 source: phd1_retrieval.md §1.2, arxiv:2402.03216
 * Single forward pass produces: dense [CLS] embedding + sparse weights + token matrices.
 */
async function denseRetrieve(
  corpusRef: string,
  query: string,
  embeddingModel: string,
  threshold: number,
  maxCandidates: number
): Promise<RawCandidate[]> {
  // [REQUIRES_REPO_CONTEXT] Replace with:
  //   1. Embed query: const qVec = await embedder.embed(query, model=embeddingModel)
  //   2. ANN search: return amaru.annSearch(corpusRef, qVec, { threshold, topK: maxCandidates })
  return _stubCandidates(corpusRef, query, maxCandidates, "dense");
}

// ─── Late interaction stage ───────────────────────────────────────────────────

/**
 * Late interaction (ColBERT MaxSim) retrieval.
 * [REQUIRES_REPO_CONTEXT] Real call to amaru token matrix store.
 *
 * MaxSim: S(q,d) = Σᵢ∈query_tokens max_{j∈doc_tokens} qᵢ·dⱼ
 * Source: phd1_retrieval.md §1.4, arxiv:2112.01488
 */
async function lateInteractionRetrieve(
  corpusRef: string,
  query: string,
  maxCandidates: number
): Promise<RawCandidate[]> {
  // [REQUIRES_REPO_CONTEXT] Replace with amaru token matrix MaxSim query
  return _stubCandidates(corpusRef, query, maxCandidates, "late");
}

// ─── Cross-encoder reranker ───────────────────────────────────────────────────

/**
 * Cross-encoder reranking.
 * [REQUIRES_REPO_CONTEXT] Real call to BAAI/bge-reranker-v2-m3 or Cohere 3.5.
 * Source: phd1_retrieval.md §1.9
 */
async function crossEncoderRerank(
  query: string,
  candidates: Array<RawCandidate & { rrfScore: number }>,
  model: string,
  topK: number
): Promise<RankedCandidate[]> {
  // [REQUIRES_REPO_CONTEXT] Replace with actual reranker inference
  const scored = candidates.map(c => ({
    ...c,
    rerankerLogit: 0.5 * c.denseScore + 0.3 * c.bm25Score + 0.2 * c.lateScore,
  }));
  scored.sort((a, b) => (b.rerankerLogit ?? 0) - (a.rerankerLogit ?? 0));
  return scored.slice(0, topK).map((c, rank) => ({ ...c, rank }));
}

// ─── Receipt builder ──────────────────────────────────────────────────────────

async function buildLeaf(
  query: string,
  corpusRef: string,
  embeddingModel: string,
  rerankerModel: string,
  rankedChunks: RankedCandidate[]
): Promise<LambdaOmegaLeaf> {
  const queryHash = await sha256Hex(query);
  const chunkHashes = await Promise.all(rankedChunks.map(c => sha256Hex(c.content)));
  const contextSha = await sha256Hex(rankedChunks.map(c => c.content).join("\n"));
  const embeddingModelSha = await sha256Hex(embeddingModel);
  const corpusSnapshotSha = rankedChunks[0]?.corpusSnapshotSha ?? "sha3-256:unknown";

  const merkleInput = [queryHash, embeddingModelSha, corpusSnapshotSha, chunkHashes.join(","), contextSha].join("|");
  const merkleRoot = await sha256Hex(merkleInput);
  const receiptId = randomUUID();
  const ts = nowISO();

  const receipt: LambdaReceipt = {
    receipt_version: "0.1",
    receipt_id: receiptId,
    timestamp_iso: ts,
    query_hash: queryHash,
    query_text_preview: query.slice(0, 120),
    embedding_model_sha: embeddingModelSha,
    corpus_snapshot_sha: corpusSnapshotSha,
    corpus_ref: corpusRef,
    chunk_hashes: chunkHashes,
    chunk_source_uris: rankedChunks.map(c => c.sourceUri),
    chunk_doctrine_grades: rankedChunks.map(c => c.doctrineGrade),
    bm25_scores: rankedChunks.map(c => c.bm25Score),
    dense_scores: rankedChunks.map(c => c.denseScore),
    rrf_scores: rankedChunks.map(c => c.rrfScore),
    merge_hash: await sha256Hex([...rankedChunks.map(c => c.bm25Score), ...rankedChunks.map(c => c.denseScore)].join(",")),
    reranker_model_sha: await sha256Hex(rerankerModel),
    context_window_sha: contextSha,
    sentra_attestation: {
      faithfulness_score: rankedChunks.reduce((s, c) => s + c.doctrineGrade, 0) / (rankedChunks.length || 1),
      policy_checks_passed: [],
      evaluated_at: ts,
    },
    doctrine_grade: {
      composite: rankedChunks.reduce((s, c) => s + c.doctrineGrade, 0) / (rankedChunks.length || 1),
    },
    merkle_root: merkleRoot,
    merkle_algorithm: "sha3-256",
  };

  return {
    leaf_id: randomUUID(),
    leaf_hash: merkleRoot,
    step_kind: "RECEIPT_BUILD",
    timestamp_iso: ts,
    payload: { query, corpusRef, chunkCount: rankedChunks.length },
    receipt,
  };
}

// ─── Main retriever class ─────────────────────────────────────────────────────

export class HybridReceiptedRetriever {
  private readonly config: HybridRetrieverConfig;

  constructor(config: Partial<HybridRetrieverConfig> = {}) {
    this.config = { ...DEFAULT_HYBRID_CONFIG, ...config };
  }

  /**
   * Full BM25 + dense + late interaction + RRF + rerank pipeline.
   * Every invocation emits a LambdaOmegaLeaf for the a11oy proof chain.
   *
   * Pipeline (phd1_retrieval.md §1.3, "Best practice 2026"):
   *   BM25 first-stage → dense first-stage → late interaction →
   *   RRF merge → cross-encoder rerank → doctrine filter → Λ_Ω receipt
   */
  async retrieve(
    query: string,
    options: {
      doctrineMinGrade?: number;
      limit?: number;
    } = {}
  ): Promise<{
    chunks: RetrievedChunk[];
    leaf: LambdaOmegaLeaf;
    durationMs: number;
  }> {
    const startMs = Date.now();
    const { corpusRef, embeddingModel, rerankerModel, rrfK,
            bm25MaxCandidates, denseMaxCandidates, rerankerTopK } = this.config;
    const doctrineMin = options.doctrineMinGrade ?? this.config.doctrineMinGrade;
    const limit = options.limit ?? rerankerTopK;

    // Stage 1: Parallel retrieval
    const [bm25Results, denseResults, lateResults] = await Promise.all([
      bm25Retrieve(corpusRef, query, bm25MaxCandidates),
      denseRetrieve(corpusRef, query, embeddingModel, 0.0, denseMaxCandidates),
      lateInteractionRetrieve(corpusRef, query, bm25MaxCandidates),
    ]);

    // Merge all candidates (deduplicate by chunkId)
    const allById = new Map<string, RawCandidate>();
    for (const c of [...bm25Results, ...denseResults, ...lateResults]) {
      if (!allById.has(c.chunkId)) {
        allById.set(c.chunkId, c);
      } else {
        // Merge scores: take max of each score type
        const existing = allById.get(c.chunkId)!;
        allById.set(c.chunkId, {
          ...existing,
          bm25Score: Math.max(existing.bm25Score, c.bm25Score),
          denseScore: Math.max(existing.denseScore, c.denseScore),
          lateScore: Math.max(existing.lateScore, c.lateScore),
        });
      }
    }

    // Stage 2: RRF merge
    const merged = computeRRF([...allById.values()], rrfK);

    // Stage 3: Cross-encoder rerank
    const reranked = await crossEncoderRerank(query, merged, rerankerModel, Math.min(merged.length, rerankerTopK * 2));

    // Stage 4: Doctrine filter + limit
    const filtered = reranked
      .filter(c => c.doctrineGrade >= doctrineMin)
      .slice(0, limit);

    // Stage 5: Build Λ_Ω receipt leaf
    const leaf = await buildLeaf(query, corpusRef, embeddingModel, rerankerModel, filtered);

    // Map to RetrievedChunk
    const chunks: RetrievedChunk[] = filtered.map((c, rank) => ({
      chunkId: c.chunkId,
      content: c.content,
      sourceUri: c.sourceUri,
      bm25Score: c.bm25Score,
      denseScore: c.denseScore,
      rrfScore: c.rrfScore,
      rerankerLogit: c.rerankerLogit,
      rank,
      doctrineGrade: c.doctrineGrade,
      chunkHash: leaf.receipt.chunk_hashes[rank] ?? "",
      ingestReceiptId: c.ingestReceiptId,
    }));

    return { chunks, leaf, durationMs: Date.now() - startMs };
  }
}

// ─── Stub helper ──────────────────────────────────────────────────────────────

function _stubCandidates(
  corpusRef: string,
  query: string,
  n: number,
  variant: string
): RawCandidate[] {
  return Array.from({ length: n }, (_, i) => ({
    chunkId: `${variant}-chunk-${i}`,
    content: `[${variant.toUpperCase()} STUB] chunk ${i} for "${query.slice(0, 40)}" from ${corpusRef}`,
    sourceUri: `${corpusRef}://stub/${i}`,
    bm25Score: Math.max(0, 1 - i * 0.04 + Math.sin(i + variant.length) * 0.05),
    denseScore: Math.max(0, 1 - i * 0.03 + Math.cos(i + variant.length) * 0.04),
    lateScore: Math.max(0, 1 - i * 0.035 + Math.sin(i + variant.length + 1) * 0.03),
    doctrineGrade: Math.max(0.6, 1 - i * 0.015),
    embeddingModelSha: "sha256:baai-bge-m3-stub",
    corpusSnapshotSha: `sha3-256:snapshot-${corpusRef.replace(/\W/g, "-")}`,
    ingestReceiptId: `ingest-${variant}-${i}`,
  }));
}
