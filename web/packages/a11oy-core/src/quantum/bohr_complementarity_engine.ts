/**
 * GRAFT 1 — Bohr Complementarity Engine (12 frame-pairs)
 *
 * Source: Bohr (1928), "The Quantum Postulate and the Recent Development
 *   of Atomic Theory", Nature 121:580-590. Bohr (1949), "Discussion with
 *   Einstein on Epistemological Problems in Atomic Physics", in Schilpp
 *   (ed.), Albert Einstein: Philosopher-Scientist, Open Court.
 *
 * Every governance decision is emitted as a ComplementaryDecisionPayload
 * with exactly two complementary frames, and the empirical uncertainty
 * product over the rolling sample window must satisfy
 *   σ_A · σ_B  >=  COMPLEMENTARITY_FLOOR
 * (the discrete-policy analogue of Heisenberg's σ_x σ_p >= ℏ/2).
 */
import type { TetradFrame } from '@a11oy/connection';

/** Lower bound on the σ_A · σ_B product. Tuned so a degenerate
 *  (deterministic) frame-pair fails the test. */
export const COMPLEMENTARITY_FLOOR = 0.25;

export type FramePair = {
  id: string;
  /** Complementary frame A label, e.g. "capability vs data-sensitivity". */
  axisA: string;
  axisB: string;
};

/**
 * 12 canonical frame-pairs spanning the governance manifold's complementary
 * facets. The pairs were chosen so that the joint observable algebra is
 * non-commutative — measuring sharply along axis A blurs axis B.
 */
export const FRAME_PAIRS: readonly FramePair[] = [
  { id: 'FP-01', axisA: 'capability_tier', axisB: 'data_sensitivity' },
  { id: 'FP-02', axisA: 'action_reversibility', axisB: 'blast_radius' },
  { id: 'FP-03', axisA: 'agent_age_days', axisB: 'capability_tier' },
  { id: 'FP-04', axisA: 'dual_spirit_light', axisB: 'dual_spirit_darkness' },
  { id: 'FP-05', axisA: 'pesher_admit', axisB: 'pesher_deny' },
  { id: 'FP-06', axisA: 'reviewer_quorum', axisB: 'time_to_decision' },
  { id: 'FP-07', axisA: 'fisher_distance', axisB: 'tetrad_norm' },
  { id: 'FP-08', axisA: 'metatron_capability_witness', axisB: 'watcher_dual_use_vector' },
  { id: 'FP-09', axisA: 'physiognomy_light_share', axisB: 'physiognomy_darkness_share' },
  { id: 'FP-10', axisA: 'primary_tablet_root', axisB: 'secondary_tablet_root' },
  { id: 'FP-11', axisA: 'povm_admit_amplitude', axisB: 'povm_deny_amplitude' },
  { id: 'FP-12', axisA: 'ks18_witness_value', axisB: 'daruan_rotation_angle' },
] as const;

export type ComplementaryDecisionPayload = {
  pairId: string;
  frames: [{ axis: string; value: number }, { axis: string; value: number }];
  ts: string;
};

export function emitDecision(
  pairId: string,
  valueA: number,
  valueB: number,
): ComplementaryDecisionPayload {
  const pair = FRAME_PAIRS.find((p) => p.id === pairId);
  if (!pair) throw new Error(`Unknown frame-pair: ${pairId}`);
  const payload: ComplementaryDecisionPayload = {
    pairId,
    frames: [
      { axis: pair.axisA, value: valueA },
      { axis: pair.axisB, value: valueB },
    ],
    ts: new Date().toISOString(),
  };
  // Doctrine §1.1: frames.length === 2 always.
  if (payload.frames.length !== 2) {
    throw new Error('ComplementaryDecisionPayload must have exactly two frames');
  }
  return payload;
}

function stddev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const v = xs.reduce((a, b) => a + (b - mean) * (b - mean), 0) / (xs.length - 1);
  return Math.sqrt(v);
}

export type ComplementarityCheck = {
  pairId: string;
  sigmaA: number;
  sigmaB: number;
  product: number;
  passes: boolean;
};

export function checkComplementarity(
  decisions: ComplementaryDecisionPayload[],
): ComplementarityCheck[] {
  const byPair = new Map<string, ComplementaryDecisionPayload[]>();
  for (const d of decisions) {
    if (!byPair.has(d.pairId)) byPair.set(d.pairId, []);
    byPair.get(d.pairId)!.push(d);
  }
  const results: ComplementarityCheck[] = [];
  for (const [pairId, ds] of byPair) {
    const a = ds.map((d) => d.frames[0].value);
    const b = ds.map((d) => d.frames[1].value);
    const sigmaA = stddev(a);
    const sigmaB = stddev(b);
    const product = sigmaA * sigmaB;
    results.push({ pairId, sigmaA, sigmaB, product, passes: product >= COMPLEMENTARITY_FLOOR });
  }
  return results;
}

/** Convenience: derive both frame values from a TetradFrame for FP-01/02/07. */
export function fromTetrad(pair: FramePair, frame: TetradFrame): [number, number] {
  const find = (axis: string) => {
    const leg = frame.legs.find((l: { axis: string; value: number }) => l.axis === axis);
    return leg ? leg.value : 0;
  };
  return [find(pair.axisA), find(pair.axisB)];
}
