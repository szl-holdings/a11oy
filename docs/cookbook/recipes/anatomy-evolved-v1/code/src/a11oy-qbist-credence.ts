/**
 * a11oy-qbist-credence.ts — QBist Bayesian credence per agent
 *
 * STATUS: TUTORIAL FIXTURE — runnable copy for the recipe smoke tests.
 *   The CANONICAL implementation is:
 *     a11oy/web/packages/a11oy-core/src/quantum/qbist_credence.ts
 *   The canonical version adds input validation, throws on degenerate
 *   evidence (Z ≤ 0), and verifies Dutch-book coherence (Σ=1 AND all ≥ 0),
 *   not just normalization.
 *
 * Source: Fuchs & Schack (2013), Rev. Mod. Phys. 85, 1693
 *         Fuchs, Mermin, Schack (2014), arXiv:1311.5253
 *         R08 — quantum_bohr_credence.ts
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

export interface Credence {
  agentId: string;
  priorWeights: number[];        // prior probability vector
  posteriorWeights: number[];    // updated posterior
  isObjectivistClaim: false;     // INVARIANT: always false (QBist)
  isDutchBookCoherent: boolean;
  iteration: number;
}

/** Bayesian credence update via likelihood weighting */
export class QBistCredenceManager {
  private credences = new Map<string, Credence>();

  /** Initialize agent credence (uniform prior) */
  init(agentId: string, nOutcomes: number): Credence {
    const c: Credence = {
      agentId,
      priorWeights: Array(nOutcomes).fill(1 / nOutcomes),
      posteriorWeights: Array(nOutcomes).fill(1 / nOutcomes),
      isObjectivistClaim: false,
      isDutchBookCoherent: true,
      iteration: 0,
    };
    this.credences.set(agentId, c);
    return c;
  }

  /** Update credence via Born-rule-inspired Bayesian update */
  update(agentId: string, likelihoods: number[], observedOutcome: number): Credence {
    const c = this.credences.get(agentId);
    if (!c) throw new Error(`Unknown agent: ${agentId}`);
    const prior = c.posteriorWeights;
    const unnorm = prior.map((p, i) => p * likelihoods[i]);
    const Z = unnorm.reduce((a, b) => a + b, 0);
    const posterior = unnorm.map(u => u / (Z + 1e-12));
    const updated: Credence = {
      ...c,
      priorWeights: prior,
      posteriorWeights: posterior,
      isObjectivistClaim: false,
      isDutchBookCoherent: Math.abs(posterior.reduce((a, b) => a + b, 0) - 1) < 1e-9,
      iteration: c.iteration + 1,
    };
    this.credences.set(agentId, updated);
    return updated;
  }

  predict(agentId: string, likelihoods: number[]): number {
    const c = this.credences.get(agentId);
    if (!c) throw new Error(`Unknown agent: ${agentId}`);
    return c.posteriorWeights.reduce((sum, p, i) => sum + p * likelihoods[i], 0);
  }

  assertSubjectivism(agentId: string): void {
    const c = this.credences.get(agentId);
    if (!c || c.isObjectivistClaim) {
      throw new Error(`QBIST VIOLATION: agent ${agentId} made objectivist claim`);
    }
  }
}

// ─── Usage Example ────────────────────────────────────────────────────────────
/*
const mgr = new QBistCredenceManager();
mgr.init("amaru", 3); // 3 possible policy outcomes
const updated = mgr.update("amaru", [0.8, 0.1, 0.1], 0);
mgr.assertSubjectivism("amaru"); // never throws — isObjectivistClaim is always false
console.log("Posterior:", updated.posteriorWeights);
*/