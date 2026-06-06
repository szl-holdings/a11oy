import { describe, it, expect } from 'vitest';
import { buildRig } from './helpers.ts';
import { sweepCorpus, BANNED_TERMS } from '../src/routes/doctrine.ts';

async function operatorGet(path: string) {
  const { app, token } = await buildRig();
  const jwt = await token({ groups: ['szl-operators'] });
  return app.request(path, { headers: { authorization: `Bearer ${jwt}` } });
}

describe('console + mesh read routes', () => {
  it('GET /v1/about returns rosie-api metadata (no Jarvis)', async () => {
    const res = await operatorGet('/v1/about');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.name).toBe('rosie-api');
    expect(body.surfaces).toContain('rosie-widget');
    expect(JSON.stringify(body).toLowerCase()).not.toContain('jarvis');
  });

  it('GET /v1/mesh/health returns the module topology', async () => {
    const res = await operatorGet('/v1/mesh/health');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.modules)).toBe(true);
    expect(body.modules.map((m: { name: string }) => m.name)).toContain('a11oy');
    expect(body.modules.every((m: { signing_key_id: string }) => m.signing_key_id.includes('ed25519'))).toBe(true);
  });

  it('GET /v1/doctrine/sweep returns a v7 clean verdict for an empty corpus', async () => {
    const res = await operatorGet('/v1/doctrine/sweep');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.doctrine_version).toBe('v7');
    expect(body.clean).toBe(true);
    expect(body.violations).toEqual([]);
  });

  it('GET /v1/formulas/live returns the gate set with Lean refs', async () => {
    const res = await operatorGet('/v1/formulas/live');
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.formulas.length).toBeGreaterThan(0);
    expect(body.formulas[0]).toHaveProperty('gate');
  });

  it('requires operator auth (401) for console routes', async () => {
    const { app } = await buildRig();
    expect((await app.request('/v1/about')).status).toBe(401);
    expect((await app.request('/v1/mesh/health')).status).toBe(401);
    expect((await app.request('/v1/doctrine/sweep')).status).toBe(401);
    expect((await app.request('/v1/formulas/live')).status).toBe(401);
  });
});

describe('doctrine sweep logic', () => {
  it('flags banned terms with line + column', () => {
    const violations = sweepCorpus([{ name: 'd', text: `clean line\nthis is revolutionary stuff` }]);
    expect(violations.length).toBe(1);
    expect(violations[0].term).toBe('revolutionary');
    expect(violations[0].line).toBe(2);
    expect(violations[0].column).toBeGreaterThan(0);
  });

  it('is clean for compliant text', () => {
    expect(sweepCorpus([{ name: 'd', text: 'plain factual description' }])).toEqual([]);
  });

  it('exposes a non-empty banned-term list', () => {
    expect(BANNED_TERMS.length).toBeGreaterThan(3);
  });
});
