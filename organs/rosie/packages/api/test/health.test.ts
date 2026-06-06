import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';

describe('GET /v1/health', () => {
  it('returns 200 with status, version, commit, uptime (no auth required)', async () => {
    const { app } = await buildRig();
    const res = await app.request('/v1/health');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(body.version).toBe('1.0.0-test');
    expect(body.commit).toBe('testsha');
    expect(typeof body.uptime_s).toBe('number');
    expect(body.uptime_s).toBeGreaterThanOrEqual(0);
  });
});
