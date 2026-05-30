// SPDX-License-Identifier: Apache-2.0
// Author: Lutar, Stephen P. | ORCID 0009-0001-0110-4173 | SZL Holdings
// Module: a11oy/putnam-router — Domain classifier for Putnam problem routing
// Doctrine V6 preflight: ✓
//
// Series-A defensible baseline: keyword heuristics with soft scoring.
// LLM-based routing is post-MVP (Tier 3.5 P8).
// Each domain maps to relevant anchor formula IDs from knowledge.json + theorems.ts.

export type Domain =
  | 'algebra'
  | 'analysis'
  | 'combinatorics'
  | 'geometry'
  | 'number_theory'
  | 'probability'
  | 'linear_algebra'
  | 'calculus';

export const ALL_DOMAINS: readonly Domain[] = [
  'algebra',
  'analysis',
  'combinatorics',
  'geometry',
  'number_theory',
  'probability',
  'linear_algebra',
  'calculus',
] as const;

// ---------------------------------------------------------------------------
// Keyword → domain signal weight table
// Lower-case match against normalised problem text.
// Weight ∈ (0, 1]; cumulative per domain, then normalised.
// ---------------------------------------------------------------------------

interface KeywordRule {
  pattern: RegExp;
  domain: Domain;
  weight: number;
}

