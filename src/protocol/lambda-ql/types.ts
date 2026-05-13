/**
 * Λ-QL AST Node Interfaces + Receipt Schema
 * File: a11oy/src/protocol/lambda-ql/types.ts
 *
 * Doctrine v2 binding. Zero-dependency. Canonical type definitions used by
 * lexer.ts, parser.ts, compiler.ts, runtime.ts, and all UI consumers.
 *
 * Source: phd5_protocol.md §5.1 EBNF grammar + §5.4 Λ_Ω Receipt Schema v0.1
 */

// ─── Token types ──────────────────────────────────────────────────────────────

export type TokenKind =
  | "KEYWORD"
  | "IDENT"
  | "STRING"
  | "NUMBER"
  | "BOOLEAN"
  | "NULL"
  | "DOT"
  | "COMMA"
  | "SEMI"
  | "LPAREN"
  | "RPAREN"
  | "STAR"
  | "EQ"
  | "NEQ"
  | "LT"
  | "LTE"
  | "GT"
  | "GTE"
  | "COLON"
  | "AT"
  | "LBRACKET"
  | "RBRACKET"
  | "PLUS"
  | "MINUS"
  | "SLASH"
  | "EOF";

export interface Token {
  kind: TokenKind;
  value: string;
  pos: number;
  line: number;
  col: number;
}

// ─── AST Statement types ──────────────────────────────────────────────────────

export type LambdaQLStatement =
  | SelectStatement
  | ExplainStatement
  | VerifyStatement;

export interface SelectStatement {
  kind: "SELECT";
  projection: ProjectionClause;
  source: SourceClause;
  where?: Predicate;
  orderBy?: OrderingItem[];
  limit?: number;
  budget?: BudgetClause;
  withOptions?: WithOption[];
  emit: EmitClause;
  anchor?: AnchorClause;
}

export interface ExplainStatement {
  kind: "EXPLAIN";
  inner: SelectStatement;
}

export interface VerifyStatement {
  kind: "VERIFY";
  receiptId: string;
  corpusRef?: string;
}

// ─── Projection ───────────────────────────────────────────────────────────────

export type ProjectionClause =
  | { kind: "STAR" }
  | { kind: "ITEMS"; items: ProjectionItem[] };

export interface ProjectionItem {
  /** Dotted path e.g. "chunks", "chunks.text", "chunks.hash" */
  path: string;
  alias?: string;
}

// ─── Source ───────────────────────────────────────────────────────────────────

export interface SourceClause {
  /** Qualified name e.g. "amaru.corpus", "amaru.corpus@v2", "amaru.corpus[\"legal_docs\"]" */
  ref: string;
  alias?: string;
  join?: JoinClause;
}

export interface JoinClause {
  ref: string;
  alias?: string;
  on: Predicate;
}

// ─── Predicate ────────────────────────────────────────────────────────────────

export type Predicate =
  | AndPredicate
  | OrPredicate
  | NotPredicate
  | ComparisonPredicate
  | SentraPredicate
  | DoctrinePredicate
  | SimilarToPredicate
  | InPredicate
  | ExistsPredicate;

export interface AndPredicate {
  kind: "AND";
  left: Predicate;
  right: Predicate;
}

export interface OrPredicate {
  kind: "OR";
  left: Predicate;
  right: Predicate;
}

export interface NotPredicate {
  kind: "NOT";
  inner: Predicate;
}

export interface ComparisonPredicate {
  kind: "COMPARISON";
  left: Expr;
  op: CompOp;
  right: Expr;
}

/**
 * Sentra policy gate predicate — evaluated at compile-time AND runtime.
 * e.g. sentra.faithfulness >= 0.95
 */
export interface SentraPredicate {
  kind: "SENTRA";
  metric: SentraMetric | string;
  op: CompOp;
  value: number;
}

export type SentraMetric =
  | "faithfulness"
  | "hallucination_risk"
  | "toxicity"
  | "pii_risk"
  | "confidentiality_class";

/**
 * Doctrine grade predicate — maps to 9-axis Lutar Invariant.
 * e.g. doctrine.grade >= 0.9
 */
export interface DoctrinePredicate {
  kind: "DOCTRINE";
  axis: DoctrineAxis | string;
  op: CompOp;
  value: number;
}

export type DoctrineAxis =
  | "grade"
  | "faithfulness"
  | "answer_relevancy"
  | "context_precision"
  | "completeness"
  | "measurability"
  | "honesty"
  | "cleanliness"
  | "originality"
  | "self_consistency";

