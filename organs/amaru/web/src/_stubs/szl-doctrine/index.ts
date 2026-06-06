export interface ThesisLineageEntry {
  id: string;
  title: string;
  status: string;
  version: string;
  doi?: string;
  arxiv?: string;
  zenodo?: string;
  abstract: string;
  children?: string[];
}

export interface ThesisPaper {
  key: string;
  title: string;
  authors: string[];
  year: number;
  doi?: string;
  arxiv?: string;
  zenodo?: string;
  journal?: string;
  status: string;
  abstract: string;
  theorems: string[];
  auditCounters: { proven: number; conjectured: number; open: number };
}

export const THESIS_LINEAGE: ThesisLineageEntry[] = [
  { id: 'TH1', title: 'Bounded-recursion runtime', status: 'published (v18.0)', version: '18.0', doi: '10.5281/zenodo.20434276', abstract: 'Ouroboros bounded-loop runtime — Banach contraction convergence proof.' },
  { id: 'TH2', title: 'POVM completeness', status: 'published', version: '18.0', abstract: 'POVM completeness Σ E_i = I for governance measurement operators.' },
  { id: 'TH3', title: 'KS-18 contextuality', status: 'published', version: '18.0', abstract: 'Kochen-Specker 18-vector 2-regular cover impossibility proof.' },
  { id: 'TH4', title: 'Fisher-Rao metric', status: 'published', version: '18.0', abstract: 'Fisher-Rao geodesic distance on simplex for governance drift.' },
  { id: 'TH5', title: 'Bohr complementarity floor', status: 'published', version: '18.0', abstract: 'Bohr floor σ_A·σ_B ≥ 0.25 − ε on conjugate governance axes.' },
  { id: 'TH6', title: 'Shor error correction', status: 'published', version: '18.0', abstract: 'Shor 9-qubit code for provenance hash error correction.' },
  { id: 'TH7', title: 'Lamport causal ordering', status: 'published', version: '18.0', abstract: 'Lamport clock timestamps for causal ordering across receipt chains.' },
  { id: 'TH8', title: 'Convergent data sync', status: 'published', version: '18.0', doi: '10.5281/zenodo.20434276', abstract: 'Amaru convergent multi-source data sync with Proof-Chain receipts.' },
];

export const THESIS_PAPERS: ThesisPaper[] = [
  {
    key: 'TH1-TH3',
    title: 'Bounded recursion, POVM completeness, and KS-18 contextuality',
    authors: ['Lutar, Stephen P.'],
    year: 2026,
    doi: '10.5281/zenodo.20434276',
    status: 'published',
    abstract: 'Chapters 1-3 of the Ouroboros thesis: bounded-recursion runtime with Banach contraction convergence, POVM measurement completeness, and Kochen-Specker 18-vector contextuality proof.',
    theorems: ['Banach contraction', 'POVM completeness', 'KS-18 2-cover', 'KS-18 unsatisfiability'],
    auditCounters: { proven: 4, conjectured: 0, open: 0 },
  },
  {
    key: 'TH4-TH7',
    title: 'Fisher-Rao geodesics, Bohr floor, Shor ECC, Lamport ordering',
    authors: ['Lutar, Stephen P.'],
    year: 2026,
    status: 'published',
    abstract: 'Chapters 4-7: Fisher-Rao metric on the probability simplex, Bohr complementarity floor for conjugate governance measurements, Shor 9-qubit code for provenance hashes, Lamport clock for causal receipt ordering.',
    theorems: ['Fisher-Rao metric', 'Bohr floor', 'Shor 9-qubit', 'Lamport clock'],
    auditCounters: { proven: 4, conjectured: 0, open: 0 },
  },
  {
    key: 'TH8-GLR',
    title: 'Convergent data sync & GLR theorem',
    authors: ['Lutar, Stephen P.'],
    year: 2026,
    status: 'published',
    abstract: 'Chapter 8 and GLR extension: convergent multi-source data synchronization with append-only delta logs, bounded-loop convergence guarantees, and the Governance-Locality-Recursion theorem.',
    theorems: ['Convergent sync', 'Append-only delta-log', 'GLR theorem'],
    auditCounters: { proven: 3, conjectured: 0, open: 0 },
  },
];

export function thesisPaperSummary(paper: ThesisPaper): {
  theoremCount: number;
  provenCount: number;
  status: string;
} {
  return {
    theoremCount: paper.theorems.length,
    provenCount: paper.auditCounters.proven,
    status: paper.status,
  };
}
