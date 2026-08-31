/**
 * @szl-holdings/a11oy-knowledge — Proposed Axioms A10–A14
 * Author: Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · Apache-2.0
 * Source: publications_harvest/niche_mind/INNOVATIONS.md §3
 */
import type { ProposedAxiom } from './schema.js';

export const PROPOSED_AXIOMS: ProposedAxiom[] = [
  {
    id: 'A10',
    name: 'temporalConsistency',
    statement: 'Gate verdict is invariant under time-shift within registered clock-drift bound ε_clock.',
    statement_latex: '\\forall \\text{input}, \\forall \\Delta t \\leq \\varepsilon_{\\text{clock}}: \\text{verdict}(\\Lambda, \\text{input}, t) = \\text{verdict}(\\Lambda, \\text{input}, t + \\Delta t)',
    source_file: 'INNOVATIONS.md',
    source_section: '§3',
    maturity: 'defined',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    floor: 0.90,
    why_not_subsumed: 'A5 (deterministicReplay) is spatial determinism. A10 is temporal determinism — different evaluation time, same verdict. These are independent properties.',
    function_signature: 'temporalConsistency(receipt: Receipt, deltaT_ms: number, clockDriftBound_ms: number): boolean',
    falsifiability_test: 'Evaluate same receipt at t and t+100ms; assert verdict identical.',
  },
  {
    id: 'A11',
    name: 'causalSeparability',
    statement: 'Receipts from disjoint actor sets carry statistically independent entropy (no shared randomness source).',
    statement_latex: '\\text{actor}(r) \\cap \\text{actor}(r\') = \\emptyset \\implies \\text{receipt\\_hash}(r) \\perp \\text{receipt\\_hash}(r\')',
    source_file: 'INNOVATIONS.md',
    source_section: '§3',
    maturity: 'defined',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    why_not_subsumed: 'A4 ensures two witnesses are distinct per receipt. A11 ensures receipts from different actors carry independent entropy — enabling cross-actor attribution without information leakage.',
    function_signature: 'causalSeparability(actorSetA: Set<ActorId>, actorSetB: Set<ActorId>): boolean',
    falsifiability_test: 'Inspect canonical-chain.seed.json; assert no shared PRNG seed between disjoint actor slots.',
  },
  {
    id: 'A12',
    name: 'constructiveTransparency',
    statement: 'Every Λ score is re-derivable from public inputs; no hidden weights or parameters.',
    statement_latex: '\\forall r: \\Lambda(r) = f(\\text{public\\_inputs}(r)) \\text{ where } f \\text{ is the published Lean-formalized scorer}',
    source_file: 'INNOVATIONS.md',
    source_section: '§3',
    maturity: 'defined',
    citation: 'https://doi.org/10.5281/zenodo.20053148',
    why_not_subsumed: 'TH_L1 proves uniqueness of the scorer given axioms. A12 adds auditability: the scorer must be a pure function of declared inputs. A "hidden trust boost" based on user history would satisfy TH_L1 but violate A12.',
    function_signature: 'constructiveTransparency(scorer: LambdaScorer): boolean  // assert scorer is pure function',
    falsifiability_test: 'Run scorer on identical axis vectors from two different actors; assert identical output.',
  },
  {
    id: 'A13',
    name: 'adversarialRobustness',
    statement: 'Gate verdict is stable under bounded perturbation of any single axis by ε ≤ 0.05, except when original score is within ε of a floor.',
    statement_latex: '\\forall x \\in [0,1]^9, \\|\\delta\\|_\\infty \\leq 0.05: \\text{gate\\_pass}(x) = \\text{gate\\_pass}(x + \\delta)',
    source_file: 'INNOVATIONS.md',
    source_section: '§3',
    maturity: 'defined',
    citation: 'https://doi.org/10.5281/zenodo.20119582',
    floor: 0.05,
    why_not_subsumed: 'A5 (soundnessAxiom) is binary — pass or fail. A13 adds a stability radius: defines how close to a floor boundary a score must be before perturbation can flip the verdict.',
    function_signature: 'adversarialRobustness(receipt: Receipt, epsilon: number): { is_robust: boolean; vulnerable_axis?: string }',
    falsifiability_test: '30 adversarial tests from runtime_memo §6.5: axis-flip attacks with ε=0.05 on each of 9 axes.',
  },
  {
    id: 'A14',
    name: 'economicGrounding',
    statement: 'Gate passes only if action declared cost ≤ registered actor budget at evaluation time.',
    statement_latex: '\\text{gate\\_pass}(r) \\implies \\text{cost}(r) \\leq B_{\\text{actor}}(t)',
    source_file: 'INNOVATIONS.md',
    source_section: '§3',
    maturity: 'defined',
    citation: 'https://doi.org/10.5281/zenodo.20162352',
    why_not_subsumed: 'No existing axiom bounds economic cost. Required by financial services (SR 11-7 position limits), insurance (underwriting ceilings), capital markets (SEC Rule 17a-4 order size). A14 adds a financial constraint as a first-class gate condition.',
    function_signature: 'economicGrounding(action_cost: number, actor_id: ActorId, timestamp_ms: number): { pass: boolean; budget_remaining: number }',
    falsifiability_test: 'Register actor with budget=100; submit action with cost=101; assert gate fails.',
  },
];

export const getProposedAxiom = (id: string): ProposedAxiom | undefined =>
  PROPOSED_AXIOMS.find(a => a.id === id);
