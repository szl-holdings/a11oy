import { createHash } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { StagedPipeline, type StageDefinition } from '../staged.js';
import { validateTabulatedStatistic, type TabulatedStatistic } from '../tabulated-statistic.js';
import { wilsonInterval } from '../wilson-ci.js';

function hash(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

describe('StagedPipeline — CRISPResso2 staged shape', () => {
  it('emits one stage artefact per stage with chained ordinals', async () => {
    const pipeline = new StagedPipeline({
      pipelineId: 'pipe-1',
      tooling: { runner: 'staged@0.1' },
      hash,
    });
    type Stages = 'filter' | 'align' | 'classify';
    const stages: StageDefinition<Stages, unknown, unknown>[] = [
      { name: 'filter',   params: { minQ: 30 }, run: (x) => x },
      { name: 'align',    params: { ref: 'GRCh38' }, run: (x) => x },
      { name: 'classify', params: { caller: 'edit-v1' }, run: () => ({ a: 4, b: 1 }) },
    ];
    const result = await pipeline.run({ reads: 5 }, stages);
    expect(result.stages.map((s) => s.stageOrdinal)).toEqual([0, 1, 2]);
    expect(result.stages.map((s) => s.stageName)).toEqual(['filter', 'align', 'classify']);
    for (const s of result.stages) {
      expect(s.receiptClass).toBe('pipeline.stage.v1');
      expect(s.parentPipelineId).toBe('pipe-1');
      expect(s.inputsHash).toMatch(/^[0-9a-f]{64}$/);
      expect(s.outputsHash).toMatch(/^[0-9a-f]{64}$/);
    }
  });

  it('chains output of stage N to input of stage N+1 (deterministic hash)', async () => {
    const pipeline = new StagedPipeline({ pipelineId: 'pipe-2', tooling: {}, hash });
    const stages: StageDefinition<'a' | 'b', unknown, unknown>[] = [
      { name: 'a', params: {}, run: (x) => ({ wrapped: x }) },
      { name: 'b', params: {}, run: (x) => x },
    ];
    const result = await pipeline.run(42, stages);
    expect(result.stages[1]!.inputsHash).toBe(result.stages[0]!.outputsHash);
  });

  it('terminal tabulated statistic is validated at receipt-write boundary', async () => {
    const pipeline = new StagedPipeline({ pipelineId: 'pipe-3', tooling: {}, hash });
    const stages: StageDefinition<'count', unknown, unknown>[] = [
      { name: 'count', params: {}, run: () => ({ edited: 18, unmodified: 82, n: 100 }) },
    ];
    const finaliser = (out: unknown): TabulatedStatistic => {
      const r = out as { edited: number; unmodified: number; n: number };
      const editedCI = wilsonInterval(r.edited, r.n);
      const unmodCI = wilsonInterval(r.unmodified, r.n);
      return {
        totalTrials: r.n,
        methodRef: 'wilson-0.95',
        requiresNegativeSpace: true,
        rows: [
          { label: 'edited',    count: r.edited,    fraction: editedCI.p, ciLower: editedCI.ciLower, ciUpper: editedCI.ciUpper, isNegativeSpace: false },
          { label: 'unmodified', count: r.unmodified, fraction: unmodCI.p,  ciLower: unmodCI.ciLower,  ciUpper: unmodCI.ciUpper,  isNegativeSpace: true  },
        ],
      };
    };
    const result = await pipeline.run({}, stages, finaliser);
    expect(result.tabulatedStatistic).toBeDefined();
    expect(() => validateTabulatedStatistic(result.tabulatedStatistic!)).not.toThrow();
  });

  it('rejects tabulated statistic without CI bounds (no claim without an interval)', () => {
    expect(() =>
      validateTabulatedStatistic({
        totalTrials: 10,
        methodRef: 'none',
        requiresNegativeSpace: false,
        rows: [{ label: 'x', count: 3, fraction: 0.3, ciLower: Number.NaN, ciUpper: 0.5, isNegativeSpace: false }],
      }),
    ).toThrow(/no claim without an interval/);
  });

  it('rejects table missing negative-space row when schema requires it (absence is a row)', () => {
    expect(() =>
      validateTabulatedStatistic({
        totalTrials: 10,
        methodRef: 'wilson-0.95',
        requiresNegativeSpace: true,
        rows: [{ label: 'edited', count: 3, fraction: 0.3, ciLower: 0.1, ciUpper: 0.5, isNegativeSpace: false }],
      }),
    ).toThrow(/absence is a row/);
  });
});