export interface SimilarToPredicate {
  kind: "SIMILAR_TO";
  expr: Expr;
  threshold?: number;
}

export interface InPredicate {
  kind: "IN";
  expr: Expr;
  values: Expr[];
}

export interface ExistsPredicate {
  kind: "EXISTS";
  subquery: SelectStatement;
}

export type CompOp = ">=" | "<=" | ">" | "<" | "=" | "!=" | "<>";

// ─── Expressions ──────────────────────────────────────────────────────────────

export type Expr =
  | LiteralExpr
  | RefExpr
  | CallExpr
  | BinOpExpr;

export interface LiteralExpr {
  kind: "LITERAL";
  value: string | number | boolean | null;
}

export interface RefExpr {
  kind: "REF";
  path: string;
}

export interface CallExpr {
  kind: "CALL";
  fn: string;
  args: Expr[];
}

export interface BinOpExpr {
  kind: "BINOP";
  op: "+" | "-" | "*" | "/";
  left: Expr;
  right: Expr;
}

// ─── Ordering ─────────────────────────────────────────────────────────────────

export type OrderingItem =
  | { kind: "EXPR"; expr: Expr; dir: "ASC" | "DESC" }
  | { kind: "SCORE" }
  | { kind: "DOCTRINE_GRADE" }
  | { kind: "INGEST_TIME"; dir: "ASC" | "DESC" };

// ─── Budget ───────────────────────────────────────────────────────────────────

export interface BudgetClause {
  /** Max retrieval latency in milliseconds. Compiles to ouroboros budget_gate. */
  latencyMs?: number;
  /** Max returned chunks. Lutar Invariant bound on result cardinality. */
  maxChunks?: number;
  /** Max context tokens assembled. */
  maxTokens?: number;
  /** Max graph traversal hops (for Prisca-GraphRAG paths). */
  maxHops?: number;
  /** Max cost in USD cents. */
  costCents?: number;
}

// ─── WITH options ─────────────────────────────────────────────────────────────

export type WithOption =
  | "receipt"
  | "explanation"
  | "lean_proof"
  | "corpus_snapshot"
  | { key: string; value: string };

// ─── EMIT clause ──────────────────────────────────────────────────────────────

export interface EmitClause {
  kind: "lambda_receipt" | "no_receipt";
  options?: EmitOption[];
}

export type EmitOption =
  | "include_chunk_hashes"
  | "include_reranker_logits"
  | "include_embedding_sha"
  | "include_context_window_sha"
  | "include_lean_obligation_sha"
  | { key: "merkle_algorithm" | "receipt_version"; value: string };

// ─── ANCHOR clause ────────────────────────────────────────────────────────────

export interface AnchorClause {
  target: "zenodo" | "ipfs" | string;
  options?: Record<string, string | boolean>;
}

// ─── Query Plan (output of compiler) ─────────────────────────────────────────

export type PlanStepKind =
  | "BM25_RETRIEVAL"
  | "DENSE_RETRIEVAL"
  | "LATE_INTERACTION"
  | "RRF_MERGE"
  | "RERANK"
  | "SENTRA_GATE"
  | "DOCTRINE_FILTER"
  | "CONTEXT_ASSEMBLE"
  | "RECEIPT_BUILD"
  | "ANCHOR";

export interface PlanStep {
  kind: PlanStepKind;
  params: Record<string, unknown>;
}

export interface QueryPlan {
  planId: string;
  sourceRef: string;
  projection: ProjectionClause;
  steps: PlanStep[];
  budget: Required<BudgetClause>;
  receiptSpec: ReceiptSpec;
  anchorTarget?: "zenodo" | "ipfs" | string;
  anchorOptions?: Record<string, string | boolean>;
  leanObligationTemplate: string;
  /** sentra predicates extracted at compile-time for policy validation */
  sentraPredicates: SentraPredicate[];
  doctrinePredicates: DoctrinePredicate[];
  similarTo?: { query: string; threshold: number };
  orderBy: OrderingItem[];
  limit: number;
}

export interface ReceiptSpec {
  includeChunkHashes: boolean;
  includeRerankerLogits: boolean;
  includeEmbeddingSha: boolean;
  includeContextWindowSha: boolean;
  includeLeanObligationSha: boolean;
  merkleAlgorithm: string;
  receiptVersion: string;
}

// ─── Λ_Ω Receipt Schema v0.1 ──────────────────────────────────────────────────

