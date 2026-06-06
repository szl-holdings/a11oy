import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';

describe('POST /v1/ask', () => {
  it('returns 200 with answer + citations + receipt_id for a valid operator JWT', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/ask', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'a11oy', question: 'what is the mesh health?' }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(typeof body.answer).toBe('string');
    expect(Array.isArray(body.citations)).toBe(true);
    expect(typeof body.conversation_id).toBe('string');
    expect(typeof body.receipt_id).toBe('string');
  });

  it('returns 401 (problem+json) without a JWT', async () => {
    const { app } = await buildRig();
    const res = await app.request('/v1/ask', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'a11oy', question: 'hi' }),
    });
    expect(res.status).toBe(401);
    expect(res.headers.get('content-type')).toContain('application/problem+json');
    const body = await res.json();
    expect(body.type).toContain('/errors/');
    expect(body.status).toBe(401);
  });

  it('returns 403 when the JWT lacks szl-operators', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['some-other-group'] });
    const res = await app.request('/v1/ask', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'a11oy', question: 'hi' }),
    });
    expect(res.status).toBe(403);
  });

  it('returns 422 for an invalid app', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/ask', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ app: 'nope', question: 'hi' }),
    });
    expect(res.status).toBe(422);
  });
});
