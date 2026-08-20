/**
 * GRAFT 3 — POVM Verdict Semantics
 *
 * Source: Preskill, J. (2015). Quantum Information, Lecture Notes for
 * Physics 219/CS 219. Caltech, Chapter 3 §3.1 (POVMs).
 * https://www.preskill.caltech.edu/ph219/chap3_15.pdf
 *
 * Replaces binary {accept, reject} verdicts with a positive-operator-
 * valued measure: a finite collection of positive-semidefinite operators
 * {Eᵢ} on the policy state space satisfying Σᵢ Eᵢ = I (the completeness
 * theorem). Each Eᵢ corresponds to a distinct admission outcome — admit-
 * with-witness, admit-with-throttle, deny, escalate, etc. — and the
 * probability of outcome i on policy state ρ is Tr(Eᵢρ).
 *
 * The completeness invariant is checked at construction; non-conforming
 * verdict sets are rejected. This is the operational equivalent of the
 * Lean theorem `povm_completeness` referenced in the doctrine.
 */

const COMPLETENESS_TOL = 1e-9;

export type Outcome = 'admit' | 'admit_throttled' | 'admit_witnessed' | 'deny' | 'escalate';

export type POVMVerdict = {
  outcome: Outcome;
  /** Effect operator diagonal entries (we restrict to diagonal effects in
   * the policy basis; full off-diagonal POVMs are out of scope for now). */
  effectDiagonal: readonly number[];
  rationale: string;
};

export type POVMSet = readonly POVMVerdict[];

/** Σᵢ Eᵢ = I (with floating-point tolerance). */
export function isComplete(verdicts: POVMSet, dim: number): boolean {
  if (verdicts.length === 0) return false;
  const sum = new Array<number>(dim).fill(0);
  for (const v of verdicts) {
    if (v.effectDiagonal.length !== dim) return false;
    for (let i = 0; i < dim; i++) {
      const x = v.effectDiagonal[i];
      if (x < -COMPLETENESS_TOL || x > 1 + COMPLETENESS_TOL) return false; // 0 ≤ Eᵢ ≤ I
      sum[i] += x;
    }
  }
  return sum.every((s) => Math.abs(s - 1) < COMPLETENESS_TOL);
}

export class POVMSetError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'POVMSetError';
  }
}

/** Construct + validate. Throws if Σᵢ Eᵢ ≠ I. */
export function makePOVM(verdicts: POVMSet, dim: number): POVMSet {
  if (!isComplete(verdicts, dim)) {
    throw new POVMSetError(`POVM completeness violated: Σᵢ Eᵢ ≠ I on dim ${dim}`);
  }
  return verdicts;
}

/** Probability of outcome i on diagonal state ρ — Tr(Eᵢρ). */
export function probability(verdict: POVMVerdict, stateDiagonal: readonly number[]): number {
  if (verdict.effectDiagonal.length !== stateDiagonal.length) {
    throw new POVMSetError('effect/state dimension mismatch');
  }
  let p = 0;
  for (let i = 0; i < stateDiagonal.length; i++) {
    p += verdict.effectDiagonal[i] * stateDiagonal[i];
  }
  return p;
}

/** Pick the most-likely outcome on state ρ (used by the policy head). */
export function argmaxOutcome(povm: POVMSet, stateDiagonal: readonly number[]): POVMVerdict {
  let best = povm[0];
  let bestP = -Infinity;
  for (const v of povm) {
    const p = probability(v, stateDiagonal);
    if (p > bestP) {
      bestP = p;
      best = v;
    }
  }
  return best;
}
