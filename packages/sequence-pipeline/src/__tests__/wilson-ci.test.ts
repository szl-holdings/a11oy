import { describe, expect, it } from 'vitest';
import { wilsonInterval } from '../wilson-ci.js';

describe('wilsonInterval — CRISPResso2 CI primitive', () => {
  it('matches a published Wilson 95% interval (Newcombe 1998, k=81 / n=263)', () => {
    // p ≈ 0.308; published Wilson 95% ≈ [0.255, 0.366].
    const r = wilsonInterval(81, 263);
    expect(r.p).toBeCloseTo(0.308, 3);
    expect(r.ciLower).toBeCloseTo(0.255, 2);
    expect(r.ciUpper).toBeCloseTo(0.366, 2);
  });

  it('stays inside [0, 1] for an edge proportion (Wald would not)', () => {
    const r = wilsonInterval(0, 5);
    expect(r.ciLower).toBe(0);
    expect(r.ciUpper).toBeGreaterThan(0);
    expect(r.ciUpper).toBeLessThan(1);
    expect(r.ciUpper).toBeLessThanOrEqual(1);
  });

  it('degenerate trials=0 returns the widest honest interval, not NaN', () => {
    const r = wilsonInterval(0, 0);
    expect(r.ciLower).toBe(0);
    expect(r.ciUpper).toBe(1);
  });

  it('p is always contained in [ciLower, ciUpper] (property)', () => {
    for (let n = 1; n <= 50; n += 7) {
      for (let k = 0; k <= n; k += 3) {
        const r = wilsonInterval(k, n);
        expect(r.p).toBeGreaterThanOrEqual(r.ciLower - 1e-12);
        expect(r.p).toBeLessThanOrEqual(r.ciUpper + 1e-12);
      }
    }
  });

  it('99% interval is wider than 95% for the same data', () => {
    const r95 = wilsonInterval(10, 50, '0.95');
    const r99 = wilsonInterval(10, 50, '0.99');
    expect(r99.ciUpper - r99.ciLower).toBeGreaterThan(r95.ciUpper - r95.ciLower);
  });

  it('rejects malformed inputs loudly', () => {
    expect(() => wilsonInterval(-1, 10)).toThrow();
    expect(() => wilsonInterval(11, 10)).toThrow();
    expect(() => wilsonInterval(1, -5)).toThrow();
  });
});
