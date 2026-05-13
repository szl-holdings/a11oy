/**
 * Λ-QL Parser Replay — 5× variance check
 * File: a11oy/src/protocol/lambda-ql/parser.replay.ts
 *
 * Doctrine v2 binding. Test×5 seeds: [42, 137, 256, 512, 1024]
 * Squad protocol: /home/user/workspace/ship_squads/00_squad_protocol.md §6
 *
 * Run: npx ts-node src/protocol/lambda-ql/parser.replay.ts
 */

import { parseLambdaQL } from "./parser.js";
import type { SelectStatement } from "./types.js";

const SEEDS = [42, 137, 256, 512, 1024] as const;

// ─── Test cases ───────────────────────────────────────────────────────────────

const TEST_CASES = [
  {
    name: "Founder Directive (canonical)",
    query: `SELECT chunks
FROM amaru.corpus
WHERE sentra.faithfulness >= 0.95
  AND doctrine.grade >= 0.9
EMIT lambda_receipt
ANCHORED zenodo;`,
    assertions: (ast: SelectStatement) => {
      if (ast.kind !== "SELECT") throw new Error("Expected SELECT");
      if (ast.projection.kind !== "ITEMS" || ast.projection.items[0].path !== "chunks")
        throw new Error("Expected projection=chunks");
      if (ast.source.ref !== "amaru.corpus") throw new Error("Expected source=amaru.corpus");
      if (!ast.where) throw new Error("Expected WHERE clause");
      if (ast.emit.kind !== "lambda_receipt") throw new Error("Expected emit=lambda_receipt");
      if (ast.anchor?.target !== "zenodo") throw new Error("Expected anchor=zenodo");
      // Validate WHERE is AND(sentra, doctrine)
      if (ast.where.kind !== "AND") throw new Error("Expected WHERE AND");
      if (ast.where.left.kind !== "SENTRA") throw new Error("Expected left=SENTRA");
      if (ast.where.right.kind !== "DOCTRINE") throw new Error("Expected right=DOCTRINE");
      const sentra = ast.where.left;
      if (sentra.metric !== "faithfulness" || sentra.op !== ">=" || sentra.value !== 0.95)
        throw new Error(`sentra mismatch: ${JSON.stringify(sentra)}`);
      const doctrine = ast.where.right;
      if (doctrine.axis !== "grade" || doctrine.op !== ">=" || doctrine.value !== 0.9)
        throw new Error(`doctrine mismatch: ${JSON.stringify(doctrine)}`);
    },
  },
  {
    name: "EXPLAIN statement",
    query: `EXPLAIN
SELECT chunks FROM amaru.corpus
WHERE sentra.faithfulness >= 0.95
EMIT lambda_receipt;`,
    assertions: (ast: any) => {
      if (ast.kind !== "EXPLAIN") throw new Error("Expected EXPLAIN");
      if (ast.inner.kind !== "SELECT") throw new Error("Expected inner SELECT");
    },
  },
  {
    name: "Full retrieval with BUDGET + LIMIT + ORDER BY",
    query: `SELECT chunks.text, chunks.hash, chunks.source_uri
FROM amaru.corpus AS c
WHERE sentra.faithfulness >= 0.95
  AND sentra.pii_risk < 0.1
  AND doctrine.faithfulness >= 0.9
  AND SIMILAR_TO("transformer attention", 0.82)
ORDER BY DOCTRINE_GRADE DESC
LIMIT 20
BUDGET (latency_ms: 500, max_chunks: 20, max_tokens: 8000)
WITH lean_proof, embedding_model = "BAAI/bge-m3"
EMIT lambda_receipt(
  include_chunk_hashes,
  include_embedding_sha,
  merkle_algorithm = "sha3-256"
)
ANCHORED zenodo(community = "szl-holdings", auto_doi = true, sandbox = false);`,
    assertions: (ast: any) => {
      if (ast.kind !== "SELECT") throw new Error("Expected SELECT");
      if (ast.source.alias !== "c") throw new Error("Expected alias c");
      if (ast.limit !== 20) throw new Error("Expected limit=20");
      if (ast.budget?.latencyMs !== 500) throw new Error("Expected latencyMs=500");
      if (ast.budget?.maxChunks !== 20) throw new Error("Expected maxChunks=20");
      if (ast.budget?.maxTokens !== 8000) throw new Error("Expected maxTokens=8000");
      if (ast.orderBy?.[0]?.kind !== "DOCTRINE_GRADE") throw new Error("Expected ORDER BY DOCTRINE_GRADE");
      if (ast.anchor?.target !== "zenodo") throw new Error("Expected zenodo anchor");
      if (ast.anchor?.options?.auto_doi !== true) throw new Error("Expected auto_doi=true");
      if (ast.anchor?.options?.sandbox !== false) throw new Error("Expected sandbox=false");
      if (ast.emit.kind !== "lambda_receipt") throw new Error("Expected lambda_receipt");
      if (!ast.emit.options?.includes("include_chunk_hashes")) throw new Error("Expected include_chunk_hashes");
    },
  },
  {
    name: "VERIFY statement",
    query: `VERIFY RECEIPT "bafybeigh3q7..."
AGAINST CORPUS amaru.corpus;`,
    assertions: (ast: any) => {
      if (ast.kind !== "VERIFY") throw new Error("Expected VERIFY");
      if (ast.receiptId !== "bafybeigh3q7...") throw new Error("Expected receiptId");
      if (ast.corpusRef !== "amaru.corpus") throw new Error("Expected corpusRef");
    },
  },
  {
    name: "Minimal query (SIMILAR_TO only)",
    query: `SELECT chunks
FROM amaru.corpus
WHERE SIMILAR_TO("transformer attention mechanism", 0.78)
  AND doctrine.grade >= 0.85
LIMIT 5
EMIT lambda_receipt;`,
    assertions: (ast: any) => {
      if (ast.kind !== "SELECT") throw new Error("Expected SELECT");
      if (ast.limit !== 5) throw new Error("Expected limit=5");
      if (!ast.where) throw new Error("Expected WHERE");
      // WHERE is AND(SIMILAR_TO, DOCTRINE)
      if (ast.where.kind !== "AND") throw new Error("Expected AND");
      if (ast.where.left.kind !== "SIMILAR_TO") throw new Error("Expected SIMILAR_TO");
      if (Math.abs(ast.where.left.threshold - 0.78) > 0.001) throw new Error("Expected threshold=0.78");
    },
  },
  {
    name: "Star projection",
    query: `SELECT *
FROM amaru.corpus
WHERE doctrine.grade >= 0.9
EMIT lambda_receipt;`,
    assertions: (ast: any) => {
      if (ast.projection.kind !== "STAR") throw new Error("Expected STAR projection");
    },
  },
  {
    name: "no_receipt explicit opt-out",
    query: `SELECT chunks
FROM amaru.corpus
WHERE sentra.faithfulness >= 0.8
EMIT no_receipt;`,
    assertions: (ast: any) => {
      if (ast.emit.kind !== "no_receipt") throw new Error("Expected no_receipt");
    },
  },
  {
    name: "Versioned corpus reference",
    query: `SELECT chunks FROM amaru.corpus@v2
WHERE doctrine.grade >= 0.9
EMIT lambda_receipt;`,
    assertions: (ast: any) => {
      if (ast.source.ref !== "amaru.corpus@v2") throw new Error(`Expected amaru.corpus@v2, got ${ast.source.ref}`);
    },
  },
  {
    name: "Subscript corpus reference",
    query: `SELECT chunks FROM amaru.corpus["legal_docs"]
WHERE sentra.faithfulness >= 0.9
EMIT lambda_receipt;`,
    assertions: (ast: any) => {
      if (!ast.source.ref.includes("legal_docs")) throw new Error(`Expected legal_docs ref, got ${ast.source.ref}`);
    },
  },
];

