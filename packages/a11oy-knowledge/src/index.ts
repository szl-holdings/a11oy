/**
 * @szl-holdings/a11oy-knowledge v0.3.0
 * Canonical knowledge graph for the a11oy covenant kernel.
 * Author: Lutar, Stephen P. <stephen@szlholdings.com>
 * ORCID: 0009-0001-0110-4173
 * License: Apache-2.0
 */

export type { Axiom, Theorem, Derivation, CanonicalConstant, DOIEntry, DoctrineClause, ProposedAxiom, VerticalPolicy, KnowledgeGraph } from './schema.js';
export { DERIVATIONS, getDerivation } from './derivations.js';
export { PROPOSED_AXIOMS, getProposedAxiom } from './proposed_axioms.js';
export { ALL_THEOREMS, MATH_POD_THEOREMS, NEW_THEOREMS, getNewTheorem, getTheorem } from './theorems.js';
export { VERTICAL_POLICIES, getPolicyForVertical } from './vertical-router.js';

import knowledgeJson from './knowledge.json' assert { type: 'json' };
export const KNOWLEDGE_GRAPH = knowledgeJson;

// Quick-access helpers
export const getAxiom = (id: string) =>
  (knowledgeJson.axioms as Array<{id: string}>).find(a => a.id === id);

export const getFormula = (id: string) =>
  (knowledgeJson.formulas as Array<{id: string}>).find(f => f.id === id);

export const getDOI = (doi: string) =>
  (knowledgeJson.dois as Array<{doi: string}>).find(d => d.doi === doi);

export const getConstant = (id: string) =>
  (knowledgeJson.canonical_constants as Array<{id: string}>).find(c => c.id === id);
