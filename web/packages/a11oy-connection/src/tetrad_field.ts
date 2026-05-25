/**
 * Tetrad Field (gauge connection over the policy manifold)
 *
 * Source: Wald (1984), General Relativity §3.4 (tetrad / vierbein
 *   formalism). Penrose & Rindler (1984), Spinors and Space-Time vol.1,
 *   Cambridge UP, §3.1.
 *
 * A tetrad is an orthonormal frame field eₐ^μ on a manifold. For
 * governance policy, the four legs are: (1) capability tier, (2) data
 * sensitivity, (3) action reversibility, (4) blast radius. The tetrad
 * lets us evaluate any decision in either frame (intrinsic vs extrinsic)
 * — the Bohr complementarity engine consumes this object.
 */

export type TetradLeg = {
  axis: 'capability_tier' | 'data_sensitivity' | 'action_reversibility' | 'blast_radius';
  unit: string;
  value: number;
};

export type TetradFrame = {
  /** Always exactly four legs (orthonormal frame). */
  legs: [TetradLeg, TetradLeg, TetradLeg, TetradLeg];
};

export function makeTetrad(values: {
  capability_tier: number;
  data_sensitivity: number;
  action_reversibility: number;
  blast_radius: number;
}): TetradFrame {
  return {
    legs: [
      { axis: 'capability_tier', unit: 'tier', value: values.capability_tier },
      { axis: 'data_sensitivity', unit: 'sensitivityLevel', value: values.data_sensitivity },
      { axis: 'action_reversibility', unit: 'reversibilityScore', value: values.action_reversibility },
      { axis: 'blast_radius', unit: 'affectedUserCount', value: values.blast_radius },
    ],
  };
}

/**
 * Inner product in the orthonormal frame (Euclidean metric η = diag(1,1,1,1)
 * since the frame is orthonormal by construction).
 */
export function tetradInner(a: TetradFrame, b: TetradFrame): number {
  let s = 0;
  for (let i = 0; i < 4; i++) {
    s += a.legs[i].value * b.legs[i].value;
  }
  return s;
}

export function tetradNorm(a: TetradFrame): number {
  return Math.sqrt(tetradInner(a, a));
}
