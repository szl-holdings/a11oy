/**
 * @szl-holdings/a11oy-knowledge — TypeScript schema types
 * Author: Lutar, Stephen P. <stephen@szlholdings.com>
 * ORCID: 0009-0001-0110-4173
 * License: Apache-2.0
 */

export type Maturity = 'proven' | 'measured' | 'defined' | 'conjectured';

export interface Axiom {
  id: string;           // A1..A14
  name: string;
  statement: string;
  source_file: string;
  source_section?: string;
  maturity: Maturity;
  citation: string;     // DOI or URL
  lean_ref?: string;    // lean file path if machine-checked
  floor?: number;       // for Λ-axis axioms: the floor value
}

export interface Theorem {
  id: string;           // TH_L1..TH_L4, TH1..TH3
  name: string;
  statement: string;
  source_file: string;
  maturity: Maturity;
  citation: string;
  proof_sketch?: string;
  sorry_count?: number; // 0 = fully discharged
}

export interface Derivation {
  id: string;           // T1..T10
  parents: string[];    // IDs of parent axioms/theorems
  statement_latex: string;
  proof_sketch: string;
  status: 'proven' | 'derived' | 'conjectured' | 'disproved';
  measurability: string; // "run X on input Y, expect Z"
  citation?: string;
}

export interface CanonicalConstant {
  id: string;           // K01..K13
  name: string;
  value: string;
  unit?: string;
  ops_per_sec?: string;
  source: string;
  doi?: string;
  maturity: Maturity;
}

export interface DOIEntry {
  doi: string;
  url: string;
  version?: string;
  role?: string;
  date?: string;
  license?: string;
}

export interface DoctrineClause {
  id: string;           // DC1..DC8
  clause: string;
  source: string;
}

export interface ProposedAxiom extends Axiom {
  why_not_subsumed: string;
  function_signature: string;
  falsifiability_test: string;
}

export interface VerticalPolicy {
  id: string;
  name: string;
  regulations: string[];
  required_attestors: string[];
  lambda_floors: Record<string, number>;  // axis → floor
  primitives_applicable: string[];        // axiom/theorem/derivation IDs
  policy_yaml_path: string;
  acv_range_usd: { low: number; mid: number; high: number };
  sales_cycle_months: number;
}

export interface KnowledgeGraph {
  version: string;
  byline: string;
  orcid: string;
  generated_at: string;
  axioms: Axiom[];
  theorems: Theorem[];
  derivations: Derivation[];
  proposed_axioms: ProposedAxiom[];
  new_theorems: Theorem[];
  canonical_constants: CanonicalConstant[];
  dois: DOIEntry[];
  doctrine_clauses: DoctrineClause[];
  verticals: VerticalPolicy[];
}
