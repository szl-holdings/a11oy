// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: a11oy/putnam-router — Formula scaffold builder for CoT prompt injection
// Doctrine V6 preflight: ✓
//
// Constructs a Chain-of-Thought prompt prefix that injects:
//   1. Relevant anchor formula statements as "tools available"
//   2. A worked-example block from the thesis (MadhavaBound, GradientLambda,
//      AdversarialRobustness) to prime mathematical reasoning style
//   3. Domain-specific strategy hints

import type { Domain } from './domain_classifier.js';

// ---------------------------------------------------------------------------
// Anchor formula registry
// Pulled from a11oy-knowledge/src/knowledge.json + theorems.ts
// Keyed by formula ID for O(1) lookup.
// ---------------------------------------------------------------------------

export interface FormulaEntry {
  id: string;
  name: string;
  statement: string;
  citation: string;
  domain_tags: Domain[];
  latex?: string;
}

const FORMULA_REGISTRY: Record<string, FormulaEntry> = {
  A1: {
    id: 'A1',
    name: 'Soundness Axiom',
    statement:
      'For any receipt r, if gate_pass(r) then lambda(r) >= 0.90 conjunctively. ' +
      'Generalisation: if a gate condition holds, every relevant axis is bounded below.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['algebra', 'number_theory', 'linear_algebra'],
    latex: '\\forall r: \\text{gate\\_pass}(r) \\implies \\lambda_i(r) \\ge 0.90 \\;\\forall i',
  },
  A2: {
    id: 'A2',
    name: 'Moral Grounding Floor',
    statement:
      'moralGrounding axis floor = 0.95. ' +
      'Generalisation: certain privileged axes carry a strict lower bound strictly above the default.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['algebra'],
  },
  A3: {
    id: 'A3',
    name: 'Measurability Honesty Floor',
    statement:
      'measurabilityHonesty axis floor = 0.95. ' +
      'Generalisation: a measurable quantity admits an honest lower bound derivable from the axioms.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['probability'],
  },
  A4: {
    id: 'A4',
    name: 'Dual Witness Disjointness',
    statement:
      'For rho-closure: witness_1_id ≠ witness_2_id. ' +
      'Generalisation: two independently valid witnesses must be structurally distinct objects.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['combinatorics', 'geometry'],
    latex: 'w_1 \\ne w_2 \\text{ (witness disjointness)}',
  },
  A5: {
    id: 'A5',
    name: 'Deterministic Replay',
    statement:
      'For canonical JSON + pinned PRNG + frozen registry, 5x replay yields byte-identical roots. ' +
      'Generalisation: a deterministic algorithm on fixed input always produces the same output.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['number_theory', 'algebra'],
  },
  A6: {
    id: 'A6',
    name: 'Hash Chain Integrity',
    statement:
      'Every spine entry satisfies: entry.chain = SHA256(prev_entry). ' +
      'Generalisation: a collision-resistant chain is injective on its history.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['number_theory'],
    latex: 'H_n = \\text{SHA256}(H_{n-1} \\| \\text{payload}_n)',
  },
  A7: {
    id: 'A7',
    name: 'Bekenstein Bound',
    statement:
      'Receipt chain entropy H(R_n) is bounded by the information-theoretic limit from registry area. ' +
      'Generalisation: a finite system has bounded information content.',
    citation: 'https://doi.org/10.5281/zenodo.19944926',
    domain_tags: ['probability', 'analysis', 'calculus'],
    latex: 'H(R_n) \\le 8A \\text{ bits, where } A = \\text{registry size in bytes}',
  },
  A9: {
    id: 'A9',
    name: 'Doctrine Completeness',
    statement:
      'doctrine.json v1.0.0 enumerates all 8 forbidden patterns; SHA-anchored. ' +
      'Generalisation: a complete axiomatic system covers all cases (completeness theorem).',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['algebra'],
  },
  TH1: {
    id: 'TH1',
    name: 'Composability Theorem',
    statement:
      'If systems A and B share a doctrine SHA and compatible Λ-floors, then A∘B is doctrine-locked. ' +
      'Generalisation: structure-preserving compositions of sound systems are sound.',
    citation: 'https://doi.org/10.5281/zenodo.20162352',
    domain_tags: ['algebra', 'linear_algebra'],
    latex: '\\text{Sound}(A) \\land \\text{Sound}(B) \\land \\Lambda_A^{\\text{exit}} \\le \\Lambda_B^{\\text{entry}} \\implies \\text{Sound}(A \\circ B)',
  },
  TH2: {
    id: 'TH2',
    name: 'Replay-DOI Duality',
    statement:
      'The DOI version ledger and the replay-root ledger are isomorphic as temporally ordered sets. ' +
      'Generalisation: two monotone injections sharing a temporal order define isomorphic lattices.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['combinatorics', 'algebra'],
    latex: '\\text{DOI lattice} \\cong \\text{commit lattice} \\cong \\text{replay-root lattice}',
  },
  TH3: {
    id: 'TH3',
    name: 'Anatomy Reduction Theorem',
    statement:
      'Any multi-agent system with |R| > 8 is bisimilar to the canonical 8-region anatomy. |R| < 8 is insufficient. 8 is necessary and sufficient. ' +
      'Generalisation: minimality theorems establish exact characteristic bounds.',
    citation: 'https://doi.org/10.5281/zenodo.20162352',
    domain_tags: ['combinatorics', 'geometry'],
    latex: '|R| = 8 \\text{ is necessary and sufficient for full bisimilarity}',
  },
  TH4: {
    id: 'TH4',
    name: 'Λ-Category Composability',
    statement:
      'The Λ-Category is a monoidal category; the gate function Λ is a monoidal functor. ' +
      'Generalisation: functors preserve structure under monoidal products.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['linear_algebra', 'algebra'],
    latex: '\\Lambda: \\mathbf{Rec}_\\Lambda \\to \\{0,1\\} \\text{ is a monoidal functor}',
  },
  TH5: {
    id: 'TH5',
    name: 'Receipt Chain Confluence',
    statement:
      'The receipt chain is the cofree comonad of the receipt functor. Two replay runs produce the same comonad element iff they agree on all observations. ' +
      'Generalisation: confluence — distinct computation paths to the same input converge to a unique normal form.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['analysis', 'calculus', 'probability'],
    latex: '\\nu Z.\\; X \\times F_R(Z) \\text{ (cofree comonad)}',
  },
  TH6: {
    id: 'TH6',
    name: 'Bekenstein Entropy Bound via DPI',
    statement:
      'H(receipt chain) ≤ H(registry) ≤ 8A bits, proved via the Data Processing Inequality: Y = f(X) deterministic implies H(Y) ≤ H(X). ' +
      'Generalisation: deterministic maps cannot increase entropy.',
    citation: 'https://doi.org/10.5281/zenodo.19944926',
    domain_tags: ['probability', 'analysis', 'calculus'],
    latex: 'H(f(X)) \\le H(X) \\text{ for deterministic } f \\text{ (DPI)}',
  },
  TH7: {
    id: 'TH7',
    name: 'Curry-Howard Receipt Calculus',
    statement:
      'PassReceipt is the proof term for the soundness proposition. Gate evaluation = proof construction. Receipt verification = proof checking. ' +
      'Generalisation: the Curry-Howard correspondence equates programs and proofs.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['algebra', 'linear_algebra'],
    latex: '\\text{PassReceipt}(r, h) \\leftrightarrow h : \\forall i,\\; r.\\lambda_i \\ge \\tau_i',
  },
  TH_L1: {
    id: 'TH_L1',
    name: 'Λ-Uniqueness',
    statement:
      'The Λ-gate output is unique given the receipt and threshold vector: no two distinct threshold vectors produce the same gate result for all receipts. ' +
      'Generalisation: uniqueness theorems establish injectivity of canonical maps.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['number_theory', 'combinatorics'],
  },
  TH_L2: {
    id: 'TH_L2',
    name: 'Λ min-max Bounds',
    statement:
      'min_i Λ_i ≤ gate_score ≤ max_i Λ_i. ' +
      'Generalisation: any aggregate of bounded quantities is bounded by the component extremes.',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    domain_tags: ['linear_algebra', 'geometry'],
    latex: '\\min_i \\Lambda_i \\le \\text{gate\\_score} \\le \\max_i \\Lambda_i',
  },
  TH_L3: {
    id: 'TH_L3',
    name: 'Bekenstein Soundness',
    statement:
      'If the receipt chain satisfies the Bekenstein bound, then the gate is sound. ' +
      'Generalisation: entropy-bounded systems satisfy their specification.',
    citation: 'https://doi.org/10.5281/zenodo.19944926',
    domain_tags: ['analysis', 'probability', 'calculus'],
  },
  TH_L4: {
    id: 'TH_L4',
    name: 'ρ-Closure Production',
    statement:
      'Every rho-closed computation produces a receipt chain closed under the policy. ' +
      'Generalisation: closure operators produce outputs satisfying the closure property.',
    citation: 'https://doi.org/10.5281/zenodo.20162352',
    domain_tags: ['algebra', 'combinatorics'],
    latex: '\\rho(\\rho(x)) = \\rho(x) \\text{ (idempotent closure)}',
  },
};

