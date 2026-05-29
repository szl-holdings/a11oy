import { describe, expect, it } from 'vitest';
import { computeLiveness, type FrameSignal } from '../liveness.js';
import { detect, type DetectorAdapter } from '../pipeline.js';

function frame(tMs: number, irisMotion: number, eyeAperture: number, headPoseDelta: number): FrameSignal {
  return { tMs, irisMotion, eyeAperture, headPoseDelta };
}

describe('computeLiveness — Human.js operator-loop primitive', () => {
  it('returns zero confidence on an empty window', () => {
    expect(computeLiveness([]).livenessConfidence).toBe(0);
  });

  it('rewards a window with blink + saccade + head motion (≈ 1.0)', () => {
    const signals = [
      frame(0, 0.0, 0.9, 0.01),
      frame(100, 0.02, 0.1, 0.03),
      frame(200, 0.05, 0.9, 0.06),
      frame(300, 0.01, 0.9, 0.0),
    ];
    const r = computeLiveness(signals);
    expect(r.livenessConfidence).toBeCloseTo(1, 5);
    expect(r.livenessReasons.length).toBe(3);
  });

  it('is monotone non-decreasing when a satisfied signal is added (property)', () => {
    const base: FrameSignal[] = [frame(0, 0.0, 0.9, 0.0), frame(100, 0.0, 0.9, 0.0)];
    const baseR = computeLiveness(base).livenessConfidence;
    const augmented: FrameSignal[] = [...base, frame(200, 0.05, 0.1, 0.2), frame(300, 0.05, 0.9, 0.2)];
    const augR = computeLiveness(augmented).livenessConfidence;
    expect(augR).toBeGreaterThanOrEqual(baseR);
  });

  it('static-image replay (no motion, no blink) yields zero confidence', () => {
    const signals = Array.from({ length: 20 }, (_, i) => frame(i * 50, 0, 0.9, 0));
    expect(computeLiveness(signals).livenessConfidence).toBe(0);
  });
});

describe('detect — multi-head pipeline budget', () => {
  it('skips heads whose cost would exceed the per-frame budget', async () => {
    const cheap: DetectorAdapter = {
      head: 'face', costMs: 5, detect: async () => [],
    };
    const expensive: DetectorAdapter = {
      head: 'body', costMs: 10_000, detect: async () => [],
    };
    const env = await detect(
      { frameHash: 'h0', tMs: 0, payload: null },
      [cheap, expensive],
      { budgetMs: 50, consumerArtifact: 'test' },
    );
    expect(env.ranHeads).toContain('face');
    expect(env.skippedHeads).toContain('body');
  });

  it('absence-of-target distinguishable from absence-of-data', async () => {
    const ran: DetectorAdapter = { head: 'face', costMs: 1, detect: async () => [] };
    const env = await detect(
      { frameHash: 'h1', tMs: 0, payload: null },
      [ran],
      { budgetMs: 100, consumerArtifact: 'test', heads: ['face', 'body'] },
    );
    expect(env.ranHeads).toEqual(['face']);
    expect(env.face).toEqual([]);
    expect(env.skippedHeads).not.toContain('face');
  });
});
