import { describe, expect, it } from 'vitest';
import { autonomyGate } from '@szl-holdings/formulas';
import { sentraSignalRisk, sentraSignalRiskNormalized } from './risk.js';

describe('sentraSignalRiskNormalized → autonomyGate', () => {
  it('low-severity advisory signal → auto', () => {
    const r = sentraSignalRiskNormalized({
      severity: 0.2,
      likelihood: 0.3,
      blastRadiusCost: 50_000,
    });
    // 0.2 * 0.3 * 50_000 = 3_000 / 1_000_000 = 0.003 → auto (<0.2)
    expect(r).toBeCloseTo(0.003, 10);
    expect(autonomyGate(r)).toBe('auto');
  });

  it('mid-severity incident → approve', () => {
    const r = sentraSignalRiskNormalized({
      severity: 0.6,
      likelihood: 0.7,
      blastRadiusCost: 600_000,
    });
    // 0.6 * 0.7 * 600_000 = 252_000 / 1_000_000 = 0.252 → approve (0.2 ≤ r < 0.6)
    expect(r).toBeCloseTo(0.252, 10);
    expect(autonomyGate(r)).toBe('approve');
  });

  it('critical breach → multi-party', () => {
    const r = sentraSignalRiskNormalized({
      severity: 0.95,
      likelihood: 0.9,
      blastRadiusCost: 900_000,
    });
    // 0.95 * 0.9 * 900_000 = 769_500 / 1_000_000 = 0.7695 → multi-party (≥0.6)
    expect(r).toBeCloseTo(0.7695, 10);
    expect(autonomyGate(r)).toBe('multi-party');
  });

  it('respects a custom cap', () => {
    const r = sentraSignalRiskNormalized({
      severity: 0.5,
      likelihood: 0.5,
      blastRadiusCost: 100_000,
      cap: 100_000,
    });
    // 0.5 * 0.5 * 100_000 = 25_000 capped at 100_000 → 25_000 / 100_000 = 0.25
    expect(r).toBeCloseTo(0.25, 10);
    expect(autonomyGate(r)).toBe('approve');
  });

  it('non-normalized variant returns raw severity·likelihood·value', () => {
    expect(
      sentraSignalRisk({ severity: 0.5, likelihood: 0.5, blastRadiusCost: 200_000 }),
    ).toBeCloseTo(50_000, 6);
  });
});