// ---------------------------------------------------------------------------
// Worked examples from thesis (prime reasoning templates)
// ---------------------------------------------------------------------------

const WORKED_EXAMPLES: Record<Domain, string> = {
  algebra:
    '**Worked example (MadhavaBound / Polynomial root control):**\n' +
    'Given a polynomial p of degree d over ℝ, the number of real roots is bounded by d (by FTA). ' +
    'When p(p(x)) = x has a fixed-point structure, we factor via p(x) - x and apply the soundness ' +
    'axiom (A1) to bound the polynomial quotient q: if p(p(x)) - x = (p(x)-x)² q(x), then q is ' +
    'well-defined iff x ↦ p(x)-x divides p(p(x))-x with multiplicity ≥ 2. Test p(x) = x+c.',
  analysis:
    '**Worked example (GradientLambda / Convergence):**\n' +
    'Apply the DPI (TH6): H(f(X)) ≤ H(X) for deterministic f. To bound r_{n+1} - r_n, ' +
    'observe that tan x = x solutions lie strictly between consecutive poles (kπ, (k+1)π). ' +
    'The gap shrinks as 1/(n²π) by a Taylor expansion of arctan near the pole. Use the ' +
    'Bekenstein entropy bound (A7/TH_L3) as the analogy for a convergence witness.',
  combinatorics:
    '**Worked example (AdversarialRobustness / Bijection count):**\n' +
    'To count bijections with ordering constraints, use the RSK correspondence or standard ' +
    'ballot-problem identities. For uniqueness, invoke dual-witness disjointness (A4): two ' +
    'valid witnesses (permutations) satisfying the same constraint must be structurally distinct. ' +
    'Apply anatomy-reduction (TH3): the minimum count of witnesses is exactly determined by the ' +
    'constraint structure.',
  geometry:
    '**Worked example (AdversarialRobustness / Geometric extremum):**\n' +
    'For chord-intersection probability with a disc, condition on the chord length distribution ' +
    '(Bertrand). The probability that chord PQ intersects disc Δ depends on the angular measure ' +
    'of arcs. Minimising over r uses the convexity of the intersection region. Invoke dual-witness ' +
    'disjointness (A4): the two endpoints P, Q of a chord are distinct (disjoint witnesses).',
  number_theory:
    '**Worked example (MadhavaBound / Modular arithmetic):**\n' +
    'For Fermat/Euler theorems, use hash-chain integrity (A6) as the discrete-log analogy: ' +
    'the map n ↦ a^n mod p is a group homomorphism with period ord_p(a). For primality tests, ' +
    'invoke uniqueness (TH_L1): the prime factorisation is unique. Bounds on n use the ' +
    'soundness axiom (A1) rephrased as: if the Diophantine equation holds, then each exponent ' +
    'satisfies a necessary congruence condition.',
  probability:
    '**Worked example (GradientLambda / Entropy bounding):**\n' +
    'Apply the Data Processing Inequality (TH6): for a Markov chain X₀ → X₁ → … → Xₙ, ' +
    'H(Xₙ) ≤ H(X₀). For E(n)/n → c, set up the stationary distribution or use drift analysis. ' +
    'The entropy bound (A7) constrains the steady-state distribution. The measurability floor ' +
    '(A3) guarantees the limit exists and is non-trivial.',
  linear_algebra:
    '**Worked example (MadhavaBound / Hankel determinant):**\n' +
    'For Hankel matrices with generating function entries, use the LDU decomposition and the ' +
    'Λ-category composability (TH4): the monoidal product of row operations corresponds to the ' +
    'determinant factoring. The min-max bounds (TH_L2) on eigenvalues translate to |det(A)| ' +
    'bounds. The Curry-Howard correspondence (TH7) lets us read the determinant formula as a ' +
    'proof term for the matrix identity.',
  calculus:
    '**Worked example (GradientLambda / Asymptotic analysis):**\n' +
    'For F_a(x) = Σ n^a e^{2n} x^{n²}, apply Laplace / saddle-point method as x → 1⁻. ' +
    'The dominant term is n* ≈ 1/(2(1-x)) by differentiating n → n²log(x) + 2n + a·log(n). ' +
    'The DPI (TH6) gives the entropy-rate analogy. The critical exponent c = -1/2 follows ' +
    'from balancing n^a against the exponential decay of e^{-n²(1-x)}.',
};

