/**
 * composition_overhead.ts
 * Doctrine v6 R3 — Vertical Governance Receipts
 *
 * Measures the latency overhead of composing (stacking) Doctrine v6 Λ-axis
 * policy evaluations across vertical policies.
 *
 * Benchmark: N = 10,000 composition runs, reports p50 / p95 / p99.
 * "Composition" = for a given inference request, evaluate all mandatory axes
 * across a loaded vertical policy and produce a composite compliance score.
 *
 * Usage:
 *   npx ts-node measurement/composition_overhead.ts
 *   # or: npx tsx measurement/composition_overhead.ts
 *
 * Citations:
 *   - Doctrine v6 §4.7 — Merkle DAG p50 write ≤ 5 µs target
 *   - Doctrine v6 §4.8 — Policy composition overhead budget ≤ 50 µs (p99)
 *   - NIST SP 800-185 (SHA3-256 throughput reference)
 */

import * as crypto from "crypto";

// ── Configuration ─────────────────────────────────────────────────────────────

const N = 10_000;          // Number of composition iterations
const NUM_CLAUSES = 8;     // Simulated policy clause count
const NUM_AXES = 10;       // All 10 Doctrine v6 Λ-axes

// ── Simulated Policy Structures ───────────────────────────────────────────────

interface AxisMapping {
  axis: string;
  weight: number;
  enforcement: "mandatory" | "recommended" | "informational";
}

interface SimulatedClause {
  clause_id: string;
  lambda_axes: AxisMapping[];
}

interface SimulatedPolicy {
  vertical: string;
  mandatory_axes: string[];
  clauses: SimulatedClause[];
}

interface InferenceRequest {
  request_id: string;
  payload_hash: string;
  actor_id: string;
  axis_scores: Record<string, number>;  // Λ1..Λ10 → [0,1]
}

interface CompositeResult {
  compliant: boolean;
  composite_score: number;
  failed_mandatory_axes: string[];
  receipt_hash: string;
}

// ── Composition Logic ─────────────────────────────────────────────────────────

function sha256_6bytes(data: string): string {
  // Lightweight 6-byte hash for receipt stub (production: SHA3-256)
  return crypto.createHash("sha256").update(data).digest("hex").slice(0, 12);
}

/**
 * Compose Λ-axis scores for a given inference request against a policy.
 * Returns a composite compliance score (weighted mean over mandatory axes)
 * and a minimal receipt hash.
 *
 * Doctrine v6 §4.8: this operation must complete in ≤ 50 µs (p99).
 */
function composeCompliance(policy: SimulatedPolicy, req: InferenceRequest): CompositeResult {
  let weightedSum = 0;
  let totalWeight = 0;
  const failed: string[] = [];

  for (const clause of policy.clauses) {
    for (const m of clause.lambda_axes) {
      const score = req.axis_scores[m.axis] ?? 0;
      weightedSum += score * m.weight;
      totalWeight += m.weight;
      if (m.enforcement === "mandatory" && score < 0.5) {
        if (!failed.includes(m.axis)) failed.push(m.axis);
      }
    }
  }

  const compositeScore = totalWeight > 0 ? weightedSum / totalWeight : 0;
  const compliant = failed.length === 0 && compositeScore >= 0.5;

  // Stub receipt hash (production: full SHA3-256 Merkle node)
  const receiptData = `${req.request_id}|${compositeScore.toFixed(6)}|${failed.join(",")}`;
  const receiptHash = sha256_6bytes(receiptData);

  return { compliant, composite_score: compositeScore, failed_mandatory_axes: failed, receipt_hash: receiptHash };
}

// ── Benchmark Setup ───────────────────────────────────────────────────────────

function buildPolicy(): SimulatedPolicy {
  const axes = ["Λ1","Λ2","Λ3","Λ4","Λ5","Λ6","Λ7","Λ8","Λ9","Λ10"];
  const clauses: SimulatedClause[] = Array.from({ length: NUM_CLAUSES }, (_, i) => ({
    clause_id: `CLAUSE-${i}`,
    lambda_axes: [
      { axis: axes[i % NUM_AXES], weight: 0.8 + (i % 3) * 0.1, enforcement: "mandatory" },
      { axis: axes[(i + 3) % NUM_AXES], weight: 0.6, enforcement: "recommended" },
    ],
  }));
  return {
    vertical: "healthcare",
    mandatory_axes: ["Λ3", "Λ6", "Λ7"],
    clauses,
  };
}

