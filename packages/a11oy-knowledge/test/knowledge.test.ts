/**
 * @szl-holdings/a11oy-knowledge — Test Suite
 * Author: Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · Apache-2.0
 */
import { describe, it, expect } from 'vitest';
import { KNOWLEDGE_GRAPH, getAxiom, getConstant, getDOI, getDerivation } from '../src/index.js';
import { DERIVATIONS } from '../src/derivations.js';
import { PROPOSED_AXIOMS } from '../src/proposed_axioms.js';
import { NEW_THEOREMS } from '../src/theorems.js';
import { VERTICAL_POLICIES, getPolicyForVertical, getTopVerticalsByDensity } from '../src/vertical-router.js';

describe('Axioms A1-A9', () => {
  it('all 9 canonical axioms present', () => {
    const ids = (KNOWLEDGE_GRAPH.axioms as Array<{id: string}>).map(a => a.id);
    for (const id of ['A1','A2','A3','A4','A5','A6','A7','A8','A9']) {
      expect(ids).toContain(id);
    }
  });

  it('moralGrounding floor = 0.95', () => {
    const a2 = getAxiom('A2');
    expect(a2).toBeDefined();
    expect(a2?.statement).toContain('0.95');
  });

  it('measurabilityHonesty floor = 0.95', () => {
    const a3 = getAxiom('A3');
    expect(a3).toBeDefined();
    expect(a3?.statement).toContain('0.95');
  });
});

describe('Canonical Constants K01-K13', () => {
  it('receipt_build_p50 = 11.5 µs', () => {
    const k = getConstant('K01');
    expect(k?.value).toBe('11.5');
  });

  it('receipt_verify_p50 = 10.4 µs', () => {
    const k = getConstant('K03');
    expect(k?.value).toBe('10.4');
  });

  it('rho_closure_rate = 100%', () => {
    const k = getConstant('K06');
    expect(k?.value).toBe('100%');
  });

  it('replay_root matches known value', () => {
    const k = getConstant('K10');
    expect(k?.value).toContain('1ed4d253');
  });

  it('all 13 constants present', () => {
    const ids = (KNOWLEDGE_GRAPH.canonical_constants as Array<{id: string}>).map(c => c.id);
    for (let i = 1; i <= 13; i++) {
      expect(ids).toContain(`K${i.toString().padStart(2,'0')}`);
    }
  });
});

describe('DOI Ledger', () => {
  it('concept DOI present', () => {
    const d = getDOI('10.5281/zenodo.19944926');
    expect(d).toBeDefined();
  });

  it('v11 paper DOI present', () => {
    const d = getDOI('10.5281/zenodo.20119582');
    expect(d).toBeDefined();
  });

  it('all 13 DOIs present', () => {
    const EXPECTED = [
      '10.5281/zenodo.19867281','10.5281/zenodo.19934129','10.5281/zenodo.19944926',
      '10.5281/zenodo.19983066','10.5281/zenodo.20020841','10.5281/zenodo.20020846',
      '10.5281/zenodo.20020845','10.5281/zenodo.20020848','10.5281/zenodo.20020849',
      '10.5281/zenodo.20053148','10.5281/zenodo.20053163','10.5281/zenodo.20119582',
      '10.5281/zenodo.20162352',
    ];
    for (const doi of EXPECTED) {
      expect(getDOI(doi)).toBeDefined();
    }
  });
});

describe('Derivations T1-T10', () => {
  it('all 10 derivations present', () => {
    const ids = DERIVATIONS.map(d => d.id);
    for (const id of ['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10']) {
      expect(ids).toContain(id);
    }
  });

  it('each derivation has at least one parent in A1-A9 or another T', () => {
    const validParents = new Set([
      'A1','A2','A3','A4','A5','A6','A7','A8','A9',
      'A1_lean','A2_lean','A3_lean','A4_lean',
      'TH_L1','TH_L2','TH_L3','TH_L4',
      'T1','T2','T3','T4','T5','T6','T7','T8','T9',
    ]);
    for (const d of DERIVATIONS) {
      expect(d.parents.length).toBeGreaterThan(0);
      const hasValidParent = d.parents.some(p => validParents.has(p));
      expect(hasValidParent, `${d.id} has no valid parent`).toBe(true);
    }
  });

  it('T5 (replay determinism) is proven', () => {
    const t5 = getDerivation('T5');
    expect(t5?.status).toBe('proven');
  });

  it('T6 (conjunctive stronger than single-axis) is proven', () => {
    const t6 = getDerivation('T6');
    expect(t6?.status).toBe('proven');
  });

  it('T4 (Bekenstein) is labeled conjectured', () => {
    const t4 = getDerivation('T4');
    expect(t4?.status).toBe('conjectured');
  });
});

describe('Proposed Axioms A10-A14', () => {
  it('all 5 proposed axioms present', () => {
    const ids = PROPOSED_AXIOMS.map(a => a.id);
    for (const id of ['A10','A11','A12','A13','A14']) {
      expect(ids).toContain(id);
    }
  });

  it('each proposed axiom has a falsifiability test', () => {
    for (const a of PROPOSED_AXIOMS) {
      expect(a.falsifiability_test.length).toBeGreaterThan(10);
    }
  });
});

describe('New Theorems TH1-TH3', () => {
  it('all 3 new theorems present', () => {
    const ids = NEW_THEOREMS.map(t => t.id);
    expect(ids).toContain('TH1');
    expect(ids).toContain('TH2');
    expect(ids).toContain('TH3');
  });

  it('each theorem cites at least 2 axioms in proof sketch', () => {
    for (const th of NEW_THEOREMS) {
      const axiomRefs = (th.proof_sketch || '').match(/A\d+|T\d+|TH_L\d+/g) || [];
      expect(axiomRefs.length, `${th.id} proof sketch has too few axiom refs`).toBeGreaterThan(1);
    }
  });
});

describe('Vertical Policies (10 verticals)', () => {
  it('all 10 verticals present', () => {
    const ids = VERTICAL_POLICIES.map(v => v.id);
    for (const id of ['defense','financial_services','healthcare','insurance','legal',
                       'public_sector','pharma','critical_infrastructure','capital_markets','academic']) {
      expect(ids).toContain(id);
    }
  });

  it('each vertical has at least one required attestor', () => {
    for (const v of VERTICAL_POLICIES) {
      expect(v.required_attestors.length, `${v.id} has no attestors`).toBeGreaterThan(0);
    }
  });

  it('each vertical has lambda_floors defined', () => {
    for (const v of VERTICAL_POLICIES) {
      expect(Object.keys(v.lambda_floors).length).toBeGreaterThan(0);
    }
  });

  it('getPolicyForVertical returns correct policy', () => {
    const p = getPolicyForVertical('defense');
    expect(p?.id).toBe('defense');
  });

  it('top 3 verticals by density are ranked correctly', () => {
    const top3 = getTopVerticalsByDensity(3);
    expect(top3.length).toBe(3);
    expect(top3[0].primitives_applicable.length).toBeGreaterThanOrEqual(top3[1].primitives_applicable.length);
  });
});

describe('Doctrine compliance', () => {
  it('byline is Lutar, Stephen P.', () => {
    expect((KNOWLEDGE_GRAPH as {byline: string}).byline).toBe('Lutar, Stephen P.');
  });

  it('ORCID is 0009-0001-0110-4173', () => {
    expect((KNOWLEDGE_GRAPH as {orcid: string}).orcid).toBe('0009-0001-0110-4173');
  });
});
