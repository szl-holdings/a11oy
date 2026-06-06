import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';

async function propose(app: any, jwt: string) {
  const res = await app.request('/v1/execute', {
    method: 'POST',
    headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
    body: JSON.stringify({ app: 'sentra', action: 'rotate', params: {}, dry_run: false }),
  });
  return res.json();
}

describe('POST /v1/execute/confirm — step-up enforcement', () => {
  it('returns 403 problem+json when step_up_completed_at is absent', async () => {
    const { app, token } = await buildRig();
    const exec = await token({ groups: ['szl-executors'] });
    const proposal = await propose(app, exec);
    const res = await app.request('/v1/execute/confirm', {
      method: 'POST',
      headers: { authorization: `Bearer ${exec}`, 'content-type': 'application/json' },
      body: JSON.stringify({ receipt_id: proposal.receipt_id, idempotency_key: 'idem-12345678' }),
    });
    expect(res.status).toBe(403);
    expect(res.headers.get('content-type')).toContain('application/problem+json');
    const body = await res.json();
    expect(body.type).toContain('/errors/step-up');
  });

  it('returns 403 when step_up_completed_at is older than 5 minutes', async () => {
    const now = Date.now();
    const { app, token } = await buildRig({ now: () => now });
    const stale = now - 6 * 60 * 1000; // 6 minutes ago
    const exec = await token({ groups: ['szl-executors'], stepUpAt: stale });
    const proposal = await propose(app, exec);
    const res = await app.request('/v1/execute/confirm', {
      method: 'POST',
      headers: { authorization: `Bearer ${exec}`, 'content-type': 'application/json' },
      body: JSON.stringify({ receipt_id: proposal.receipt_id, idempotency_key: 'idem-12345678' }),
    });
    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.type).toContain('/errors/step-up-stale');
  });

  it('executes with a fresh step-up and is idempotent on repeat', async () => {
    const now = Date.now();
    const { app, token } = await buildRig({ now: () => now });
    const exec = await token({ groups: ['szl-executors'], stepUpAt: now - 1000 });
    const proposal = await propose(app, exec);

    const first = await app.request('/v1/execute/confirm', {
      method: 'POST',
      headers: { authorization: `Bearer ${exec}`, 'content-type': 'application/json' },
      body: JSON.stringify({ receipt_id: proposal.receipt_id, idempotency_key: 'idem-12345678' }),
    });
    expect(first.status).toBe(200);
    const firstBody = await first.json();
    expect(firstBody.status).toBe('executed');

    const second = await app.request('/v1/execute/confirm', {
      method: 'POST',
      headers: { authorization: `Bearer ${exec}`, 'content-type': 'application/json' },
      body: JSON.stringify({ receipt_id: proposal.receipt_id, idempotency_key: 'idem-12345678' }),
    });
    expect(second.status).toBe(200);
    const secondBody = await second.json();
    expect(secondBody.status).toBe('already_executed');
  });
});