const KEYWORD_RULES: KeywordRule[] = [
  // ALGEBRA
  { pattern: /\bpolynomial\b/gi,       domain: 'algebra',       weight: 0.9 },
  { pattern: /\bpolynomials\b/gi,      domain: 'algebra',       weight: 0.9 },
  { pattern: /\bfactori[sz]e\b/gi,     domain: 'algebra',       weight: 0.7 },
  { pattern: /\broot[s]?\b/gi,         domain: 'algebra',       weight: 0.5 },
  { pattern: /\bequation[s]?\b/gi,     domain: 'algebra',       weight: 0.4 },
  { pattern: /\bfunction[s]?\b/gi,     domain: 'algebra',       weight: 0.3 },
  { pattern: /\breal polynomial/gi,    domain: 'algebra',       weight: 1.0 },
  { pattern: /\binequality\b/gi,       domain: 'algebra',       weight: 0.5 },
  { pattern: /\bsymmetric\b/gi,        domain: 'algebra',       weight: 0.4 },

  // ANALYSIS
  { pattern: /\bintegral\b/gi,         domain: 'analysis',      weight: 0.9 },
  { pattern: /\bconvergent?\b/gi,      domain: 'analysis',      weight: 0.8 },
  { pattern: /\bseries\b/gi,           domain: 'analysis',      weight: 0.7 },
  { pattern: /\bsequence[s]?\b/gi,     domain: 'analysis',      weight: 0.5 },
  { pattern: /\blimit\b/gi,            domain: 'analysis',      weight: 0.7 },
  { pattern: /\bcontinuous\b/gi,       domain: 'analysis',      weight: 0.7 },
  { pattern: /\bdifferentiab/gi,       domain: 'analysis',      weight: 0.8 },
  { pattern: /\btan x = x\b/gi,        domain: 'analysis',      weight: 1.0 },
  { pattern: /\bsupremum\b/gi,         domain: 'analysis',      weight: 0.8 },
  { pattern: /\binfimum\b/gi,          domain: 'analysis',      weight: 0.8 },
  { pattern: /\bcauchy\b/gi,           domain: 'analysis',      weight: 0.8 },
  { pattern: /\buniformly?\b/gi,       domain: 'analysis',      weight: 0.5 },
  { pattern: /\bpower series\b/gi,     domain: 'analysis',      weight: 0.9 },

  // COMBINATORICS
  { pattern: /\bcombinator\w*/gi,      domain: 'combinatorics', weight: 0.9 },
  { pattern: /\bbijection[s]?\b/gi,    domain: 'combinatorics', weight: 0.9 },
  { pattern: /\bpermutation[s]?\b/gi,  domain: 'combinatorics', weight: 0.9 },
  { pattern: /\bgraph\b/gi,            domain: 'combinatorics', weight: 0.6 },
  { pattern: /\bcoloring\b/gi,         domain: 'combinatorics', weight: 0.8 },
  { pattern: /\btiling\b/gi,           domain: 'combinatorics', weight: 0.8 },
  { pattern: /\bcounting\b/gi,         domain: 'combinatorics', weight: 0.7 },
  { pattern: /\bsequence.*rearranged/gi,domain: 'combinatorics',weight: 0.8 },
  { pattern: /\bn-by-n grid\b/gi,      domain: 'combinatorics', weight: 0.9 },
  { pattern: /\bpolynomial.*coefficients/gi, domain: 'combinatorics', weight: 0.6 },

  // GEOMETRY
  { pattern: /\bgeometr\w*/gi,         domain: 'geometry',      weight: 0.9 },
  { pattern: /\bcircle[s]?\b/gi,       domain: 'geometry',      weight: 0.8 },
  { pattern: /\btriangle[s]?\b/gi,     domain: 'geometry',      weight: 0.8 },
  { pattern: /\bquadrilateral[s]?\b/gi,domain: 'geometry',      weight: 0.9 },
  { pattern: /\bvertex\b/gi,           domain: 'geometry',      weight: 0.6 },
  { pattern: /\bvertices\b/gi,         domain: 'geometry',      weight: 0.7 },
  { pattern: /\bconvex\b/gi,           domain: 'geometry',      weight: 0.7 },
  { pattern: /\bperpendicular\b/gi,    domain: 'geometry',      weight: 0.8 },
  { pattern: /\bbisector\b/gi,         domain: 'geometry',      weight: 0.8 },
  { pattern: /\bchord\b/gi,            domain: 'geometry',      weight: 0.8 },
  { pattern: /\bradius\b/gi,           domain: 'geometry',      weight: 0.6 },
  { pattern: /\breflection\b/gi,       domain: 'geometry',      weight: 0.7 },

  // NUMBER THEORY
  { pattern: /\bprime[s]?\b/gi,        domain: 'number_theory', weight: 0.9 },
  { pattern: /\bcongruence\b/gi,       domain: 'number_theory', weight: 0.9 },
  { pattern: /\bdivisible\b/gi,        domain: 'number_theory', weight: 0.8 },
  { pattern: /\bdivisibility\b/gi,     domain: 'number_theory', weight: 0.8 },
  { pattern: /\bmod\b/gi,              domain: 'number_theory', weight: 0.7 },
  { pattern: /\bmodular\b/gi,          domain: 'number_theory', weight: 0.8 },
  { pattern: /\binteger[s]?\b/gi,      domain: 'number_theory', weight: 0.4 },
  { pattern: /\bpositive integer[s]?\b/gi, domain: 'number_theory', weight: 0.6 },
  { pattern: /\bdiophantine\b/gi,      domain: 'number_theory', weight: 1.0 },
  { pattern: /\bgcd\b/gi,              domain: 'number_theory', weight: 0.9 },
  { pattern: /\bfermats?\b/gi,         domain: 'number_theory', weight: 0.9 },

  // PROBABILITY
  { pattern: /\bprobability\b/gi,      domain: 'probability',   weight: 0.9 },
  { pattern: /\bprobabilit\w*/gi,      domain: 'probability',   weight: 0.9 },
  { pattern: /\brandom\b/gi,           domain: 'probability',   weight: 0.8 },
  { pattern: /\bexpected value\b/gi,   domain: 'probability',   weight: 0.9 },
  { pattern: /\buniformly at random\b/gi, domain: 'probability', weight: 1.0 },
  { pattern: /\bmarkov\b/gi,           domain: 'probability',   weight: 0.9 },
  { pattern: /\bstochastic\b/gi,       domain: 'probability',   weight: 0.9 },
  { pattern: /\bindependent\b/gi,      domain: 'probability',   weight: 0.5 },
  { pattern: /\bvariance\b/gi,         domain: 'probability',   weight: 0.8 },

  // LINEAR ALGEBRA
  { pattern: /\bmatrix\b/gi,           domain: 'linear_algebra',weight: 0.9 },
  { pattern: /\bmatrices\b/gi,         domain: 'linear_algebra',weight: 0.9 },
  { pattern: /\bdeterminant\b/gi,      domain: 'linear_algebra',weight: 0.9 },
  { pattern: /\beigenvalue[s]?\b/gi,   domain: 'linear_algebra',weight: 0.9 },
  { pattern: /\bvector\b/gi,           domain: 'linear_algebra',weight: 0.6 },
  { pattern: /\blinear\b/gi,           domain: 'linear_algebra',weight: 0.5 },
  { pattern: /\btrace\b/gi,            domain: 'linear_algebra',weight: 0.7 },
  { pattern: /\brunks?\b/gi,           domain: 'linear_algebra',weight: 0.8 },
  { pattern: /\bn-by-n matrix\b/gi,    domain: 'linear_algebra',weight: 1.0 },
  { pattern: /\bhankel\b/gi,           domain: 'linear_algebra',weight: 1.0 },

  // CALCULUS
  { pattern: /\bderivative\b/gi,       domain: 'calculus',      weight: 0.9 },
  { pattern: /\bdifferential\b/gi,     domain: 'calculus',      weight: 0.8 },
  { pattern: /\bpartial\b/gi,          domain: 'calculus',      weight: 0.7 },
  { pattern: /\bgradient\b/gi,         domain: 'calculus',      weight: 0.8 },
  { pattern: /\boptimiz\w*/gi,         domain: 'calculus',      weight: 0.6 },
  { pattern: /\blaplacian\b/gi,        domain: 'calculus',      weight: 0.8 },
  { pattern: /\btaylor\b/gi,           domain: 'calculus',      weight: 0.7 },
];

// ---------------------------------------------------------------------------
// Anchor formula IDs from a11oy-knowledge, keyed by domain
// Maps to: axioms (A1–A9), theorems (TH1–TH7), Lean-theorems (TH_L1–TH_L4)
// that are most relevant to each mathematical domain.
// ---------------------------------------------------------------------------

