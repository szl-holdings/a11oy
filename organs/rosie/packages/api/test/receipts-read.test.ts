import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';
import { createSubstrate } from '../src/lib/receipt-substrate.ts';
import { parseStepUp, STEP_UP_MAX_AGE_MS } from '../src/middleware/step-up.ts';

describe('GET /v1/receipts (list) + GET /v1/receipts/:id', () => {
  it('lists receipts with pagination and filters by app', async () => {
    const { app, token, store, signer } = await buildRig();
    const sub = createSubstrate(signer);
    let prev: string | null = null;
    for (let i = 0; i < 3; i++) {
      const r = sub.emit({ kind: 'ask', app: i === 0 ? 'sentra' : 'a11oy' }, prev, i);
      store.append(r);
      prev = store.headHash;
    }
    const jwt = await token({ groups: ['szl-operators'] });

    const all = await app.request('/v1/receipts?limit=2', { headers: { authorization: `Bearer ${jwt}` } });
    expect(all.status).toBe(200);
    const page = await all.json();
    expect(page.items.length).toBe(2);
    expect(page.next_cursor).toBe('2');

    const filtered = await app.request('/v1/receipts?app=sentra', { headers: { authorization: `Bearer ${jwt}` } });
    const fbody = await filtered.json();
    expect(fbody.items.length).toBe(1);
  });

  it('fetches a single receipt by id, 404 for unknown', async () => {
    const { app, token, store, signer } = await buildRig();
    const sub = createSubstrate(signer);
    const id = store.append(sub.emit({ kind: 'ask', app: 'a11oy' }, null, 0));
    const jwt = await token({ groups: ['szl-operators'] });

    const ok = await app.request(`/v1/receipts/${id}`, { headers: { authorization: `Bearer ${jwt}` } });
    expect(ok.status).toBe(200);
    const r = await ok.json();
    expect(r.payloadType).toContain('szl.receipt');

    const missing = await app.request('/v1/receipts/does-not-exist', { headers: { authorization: `Bearer ${jwt}` } });
    expect(missing.status).toBe(404);
    expect(missing.headers.get('content-type')).toContain('application/problem+json');
  });

  it('filters the list by since timestamp', async () => {
    const { app, token, store, signer } = await buildRig();
    const sub = createSubstrate(signer);
    store.append(sub.emit({ kind: 'ask', app: 'a11oy' }, null, 0));
    const future = new Date(Date.now() + 60_000).toISOString();
    const jwt = await token({ groups: ['szl-operators'] });
    const res = await app.request(`/v1/receipts?since=${encodeURIComponent(future)}`, {
      headers: { authorization: `Bearer ${jwt}` },
    });
    const body = await res.json();
    expect(body.items.length).toBe(0);
  });
});

describe('parseStepUp', () => {
  it('parses ISO-8601 strings', () => {
    const iso = '2026-05-30T20:00:00.000Z';
    expect(parseStepUp(iso)).toBe(Date.parse(iso));
  });
  it('treats small numbers as epoch seconds', () => {
    expect(parseStepUp(1_700_000_000)).toBe(1_700_000_000 * 1000);
  });
  it('treats large numbers as epoch milliseconds', () => {
    expect(parseStepUp(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
  it('returns null for undefined or unparseable', () => {
    expect(parseStepUp(undefined)).toBeNull();
    expect(parseStepUp('not-a-date')).toBeNull();
  });
  it('exposes the 5-minute window', () => {
    expect(STEP_UP_MAX_AGE_MS).toBe(300_000);
  });
});