function buildRequest(i: number): InferenceRequest {
  const scores: Record<string, number> = {};
  const axes = ["Λ1","Λ2","Λ3","Λ4","Λ5","Λ6","Λ7","Λ8","Λ9","Λ10"];
  for (const ax of axes) {
    // Vary scores slightly to prevent CPU branch prediction from trivialising
    scores[ax] = 0.6 + (Math.sin(i + ax.charCodeAt(1)) * 0.3);
  }
  return {
    request_id: `req-${i.toString().padStart(6, "0")}`,
    payload_hash: `ph-${i}`,
    actor_id: `actor-${i % 100}`,
    axis_scores: scores,
  };
}

// ── Percentile Calculator ─────────────────────────────────────────────────────

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
}

// ── Main Benchmark ────────────────────────────────────────────────────────────

function main(): void {
  console.log("=".repeat(60));
  console.log("Doctrine v6 R3 — Composition Overhead Benchmark");
  console.log(`N = ${N.toLocaleString()} compositions | Clauses = ${NUM_CLAUSES} | Axes = ${NUM_AXES}`);
  console.log("=".repeat(60));

  const policy = buildPolicy();
  const latencies: number[] = new Array(N);

  // Warmup: 500 iterations (not measured)
  for (let i = 0; i < 500; i++) {
    composeCompliance(policy, buildRequest(i));
  }

  // Measured iterations
  let compliantCount = 0;
  for (let i = 0; i < N; i++) {
    const req = buildRequest(i);
    const t0 = process.hrtime.bigint();
    const result = composeCompliance(policy, req);
    const t1 = process.hrtime.bigint();
    latencies[i] = Number(t1 - t0);  // nanoseconds
    if (result.compliant) compliantCount++;
  }

  // Convert to microseconds and sort for percentile
  const latenciesUs = latencies.map((ns) => ns / 1000);
  latenciesUs.sort((a, b) => a - b);

  const p50 = percentile(latenciesUs, 50);
  const p95 = percentile(latenciesUs, 95);
  const p99 = percentile(latenciesUs, 99);
  const mean = latenciesUs.reduce((s, v) => s + v, 0) / N;
  const min = latenciesUs[0];
  const max = latenciesUs[latenciesUs.length - 1];

  console.log("\nLatency Results (µs):");
  console.log("─".repeat(40));
  console.log(`  Min   : ${min.toFixed(3)} µs`);
  console.log(`  Mean  : ${mean.toFixed(3)} µs`);
  console.log(`  p50   : ${p50.toFixed(3)} µs`);
  console.log(`  p95   : ${p95.toFixed(3)} µs`);
  console.log(`  p99   : ${p99.toFixed(3)} µs`);
  console.log(`  Max   : ${max.toFixed(3)} µs`);
  console.log("─".repeat(40));
  console.log(`  Compliant requests: ${compliantCount}/${N} (${((compliantCount / N) * 100).toFixed(1)}%)`);

  const budget_p99_us = 50.0; // Doctrine v6 §4.8 budget
  const within_budget = p99 <= budget_p99_us;
  console.log(`\n  Doctrine v6 §4.8 p99 budget: ${budget_p99_us} µs`);
  console.log(`  Budget met: ${within_budget ? "✓ YES" : "✗ NO — requires optimisation"}`);

  console.log("\n=".repeat(60));

  // Histogram (10 buckets)
  const bucketCount = 10;
  const step = (max - min) / bucketCount || 1;
  const buckets = Array(bucketCount).fill(0);
  for (const v of latenciesUs) {
    const b = Math.min(Math.floor((v - min) / step), bucketCount - 1);
    buckets[b]++;
  }
  console.log("Latency Histogram (µs):");
  for (let i = 0; i < bucketCount; i++) {
    const lo = (min + i * step).toFixed(2);
    const hi = (min + (i + 1) * step).toFixed(2);
    const bar = "█".repeat(Math.round((buckets[i] / N) * 40));
    const pct = ((buckets[i] / N) * 100).toFixed(1);
    console.log(`  [${lo} – ${hi}]: ${bar} ${pct}%`);
  }
  console.log("=".repeat(60));
}

main();