/**
 * Λ_Ω Receipt — cryptographic provenance record for every Λ-QL execution.
 * Inserted as _meta.lambda_receipt on MCP CallToolResult.
 * Schema version: 0.1
 * Source: phd5_protocol.md §5.4
 */
export interface LambdaReceipt {
  receipt_version: "0.1";
  receipt_id: string;          // UUID v4
  timestamp_iso: string;       // ISO 8601 UTC

  // Query identity
  query_hash: string;          // sha3-256(normalized_query_text)
  query_text_preview?: string; // first 120 chars

  // Retrieval provenance
  embedding_model_sha: string; // sha3-256(model_id + model_version)
  corpus_snapshot_sha: string; // sha3-256(amaru.corpus.snapshot_at_query_time)
  corpus_ref: string;          // e.g. "amaru.corpus@2026-05-13T16:39:00Z"

  // Chunk-level provenance
  chunk_hashes: string[];           // sha3-256 of each retrieved chunk text
  chunk_source_uris: string[];      // source URI per chunk
  chunk_doctrine_grades: number[];  // doctrine.grade per chunk (0-1)

  // BM25 + dense scores (a11oy extension over §5.4 base schema)
  bm25_scores?: number[];
  dense_scores?: number[];
  rrf_scores?: number[];
  merge_hash?: string;           // sha3-256(bm25_scores + dense_scores concat)

  // Reranking provenance
  reranker_model_sha?: string;   // sha3-256(reranker_id + version)
  reranker_logits_sha?: string;  // sha3-256(logit_vector)

  // Context window
  context_window_sha: string;    // sha3-256(concatenated context passed to LLM)

  // Policy attestation (sentra)
  sentra_attestation: SentraAttestation;

  // Doctrine grade
  doctrine_grade: DoctrineGrade;

  // Lean 4 obligation
  lean_obligation_sha?: string;
  lean_obligation_stub?: string;

  // Merkle root
  merkle_root: string;       // sha3-256(merkle_tree_of_all_above_fields)
  merkle_algorithm: string;  // "sha3-256"

  // Zenodo anchor
  zenodo_doi?: string;
  zenodo_deposit_url?: string;

  // a11oy proof chain
  a11oy_proof_chain_leaf?: string;
}

export interface SentraAttestation {
  faithfulness_score: number;
  pii_risk_score?: number;
  hallucination_risk_score?: number;
  policy_checks_passed: string[];
  evaluated_at: string;
}

export interface DoctrineGrade {
  composite: number;  // 0-1
  axes?: {
    faithfulness?: number;
    answer_relevancy?: number;
    context_precision?: number;
    completeness?: number;
    measurability?: number;
    honesty?: number;
    cleanliness?: number;
    originality?: number;
    self_consistency?: number;
  };
}

/** Λ_Ω Merkle leaf — emitted by every retrieval step */
export interface LambdaOmegaLeaf {
  leaf_id: string;
  leaf_hash: string;
  parent_leaf_id?: string;
  step_kind: PlanStepKind;
  timestamp_iso: string;
  payload: Record<string, unknown>;
  receipt: LambdaReceipt;
}

// ─── Runtime result ───────────────────────────────────────────────────────────

export interface RetrievedChunk {
  chunkId: string;
  content: string;
  sourceUri: string;
  bm25Score: number;
  denseScore: number;
  rrfScore: number;
  rerankerLogit?: number;
  rank: number;
  doctrineGrade: number;
  chunkHash: string;
  ingestReceiptId: string;
}

export interface ExecutionResult {
  chunks: RetrievedChunk[];
  contextWindow: string;
  receipt: LambdaReceipt;
  leaf: LambdaOmegaLeaf;
  planUsed: QueryPlan;
  durationMs: number;
  explain?: string;
}

// ─── Compile error ────────────────────────────────────────────────────────────

export class LambdaQLCompileError extends Error {
  constructor(
    message: string,
    public readonly phase: "LEXER" | "PARSER" | "COMPILE_TIME_VALIDATION" | "PLAN_EMIT",
    public readonly pos?: number
  ) {
    super(`[Λ-QL ${phase}] ${message}`);
    this.name = "LambdaQLCompileError";
  }
}

export class LambdaQLRuntimeError extends Error {
  constructor(
    message: string,
    public readonly phase: "SENTRA_GATE" | "AMARU_QUERY" | "RERANK" | "RECEIPT_BUILD" | "ANCHOR"
  ) {
    super(`[Λ-QL RUNTIME:${phase}] ${message}`);
    this.name = "LambdaQLRuntimeError";
  }
}
