import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';

describe('POST /v1/execute', () => {
  it('returns a proposal with expires_at ~5min in the future', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['szl-executors'] });
    const res = await app.request('/v1/execute', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'sentra', action: 'rotate-key', params: { keyid: 'k1' }, dry_run: false }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.requires_confirm).toBe(true);
    expect(body.payloadType).toContain('szl.receipt');
    expect(typeof body.receipt_id).toBe('string');
    const ttl = Date.parse(body.expires_at) - Date.now();
    // Within (4.5min, 5min].
    expect(ttl).toBeGreaterThan(4.5 * 60 * 1000);
    expect(ttl).toBeLessThanOrEqual(5 * 60 * 1000 + 1000);
  });

  it('requires szl-executors (403 for operator-only)', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/execute', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'sentra', action: 'x', params: {}, dry_run: true }),
    });
    expect(res.status).toBe(403);
  });

  it('confirming an EXPIRED proposal returns 410 Gone', async () => {
    // Step-up clock fixed to "now"; advance the wall clock past expiry by stubbing Date.
    const fixedStepUp = Date.now();
    const { app, token } = await buildRig({ now: () => fixedStepUp });
    const jwt = await token({ groups: ['szl-executors'], stepUpAt: fixedStepUp });

    const proposeRes = await app.request('/v1/execute', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'sentra', action: 'x', params: {}, dry_run: false }),
    });
    const proposal = await proposeRes.json();

    // Force expiry by overriding Date.now beyond expires_at.
    const realNow = Date.now;
    const expired = Date.parse(proposal.expires_at) + 1000;
    Date.now = () => expired;
    try {
      const confirmRes = await app.request('/v1/execute/confirm', {
        method: 'POST',
        headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
        body: JSON.stringify({ receipt_id: proposal.receipt_id, idempotency_key: 'idem-12345678' }),
      });
      expect(confirmRes.status).toBe(410);
      expect(confirmRes.headers.get('content-type')).toContain('application/problem+json');
    } finally {
      Date.now = realNow;
    }
  });
});
