/**
 * GRAFT 4 — QBist Subjective Credence Manager
 *
 * Source: Fuchs, C. A. & Schack, R. (2013). "Quantum-Bayesian coherence."
 *   Reviews of Modern Physics 85(4), 1693.
 *   Fuchs, C. A., Mermin, N. D. & Schack, R. (2014). "An introduction to
 *   QBism with an application to the locality of quantum mechanics."
 *   arXiv:1311.5253.
 *
 * Per-agent credence updated by Bayesian likelihood weighting. The QBist
 * commitment is structural: the credence record cannot be claimed as an
 * objective probability (`isObjectivistClaim` is a const-false flag),
 * so every emitted prediction is by construction a subjective gamble of
 * the agent against the world. This is the operational analogue of the
 * Fuchs-Schack subjective-Bayesian reading of quantum probabilities.
 *
 * Canonical home: a11oy/web/packages/a11oy-core/src/quantum/qbist_credence.ts
 *
 * Distribution note (2026-05-28): previously co-located only in
 * szl-cookbook/recipes/anatomy-evolved-v1/code/src/a11oy-qbist-credence.ts.
 * The cookbook file is now a tutorial fixture; this is the canonical
 * implementation that ch9 §9.1 names.
 */

export interface Credence {
  agentId: string;
  priorWeights: readonly number[];
  posteriorWeights: readonly number[];
  /** Structural QBist commitment — must always be false. */
  isObjectivistClaim: false;
  /** True iff posterior is a valid probability vector (Σ=1, all ≥0, finite). */
  isCoherent: boolean;
  iteration: number;
}

const COHERENCE_TOL = 1e-9;

/** Validate that p is a coherent probability vector — the dutch-book test. */
export function isCoherentProbability(p: readonly number[]): boolean {
  if (p.length === 0) return false;
  let sum = 0;
  for (const x of p) {
    if (!Number.isFinite(x)) return false;
    if (x < -COHERENCE_TOL) return false;
    sum += x;
  }
  return Math.abs(sum - 1) < COHERENCE_TOL;
}

export class QBistCredenceManager {
  private credences = new Map<string, Credence>();

  init(agentId: string, nOutcomes: number): Credence {
    if (!Number.isInteger(nOutcomes) || nOutcomes <= 0) {
      throw new Error(`nOutcomes must be a positive integer; got ${nOutcomes}`);
    }
    const uniform = Array<number>(nOutcomes).fill(1 / nOutcomes);
    const c: Credence = {
      agentId,
      priorWeights: uniform,
      posteriorWeights: uniform,
      isObjectivistClaim: false,
      isCoherent: true,
      iteration: 0,
    };
    this.credences.set(agentId, c);
    return c;
  }

  /** Bayesian update p ← (p · L) / Σ(p · L). Throws if posterior is degenerate. */
  update(agentId: string, likelihoods: readonly number[], _observedOutcome: number): Credence {
    const c = this.credences.get(agentId);
    if (!c) throw new Error(`Unknown agent: ${agentId}`);
    if (likelihoods.length !== c.posteriorWeights.length) {
      throw new Error(
        `likelihood length ${likelihoods.length} != credence length ${c.posteriorWeights.length}`,
      );
    }
    const prior = c.posteriorWeights;
    const unnorm = prior.map((p, i) => p * likelihoods[i]);
    const Z = unnorm.reduce((a, b) => a + b, 0);
    if (!Number.isFinite(Z) || Z <= 0) {
      throw new Error(`degenerate update (Z = ${Z}); zero or negative evidence`);
    }
    const posterior = unnorm.map((u) => u / Z);
    const updated: Credence = {
      ...c,
      priorWeights: prior,
      posteriorWeights: posterior,
      isObjectivistClaim: false,
      isCoherent: isCoherentProbability(posterior),
      iteration: c.iteration + 1,
    };
    this.credences.set(agentId, updated);
    return updated;
  }

  predict(agentId: string, likelihoods: readonly number[]): number {
    const c = this.credences.get(agentId);
    if (!c) throw new Error(`Unknown agent: ${agentId}`);
    let p = 0;
    for (let i = 0; i < c.posteriorWeights.length; i++) p += c.posteriorWeights[i] * likelihoods[i];
    return p;
  }

  get(agentId: string): Credence | undefined {
    return this.credences.get(agentId);
  }

  /** Structural assertion — fails only if the type system was bypassed. */
  assertSubjectivism(agentId: string): void {
    const c = this.credences.get(agentId);
    if (!c) throw new Error(`Unknown agent: ${agentId}`);
    if ((c.isObjectivistClaim as boolean) !== false) {
      throw new Error(`QBIST VIOLATION: agent ${agentId} made objectivist claim`);
    }
  }
}
