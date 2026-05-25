/**
 * Fisher Information Manifold (governance credences)
 *
 * Source: Fisher (1925), "Theory of Statistical Estimation", Proc.
 *   Cambridge Phil. Soc. 22:700-725. Amari & Nagaoka (2000), Methods of
 *   Information Geometry, AMS Translations 191.
 *
 * Treats agent credences as points on a Fisher manifold (a Riemannian
 * manifold whose metric is the Fisher information matrix). Two credence
 * distributions p, q are "distinguishable enough" when their Fisher-Rao
 * distance exceeds an admit-threshold.
 */

export type CredenceVector = number[]; // discrete probability distribution

export function normalize(v: CredenceVector): CredenceVector {
  const s = v.reduce((a, b) => a + b, 0);
  if (s <= 0) throw new Error('Credence vector must have positive mass');
  return v.map((x) => x / s);
}

/**
 * Fisher-Rao distance for discrete distributions: 2·arccos(Σᵢ √(pᵢ qᵢ)).
 * Range: [0, π]. Numerically stable for small overlaps.
 */
export function fisherRaoDistance(p: CredenceVector, q: CredenceVector): number {
  if (p.length !== q.length) throw new Error('Credence vectors must be same length');
  const pn = normalize(p);
  const qn = normalize(q);
  let bhattacharyya = 0;
  for (let i = 0; i < pn.length; i++) {
    bhattacharyya += Math.sqrt(pn[i] * qn[i]);
  }
  // Clamp for arccos domain safety.
  const clipped = Math.min(1, Math.max(-1, bhattacharyya));
  return 2 * Math.acos(clipped);
}

/**
 * Fisher information matrix (diagonal approximation) for a categorical
 * distribution: F_ii = 1/p_i. Used as the local metric for credence updates.
 */
export function fisherDiagonal(p: CredenceVector): number[] {
  const pn = normalize(p);
  return pn.map((pi) => 1 / Math.max(pi, 1e-12));
}