export const DOMAIN_FORMULA_MAP: Record<Domain, string[]> = {
  algebra: [
    'A1',   // soundnessAxiom — bound logic, analogous to algebraic inequalities
    'TH4',  // lambda_category_composability — algebraic structure (monoidal)
    'TH7',  // curry_howard_receipt_calculus — type-theoretic / algebraic foundation
    'A9',   // doctrineCompleteness — completeness argument
  ],
  analysis: [
    'TH_L3', // bekenstein_soundness — bounding/limiting argument
    'TH6',   // bekenstein_entropy_bound_dpi — data processing inequality (limit/bound)
    'A7',    // bekensteinBound — entropy bound analogous to convergence bounds
    'TH5',   // receipt_chain_confluence — confluence = convergence analogy
  ],
  combinatorics: [
    'A4',    // dualWitnessDisjointness — counting distinct witnesses
    'TH2',   // replay_doi_duality — bijection argument (isomorphism of ordered sets)
    'TH_L1', // Λ_uniqueness — uniqueness counting
    'TH3',   // anatomy_reduction — necessary/sufficient (8 = min)
  ],
  geometry: [
    'TH3',   // anatomy_reduction — spatial/structural necessity argument
    'A4',    // dualWitnessDisjointness — disjoint witnesses (geometric regions)
    'TH_L2', // Λ_min_max_bounds — bounding in geometric space
  ],
  number_theory: [
    'A5',    // deterministicReplay — modular arithmetic analogies (determinism mod p)
    'A6',    // hashChainIntegrity — SHA-256 (modular hash)
    'TH_L1', // Λ_uniqueness — unique factorisation analogy
    'A1',    // soundnessAxiom — primality / completeness
  ],
  probability: [
    'TH6',   // bekenstein_entropy_bound_dpi — data processing inequality
    'A7',    // bekensteinBound — entropy / information bound
    'TH5',   // receipt_chain_confluence — Markov chain / convergence
    'TH_L3', // bekenstein_soundness — measure-theoretic bound
    'A3',    // measurabilityHonestyFloor — measurability axiom
  ],
  linear_algebra: [
    'TH4',   // lambda_category_composability — monoidal / linear-algebraic structure
    'TH_L2', // Λ_min_max_bounds — spectral bound analogy
    'TH7',   // curry_howard_receipt_calculus — type-theory ↔ linear algebra via CHC
    'A1',    // soundnessAxiom — gate matrix (Λ-vector ≥ threshold)
  ],
  calculus: [
    'TH_L3', // bekenstein_soundness — integral / asymptotic bound
    'TH6',   // bekenstein_entropy_bound_dpi — DPI (chain rule for derivatives analogy)
    'A7',    // bekensteinBound — limit-based argument
    'TH5',   // receipt_chain_confluence — convergence to normal form
  ],
};

// ---------------------------------------------------------------------------
// Classifier core
// ---------------------------------------------------------------------------

export interface DomainScores {
  algebra: number;
  analysis: number;
  combinatorics: number;
  geometry: number;
  number_theory: number;
  probability: number;
  linear_algebra: number;
  calculus: number;
}

export interface ClassificationResult {
  domain: Domain;
  confidence: number;
  scores: DomainScores;
  formula_ids: string[];
  matched_keywords: string[];
}

/**
 * Classify the mathematical domain of a Putnam problem.
 *
 * Returns the top domain, its confidence (normalised to [0,1] over all
 * domain scores), the full score vector, and relevant anchor formula IDs.
 *
 * @param text - Raw problem text (plain text or LaTeX)
 */
export function classifyDomain(text: string): ClassificationResult {
  const scores: DomainScores = {
    algebra: 0,
    analysis: 0,
    combinatorics: 0,
    geometry: 0,
    number_theory: 0,
    probability: 0,
    linear_algebra: 0,
    calculus: 0,
  };

  const matched_keywords: string[] = [];

  for (const rule of KEYWORD_RULES) {
    const matches = text.match(rule.pattern);
    if (matches && matches.length > 0) {
      // Diminishing returns: sqrt(count) weighting
      const contribution = rule.weight * Math.sqrt(matches.length);
      scores[rule.domain] += contribution;
      matched_keywords.push(...matches.map((m) => m.toLowerCase()));
    }
  }

  // Deduplicate matched keywords
  const unique_keywords = [...new Set(matched_keywords)];

  // Find top domain
  const entries = Object.entries(scores) as [Domain, number][];
  entries.sort(([, a], [, b]) => b - a);
  const [topDomain, topScore] = entries[0]!;
  const totalScore = entries.reduce((s, [, v]) => s + v, 0);

  // Normalise confidence (0 if no signal at all)
  const confidence = totalScore > 0 ? topScore / totalScore : 0;

  return {
    domain: topDomain,
    confidence,
    scores,
    formula_ids: DOMAIN_FORMULA_MAP[topDomain],
    matched_keywords: unique_keywords,
  };
}

/**
 * Classify and return only the top domain string (convenience wrapper).
 */
export function topDomain(text: string): Domain {
  return classifyDomain(text).domain;
}