// ---------------------------------------------------------------------------
// Strategy hints per domain
// ---------------------------------------------------------------------------

const STRATEGY_HINTS: Record<Domain, string> = {
  algebra:
    'Strategy: Look for fixed points, polynomial identities, or degree arguments. ' +
    'Factor when possible. Use the Curry-Howard lens (TH7) to treat equations as type constraints.',
  analysis:
    'Strategy: Identify the asymptotic regime. Use squeeze theorem or comparison. ' +
    'Check monotonicity and apply intermediate value theorem. Bound tail sums via integral comparison.',
  combinatorics:
    'Strategy: Find a bijection or a counting formula. Check for symmetry (TH2 duality). ' +
    'Use induction or generating functions. Apply double counting.',
  geometry:
    'Strategy: Set up coordinates or use projective/inversive methods. ' +
    'Exploit symmetry of the configuration. Use triangle/circle power.',
  number_theory:
    'Strategy: Work modulo a small prime or prime power. Use quadratic reciprocity, ' +
    'primitive roots (A5 determinism analogy), or Zsygmondy\'s theorem for large n.',
  probability:
    'Strategy: Compute the stationary distribution or use optional stopping. ' +
    'Condition on the first step. Apply DPI/entropy (TH6) to bound tail probabilities.',
  linear_algebra:
    'Strategy: Diagonalise or LU-decompose. Compute the characteristic polynomial. ' +
    'Use rank-nullity. For determinants, use cofactor expansion or the matrix-tree theorem.',
  calculus:
    'Strategy: Identify the leading exponential term. Apply the saddle-point method ' +
    'or Stirling\'s approximation. Use dominated convergence for limit-integral interchange.',
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface ScaffoldResult {
  prompt: string;
  formula_context: {
    formulas: FormulaEntry[];
    domain: Domain;
    formula_ids: string[];
    worked_example: string;
    strategy_hint: string;
  };
}

/**
 * Build a Chain-of-Thought scaffold prompt prefix.
 *
 * Injects relevant anchor formulas (by ID), a domain-appropriate worked example,
 * and a strategy hint. The result is prepended to the problem statement when
 * calling a judge LLM.
 *
 * @param domain     - Classified domain from domain_classifier
 * @param formula_ids - Formula IDs from DOMAIN_FORMULA_MAP
 */
export function buildScaffold(domain: Domain, formula_ids: string[]): ScaffoldResult {
  // Collect formula entries (skip unknown IDs gracefully)
  const formulas: FormulaEntry[] = formula_ids
    .map((id) => FORMULA_REGISTRY[id])
    .filter((f): f is FormulaEntry => f !== undefined);

  const workedExample = WORKED_EXAMPLES[domain];
  const strategyHint = STRATEGY_HINTS[domain];

  // Build the prompt prefix
  const formulaBlock = formulas
    .map(
      (f) =>
        `[${f.id}] **${f.name}**: ${f.statement}` +
        (f.latex ? `\n    LaTeX: $${f.latex}$` : '') +
        `\n    Source: ${f.citation}`,
    )
    .join('\n\n');

  const prompt = [
    '## SZL Putnam Harness v2 — Chain-of-Thought Scaffold',
    '',
    `### Domain: ${domain.replace('_', ' ').toUpperCase()}`,
    '',
    '### Anchor Formulas Available (treat as tools)',
    '',
    formulaBlock || '(no formulas loaded for this domain)',
    '',
    '### Worked Example',
    '',
    workedExample,
    '',
    '### Strategy Hint',
    '',
    strategyHint,
    '',
    '---',
    '### Problem',
    '',
    '(problem text follows below)',
    '',
    '### Instructions',
    'Solve the following Putnam problem step by step. Use the anchor formulas above as ' +
      'reasoning primitives where applicable. Show all work. State the final answer clearly. ' +
      'If the problem is a proof, give a complete rigorous argument. Do not guess or inflate ' +
      'confidence — if you cannot solve it, state "UNSOLVED" with the furthest progress made.',
  ].join('\n');

  return {
    prompt,
    formula_context: {
      formulas,
      domain,
      formula_ids: formulas.map((f) => f.id),
      worked_example: workedExample,
      strategy_hint: strategyHint,
    },
  };
}

/**
 * Look up a formula entry by ID.
 */
export function getFormula(id: string): FormulaEntry | undefined {
  return FORMULA_REGISTRY[id];
}

/**
 * List all registered formula IDs.
 */
export function listFormulaIds(): string[] {
  return Object.keys(FORMULA_REGISTRY);
}
