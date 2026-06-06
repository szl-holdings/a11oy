import { describe, it, expect } from 'vitest';
import { buildRig, buildSignedReceipt } from './helpers.ts';

describe('POST /v1/receipts/verify', () => {
  it('returns {verified:true} for a valid DSSE envelope', async () => {
    const { app, token, signer } = await buildRig();
    const receipt = buildSignedReceipt(signer, { kind: 'ask', app: 'a11oy', q: 'hi' });
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/receipts/verify', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify(receipt),
    });
    expect(res.status).toBe(200);
    const verdict = await res.json();
    expect(verdict.verified).toBe(true);
    expect(verdict.errors).toEqual([]);
  });

  it('returns {verified:false, errors:[...]} for a tampered payload', async () => {
    const { app, token, signer } = await buildRig();
    const receipt = buildSignedReceipt(signer, { kind: 'ask', app: 'a11oy', q: 'hi' });
    // Tamper: replace the payload with a different canonical body, keep old sig.
    const tampered = {
      ...receipt,
      payload: Buffer.from(JSON.stringify({ kind: 'ask', app: 'sentra', q: 'evil' })).toString('base64'),
    };
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/receipts/verify', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify(tampered),
    });
    expect(res.status).toBe(200);
    const verdict = await res.json();
    expect(verdict.verified).toBe(false);
    expect(verdict.errors.length).toBeGreaterThan(0);
  });

  it('flags a missing signature', async () => {
    const { app, token } = await buildRig();
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request('/v1/receipts/verify', {
      method: 'POST',
      headers: { authorization: `Bearer ${jwt}`, 'content-type': 'application/json' },
      body: JSON.stringify({ payload: 'e30=', payloadType: 'application/vnd.szl.receipt.v1+json', signatures: [], chain: { prev_hash: 'GENESIS', index: 0, ts: new Date().toISOString() } }),
    });
    const verdict = await res.json();
    expect(verdict.verified).toBe(false);
    expect(verdict.errors.join(' ')).toContain('signature');
  });
});
