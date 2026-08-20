/**
 * @szl-holdings/a11oy-knowledge — Derivations T1–T10
 * Author: Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · Apache-2.0
 * Source: publications_harvest/niche_mind/INNOVATIONS.md §2
 */
import type { Derivation } from './schema.js';

export const DERIVATIONS: Derivation[] = [
  {
    id: 'T1',
    parents: ['A4', 'A5', 'TH_L4'],
    statement_latex: '\\rho(r_1) \\land \\rho(r_2) \\implies \\rho(r_1 \\circ r_2) \\iff W_1 \\cap W_2 = \\emptyset \\lor \\exists w_3 \\notin W_1 \\cup W_2',
    proof_sketch: 'ρ-closure of composed receipt holds iff witness sets are pairwise disjoint OR a third independent witness co-signs. Follows from A4 (dualWitnessDisjointness) and hash-chain integrity (A6). See INNOVATIONS.md §2 T1.',
    status: 'derived',
    measurability: 'Extend dual-witness.test.ts with 2-receipt composition test cases; assert closure matches disjointness criterion.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T2',
    parents: ['A1_lean', 'A5', 'A6'],
    statement_latex: "r' = r \\oplus e_{\\text{consistent}} \\implies \\Lambda(r') \\geq \\Lambda(r)",
    proof_sketch: 'By Lean A1 (IsMonotone), adding consistent evidence weakly increases all axis scores component-wise, hence the geometric mean weakly increases. Fails under conflicting evidence (gate correctly penalizes inconsistency). See INNOVATIONS.md §2 T2.',
    status: 'derived',
    measurability: 'lambda-gate.test.ts: add consistent and conflicting evidence augmentation test cases.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T3',
    parents: ['A6', 'K01'],
    statement_latex: '\\forall B \\geq 7: \\text{build\\_p50}(\\text{batch}_B) \\in O(\\log B) \\implies \\text{build\\_p50} \\leq 5\\,\\mu s',
    proof_sketch: 'Merkle-DAG depth = ⌈log₂ B⌉. At B=7, depth=3 levels. BLAKE3 per-block ≈ 0.3 µs → total ≈ 2.4 µs amortized. Requires BLAKE3 (not SHA-256). See INNOVATIONS.md §2 T3.',
    status: 'conjectured',
    measurability: 'Benchmark SHA-256 vs BLAKE3 batch in bench.test.ts at B ∈ {1,4,7,16,32}. Expect p50 ≤ 5 µs at B=7.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T4',
    parents: ['A7'],
    statement_latex: 'H(R_n) \\leq \\frac{k \\cdot A}{4 \\ln 2}',
    proof_sketch: 'Data processing inequality: chain entropy ≤ registry entropy ≤ 8A bits. Bekenstein analogy maps registry size to information radius. 49.5% fire-rate (K13) is near-maximum-entropy. Formal proof pending lutar-lean Paper R2. See INNOVATIONS.md §2 T4.',
    status: 'conjectured',
    measurability: 'Measure chain entropy via Shannon estimator on 10,000 receipt hashes. Compare to registry size. Expect H/A ≤ 8 bits/byte.',
    citation: 'https://doi.org/10.5281/zenodo.19944926',
  },
  {
    id: 'T5',
    parents: ['A5', 'A6', 'A8', 'K10'],
    statement_latex: '\\forall i \\in \\{1..5\\}: \\text{root}_i = \\texttt{1ed4d253\\ldots} \\iff \\text{canonical JSON} \\land \\text{pinned PRNG} \\land \\text{frozen registry}',
    proof_sketch: 'SHA-256 is deterministic given fixed input. Canonical JSON: fixed key-sort. PRNG: mulberry32 seed=const. Registry: read-frozen. All Λ computations use Egyptian fractions (integer-representable rationals). QED. See INNOVATIONS.md §2 T5.',
    status: 'proven',
    measurability: 'bench.test.ts already verifies this. Run 5 times; assert all roots equal K10.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T6',
    parents: ['A1_lean', 'A5', 'TH_L1', 'TH_L2'],
    statement_latex: '\\exists x: \\Lambda_i(x) \\geq 0.95 \\text{ for some } i \\land \\Lambda(x) < 0.90',
    proof_sketch: 'Counterexample: x=(0.95, 0.10, 1,1,1,1,1,1,1). GM = (0.095)^(1/9) ≈ 0.770 < 0.90 yet axis_0 = 0.95 ≥ 0.95. Conjunctive AND gate correctly blocks this. See INNOVATIONS.md §2 T6.',
    status: 'proven',
    measurability: 'lambda-gate.test.ts: add axis=(0.95,0.10,1,...) test case; assert gate fails despite high single axis.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T7',
    parents: ['A5', 'A6', 'A7'],
    statement_latex: '\\text{bits\\_leaked}(\\text{mask}) = 9 \\ll 576 \\text{ bits (raw Λ-vector)}',
    proof_sketch: 'The 9-bit mask reveals pass/fail per axis only (not quantitative values). Raw Λ-vector = 9 × 64-bit floats = 576 bits. Privacy reduction = 98.4%. See INNOVATIONS.md §2 T7 (correction: 9 bits, not ⌈log₂ 9⌉=4).',
    status: 'proven',
    measurability: 'Inspect mask construction: assert mask has exactly 9 bits; assert raw scores are not transmitted.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T8',
    parents: ['A4', 'A5', 'A9'],
    statement_latex: '\\text{actor}(r_1) \\neq \\text{actor}(r_2) \\land \\text{digest}(r_1) = \\text{digest}(r_2) \\implies \\rho_{\\text{single-witness}} = \\text{false}',
    proof_sketch: 'Different actors → different canonical JSON → different SHA-256 receipt hashes. Single witness signs both differently. Dual witness required. By A4 + SHA-256 collision resistance. See INNOVATIONS.md §2 T8.',
    status: 'proven',
    measurability: 'dual-witness.test.ts: add same-content-different-actor test; assert single-witness closure fails.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T9',
    parents: ['A5', 'A8', 'TH_L1'],
    statement_latex: '\\Lambda_{\\text{vec}}(\\text{receipt}(e)) \\geq_{\\text{comp}} \\max(\\Lambda_{\\text{floor}}(r_{\\text{src}}), \\Lambda_{\\text{floor}}(r_{\\text{dst}}))',
    proof_sketch: 'Cross-region receipt must pass both source exit policy and destination entry policy. By A5 (soundnessAxiom), the gate only passes if the Λ-vector meets the conjunctive floor. The stricter policy dominates component-wise. See INNOVATIONS.md §2 T9.',
    status: 'derived',
    measurability: 'Vertical policies (Phase 8): each policy.yaml specifies lambda_floors. Cross-region validation asserts T9 holds.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
  },
  {
    id: 'T10',
    parents: ['A9', 'A8'],
    statement_latex: '\\text{SHA256}(\\text{doctrine.json}) = \\text{canonical} \\land \\text{all gates pass} \\implies \\forall p \\in \\text{FP}: p \\notin \\text{artifacts}',
    proof_sketch: 'doctrine-check.sh reads doctrine.json, verifies SHA-256, greps all artifacts for forbidden patterns (FP-1..FP-8). If passes, no pattern present. Conditional on: (a) SHA-256 collision resistance, (b) no admin bypass of CI. See INNOVATIONS.md §2 T10.',
    status: 'proven',
    measurability: 'bash scripts/doctrine-check.sh → expect "[doctrine-check] PASS". Currently verified in demo repo.',
    citation: 'https://github.com/szl-holdings/szl-trust',
  },
];

export const getDerivation = (id: string): Derivation | undefined =>
  DERIVATIONS.find(d => d.id === id);