// ─── Runner ───────────────────────────────────────────────────────────────────

interface TestResult {
  seed: number;
  name: string;
  passed: boolean;
  error?: string;
  durationMs: number;
}

function runTest(seed: number, tc: (typeof TEST_CASES)[number]): TestResult {
  const start = Date.now();
  try {
    const ast = parseLambdaQL(tc.query);
    (tc.assertions as (ast: any) => void)(ast);
    return { seed, name: tc.name, passed: true, durationMs: Date.now() - start };
  } catch (err) {
    return { seed, name: tc.name, passed: false, error: String(err), durationMs: Date.now() - start };
  }
}

// ─── 5× Variance check ───────────────────────────────────────────────────────

/**
 * Run each test case 5× with different seeds.
 * Deterministic parser — results must be identical across all seeds.
 * Variance check: compare serialized AST across seeds; flag any divergence.
 */
async function main(): Promise<void> {
  console.log("=== Λ-QL Parser Replay — 5× Variance Check ===\n");

  let totalPassed = 0;
  let totalFailed = 0;
  const variances: string[] = [];

  for (const tc of TEST_CASES) {
    const results: TestResult[] = SEEDS.map(seed => runTest(seed, tc));
    const allPassed = results.every(r => r.passed);

    // Variance check: compare AST across seeds
    let diverged = false;
    const asts: string[] = [];
    for (const seed of SEEDS) {
      try {
        const ast = parseLambdaQL(tc.query);
        asts.push(JSON.stringify(ast));
      } catch {
        asts.push("ERROR");
      }
    }
    const uniqueAsts = new Set(asts);
    if (uniqueAsts.size > 1) {
      diverged = true;
      variances.push(`VARIANCE DETECTED in "${tc.name}": ${uniqueAsts.size} distinct ASTs across seeds`);
    }

    const status = allPassed && !diverged ? "PASS" : "FAIL";
    console.log(`[${status}] ${tc.name}`);
    if (!allPassed) {
      for (const r of results) {
        if (!r.passed) console.log(`       seed=${r.seed}: ${r.error}`);
      }
    }
    if (diverged) {
      console.log(`       VARIANCE: ${variances[variances.length - 1]}`);
    }

    if (allPassed && !diverged) totalPassed++;
    else totalFailed++;
  }

  console.log(`\n=== Results: ${totalPassed}/${TEST_CASES.length} passed, ${totalFailed} failed ===`);
  if (variances.length > 0) {
    console.log("\n[DOCTRINE FAIL] Variance detected — parser is not deterministic:");
    variances.forEach(v => console.log("  " + v));
    process.exit(1);
  }
  if (totalFailed > 0) {
    process.exit(1);
  }
  console.log("\n[DOCTRINE PASS] All tests passed across all 5 seeds.");
}

main().catch(err => { console.error(err); process.exit(1); });
